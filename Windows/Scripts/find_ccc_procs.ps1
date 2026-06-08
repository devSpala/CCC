<#
  find_ccc_procs.ps1  -  Identify the REAL process image names involved in CCC.

  Run this in an ELEVATED PowerShell WHILE the cycle is being forced:
     powershell -ExecutionPolicy Bypass -File .\find_ccc_procs.ps1

  It snapshots running processes 10 times over ~5 s and reports any whose name or
  command line looks related to the bridge / background task, plus the ones whose
  PID set is churning (being created/destroyed) - that churn is the CCC re-fire.
#>

$ErrorActionPreference="SilentlyContinue"

Write-Host "Snapshotting processes for ~5s while CCC runs..."
$seen = @{}     # name -> count of snapshots it appeared in
$pidsByName = @{}  # name -> hashset of pids observed (churn indicator)

for ($i=0; $i -lt 10; $i++) {
    $procs = Get-CimInstance Win32_Process
    foreach ($p in $procs) {
        $n = $p.Name
        if (-not $seen.ContainsKey($n)) { $seen[$n]=0; $pidsByName[$n]=New-Object System.Collections.Generic.HashSet[int] }
        $seen[$n]++
        [void]$pidsByName[$n].Add([int]$p.ProcessId)
    }
    Start-Sleep -Milliseconds 500
}

Write-Host "`n=== Candidates (name contains bridge/host/handler/test/dotnet/wpf) ==="
foreach ($n in $seen.Keys | Sort-Object) {
    if ($n -match "bridge|host|handler|test|dotnet|wpf|uwp|samsung|backgroundtask") {
        $churn = $pidsByName[$n].Count
        Write-Host ("{0,-35} appeared_in={1,2}/10 snapshots  distinct_PIDs={2}" -f $n,$seen[$n],$churn)
    }
}

Write-Host "`n=== HIGH CHURN (>=3 distinct PIDs = likely the re-firing CCC process) ==="
foreach ($n in $seen.Keys | Sort-Object) {
    if ($pidsByName[$n].Count -ge 3) {
        Write-Host ("{0,-35} distinct_PIDs={1}" -f $n,$pidsByName[$n].Count)
    }
}

Write-Host "`nFull command lines for likely matches:"
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match "bridge|host|handler|test|wpf|samsung|backgroundtask" } |
  Select-Object Name, ProcessId, CommandLine | Format-List
