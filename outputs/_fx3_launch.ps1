param([string]$Queue, [string]$Log, [int]$MaxPar = 14, [double]$MinFree = 3.0)
# fix3a: start outputs/_mf2_pool.py detached (survives the tool call), like the fix2 launches.
$py = "E:\Projects\SAS\.venv\Scripts\python.exe"
$pool = "E:\Projects\SAS\outputs\_mf2_pool.py"
Start-Process -FilePath $py -ArgumentList @($pool, $Queue, $Log, "--maxpar", "$MaxPar", "--min-free-gb", "$MinFree") -WorkingDirectory "E:\Projects\SAS" -WindowStyle Hidden
