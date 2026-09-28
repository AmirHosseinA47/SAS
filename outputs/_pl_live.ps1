# Planner round: one box-wide snapshot for outputs/_pl_pool.sh (outputs/_dcd4rb_live.ps1 with
# the planner's job kinds). Kept in a file so the match strings never appear on the command
# line of the shell that invokes it (memory: windows-bash-tool-gotchas).
# Prints:  FREE <FreeVirtualMemory kB>
#          SIMS <live simulation jobs box-wide, any kind, any tag>
#          LIVE <output json path>  one per live job whose --tag starts with TagPrefix
#   harness job (any python with --out: _ffr_harness.py, _pl_obs_stock.py, _pl_obs_crn.py)
#                -> its --out path as given on the command line
#   gate shard   -> <dir of the campaign script as given>/_rblatch_camp2_<tag>_D_<wind>.json
#                   (the campaign writes next to itself; --wind defaults to east)
# Each job shows as TWO python.exe (launcher + interpreter); paths are de-duplicated.
param([string]$TagPrefix = "pl")
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
    $rb = [regex]::Match($cl, '([^"\s]*_rblatch_campaign2\.py)')
    if ($rb.Success) {
      if (-not $tag) { continue }
      $w = [regex]::Match($cl, '--wind\s+"?([^"\s]+)"?')
      $wind = "east"
      if ($w.Success) { $wind = $w.Groups[1].Value }
      $dir = $rb.Groups[1].Value -replace '\\', '/'
      $dir = $dir.Substring(0, $dir.LastIndexOf('/'))
      $o = "$dir/_rblatch_camp2_$($tag)_D_$($wind).json"
    } else {
      $m = [regex]::Match($cl, '--out\s+"?([^"\s]+)"?')
      if (-not $m.Success) { continue }
      $o = $m.Groups[1].Value
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
