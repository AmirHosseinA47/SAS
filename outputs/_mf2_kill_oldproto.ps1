$procs = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match '_mf2_p1_proto_plugin' }
foreach ($p in $procs) { Write-Output ("stopping " + $p.ProcessId + " " + $p.CommandLine.Substring(0, [Math]::Min(120, $p.CommandLine.Length))); Stop-Process -Id $p.ProcessId -Force }
