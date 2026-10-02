# untune Part 3: the full suite on the Part 2 head, detached; output to outputs\_ut_fullsuite3.log, then "EXIT <rc>".
Set-Location "E:\Projects\SAS"
$log = "E:\Projects\SAS\outputs\_ut_fullsuite3.log"
& "E:\Projects\SAS\.venv\Scripts\python.exe" -m pytest tests -q -p no:cacheprovider *> $log
$rc = $LASTEXITCODE
Add-Content -Path $log -Value ("EXIT " + $rc)
