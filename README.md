# Call Cycle Creation (CCC)

Artifact repository for the paper  
**"Call Cycle Creation: A Migration-Era, Lifecycle-Induced IPC Failure in Hybrid UWP–WPF Windows IoT Deployments"**

---

## The Problem

When a Windows UWP app resumes from suspension, its `Resuming` handler launches a companion Win32 (WPF) process to restore the AppService connection. A single-instance invariant means the newly spawned process finds an incumbent already alive, signals it over the named pipe, and immediately self-terminates. A UWP lifecycle bug then re-fires `Resuming` on that exit — so the handler spawns another process, which also dies, looping indefinitely. Any heavy task or network call in the resume path amplifies the cost: sustained CPU drain, power waste, and on constrained IoT hardware, device overheat.

**The fix** is a foreground gate: move all reconnection logic out of the background resume handler and into `CoreWindow.Activated`. **The long-term remedy** is WinUI 3, which hosts Win32/.NET in-process and removes the separate process entirely.

---

## Repository Structure

```
CCC/
├── Windows/                   Windows UWP–WPF production application and CCCHarness
│   ├── BridgeTest/            UWP app (PID1) — contains the vulnerable Resuming handler
│   ├── BridgeHandler/         WPF service (PID2) — single-instance guard, AppService provider
│   ├── Communicator_OutProc/  Out-of-process background task
│   ├── BridgeInstaller/       MSIX packaging (Desktop Bridge)
│   └── README.md              Windows-specific build and run guide
│
├── Android/                   AndroidCCCHarness — cross-platform control measurement
│   ├── app/src/main/java/com/example/myapplication/
│   │   ├── BridgeService.kt   Persistent socket service (separate :bridge process)
│   │   ├── ReconnectWorker.kt WorkManager worker — unguarded and gated variants
│   │   └── ...                SocketTransport, WorkEnqueuer, ControlReceiver, etc.
│   ├── run_experiment.sh      adb-driven measurement driver (all five phases)
│   ├── perfetto_capture.sh    On-device CPU trace capture
│   ├── analyze_ccc.py         Fits κ, α from sweep logs; computes window and knee
│   └── README.md              Android build, run, and measurement guide
│
├── Figures/
│   └── plot_paper_figures_v4.py   Generates all 7 paper figures from the Windows data
│
└── README.md                  This file
```

---

## Quick Start

**Reproduce the Windows failure** — open `Windows/BridgeTest/App.xaml.cs`, find `CoreApplication_Resuming`, and observe `FullTrustProcessLauncher.LaunchFullTrustProcessForCurrentAppAsync()` called without a foreground guard. Build with Visual Studio 2022 and trigger a suspend/resume cycle to see the loop.

**Reproduce the Android control measurement** — see `Android/README.md` for the full five-phase measurement procedure using `run_experiment.sh`.

**Regenerate the paper figures** — install matplotlib/numpy, then:
```bash
cd Figures && python3 plot_paper_figures_v4.py
```

---

## Key Results

| | Windows UWP | Android (control) |
|---|---|---|
| Loop recurs? | **Yes** — deterministic, every resume | **No** — single bounded transfer |
| Root cause | `Resuming` handler + single-instance invariant + UWP re-fire bug | WorkManager has no resume-re-fire on child exit |
| Per-iteration cost | κ = 7.29 ms/MB^α, α = 0.958 | κ = 6.19 ms/MB^α, α = 0.72 |
| CPU amplification Φ | ≈ 11.6× (model-calibrated) | Not applicable (no cycle) |
| Remedy | Foreground gate (`CoreWindow.Activated`) | Same gate principle, not needed |

---

## Citation

```bibtex
@inproceedings{Mozumder2026CCC,
  title     = {Call Cycle Creation: A Migration-Era, Lifecycle-Induced IPC Failure
               in Hybrid {UWP--WPF} Windows {IoT} Deployments},
  author    = {Mozumder, Md. Shamsul Arifin and Adnan, Muhammad Abdullah},
  year      = {2026},
  note      = {Artifact: \url{https://github.com/arifincsebuet/CCC}}
}
```
