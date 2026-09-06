# Stop any detached shell running the dimension-round pool/launcher, then report.
$procs = Get-CimInstance Win32_Process | Where-Object { ($_.Name -match '^(bash|sh)\.exe$') -and ($_.CommandLine -match '_dim_launch|_dim_pool') }
foreach ($p in $procs) {
  Write-Output ("KILL {0} {1}" -f $p.ProcessId, $p.CommandLine)
  Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
$left = @(Get-CimInstance Win32_Process | Where-Object { ($_.Name -match '^(bash|sh)\.exe$') -and ($_.CommandLine -match '_dim_launch|_dim_pool') })
Write-Output ("remaining pool shells: {0}" -f $left.Count)
$py = @(Get-CimInstance Win32_Process -Filter "name='python.exe'")
Write-Output ("python.exe processes: {0}" -f $py.Count)
