# dcd4 round: start outputs/_dcd4_pool.sh DETACHED from any tool shell.
# Start-Process gives Git bash its own hidden console, so the pool does not die
# with the shell that launched it (the dock-fix wave's first launch did, via
# nohup ... & from the tool shell). Prints the Windows PID of the pool bash.
#
# Optional overrides are passed as environment variables, e.g. for a smoke test:
#   powershell -File outputs/_dcd4_launch.ps1 -Env "QUEUE=...;LOG=...;HB_SECS=3"
param([string]$Env = "", [string]$Script = "/e/Projects/SAS/outputs/_dcd4_pool.sh")
$bash = "D:\Programs\Git\usr\bin\bash.exe"
if (-not (Test-Path $bash)) { "ERROR git bash not found at $bash"; exit 1 }
foreach ($kv in ($Env -split ';')) {
  if ($kv -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
    Set-Item -Path ("Env:" + $Matches[1]) -Value $Matches[2]
  }
}
$p = Start-Process -FilePath $bash -ArgumentList '-l', $Script -WindowStyle Hidden -PassThru
"LAUNCHED pool winpid=$($p.Id) script=$Script"
