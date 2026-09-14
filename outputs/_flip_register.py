"""Flip round: build outputs/flip_runner_register.txt from the Part 1 audit coverage.

Input: outputs/_flip_audit_coverage.json - the per-file coverage lines of the
read-only audit (outputs/flip_part1.txt sections 1.5 and 5), verbatim, one
[path, class, reason] per file. The CORRECTIONS below are the verifier and critic
rulings that changed a class after the finders wrote their coverage lines. The PINS
record what the flip commit itself changed. Pure text; imports nothing from the model.

  python outputs/_flip_register.py        (writes outputs/flip_runner_register.txt)
"""
import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "_flip_audit_coverage.json")
OUT = os.path.join(HERE, "flip_runner_register.txt")

# class overrides from the verification passes (flip_part1.txt sections 5 and 13)
CORRECTIONS = {
    "shell": {
        "outputs/_rh_drive.sh": ("DESTRUCTIVE+FAILS-LOUDLY",
            "already broken at HEAD, not flip-caused: rm -f the 13 tracked _rh_run_*.json "
            "first; the 13 patched _rh_probe runs then raise AttributeError (deleted "
            "ModeManager methods); only the --nopatch control runs silently (overwrites "
            "tracked _rh_control_nopatch.json); the aggregate overwrites tracked "
            "_rh_probe.json with 0 runs"),
        "outputs/_l808_pool.sh": ("SILENT-BY-CONSTRUCTION",
            "hardcodes _l808_sweep.py with MODE as the only base-station field; its "
            "14 mode-3 lines would be dcD, but the CRLF queue is not stripped, so every "
            "line dies at the final write (0/28 outputs exist)"),
        "outputs/_l808_pool2.sh": ("SILENT-BY-CONSTRUCTION",
            "hardcodes _l808_sweep.py (MODE only); 17 mode-3 lines would be dcD; inert "
            "while its 34 outputs exist"),
        "outputs/_lf_sweeppool.sh": ("SILENT-BY-CONSTRUCTION",
            "hardcodes _lf_assert.py (MODE only, --set ROUTE_BLOCK_STALE_CLEAR); 21 "
            "mode-3 lines would be dcD; inert while its 41 outputs exist"),
        "outputs/_sc_run.sh": ("SILENT-CHANGE",
            "_sc_probe.py; skip-if-exists, 105/105 present, BUT :9 truncates the tracked "
            "_sc_jobs.txt unconditionally, so even an inert run dirties the tree"),
    },
    "python": {},
}

PINS = {
    # path: (class AFTER the flip commit, note)
    "outputs/_vm_runwaves.sh": ("PINNED (FLIP-SAFE since the flip commit)",
        "vmoff and vmon now pass --set BASE_STATION_MODE=0. A rerun is mode 0 again but not "
        "byte-identical to the committed JSON (extra_params gains the key; later commits moved "
        "some mode-0 outputs). Overwrite still unconditional. NOTICED DOWNSTREAM: vmoff vs vmbase "
        "kill-switch identity (_vm_analyze.py) is loud; vmon feature metrics are not"),
    "outputs/_vm_runwaves2.sh": ("PINNED (FLIP-SAFE since the flip commit)",
        "vmon3 and vmoff2 now pass --set BASE_STATION_MODE=0 (same caveats as _vm_runwaves.sh); "
        "vmon3 is the _ph_analyze.py identity reference"),
    "outputs/_ir/rbgate.sh": ("PINNED (FLIP-SAFE since the flip commit)",
        "the campaign call now passes --set BASE_STATION_MODE=0; a rerun's shard params gain the "
        "key; still NO skip, so it still overwrites the tracked irfix shards. NOT NOTICED "
        "DOWNSTREAM: _lc_rbcompare.py only reports a delta"),
    "outputs/_rb_eval_after.sh": ("FAILS-LOUDLY (fixed in the flip commit)",
        "`|| exit 1` added on the cd to the deleted worktree; before, from the repo root it ran "
        "evaluate_scenarios on the LIVE tree over tracked _rb_eval_after_D_*.txt"),
}
PIPE_NOTES = {
    "outputs/_ih_post.sh": "GATE STAGE PINNED at the flip commit (ihrest --set BASE_STATION_MODE=0); "
                           "its PYTEST stage still runs the shipped default over tracked "
                           "_ih_pytest_rest99.log (read by _ih_gate.py)",
    "outputs/_dim_post.sh": "GATE STAGE PINNED at the flip commit (dimfix --set BASE_STATION_MODE=0); "
                            "its PYTEST stage still runs the shipped default over tracked "
                            "_dim_pytest_fix.log",
    "outputs/_vm_postwave.sh": "GATE STAGE PINNED at the flip commit (vmon --set BASE_STATION_MODE=0); "
                               "its PYTEST stage still runs the shipped default over tracked "
                               "_vm_pytest_feature.txt",
}
PINNED_NAMES = ("_vm_runwaves.sh", "_vm_runwaves2.sh", "_ir/rbgate.sh", "_ih_post.sh",
                "_dim_post.sh", "_vm_postwave.sh", "_rb_eval_after.sh")


def annotate(text, path=""):
    hits = [n for n in PINNED_NAMES if n in text or path.endswith(n)]
    return text + ("  [NB: %s pinned/fixed at the flip commit; see section A]" % ", ".join(hits) if hits else "")

EXTRA_SHELL = [
    ["outputs/_flip_pytest.sh", "PYTEST",
     "this round's own serial suite driver; VARIANT=base/p0 with the default FLIPTAG flip1 "
     "would overwrite the PRE-flip _flip1_pytest_* logs; use VARIANT=post and a new FLIPTAG"],
]

EXTRA_QUEUES = [
    ["outputs/_lc_jobs.txt", "SILENT-CHANGE 62",
     "regenerated and run by _lc_run.sh with no skip: 62 jobs overwrite 62 of the 99 tracked "
     "_lc_*.json (none/a/b/c x canonical 13 + none x fresh 10)"],
    ["outputs/_sc_jobs.txt", "SILENT-CHANGE 2 (inert)", "arm c 303/404; outputs present"],
]

HEADER = """FLIP RUNNER REGISTER - tooling whose meaning changed at the dcD default flip
Flip commit on branch depot-cost-round, 2026-09-14. Generated by outputs/_flip_register.py
from outputs/_flip_audit_coverage.json (the Part 1 audit, outputs/flip_part1.txt).

THE FLIP: common_fixed_variables BASE_STATION_MODE 0 -> 3, BASE_STATION_DEPOTS 0 -> 9,
BASE_STATION_SPAWN_SPLIT 0 -> 2, UAV_RETURN_TO_BASE_RESERVE 60.0 -> 0.0,
BASE_STATION_RETURN_MARGIN 5.0 -> 39.23 (and the agents.py fallbacks with them).

WHY THIS FILE EXISTS. Everything listed SILENT-CHANGE keeps running after the flip and
quietly measures the new default (dcD) instead of mode 0 - and the pool validators
(_dcd4_validate.py, _dcd4rb_validate.py) still call such a run VALID, because they
compare only a queue line's own --set list, never the effective configuration. The
harness JSON betrays a changed run after the fact (base_station None -> depot dict,
rtb_log trigger levels); a gate shard (_rblatch_camp2_*) and evaluate_scenarios text do
not. Blast radius, from the audit:
  shell/PowerShell runners (91 tracked): at b853617, 53 changed silently - 50 directly
  and 3 pools by construction - and 5 more pass their meaning through. The flip commit
  pins 3 of the 50 and makes 1 fail loudly, so 49 remain silent AFTER it (46 + 3).
  (flip_part1.txt's "51" counted _rh_drive.sh, which verification showed deletes tracked
  files and then FAILS LOUDLY, and counted the 3 pools among its 19 not-a-simulation
  files. Section A lists 92: the 91 plus this round's own _flip_pytest.sh.)
  560 of 1,092 lines in the 18 queue files change silently
  81 of 227 Python files in outputs/ change silently (+6 lane/rh probes by invocation)
  plus entry points, tests/ diagnostics, pytest runners and config-blind analyzers.

RULE. A run is FLIP-SAFE iff it sets BASE_STATION_MODE=0 explicitly, or MODE >= 1 plus
every constant reachable at that mode: MODE 1 reaches DEPOTS and SPLIT; MODE >= 2 also
RESERVE and MARGIN (wildfire_model.py _build_base_station / _assign_depot_homes gates;
agents.py _apply_return_to_base gate). SPLIT is inert with one depot or one searcher.

HOW TO REUSE ANY OF THIS: pass the full BASE_STATION_* set (or MODE=0) explicitly; give
new runs NEW tags; never edit a completed queue line in place (the dcd4 pools would
quarantine the committed runs and silently rerun them under the edited line); never
delete or rename a reference shard that a SKIP-if-exists runner protects.

READ ALSO:
  - dimctrl (_dim_queue.txt, --dim-hook deny) now CRASHES at WildFireModel() instead of
    silently changing: the deny hook raises on HEIGHT, which _build_base_station reads at
    MODE >= 1. That is the correct failure mode for a mode-0-only instrument, NOT a
    regression; rerun it with --set BASE_STATION_MODE=0.
  - a bare `python main.py` is the dashboard at east wind for 80 steps: it shows the new
    spawn positions and both depot outlines only (no return can trigger before step
    154 at the default preset A; 151-155 depending on UAV count). West and north winds were never measured at dcD (0 of 57 distinct runs).
  - a ROUTE_BLOCK_STALE_CLEAR rung-0 control must now also set BASE_STATION_MODE=0 to stay
    byte-identical to f4e79d5.
  - _dim_patch.py --revert would now break every default model construction.

READING THE ENTRIES
  - Reasons are the audit's coverage lines, verbatim, with verifier corrections applied.
    "rank N" is the audit's danger ranking of silent runners (1 = most dangerous);
    IDs such as S-02, Q-10, A-17, C-08 name audit findings summarised in
    outputs/flip_part1.txt sections 1-5; "NOT in assigned list", "grep-level" and
    "UNVERIFIED" are the audit's own coverage qualifiers.
  - ALL path:line CITATIONS ARE AT b853617, the audit HEAD. The flip commit adds lines to
    agents.py, wildfire_model.py, common_fixed_variables.py and outputs/_ffr_harness.py;
    locate by content.

CLASSES
  PINNED                  was SILENT-CHANGE; the flip commit made it pass MODE=0
  FLIP-SAFE               sets MODE=0, or MODE>=1 with every reachable constant
  SILENT-CHANGE           runs the live tree on a reachable default -> now dcD
  SILENT-BY-CONSTRUCTION  hardcoded command with no base-station channel (MODE only)
  PASSTHROUGH             meaning set by caller arguments (callers listed)
  PYTEST                  runs the suite on the live tree: now tests the shipped dcD
  FAILS-LOUDLY            pinned to a checkout that no longer exists, or already broken
  OTHER-CHECKOUT          runs another existing checkout (dc_e703861, at e703861)
  NOT-A-SIM               analysis / plumbing only
"""


def section(title):
    return "\n" + "=" * 78 + "\n" + title + "\n" + "=" * 78 + "\n"


def main():
    data = json.load(open(SRC, encoding="utf-8"))
    lines = [HEADER]

    shell = [list(r) for r in data["shell"]] + EXTRA_SHELL
    for r in shell:
        c = CORRECTIONS["shell"].get(r[0])
        if c:
            r[1], r[2] = c
    before = collections.Counter(r[1] for r in shell if r[0] != "outputs/_flip_pytest.sh")
    for r in shell:
        if r[0] in PINS:
            r[2] = "AT b853617: %s (%s)  ||  NOW: %s" % (r[1], r[2], PINS[r[0]][1])
            r[1] = PINS[r[0]][0]
    after = collections.Counter(r[1] for r in shell if r[0] != "outputs/_flip_pytest.sh")
    lines.append(section("A. SHELL / POWERSHELL RUNNERS (%d = 91 tracked + _flip_pytest.sh)" % len(shell)))
    lines.append("Silent at b853617: %d direct + %d pools = %d of 91. After the flip commit: %d direct "
                 "+ %d pools = %d of 91 (pinned %d, fixed-to-loud 1).\n" % (
                     before["SILENT-CHANGE"], before["SILENT-BY-CONSTRUCTION"],
                     before["SILENT-CHANGE"] + before["SILENT-BY-CONSTRUCTION"],
                     after["SILENT-CHANGE"], after["SILENT-BY-CONSTRUCTION"],
                     after["SILENT-CHANGE"] + after["SILENT-BY-CONSTRUCTION"],
                     after["PINNED (FLIP-SAFE since the flip commit)"]))
    order = ["SILENT-CHANGE", "SILENT-BY-CONSTRUCTION", "PASSTHROUGH", "PYTEST",
             "PINNED (FLIP-SAFE since the flip commit)", "DESTRUCTIVE+FAILS-LOUDLY",
             "FAILS-LOUDLY (fixed in the flip commit)", "FAILS-LOUDLY", "FLIP-SAFE", "NOT-A-SIM"]
    groups = collections.OrderedDict((k, []) for k in order)
    for path, cls, why in shell:
        groups.setdefault(cls, []).append((path, why))
    for cls, rows in groups.items():
        if not rows:
            continue
        lines.append("\n-- %s (%d)\n" % (cls, len(rows)))
        for path, why in sorted(rows):
            lines.append("  %s\n      %s\n" % (path, why if path in PINS else annotate(why)))
            if path in PIPE_NOTES:
                lines.append("      >>> %s\n" % PIPE_NOTES[path])

    lines.append(section("B. QUEUE FILES AND THEIR PLUMBING"))
    lines.append("Per arm: FLIP-SAFE / SILENT-CHANGE / FAILS-LOUDLY / OTHER-CHECKOUT line counts.\n"
                 "Totals over the 18 queue files: 422 / 560 / 83 / 27 (1,092 lines).\n"
                 "Silent live arms by name: _dim_queue dimfix diminst dimfreshfix dimpinall dimA\n"
                 "dimB dimC (dimctrl CRASHES); _ih_queue ihfix ihdeadC3 ihdeadC5 ihdeadC7\n"
                 "ihdeadC7C6; _ih_queue3 ihoff ihrest99 ihrest6 ihrest99fresh ihrest6fresh\n"
                 "ihofffresh ihrbx222 ihrbx222off; _mm_queue mainff.\n")
    for path, cls, why in list(data["queues"]) + EXTRA_QUEUES:
        lines.append("  %s\n      %s%s\n" % (path, cls, annotate(("  | " + why) if why else "", path)))

    lines.append(section("C. PYTHON FILES IN outputs/ (%d)" % len(data["python"])))
    pgroups = collections.OrderedDict()
    for path, cls, why in data["python"]:
        pgroups.setdefault(cls, []).append((path, why))
    for cls in sorted(pgroups, key=lambda k: (k == "NOT-A-SIM", k)):
        rows = pgroups[cls]
        lines.append("\n-- %s (%d)\n" % (cls, len(rows)))
        for path, why in sorted(rows):
            lines.append("  %s\n      %s\n" % (path, why))

    lines.append(section("D. ENTRY POINTS, tests/ DIAGNOSTICS, DOCS, REPORTS, MEMORY"))
    for path, cls, why in data["entrypoints"]:
        lines.append("  %s\n      %s%s\n" % (path, cls, ("  | " + why) if why else ""))

    lines.append(section("E. PROBES KEYED ON SOURCE LINE NUMBERS"))
    lines.append(
        "Their site tables changed at the flip commit PURELY because its comment and\n"
        "docstring edits moved lines in agents.py and wildfire_model.py, whatever the flip\n"
        "does to behaviour: _dim_hooks.py (reader:line), _irh_probe.py, _irh2_probe.py,\n"
        "_irh2_probe_h.py (whose hardlc arm was already keyed to a stale line),\n"
        "_rb_campaign.py, _route_blocked_probe.py, _route_blocked_reach_probe.py\n"
        "(f_lineno), _bat_probe.py, _fs_probe.py (file:func:line).\n"
        "Also staled by the same edits, with no behaviour effect: path:line COMMENT CITATIONS\n"
        "into agents.py, wildfire_model.py, common_fixed_variables.py and _ffr_harness.py\n"
        "across the repo (e.g. serve_dashboard.py, dashboard_state_builder.py,\n"
        "_rblatch_campaign2.py). Locate by function name.\n")

    lines.append(section("F. CONFIG-BLIND VALIDATORS AND ANALYZERS"))
    lines.append(
        "  _dcd4_validate.py / _dcd4rb_validate.py  compare only the queue's --set list:\n"
        "      a changed-meaning run is VALID; an in-place pin quarantines committed runs\n"
        "  _ffr_rbcompare.py   outcome-only, never reads params; two-way prefix glob\n"
        "  _dcd4rb_controls.py --pairs   passes vacuously on 0/0 (check n)\n"
        "  _l808_armcount.py   buckets on extra_params MODE (a missing key is not 'pre-feature')\n"
        "  _lf_sweepanalyze.py joins post-flip mode-3 runs to single-NW _l808sw2 by (seed, mode, wind)\n"
        "  _sc_analyze.py      hardcoded mode-0 firefighter death cells\n"
        "  _pr_control.py / _sc_control.py   a bare run overwrites tracked *_pre.json (tag 'pre')\n")

    lines.append(section("G. CONSEQUENCES WORTH KNOWING (flip_part1.txt sections 1.2, 5.3-5.5)"))
    lines.append(
        "  WHAT NOTICES A POST-FLIP OVERWRITE (flip_part1.txt 5.1 vs 5.2)\n"
        "    LOUD downstream: dcinerta (always paired with rbca by _dc_rbinert.py); vmoff/vmoff2\n"
        "      (kill-switch identity vs vmbase in _vm_analyze.py); gs val50 (validated field for\n"
        "      field against _ffr_latbase); any harness wave (base_station becomes a depot dict)\n"
        "    SILENT downstream: irfix shards (_lc_rbcompare.py reports a delta); _ir_p3_POST_*\n"
        "      (_lc_analyze.py aggregates); lane_matrix/*.json (_cast_gates.py computes numbers);\n"
        "      lane_clamp_default_* (its only reader is dead); _rb_eval_after_D_*.txt (no reader);\n"
        "      gs A100/B100/C100 (arm-vs-arm, both sides re-runnable); vmon/vmon3 feature metrics\n"
        "  DESTRUCTIVE BEFORE FAILING: _lat_launch_base.sh truncates tracked _ffr_runall_latbase.log\n"
        "    and overwrites the 13 tracked _ffr_logs/latbase_*.out (and .err) before every harness\n"
        "    process dies on the missing checkout; _dim_flips.sh truncates tracked _dim_flips.txt;\n"
        "    _rh_drive.sh deletes 13 tracked _rh_run_*.json (section A)\n"
        "  ARGUMENT-DRIVEN RUNNERS: _pr_rbgate.sh, _rh_rbgate.sh (tag), _dr_run.sh, _rh_ctl_drive.sh\n"
        "    (tag/tuple) are inert only for their recorded arguments; with a new one they run dcD\n"
        "  OTHER CHECKOUT: dcref / dcAref run the dc_e703861 worktree, which lives in another\n"
        "    session's Temp scratchpad; if that directory is cleaned they fail loudly\n"
        "  BASELINES THAT STOP BEING THE SHIPPED CONFIGURATION: ihrest99 / ihrest99fresh (the\n"
        "    recorded 50x50 baseline), dfzero, d4off, drhZ, rbc, ihrest - valid as MODE=0\n"
        "    references only. The shipped-default references are dfD, d4D, drhD (and flhD after\n"
        "    the flip round's Part 3)\n"
        "  NOT COMPARABLE EVEN WHEN IT RUNS: diminst (--dim-hook record) gains two HEIGHT/WIDTH\n"
        "    readers (_build_base_station, _assign_depot_homes)\n"
        "  POST-FLIP EQUIVALENCES of under-specified arms: bsspawn == dlS, bsspawnu == dlF,\n"
        "    bsfull == dcD/d4D, bsfullp == dfW1, d4A == d4D, dcA and dcB -> dcD, dfA and dfB -> dcD,\n"
        "    dfkill and drxK -> drhK, drxrbB and drxrbZ -> drgD\n")

    text = "".join(lines)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote %s (%d lines)" % (OUT, text.count("\n")))


if __name__ == "__main__":
    main()
