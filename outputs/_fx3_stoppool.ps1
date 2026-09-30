param([string]$QueueFile)
# fix3a: stop ONE pool process (python.exe running _mf2_pool.py on the named queue). Only python.exe
# processes are matched, so the calling tool shell (bash / powershell) can never match; the pool's
# already-running child runs are left to finish (they are separate processes).
$procs = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'python.exe' -and $_.CommandLine -like '*_mf2_pool.py*' -and $_.CommandLine -like ('*' + $QueueFile + '*')
}
foreach ($p in $procs) {
    Write-Output ("stopping pool pid {0}: {1}" -f $p.ProcessId, $p.CommandLine)
    Stop-Process -Id $p.ProcessId -Force
}
if (-not $procs) { Write-Output "no pool process for $QueueFile" }
