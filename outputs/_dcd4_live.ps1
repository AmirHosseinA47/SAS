# dcd4 round: one box-wide snapshot for the pool, in a file so the match strings
# never appear on the command line of the shell that invokes it (a kill/match
# regex once hit the Bash tool's own shell - memory: windows-bash-tool-gotchas).
#
# Prints:  FREE <FreeVirtualMemory kB>
#          SIMS <number of live harness runs, box-wide, any tag>
#          LIVE <--out path>          one per live harness run of THIS wave
# Each run shows as TWO python.exe (the .venv launcher and the real
# interpreter) with the same command line, so --out paths are de-duplicated.
param([string]$TagPrefix = "d4", [string]$HarnessLike = "*_ffr_harness.py*")
$ErrorActionPreference = "Stop"
try {
  $os = Get-CimInstance Win32_OperatingSystem
  "FREE $($os.FreeVirtualMemory)"
  $procs = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like $HarnessLike })
  $outs = @{}
  $all = @{}
  foreach ($p in $procs) {
    $m = [regex]::Match($p.CommandLine, '--out\s+"?([^"\s]+)"?')
    if (-not $m.Success) { continue }
    $o = $m.Groups[1].Value
    $all[$o] = 1
    $t = [regex]::Match($p.CommandLine, '--tag\s+"?([^"\s]+)"?')
    if ($t.Success -and $t.Groups[1].Value.StartsWith($TagPrefix)) { $outs[$o] = 1 }
  }
  "SIMS $($all.Count)"
  foreach ($o in $outs.Keys) { "LIVE $o" }
} catch {
  "ERROR $($_.Exception.Message)"
  exit 1
}
