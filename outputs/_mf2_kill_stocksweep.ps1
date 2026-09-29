$procs = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'no:cacheprovider' -and $_.CommandLine -notmatch '_mf2_p1_proto_plugin' }
foreach ($p in $procs) { Write-Output ("stopping " + $p.ProcessId); Stop-Process -Id $p.ProcessId -Force }
