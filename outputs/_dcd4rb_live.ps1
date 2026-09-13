# dcd4rb round: one box-wide snapshot for outputs/_dcd4rb_pool.sh. Extends
# outputs/_dcd4_live.ps1 to the second job kind (route_blocked gate shards).
# Kept in a file so the match strings never appear on the command line of the
# shell that invokes it (a kill/match regex once hit the Bash tool's own shell -
# memory: windows-bash-tool-gotchas).
#
# Prints:  FREE <FreeVirtualMemory kB>
#          SIMS <number of live simulation jobs box-wide, either kind, any tag>
#          LIVE <output json path>   one per live job of THIS wave (tag prefix)
#   harness job  -> its --out path as given on the command line
#   gate shard   -> <RbDir>/_rblatch_camp2_<tag>_D_<wind>.json, the path the
#                   campaign derives (it takes no --out); --wind defaults to east
# Each job shows as TWO python.exe (the .venv launcher and the real interpreter)
# with the same command line, so paths are de-duplicated.
param([string]$TagPrefix = "dr",
      [string]$HarnessLike = "*_ffr_harness.py*",
      [string]$RbLike = "*_rblatch_campaign2.py*",
      [string]$RbDir = "outputs")
$ErrorActionPreference = "Stop"
try {
  $os = Get-CimInstance Win32_OperatingSystem
  "FREE $($os.FreeVirtualMemory)"
  $procs = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'")
  $outs = @{}
  $all = @{}
  foreach ($p in $procs) {
    $cl = $p.CommandLine
    if (-not $cl) { continue }
    $t = [regex]::Match($cl, '--tag\s+"?([^"\s]+)"?')
    $tag = ""
    if ($t.Success) { $tag = $t.Groups[1].Value }
    $o = $null
    if ($cl -like $HarnessLike) {
      $m = [regex]::Match($cl, '--out\s+"?([^"\s]+)"?')
      if (-not $m.Success) { continue }
      $o = $m.Groups[1].Value
    } elseif ($cl -like $RbLike) {
      if (-not $tag) { continue }
      $w = [regex]::Match($cl, '--wind\s+"?([^"\s]+)"?')
      $wind = "east"
      if ($w.Success) { $wind = $w.Groups[1].Value }
      $o = "$RbDir/_rblatch_camp2_$($tag)_D_$($wind).json"
    } else {
      continue
    }
    $all[$o] = 1
    if ($tag -and $tag.StartsWith($TagPrefix)) { $outs[$o] = 1 }
  }
  "SIMS $($all.Count)"
  foreach ($o in $outs.Keys) { "LIVE $o" }
} catch {
  "ERROR $($_.Exception.Message)"
  exit 1
}
