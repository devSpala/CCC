# Call Cycle Creation (CCC): Windows UWP/WPF IPC Antipattern

## Overview

This repository contains a comprehensive research implementation and documentation of **Call Cycle Creation (CCC)**, a critical failure pattern that occurs in hybrid Windows UWP-WPF applications on Windows IoT platforms. CCC is a lifecycle-induced inter-process communication (IPC) antipattern that causes infinite recursive process creation cycles, leading to severe CPU overheads, thermal damage, and power consumption issues on constrained IoT hardware.

This is a **migration-era antipattern** affecting the Windows 10 LTSC 2021 installed base (supported through January 2032) where immediate migration to WinUI 3 is infeasible.

## The Problem: CCC Failure Pattern

### What is Call Cycle Creation?

When a Windows UWP application resumes from suspension on IoT devices, it attempts to restore IPC connections to a companion WPF process that maintains device connectivity. However, a UWP lifecycle bug triggers the resume handler repeatedly when:

1. The resume handler launches a new Win32 (WPF) process to restore the AppService connection
2. A single-instance invariant ensures only one WPF process runs at a time
3. The newly spawned process detects the already-alive incumbent, signals it, and terminates
4. The **OS re-fires the resume handler on process exit** (the UWP lifecycle bug)
5. Steps 1-4 repeat indefinitely in a self-sustaining loop

### Seven-Step Failure Sequence

| Step | Description |
|------|-------------|
| **S1** | Initialization: UWP app launches and spawns a single WPF process; AppService connection established |
| **S2** | Suspension Event: OS suspends UWP after inactivity threshold |
| **S3** | Resume: OS resumes UWP and invokes the `Resuming` lifecycle handler |
| **S4** | Single-Instance Collision: New WPF process detects incumbent, signals it, terminates |
| **S5** | Bug-Induced Resume Re-fire: Child exit re-triggers `Resuming` handler (THE BUG) |
| **S6** | Cost Amplification: Heavy tasks/REST calls/IPC payloads execute on each iteration |
| **S7** | Cycle Re-entry: Steps S3-S6 repeat indefinitely with no terminating condition |

## Technical Architecture

### Hybrid System Design

This project implements a hybrid Windows architecture for IoT applications:

- **BridgeTest (UWP, PID1)**: Modern sandboxed UI layer
  - Subject to strict OS-enforced execution quotas (3-5 seconds per background task)
  - H264 codec restrictions mandate Win32 proxy for WebRTC media streaming
  - Manages user interface and lifecycle events

- **BridgeHandler (WPF, PID2)**: Win32 proxy process
  - Persistent execution without OS quotas
  - Full codec access (H264 hardware acceleration)
  - Maintains device connectivity during UWP suspension
  - Registered as AppService provider

- **Communicator_OutProc**: Out-of-process background task
  - Handles bidirectional IPC via AppService
  - Manages connection state across lifecycle transitions
  - Subject to background execution quotas

### Why Hybrid Architecture is Necessary

- UWP natively lacks H264 hardware-accelerated codec support in WebRTC pipeline
- All modern IoT media streams must be routed through Win32 proxy
- Windows 10 LTSC 2021 receives security updates until January 2032
- Migration to WinUI 3 is contractually/operationally infeasible for many deployments

## The Root Cause: Lifecycle-Quota IPC Antipattern (LQIA)

CCC is a specific Windows instantiation of a general antipattern defined by three structural preconditions:

### **L1: Quota-Bounded Context**
A background execution context subject to OS-enforced time/energy budget:
- UWP background task quota: 3,000-5,000 ms
- Subject to suspension and forced termination

### **L2: Persistent Out-of-Process Service**
A stateful IPC endpoint running in a process not subject to the same quota:
- WPF AppService provider (PID2)
- Maintains device connectivity independently

### **L3: Unguarded Recovery Logic**
Reconnection logic executing inside L1 that attempts to restore L2 without verifying remaining quota:
- No checks before launching new processes
- No foreground/background state verification
- Executes inside lifecycle handler bound to resume event

**Critical Finding**: These preconditions exist on Android and macOS too, but **Android does not re-fire separate-process launch logic on every resumption**, and **macOS has different lifecycle semantics**. Only Windows UWP exhibits the self-sustaining cycle due to its specific lifecycle contract.

## Mathematical Characterization

### Payload Transmission Model

AppService latency follows a power-law relationship:

$$T_{\text{payload}}(P) = \kappa \cdot P^\alpha$$

Where:
- $\kappa = 7.29$ ms·MB$^{-\alpha}$
- $\alpha = 0.958$
- $P$ = payload size in MB
- Fit: MAPE = 13.9% (single-trial measurements)

### Critical Payload Threshold

A single resume iteration exhausts the UWP quota when:

$$T_{\text{conn}} + T_{\text{payload}}(P) \geq T_{\text{bg}}$$

This yields a critical threshold $P^*$:

$$P^* = \left(\frac{T_{\text{bg}} - T_{\text{conn}}}{\kappa}\right)^{1/\alpha} \approx 513 \text{ MB}$$

**Above this threshold**: Single iteration alone exhausts quota; loop causes extreme per-iteration severity
**Below this threshold**: Loop still recurs, but each iteration is individually quota-feasible

### CPU Overhead Amplification

Model-calibrated CPU overhead factor:

$$\Phi = \frac{\overline{u}_{\text{CCC}}}{\overline{u}_{\text{idle}}} \approx 11.6\times$$

- **CCC active**: 13.1% sustained CPU utilization (model-calibrated estimate; see note below)
- **Idle**: 1.1% CPU utilization (assumed model input)
- Measured re-fire rate: **~0.4 Hz mean** (36 re-launches in 90 s), occurring in bursts at a median inter-launch interval of **~1.1 s** with longer gaps between bursts; each WPF process lives a median **~0.5 s** before the single-instance guard terminates it

> **Note on Φ.** Φ ≈ 11.6× is a *model-calibrated estimate*, not a directly sampled CPU measurement. The re-fire **mechanism and its timing are directly measured** (see [Result Generation](#result-generation-process) below — 36 re-launches vs. 0 in the idle control). Because each WPF process lives only ~0.5 s, accurate per-process CPU attribution requires kernel-level (ETW) or in-process tracing, which is listed as future work. The capture scripts record per-PID `TotalProcessorTime`, but at a 250 ms sampling interval this undercounts the short-lived processes, so Φ remains an estimate while the re-fire count is exact.

### AppService Overhead vs. Named-Pipe

Named-pipe baseline: $T_{\text{pipe}}(P) \approx 0.50 + 0.048P$ (ms)

AppService overhead ratio:
- **1 MB**: $\eta \approx 15\times$ vs. named-pipe
- **1 GB**: $\eta \approx 148\times$ vs. named-pipe

CCC would occur with any quota-limited transport, but AppService severity is magnified due to serialized broker overhead.

### CCC Risk Score

Dimensionless risk metric mapping any $(N, P)$ operating point:

$$\mathcal{R}(N, P) = \frac{T_{\text{total}}(N,P)}{T_{\text{bg}}}$$

- $\mathcal{R} \geq 1$: Quota violation severity
- Risk heatmap visualizes safe/unsafe parameter zones

## Impact Assessment

### Performance Consequences

| Metric | Impact |
|--------|--------|
| **CPU Utilization** | 11.6× amplification vs. idle |
| **Power Consumption** | Sustained drain during background lifecycle |
| **Thermal Load** | Device overheat risk on IoT hardware |
| **Network Calls** | Infinite repetition of failed reconnection attempts |
| **Device Lifespan** | Accelerated degradation of constrained hardware |

### Real-World Scenarios

- **Video Streaming IoT Device**: Resume every 30 seconds → 1,920 cycles/hour → sustained CPU spike
- **Thermal Stress**: Constrained IoT devices (e.g., embedded ARM) → device shutdown risk
- **Power Budget**: Battery-powered IoT → rapid depletion during resume cycles
- **Network Costs**: Unlimited REST calls in resume path → significant operational cost

## Solutions

### 1. Foreground-Gated Recovery (Bridge-Era Solution)

**For LTSC 2021 deployments through 2032**, implement lifecycle-aware IPC recovery:

#### **Background Passivity**
When AppService connection drops in background state:
- Record disconnection flag
- Immediately abandon all reconnection attempts
- **Eliminates LQIA-L3**: No recovery logic executes during background

#### **Creation Isolation**
Move ALL AppServiceConnection reinitialization to foreground:
- Register handler for `CoreWindow.Activated`
- Trigger reconnection **only when foreground state confirmed**
- No process spawning from background lifecycle events

#### **Lifecycle Delay Stabilization**
Add stabilization timer after foreground activation:
- Minimum 500 ms buffer before bridge validation
- Allows OS memory managers to un-page execution context
- Prevents premature reconnection during wake-up thrashing

#### Results
- **$\Phi$ reduced from 11.6× to 1.0×** (CPU returns to idle norms)
- Validated across **200 consecutive lifecycle transition tests**
- Prevents device thermal damage
- Eliminates infinite process creation

### 2. WinUI 3 Migration (Long-Term Solution)

**Definitive remedy** for post-2032 platforms:

- WinUI 3 hosts Win32/.NET **in-process** (no separate launch)
- No lifecycle-handler-spawned process to collide
- No resume re-fire trigger → CCC structurally impossible
- **LQIA-L1 and L2 both eliminated**
- Named-pipe transport: $P^*_{\text{pipe}} \approx 60,000$ MB (safe operating zone)

### 3. Cross-Platform Design Guidance

For analogous architectures on other platforms:

| Platform | L1 Quota | L2 Service | Recovery Gate |
|----------|----------|-----------|---------------|
| **Windows UWP** | Background task quota | AppService provider | `CoreWindow.Activated` |
| **Android** | WorkManager maintenance window | Bound Service | `ActivityLifecycleCallbacks.onActivityResumed` |
| **macOS** | NSBackgroundActivityScheduler | XPC service | `NSApplicationDelegate.applicationDidBecomeActive` |

## Project Structure

```
BridgeTest.sln
├── BridgeTest/              (UWP Application, PID1)
│   ├── App.xaml            XAML UI definitions
│   ├── App.xaml.cs         UWP lifecycle handler (Contains Resume)
│   ├── MainPage.xaml       Primary UI surface
│   ├── MainPage.xaml.cs    UI logic and event handlers
│   ├── Package.appxmanifest Platform capabilities and registration
│   └── Properties/
│
├── BridgeHandler/           (WPF Service, PID2)
│   ├── Program.cs          Entry point and AppService registration
│   ├── AppServiceCommunicator.cs  AppService connection handling
│   ├── SingleThreadExecutor.cs    Message dispatch and execution
│   ├── SystemMutex.cs       Single-instance guard (prevents dual processes)
│   └── BridgeHandler.csproj WPF project configuration
│
├── Communicator_OutProc/    (Out-of-Process Background Task)
│   ├── BridgeCommunicator.cs IPC relay logic
│   ├── Communicator_OutProc.csproj Background task configuration
│   └── Properties/
│
├── BridgeInstaller/         (MSIX Packaging & Desktop Bridge)
│   ├── Package.appxmanifest MSIX manifest with FullTrust grant
│   ├── BridgeInstaller.wapproj Packaging project
│   └── Images/              Application icons and assets
│
└── Scripts/                 (Measurement & trace-capture tooling)
    ├── find_ccc_procs.ps1   Discover the churning process image names
    └── capture_ccc_v2.ps1   Capture spawn/exit timeline + per-PID CPU

```

## Key Code Components

### 1. **SingleThreadExecutor.cs** (WPF Service)
- Implements the AppService message loop
- Executes received commands sequentially
- Maintains persistent state across UWP suspension

### 2. **SystemMutex.cs** (Single-Instance Guard)
- Named mutex for process synchronization
- Prevents concurrent WPF instances
- Signals incumbent process on collision

### 3. **AppServiceCommunicator.cs** (IPC Handler)
- Manages bidirectional AppService connections
- Queues messages during UWP suspension
- **CRITICAL**: Must implement foreground-gate checks

### 4. **App.xaml.cs** (Resume Handler - THE VULNERABILITY)
```csharp
// VULNERABLE PATTERN:
private void CoreApplication_Resuming(object sender, object e)
{
    // This is where the loop originates:
    // 1. Launches new WPF process
    // 2. New process detects incumbent and dies
    // 3. BUGGY RE-FIRE: OS re-invokes this handler
    // 4. Loop continues indefinitely
    
    FullTrustProcessLauncher.LaunchFullTrustProcessForCurrentAppAsync();
}
```

**FIX**: Add foreground-gate check before launching:
```csharp
private void CoreApplication_Resuming(object sender, object e)
{
    // Only reconnect if app is in foreground
    if (CoreApplication.MainView.CoreWindow.Activated)
    {
        // Safe to reconnect
    }
    // Otherwise: background state, skip reconnection
}
```

## Measurement Scripts

The `Scripts/` folder contains the PowerShell tooling used to directly measure the CCC re-fire loop on a live Windows host. Both scripts are self-contained, require no external dependencies, and must be run from an **elevated** PowerShell session. Because they are unsigned, invoke them with an execution-policy bypass scoped to the single process:

```powershell
powershell -ExecutionPolicy Bypass -File .\<script>.ps1 [options]
```

### Script 1 — `find_ccc_procs.ps1` (discovery)

Identifies the *real* process image names involved in the cycle. The image name of the WPF child and the background-task host is environment-dependent (e.g. a `dotnet`-hosted process or a generic `backgroundTaskHost.exe`), so this script is run **first**, while the cycle is being forced, to learn what to capture.

It snapshots all running processes 10 times over ~5 s and reports two things: candidate processes whose name matches a bridge/host/handler pattern, and **high-churn** processes that appear under three or more distinct PIDs during the window. High churn is the signature of the CCC re-fire — the same logical process being created and destroyed repeatedly.

```powershell
# Run WHILE the cycle is being forced:
powershell -ExecutionPolicy Bypass -File .\find_ccc_procs.ps1
```

Output (console only): a candidate list, a `HIGH CHURN (>=3 distinct PIDs)` list, and the full command lines of likely matches. Note the image name(s) and command-line fragments that show high churn — these feed Script 2.

### Script 2 — `capture_ccc_v2.ps1` (capture)

Records the spawn/exit timeline and per-PID CPU of the matching processes over a fixed window. A process matches if **either** its image name contains any `-NamePatterns` substring **or** its full command line contains any `-CmdLinePatterns` substring (case-insensitive). The command-line matching is what catches generic-named hosts that name matching alone would miss.

**Options:**

| Option | Default | Meaning |
|--------|---------|---------|
| `-Seconds` | `90` | Total capture duration (the paper uses 90 s) |
| `-IntervalMs` | `250` | Sampling interval in milliseconds |
| `-NamePatterns` | `"Bridge","backgroundTaskHost","Communicator"` | Substrings matched against the process **image name** |
| `-CmdLinePatterns` | `"bridgecom","Communicator_OutProc","BridgeHandler","BridgeTest"` | Substrings matched against the **full command line** |

```powershell
# Capture the CCC condition (run WHILE forcing the cycle):
powershell -ExecutionPolicy Bypass -File .\capture_ccc_v2.ps1 -Seconds 90 -IntervalMs 250 `
   -NamePatterns "Bridge","backgroundTaskHost","Communicator" `
   -CmdLinePatterns "bridgecom","Communicator_OutProc","BridgeHandler","BridgeTest"
```

**Outputs** (written to the current directory):

- `proc_events.csv` — one row per lifecycle event: `event` (`spawn`/`exit`), `elapsed_s`, `wallclock` (ISO 8601), `pid`, `name`. This is the primary evidence: each `spawn`/`exit` pair is one turn of the CCC loop (steps S3–S5).
- `cpu_trace.csv` — one row per sample: `elapsed_s`, `wallclock`, `live_proc_count`, `cpu_pct_onecore`, `cpu_pct_machine`. CPU is derived from per-PID `TotalProcessorTime` deltas between samples.

On completion the script prints a summary (`spawns`, `exits`, `max live procs`). If it matched zero processes, it tells you to re-run `find_ccc_procs.ps1` and pass the discovered names/cmdlines explicitly.

> **Capture-fidelity caveat.** At the default 250 ms interval, the `spawn`/`exit` **counts** are reliable (each short-lived process is observed at least once), but the per-PID **CPU** figures undercount processes that live and die entirely between two samples (median lifetime ~0.5 s). This is why the paper reports the **re-fire count as a direct measurement** while keeping **Φ as a model-calibrated estimate**. A future kernel-level (ETW) capture would close this gap.

## Result Generation Process

The figures and headline numbers in the paper are reproduced from the two CSVs above via the plotting script (`plot_paper_figures_v6.py`, in the repository root). The end-to-end process:

### Step 1 — Force the cycle

Deploy `BridgeTest` (the vulnerable, non-foreground-gated build) on the Windows host and drive it through a suspend → resume transition so the `Resuming` handler begins re-spawning the WPF child. Leave the cycle running.

### Step 2 — Discover process names

In an elevated PowerShell, while the cycle runs:

```powershell
powershell -ExecutionPolicy Bypass -File .\find_ccc_procs.ps1
```

Record the high-churn image name(s) and command-line fragments.

### Step 3 — Capture the CCC condition

Still while the cycle runs, using the names from Step 2:

```powershell
powershell -ExecutionPolicy Bypass -File .\capture_ccc_v2.ps1 -Seconds 90 -IntervalMs 250 `
   -NamePatterns <discovered-names> -CmdLinePatterns <discovered-cmdlines>
```

This produces `cpu_trace.csv` and `proc_events.csv` for the **active** condition.

### Step 4 — Capture the idle baseline (control)

Restart the application **without** forcing the cycle (or run the foreground-gated build), leave it open and idle, and run the same capture. Then rename the outputs to mark them as the control:

```powershell
powershell -ExecutionPolicy Bypass -File .\capture_ccc_v2.ps1 -Seconds 90 -IntervalMs 250
Rename-Item cpu_trace.csv   cpu_trace_idle.csv
Rename-Item proc_events.csv proc_events_idle.csv
```

The idle baseline is what establishes the contrast: **0 re-launches** with the application open but not cycling.

### Step 5 — Verify the trace

A correct active capture yields a `proc_events.csv` in which the matching WPF process appears as a repeating `spawn`/`exit` sequence (≈36 spawn events over 90 s in the reference run), and an idle `proc_events_idle.csv` with a single stable instance and no re-launches. Quick sanity check:

```powershell
Import-Csv proc_events.csv | Group-Object event | Select-Object Name, Count
# Expect: spawn ~36+, exit ~36   (active)
Import-Csv proc_events_idle.csv | Group-Object event | Select-Object Name, Count
# Expect: spawn 1, exit 0/1      (idle baseline)
```

### Step 6 — Generate the figures

Place the four CSVs alongside the plotting script (or use the committed reference values, which the v6 script hard-codes for the re-fire figure) and run:

```bash
python plot_paper_figures_v6.py
```

This regenerates all seven figures, including the measured re-fire timeline (`refire_timeline.png`) that contrasts the 36 active re-launches against the zero-re-launch idle baseline.

### Reference results from the committed capture

| Condition | WPF re-launches (90 s) | Median inter-launch | Median process lifetime |
|-----------|------------------------|---------------------|-------------------------|
| **CCC active** | **36** | ~1.1 s (in bursts) | ~0.5 s |
| **Idle baseline** | **0** | — | stable single instance |

The committed CSVs (`cpu_trace.csv`, `proc_events.csv`, `cpu_trace_idle.csv`, `proc_events_idle.csv`) are the exact traces behind these numbers.

## Experimental Results

### Single-Request IPC Performance

| Payload | Latency | CPU Used | Overhead vs. Pipe |
|---------|---------|----------|------------------|
| 1 MB | 8.50 ms | 0 ms | 15.5× |
| 10 MB | 60.39 ms | 15.63 ms | 61.6× |
| 100 MB | 509.12 ms | 125 ms | 96.1× |
| 200 MB | 1,010.11 ms | 234.38 ms | 100× |
| 500 MB | 2,752.59 ms | 578.13 ms | 112.4× |
| **1 GB** | **7,341.76 ms** | **1,843.75 ms** | **147.9×** |

*Note: UWP quota = 3,000 ms. Payloads above ~200 MB exceed quota.*

### Concurrent Request Scaling

- **N = 1,000 @ 100 MB**: 257,409 ms total = **86× quota violations**
- Each violation = full resume cycle restart
- Cumulative cost compounds across the measured ~0.4 Hz re-fire rate

### Validation: CCCHarness Minimal Reproduction

Independent minimal harness (200 lines C#) confirming failure is application-agnostic:
- HarnessUWP: Minimal UWP stub
- HarnessWPF: Minimal AppService provider
- **Result**: Identical periodic CPU spike pattern and AppService disconnection semantics

### Android Control Measurement

Measured analogous architecture on Samsung Galaxy Note20 Ultra:
- **Android background reconnection**: Single bounded transfer (184-509 ms for 100-300 MB)
- **No re-entry cycle** despite satisfying L1-L3 preconditions
- **Conclusion**: Windows UWP lifecycle contract is the specific cause, not generic preconditions

## Implementation Guidelines

### For Existing LTSC 2021 Deployments

1. **Implement foreground-gate immediately**
   - Prevents infinite cycle
   - Returns CPU to idle levels
   - Minimal code changes (~20-30 lines)

2. **Add connection state machine**
   - Track: Foreground/Background, Connected/Disconnected
   - Suppress reconnection logic in background state
   - Defer reconnection to foreground activation

3. **Validate with lifecycle stress testing**
   - Simulate rapid suspend/resume cycles (10-100/min)
   - Monitor CPU utilization (target: return to idle)
   - Confirm no process accumulation

4. **Plan WinUI 3 migration**
   - Timeline: Before LTSC 2021 security support ends (Jan 2032)
   - Effort: Repackage UI layer as Win32 process
   - Benefit: Eliminates entire antipattern class structurally

## References

- **Cost Model**: Power-law transmission model with critical payload threshold
- **Cross-Platform Analysis**: LQIA preconditions on Windows/Android/macOS
- **Artifact Repository**: Source code and measurement scripts

## Deployment Checklist

- [ ] Review Application.OnResuming() handler implementation
- [ ] Implement foreground-gate check before IPC reconnection
- [ ] Add 500+ ms stabilization delay on foreground activation
- [ ] Run lifecycle transition tests (200+ resume/suspend cycles)
- [ ] Monitor CPU utilization (confirm return to idle baseline)
- [ ] Verify no process accumulation in Task Manager
- [ ] Plan WinUI 3 migration timeline
- [ ] Document architectural changes for team

## Known Limitations & Future Work

1. **Single-Trial Measurements**: Power-law model lacks repeated averaging (13.9% MAPE)
2. **Named-Pipe Baseline**: Literature-derived; same-hardware measurement needed
3. **macOS Verification**: Analytically treated; measured reproduction pending
4. **CPU Trace Validation**: Model-calibrated $\Phi$; real ETW traces recommended
5. **Thermal Testing**: Overheat characterization on actual IoT hardware

## Support & Contributing

For questions about CCC, the antipattern characterization, or implementation guidance:
- Examine CCCHarness for minimal reproduction case
- Check AppServiceCommunicator.cs for current implementation patterns


## Glossary

| Term | Definition |
|------|-----------|
| **CCC** | Call Cycle Creation; self-sustaining process creation loop |
| **LQIA** | Lifecycle-Quota IPC Antipattern; three-condition failure pattern |
| **UWP** | Universal Windows Platform; sandboxed modern Windows UI framework |
| **WPF** | Windows Presentation Foundation; Win32-based UI framework |
| **AppService** | Windows Runtime IPC mechanism for UWP/Win32 bridging |
| **PID1** | Process ID of UWP application |
| **PID2** | Process ID of WPF service process |
| **LTSC** | Long-Term Servicing Channel; enterprise/IoT Windows baseline |
| **WinUI 3** | Modern successor to UWP; eliminates lifecycle constraints |
| **Foreground-Gate** | Architectural pattern: defer reconnection to foreground state |
| **Named Pipe** | Win32 IPC mechanism; lower overhead than AppService |

---

**Last Updated**: 2026
**Version**: 1.0
**Status**: Production-Ready with Bridge-Era Foreground-Gate Solution
