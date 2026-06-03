# PowerShell equivalent of run_experiment.sh
# Drives CCCHarness on a connected device via adb and captures CCCDATA lines.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$PKG = "com.example.cccharness"
$OUT = "./logs"
if (-not (Test-Path $OUT)) { New-Item -ItemType Directory -Path $OUT | Out-Null }
function TS { Get-Date -Format "yyyyMMdd_HHmmss" }

function Clear-Log { & adb logcat -c }

function Capture($outfile, $sentinel) {
    Write-Host "Capturing -> $outfile  (waiting for sentinel: $sentinel)"
    & adb logcat -s CCCHarness:D | Tee-Object -FilePath $outfile | ForEach-Object {
        $line = $_
        if ($sentinel -ne "__never__" -and $line -match [regex]::Escape($sentinel)) {
            Write-Host "[sentinel reached]"
            Get-Process -Name adb -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
            break
        }
    }
}

function Force-Doze {
    Write-Host "Forcing Doze..."
    & adb shell dumpsys deviceidle enable        *> $null 2>&1
    & adb shell dumpsys battery unplug            *> $null 2>&1
    & adb shell dumpsys deviceidle force-idle     *> $null 2>&1
    & adb shell dumpsys deviceidle get deep | Out-Host
}

function Undoze {
    & adb shell dumpsys deviceidle unforce        *> $null 2>&1
    & adb shell dumpsys battery reset             *> $null 2>&1
}

# Parse args
$phase = $args[0]
switch ($phase) {
    'sweep' {
        $REPS = if ($args.Length -gt 1) { [int]$args[1] } else { 30 }
        $F = "$OUT/sweep_$(TS).log"
        Clear-Log
        Write-Host ">>> Keep the app in the FOREGROUND for this phase."
        & adb shell am broadcast -p com.example.myapplication -a "$PKG.SWEEP" --es reps $REPS *> $null
        Capture $F "CCCDATA sweep_done"
    }

    'window' {
        $N = if ($args.Length -gt 1) { [int]$args[1] } else { 30 }
        $F = "$OUT/window_$(TS).log"
        Clear-Log; Force-Doze
        for ($i=1; $i -le $N; $i++) {
            & adb shell am broadcast -p com.example.myapplication -a "$PKG.RECONNECT" --ei payload_mb 1 --ez gated false --ei max_retries 0 *> $null
            Start-Sleep -Seconds 8
        }
        Undoze
        # run capture in background as a job; Ctrl-C to stop when interactive
        Start-Job -ScriptBlock { param($outfile) & adb logcat -s CCCHarness:D | Tee-Object -FilePath $outfile } -ArgumentList $F | Out-Null
        Start-Sleep -Seconds 5
        Get-Process -Name adb -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Write-Host "Window samples captured to $F"
    }

    'knee' {
        $MB = if ($args.Length -gt 1) { [int]$args[1] } else { 50 }
        $F = "$OUT/knee_${MB}mb_$(TS).log"
        Clear-Log; Force-Doze
        & adb shell am broadcast -p com.example.myapplication -a "$PKG.RECONNECT" --ei payload_mb $MB --ez gated false --ei max_retries 20 *> $null
        Write-Host ">>> Unguarded worker enqueued at ${MB} MB under Doze. Capturing re-entry lines..."
        Capture $F "worker_retry_cap"
        Undoze
    }

    'gated' {
        $MB = if ($args.Length -gt 1) { [int]$args[1] } else { 50 }
        $F = "$OUT/gated_${MB}mb_$(TS).log"
        Clear-Log; Force-Doze
        & adb shell am broadcast -p com.example.myapplication -a "$PKG.RECONNECT" --ei payload_mb $MB --ez gated true --ei max_retries 20 *> $null
        Write-Host ">>> Gated worker enqueued at ${MB} MB under Doze (expect gated_skip, no re-entry)."
        Capture $F "worker_gated_skip"
        Undoze
    }

    'cpu' {
        $F = "$OUT/cpu_$(TS).log"
        Clear-Log
        Write-Host ">>> Capturing 60s of CCCDATA for CPU-context alignment."
        $proc = Start-Process -FilePath adb -ArgumentList 'logcat','-s','CCCHarness:D' -NoNewWindow -RedirectStandardOutput $F -PassThru
        Start-Sleep -Seconds 60
        if (-not $proc.HasExited) { $proc | Stop-Process -Force }
    }

    Default {
        Write-Host "Usage: .\run_experiment.ps1 {sweep [reps] | window [n] | knee <mb> | gated <mb> | cpu}"
        exit 1
    }
}

Write-Host "Done. Logs in $OUT/"
