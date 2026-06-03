# CCCHarness — Android

A measurement harness that accompanies the paper **"Call Cycle Creation: Identifying and
Resolving a Migration-Era IPC Antipattern in Windows IoT Deployments."**

Call Cycle Creation (CCC) is a recursive IPC failure that occurs on **Windows UWP**, where
the `Resuming` lifecycle handler hosts the launch-and-connect logic for a separate
Win32 (WPF) process; every OS-issued resume re-fires that logic against a short, unguarded
background quota, producing an indefinite restart loop.

This Android project is the paper's **cross-platform control**. It constructs the same
structural preconditions (a quota-bounded worker, a persistent out-of-process service, and
unguarded reconnection logic) and **measures** what happens. The finding is that the cycle
**does not** arise on Android: each background reconnection completes as a single bounded
transfer rather than recurring. That negative result is the point — it isolates the Windows
UWP lifecycle contract as the specific cause of CCC.

> **Why a localhost socket instead of Binder/Messenger?** Android's Binder transaction
> buffer is ~1 MB, so a `Messenger`/AIDL payload cannot carry the tens-to-hundreds of MB
> needed to probe the regime where CCC would occur on Windows. The harness uses a
> loopback TCP socket between the app and a separate `:bridge` process: it lifts the size
> limit, stays genuinely stateful, and has realistic per-byte cost.

---

## Repository layout

```
app/src/main/java/com/example/myapplication/
  MainActivity.kt          # UI host; starts BridgeService; on-screen phase buttons
  BridgeService.kt         # L2: persistent service in a separate ":bridge" process (loopback ServerSocket)
  SocketTransport.kt       # client send; logs t_conn_ms and t_payload_ms separately
  ReconnectWorker.kt       # L1+L3: WorkManager worker, unguarded vs foreground-gated variants
  WorkEnqueuer.kt          # enqueues the worker
  AppForegroundTracker.kt  # foreground gate (analogue of Windows CoreWindow.Activated)
  HarnessApp.kt            # Application; registers the foreground tracker
  ControlReceiver.kt       # adb-driven control surface (broadcast receiver)
  ForegroundSweep.kt       # foreground transport-curve sweep

AndroidManifest_snippet.xml  # entries to merge into your AndroidManifest.xml
build_gradle_snippet.gradle  # dependencies to merge into app/build.gradle

run_experiment.sh         # host-side driver: runs each measurement phase via adb
perfetto_capture.sh       # host-side: capture a 60s CPU trace
analyze_ccc.py            # host-side: turn captured logs into numbers (kappa, alpha, window, knee)

SETUP.md                  # detailed build/assembly guide
```

All Kotlin sources use package **`com.example.myapplication`**. If you change the
`applicationId`, update the `package` lines and the manifest accordingly. The broadcast
control surface matches on the **action suffix** (`...SWEEP` / `...RECONNECT`), so the package
prefix does not need to match the action strings.

---

## What it logs

Every measurement is emitted to logcat under tag **`CCCHarness`** as a machine-parseable
line beginning with `CCCDATA`, e.g.:

```
CCCDATA send_complete tag=fg_sweep payload_mb=100.0000 t_conn_ms=2.9 t_payload_ms=175.4 ...
CCCDATA worker_window_observed run_index=0 observed_window_ms=191 ...
CCCDATA worker_complete run_index=0 outcome=success ...
CCCDATA worker_gated_skip step=S4 reason=not_foreground
```

You capture these lines to files and run `analyze_ccc.py` on them.

---

## Prerequisites

- **Android Studio** (to build/install the app) and an Android device with **USB debugging** enabled.
- **adb** on your PATH (ships with Android Studio under `platform-tools/`). Verify:
  ```bash
  adb version
  adb devices      # your device must show, ending in "device"
  ```
- A **bash** shell for the scripts: native on macOS/Linux; on Windows use **Git Bash** or **WSL**
  (PowerShell/CMD will not run the `.sh` files).
- **Python 3** for `analyze_ccc.py` (standard library only; `numpy` optional).
- **Perfetto** is on-device (no host install needed) for `perfetto_capture.sh`.

---

## Build & install

See `SETUP.md` for the full walkthrough. In brief:

1. Place the Kotlin files under `app/src/main/java/com/example/myapplication/`.
2. Merge `AndroidManifest_snippet.xml` and `build_gradle_snippet.gradle`, then Gradle-sync.
3. Build and launch:
   ```bash
   ./gradlew installDebug
   adb shell am start -n com.example.myapplication/.MainActivity
   ```
4. Confirm the service is up:
   ```bash
   adb logcat -s CCCHarness:D
   # expect: CCCDATA server_listening port=38917 ...
   ```

---

## Running `run_experiment.sh`

This script runs **on your computer**, not the phone. It drives the connected device over
`adb`, triggers each phase, waits, then **dumps** the logcat buffer to `./logs/`. Capture is
time-bounded, so it never hangs.

```bash
chmod +x run_experiment.sh

# 0. Sanity check that logging works end-to-end
./run_experiment.sh diag

# A. Foreground transport curve (kappa, alpha, T_conn). KEEP THE APP ON SCREEN.
./run_experiment.sh sweep 30

# B. Background execution window probe
./run_experiment.sh window 30

# C. Unguarded background reconnect at several payloads
./run_experiment.sh knee 100
./run_experiment.sh knee 200
./run_experiment.sh knee 300

# D. Foreground-gated reconnect (remedy: expect a gated skip, no transfer)
./run_experiment.sh gated 300

# E. Timed CCCDATA capture window (pairs with perfetto_capture.sh)
./run_experiment.sh cpu 60
```

Each phase prints a one-line verdict (e.g. `worker_reentry=0  worker_complete=1`) and writes
a timestamped log to `./logs/<phase>_<timestamp>.log`.

### Trigger mode

Some devices (notably Samsung One UI) restrict delivery of custom broadcasts. The script
supports two ways to start each phase:

```bash
# default: adb broadcast, targeted at the package with -p (required on Samsung)
./run_experiment.sh sweep 30

# fallback: YOU tap the on-screen button; the script only manages device state + log dump
MODE=buttons ./run_experiment.sh sweep 30
```

If `./run_experiment.sh diag` prints `cmd_unknown` or captures 0 lines, switch to
`MODE=buttons`.

### Environment overrides

| Variable | Meaning | Default |
|---|---|---|
| `PKG` | applicationId to target | `com.example.myapplication` |
| `MODE` | `broadcast` or `buttons` | `broadcast` |
| `WAIT_SECS` | capture/wait duration per phase (s) | phase-specific |
| `PROBE_GAP` | gap between window probes (s) | `8` |

Examples:
```bash
WAIT_SECS=240 ./run_experiment.sh sweep 30
WAIT_SECS=180 ./run_experiment.sh knee 300
PROBE_GAP=15 ./run_experiment.sh window 30
PKG=com.example.myapplication MODE=buttons ./run_experiment.sh gated 100
```

---

## Running `perfetto_capture.sh`

Captures a 60-second on-device CPU trace and pulls it to `./logs/`. Run it **twice** — once
while a background-reconnect workload is active, once while idle — if you want a CPU
comparison:

```bash
chmod +x perfetto_capture.sh

# while a workload is running (e.g. a loop of reconnect broadcasts in another terminal):
./perfetto_capture.sh ccc_loop

# while the app is idle:
./perfetto_capture.sh idle
```

Each run writes `./logs/cpu_<label>_<timestamp>.pftrace`. Open the trace at
https://ui.perfetto.dev and read mean CPU for the `com.example.myapplication` and
`:bridge` processes.

To generate the workload during the `ccc_loop` capture, in a second terminal:
```bash
adb shell dumpsys deviceidle force-idle
for i in $(seq 1 30); do
  adb shell am broadcast -a com.example.myapplication.RECONNECT -p com.example.myapplication \
    --ei payload_mb 100 --ez gated false --ei max_retries 0
  sleep 2
done
```

> **Note:** In the paper's final framing the Android CPU-amplification figure is **not**
> reported (there is no cycle on Android to amplify), so `perfetto_capture.sh` is optional.
> It is retained for completeness and for anyone wanting to inspect per-attempt CPU cost.

---

## Turning logs into numbers

```bash
python3 analyze_ccc.py --sweep logs/sweep_*.log
python3 analyze_ccc.py --window logs/window_*.log
python3 analyze_ccc.py --sweep logs/sweep_*.log --window logs/window_*.log --knee logs/knee_*mb_*.log
```

The sweep fit reports `kappa`, `alpha`, and median `T_conn`; the window phase reports the
observed-window mean +/- SD; the knee phase reports which payloads completed vs cycled.

| CCCDATA field | Paper quantity |
|---|---|
| `send_complete ... payload_mb, t_payload_ms` (tag=fg_sweep) | transport curve `T_payload(P)=kappa*P^alpha` |
| `send_complete ... t_conn_ms` | `T_conn` (median) |
| `worker_window_observed ... observed_window_ms` | background window |
| `worker_complete` vs `worker_reentry` | bounded completion vs cycle |
| `worker_gated_skip ... not_foreground` | foreground-gate remedy |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `diag` captures 0 lines / prints `cmd_unknown` | Broadcast not delivered or stale build. Rebuild/reinstall; if still failing use `MODE=buttons`. |
| `server_listening` never appears | BridgeService not started — check `startService` in `MainActivity` and the `<service android:process=":bridge">` manifest entry. |
| `send_error ... ECONNREFUSED` | `:bridge` socket not open yet — wait 1-2 s after launch, or relaunch the app. |
| `TransactionTooLargeException` | You are still running the old Messenger code — delete it; this project uses sockets. |
| No `worker_window_observed` lines | Probe didn't land in a window — adjust `PROBE_GAP`. |
| Samsung: broadcasts ignored | Settings > Apps > (app) > Battery > **Unrestricted**; or use `MODE=buttons`. |

---

## Citation

If you use this harness, please cite the accompanying paper (see the repository root for the
BibTeX entry).
