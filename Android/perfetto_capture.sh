#!/usr/bin/env bash
# =====================================================================
#  perfetto_capture.sh — capture a 60s CPU trace for Phi_android.
#
#  Run TWICE:
#    (1) while the UNGUARDED worker is cycling under Doze   -> ccc-loop trace
#    (2) while the GATED worker is installed and app idle    -> idle trace
#
#  Then compute Phi_android = mean_cpu(ccc-loop) / mean_cpu(idle)
#  from the traces (open in https://ui.perfetto.dev, or use trace_processor).
#
#  Usage: ./perfetto_capture.sh ccc_loop
#         ./perfetto_capture.sh idle
# =====================================================================
set -euo pipefail
LABEL="${1:-trace}"
OUT="./logs"; mkdir -p "$OUT"
TS=$(date +%Y%m%d_%H%M%S)
DEVTRACE="/data/misc/perfetto-traces/ccc_${LABEL}_${TS}.pftrace"
LOCAL="$OUT/cpu_${LABEL}_${TS}.pftrace"

CFG=$(cat <<'EOF'
buffers: { size_kb: 65536 fill_policy: RING_BUFFER }
data_sources: {
  config {
    name: "linux.process_stats"
    process_stats_config { scan_all_processes_on_start: true proc_stats_poll_ms: 1000 }
  }
}
data_sources: { config { name: "linux.sys_stats" sys_stats_config { stat_period_ms: 1000 stat_counters: STAT_CPU_TIMES } } }
duration_ms: 60000
EOF
)

echo ">>> Capturing 60s Perfetto trace ($LABEL). Start your workload NOW."
echo "$CFG" | adb shell perfetto -c - --txt -o "$DEVTRACE"
adb pull "$DEVTRACE" "$LOCAL"
echo "Trace saved: $LOCAL"
echo "Open in https://ui.perfetto.dev and read mean CPU% for the :bridge + app processes,"
echo "or query with trace_processor_shell. Record the mean for analyze_ccc.py --phi."
