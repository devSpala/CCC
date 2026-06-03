#!/usr/bin/env bash
# =====================================================================
#  run_experiment.sh — drives CCCHarness (package com.example.myapplication)
#  on a connected device via adb. Runs on your COMPUTER, not the phone.
#
#  CAPTURE MODEL: no backgrounded logcat. Each phase clears the buffer,
#  triggers the work, waits, then DUMPS once with `adb logcat -d` and exits.
#  Robust on Git Bash/Windows, macOS, Linux. No hang possible.
#
#  TRIGGER MODE (two ways to start each phase's work):
#    broadcast  (default) : adb am broadcast, targeted at the package with -p
#                           (the -p target is required on Samsung/One UI).
#    buttons              : YOU tap the on-screen button; the script only
#                           forces Doze + dumps logs. Most reliable on Samsung.
#    Select with:  MODE=buttons ./run_experiment.sh knee 100
#
#  Usage:
#     ./run_experiment.sh diag
#     ./run_experiment.sh sweep [reps]
#     ./run_experiment.sh window [n]
#     ./run_experiment.sh knee <mb>
#     ./run_experiment.sh gated <mb>
#     ./run_experiment.sh cpu [secs]
#
#  Env:  PKG=<applicationId>  MODE=broadcast|buttons  WAIT_SECS=<s>  PROBE_GAP=<s>
# =====================================================================
set -uo pipefail

PKG="${PKG:-com.example.myapplication}"
MODE="${MODE:-broadcast}"
OUT="./logs"
PROBE_GAP="${PROBE_GAP:-8}"
mkdir -p "$OUT"
TS() { date +%Y%m%d_%H%M%S; }
count() { grep -c "$1" "$2" 2>/dev/null | head -1 | tr -d '\r\n '; }

require_device() {
  if ! adb get-state >/dev/null 2>&1; then
    echo "ERROR: no device. 'adb devices' must show a line ending in 'device'." >&2
    exit 1
  fi
}

# Dump current tag buffer to $1, with a grep fallback if the tag filter misses.
dump_log() {
  local outfile="$1"
  adb logcat -d CCCHarness:D "*:S" > "$outfile" 2>/dev/null
  if [ ! -s "$outfile" ] || [ "$(count CCCDATA "$outfile")" = "0" ]; then
    adb logcat -d 2>/dev/null | grep "CCCDATA" > "$outfile" || true
  fi
}

set_big_buffer() { adb logcat -G 16M >/dev/null 2>&1 || true; }

# Fire a SWEEP broadcast, targeted at the package (Samsung needs -p).
bc_sweep() {
  adb shell am broadcast -a "$PKG.SWEEP" -p "$PKG" --es reps "$1" >/dev/null 2>&1
}
# Fire a RECONNECT broadcast: $1=payload_mb $2=gated(true|false) $3=max_retries
bc_reconnect() {
  adb shell am broadcast -a "$PKG.RECONNECT" -p "$PKG" \
    --ei payload_mb "$1" --ez gated "$2" --ei max_retries "$3" >/dev/null 2>&1
}

prompt_tap() {  # $1 = human description of the button to tap
  echo ""
  echo "    ===================================================================="
  echo "    >>> NOW TAP ON THE PHONE:  $1"
  echo "    ===================================================================="
  read -r -p "    Press ENTER here the moment after you tap it... " _ || true
}

force_doze() {
  echo "    forcing Doze..."
  adb shell dumpsys deviceidle enable        >/dev/null 2>&1 || true
  adb shell dumpsys battery unplug           >/dev/null 2>&1 || true
  adb shell dumpsys deviceidle force-idle    >/dev/null 2>&1 || true
  local state
  state=$(adb shell dumpsys deviceidle get deep 2>/dev/null | tr -d '\r\n ')
  echo "    deviceidle deep state = ${state:-unknown}"
  if [ "$state" != "IDLE" ]; then
    echo "    >>> WARNING: not in deep Doze. Samsung: Settings>Apps>(app)>Battery"
    echo "    >>> >Unrestricted, screen OFF, re-run. Without Doze the cycle won't appear."
  fi
}
undoze() {
  echo "    restoring device..."
  adb shell dumpsys deviceidle unforce       >/dev/null 2>&1 || true
  adb shell dumpsys battery reset            >/dev/null 2>&1 || true
}

PHASE="${1:-}"
require_device
set_big_buffer
echo "    (PKG=$PKG  MODE=$MODE)"

case "$PHASE" in
  diag)
    echo ">>> DIAGNOSTIC"
    echo "--- adb devices ---"; adb devices
    echo "--- installed package present? ---"
    adb shell pm list packages | tr -d '\r' | grep -i "$PKG" || echo "  NOT FOUND: $PKG"
    echo "--- clearing buffer, then trigger ---"
    adb logcat -c
    if [ "$MODE" = "buttons" ]; then
      prompt_tap 'Send one 10 MB payload (sanity check)'
    else
      echo "    broadcasting one 1MB RECONNECT (targeted -p $PKG)..."
      bc_reconnect 1 false 0
      sleep 6
    fi
    F="$OUT/diag_$(TS).log"; dump_log "$F"
    n=$(count CCCDATA "$F")
    echo "--- dumped $n CCCDATA lines to $F ---"
    if [ "$n" = "0" ]; then
      echo ">>> Still nothing. Decisive manual test — tap a button on the phone, then run:"
      echo "      adb logcat -d | grep CCCDATA"
      echo "    If THAT prints lines, broadcasts are blocked -> use MODE=buttons."
      echo "    If even that is empty, the installed build lacks the harness logging."
    else
      echo ">>> Logging works. Sample:"; head -3 "$F"
      echo ">>> If MODE=broadcast worked here, all phases will work in broadcast mode."
    fi
    ;;

  sweep)
    REPS="${2:-30}"; WAIT="${WAIT_SECS:-150}"; F="$OUT/sweep_$(TS).log"
    echo ">>> Phase A (sweep). KEEP THE APP IN THE FOREGROUND."
    adb logcat -c
    if [ "$MODE" = "buttons" ]; then prompt_tap 'Phase A · Foreground sweep (κ, α)'
    else bc_sweep "$REPS"; fi
    echo "    waiting ${WAIT}s for the sweep to finish..."; sleep "$WAIT"
    dump_log "$F"
    echo ">>> $(count CCCDATA "$F") CCCDATA lines ($(count 'send_complete' "$F") send_complete) -> $F"
    [ "$(count 'sweep_done' "$F")" != "0" ] && echo ">>> sweep_done found — complete." \
      || echo ">>> no sweep_done — raise wait: WAIT_SECS=240 ./run_experiment.sh sweep 30"
    ;;

  window)
    N="${2:-30}"; F="$OUT/window_$(TS).log"
    echo ">>> Phase B (Doze window), $N probes."
    adb logcat -c
    force_doze
    if [ "$MODE" = "buttons" ]; then
      echo "    NOTE: buttons mode does one probe per tap; broadcast mode loops automatically."
      for i in $(seq 1 "$N"); do
        prompt_tap "Phase B · Window probe (1 MB, no retry)   [probe $i/$N]"
        sleep 1
      done
    else
      for i in $(seq 1 "$N"); do
        bc_reconnect 1 false 0
        echo "    probe $i/$N (gap ${PROBE_GAP}s)"; sleep "$PROBE_GAP"
      done
    fi
    sleep 3; dump_log "$F"; undoze
    WN=$(count "worker_window_observed" "$F")
    echo ">>> $WN worker_window_observed lines -> $F"
    [ "$WN" = "0" ] && echo ">>> WARNING: 0 window lines — run './run_experiment.sh diag' first."
    ;;

  knee)
    MB="${2:-100}"; WAIT="${WAIT_SECS:-120}"; F="$OUT/knee_${MB}mb_$(TS).log"
    echo ">>> Phase C (unguarded reconnect @ ${MB} MB under Doze)."
    adb logcat -c
    force_doze
    if [ "$MODE" = "buttons" ]; then
      echo "    (Tap the Phase C button. Its payload is fixed at 100 MB in the UI;"
      echo "     for other sizes use broadcast mode: MODE=broadcast)"
      prompt_tap "Phase C · Unguarded reconnect @100 MB"
    else
      bc_reconnect "$MB" false 20
    fi
    echo "    waiting ${WAIT}s for cycle / completion..."; sleep "$WAIT"
    dump_log "$F"; undoze
    RE=$(count "worker_reentry" "$F"); OK=$(count "worker_complete" "$F")
    echo ">>> @${MB}MB: worker_reentry=$RE  worker_complete=$OK  -> $F"
    if [ "$RE" != "0" ]; then echo "    -> CYCLED (S4-S7 re-entry) at ${MB} MB"
    elif [ "$OK" != "0" ]; then echo "    -> COMPLETED (no cycle) at ${MB} MB"
    else echo "    -> inconclusive; run diag or raise WAIT_SECS"; fi
    ;;

  gated)
    MB="${2:-100}"; WAIT="${WAIT_SECS:-90}"; F="$OUT/gated_${MB}mb_$(TS).log"
    echo ">>> Phase D (gated reconnect @ ${MB} MB under Doze)."
    adb logcat -c
    if [ "$MODE" = "buttons" ]; then
      echo "    Tap Phase D, THEN immediately press Home so the app is backgrounded."
      prompt_tap "Phase D · Gated reconnect @100 MB (remedy)  — then press Home"
      adb shell input keyevent KEYCODE_HOME; sleep 2
      force_doze
    else
      echo "    backgrounding app (Home)..."; adb shell input keyevent KEYCODE_HOME; sleep 2
      force_doze
      bc_reconnect "$MB" true 20
    fi
    echo "    waiting ${WAIT}s..."; sleep "$WAIT"
    dump_log "$F"; undoze
    SK=$(count "worker_gated_skip" "$F"); RE=$(count "worker_reentry" "$F")
    echo ">>> @${MB}MB gated: worker_gated_skip=$SK  worker_reentry=$RE  -> $F"
    if [ "$SK" != "0" ] && [ "$RE" = "0" ]; then
      echo "    -> REMEDY CONFIRMED (gate skipped reconnection, no re-entry)"
    else echo "    -> NOT confirmed; ensure app backgrounded + Doze engaged"; fi
    ;;

  cpu)
    WAIT="${WAIT_SECS:-${2:-60}}"; F="$OUT/cpu_$(TS).log"
    echo ">>> Phase E (timed dump, ${WAIT}s)."
    adb logcat -c; sleep "$WAIT"; dump_log "$F"
    echo ">>> $(count CCCDATA "$F") CCCDATA lines -> $F"
    ;;

  *)
    echo "Usage: $0 {diag | sweep [reps] | window [n] | knee <mb> | gated <mb> | cpu [secs]}"
    echo "Env:   PKG=<applicationId>  MODE=broadcast|buttons  WAIT_SECS=<s>  PROBE_GAP=<s>"
    exit 1
    ;;
esac
echo "Done. Logs in $OUT/"