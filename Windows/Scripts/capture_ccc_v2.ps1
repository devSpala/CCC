<#
  capture_ccc_v2.ps1  -  robust CCC trace capture (substring + commandline matching)

  Run elevated:
    powershell -ExecutionPolicy Bypass -File .\capture_ccc_v2.ps1 -Seconds 90 -IntervalMs 250 `
       -NamePatterns "Bridge","backgroundTaskHost","Communicator" `
       -CmdLinePatterns "bridgecom","Communicator_OutProc","BridgeHandler","BridgeTest"

  - NamePatterns     : substrings matched against the process image name (case-insensitive).
  - CmdLinePatterns  : substrings matched against the FULL command line (catches background
                       task hosts and dotnet-hosted processes whose image name is generic).
  A process matches if EITHER its name OR its command line contains ANY pattern.

  Outputs cpu_trace.csv + proc_events.csv (same schema as before).
  For idle baseline: run again without forcing the cycle, rename to *_idle.csv.
#>

param(
    [int]$Seconds = 90,
    [int]$IntervalMs = 250,
    [string[]]$NamePatterns    = @("Bridge","backgroundTaskHost","Communicator"),
    [string[]]$CmdLinePatterns = @("bridgecom","Communicator_OutProc","BridgeHandler","BridgeTest")
)

$ErrorActionPreference = "Stop"
$nCores = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
Write-Host "Logical processors: $nCores"
Write-Host "Name patterns:    $($NamePatterns -join ', ')"
Write-Host "CmdLine patterns: $($CmdLinePatterns -join ', ')"

function Get-MatchingProcs {
    # returns array of @{ pid; name; cmd }
    $all = Get-CimInstance Win32_Process
    $out = @()
    foreach ($p in $all) {
        $nm  = [string]$p.Name
        $cmd = [string]$p.CommandLine
        $hit = $false
        foreach ($np in $NamePatterns)    { if ($nm  -and $nm.ToLower().Contains($np.ToLower()))  { $hit=$true; break } }
        if (-not $hit) { foreach ($cp in $CmdLinePatterns) { if ($cmd -and $cmd.ToLower().Contains($cp.ToLower())) { $hit=$true; break } } }
        if ($hit) { $out += @{ pid=[int]$p.ProcessId; name=$nm; cmd=$cmd } }
    }
    return $out
}

$cpuRows  = New-Object System.Collections.Generic.List[object]
$procRows = New-Object System.Collections.Generic.List[object]
$seen     = @{}   # pid -> name
$prevCpu  = @{}   # pid -> @{ ms; t }

$t0 = Get-Date
$endAt = $t0.AddSeconds($Seconds)

while ((Get-Date) -lt $endAt) {
    $now = Get-Date
    $elapsed = ($now - $t0).TotalSeconds
    $procs = Get-MatchingProcs
    $curPids = @{}
    $totalCpuPct = 0.0

    foreach ($p in $procs) {
        $curPids[$p.pid] = $true
        if (-not $seen.ContainsKey($p.pid)) {
            $seen[$p.pid] = $p.name
            $procRows.Add([pscustomobject]@{
                event="spawn"; elapsed_s=[math]::Round($elapsed,3); wallclock=$now.ToString("o")
                pid=$p.pid; name=$p.name
            })
        }
        try {
            $proc = Get-Process -Id $p.pid -ErrorAction Stop
            $cpuMsNow = $proc.TotalProcessorTime.TotalMilliseconds
            if ($prevCpu.ContainsKey($p.pid)) {
                $dtMs = ($now - $prevCpu[$p.pid].t).TotalMilliseconds
                $dCpu = $cpuMsNow - $prevCpu[$p.pid].ms
                if ($dtMs -gt 0 -and $dCpu -ge 0) { $totalCpuPct += 100.0 * $dCpu / $dtMs }
            }
            $prevCpu[$p.pid] = @{ ms=$cpuMsNow; t=$now }
        } catch {}
    }

    foreach ($oldPid in @($seen.Keys)) {
        if (-not $curPids.ContainsKey($oldPid)) {
            $procRows.Add([pscustomobject]@{
                event="exit"; elapsed_s=[math]::Round($elapsed,3); wallclock=$now.ToString("o")
                pid=$oldPid; name=$seen[$oldPid]
            })
            $seen.Remove($oldPid) | Out-Null
            $prevCpu.Remove($oldPid) | Out-Null
        }
    }

    $cpuRows.Add([pscustomobject]@{
        elapsed_s=[math]::Round($elapsed,3); wallclock=$now.ToString("o")
        live_proc_count=$procs.Count
        cpu_pct_onecore=[math]::Round($totalCpuPct,3)
        cpu_pct_machine=[math]::Round(($totalCpuPct/$nCores),3)
    })
    Start-Sleep -Milliseconds $IntervalMs
}

$cpuRows  | Export-Csv -NoTypeInformation -Path ".\cpu_trace.csv"
$procRows | Export-Csv -NoTypeInformation -Path ".\proc_events.csv"
$spawns=($procRows|Where-Object{$_.event -eq "spawn"}).Count
$exits =($procRows|Where-Object{$_.event -eq "exit"}).Count
$maxlive=($cpuRows | Measure-Object -Property live_proc_count -Maximum).Maximum
Write-Host ""
Write-Host "Wrote cpu_trace.csv ($($cpuRows.Count) samples, max live procs=$maxlive)"
Write-Host "Wrote proc_events.csv ($spawns spawns, $exits exits)"
if ($maxlive -eq 0) {
    Write-Host "WARNING: still matched 0 processes. Run find_ccc_procs.ps1 during the cycle to get exact names/cmdlines, then pass them via -NamePatterns / -CmdLinePatterns."
}
