"""bayesprep Part 3 screen queues (outputs/bayesprep_part1.txt section 7 + the rulings of section 10, D-6).
Lines for outputs/_mf2_pool.py ({"name", "argv", "out", "cwd"}). A development check, not the measurement.

usage (worktree root): .venv/Scripts/python.exe outputs/_bp_queue.py <wave> [--resume]
  -> writes outputs/_bp_q_<wave>.jsonl
  first  bpi (identity) in r, u and the u2 cell D_W  +  V1 (6 instrument reproductions)  +  V1b (2 fresh runs
         without --instrument). Read first: nothing else is read until ID and V1 pass.
  arms   every other arm (bpc bpl bpd bpf bpx bpp bpw bpg) in r, u and the u2 cell D_W
  rb     the four route_blocked shards (the untune utR shards, worktree script, tags bprba/bprbb/bprbc/bprbs)
  all    first + rb + arms, in that order
  twins  ONLY V1b's two twins bpfr_A_E / bppr_A_E (lines of the arms wave). V1b compares against them, so it cannot
         be read before they exist: if V1 fails and the item-3 risk rule needs V1b before the arms wave, run this
         wave, then generate 'arms' with --resume (the pool SKIPS the two valid twins).
  --resume  allow EXISTING UNTRACKED files of the wave's tags when they belong to one of the wave's own lines (a
            re-generation after a partial wave or after 'twins'; the pool skips a run whose .argv matches). Without
            it any existing file is a hard failure; a file of the tag that is no line of the wave, or a TRACKED
            file, is always a hard failure.

EVERY probe line runs outputs/_ut_probe.py --crn --hazard --instrument -- --repo E:\\Projects\\SAS_wt\\bayesprep ...
(the probes default to the MAIN checkout without --repo), cwd = the worktree, 360 steps, BATCH_SIZE=360,
GLOBAL_PLANNER_MODE=0 (1 for bpg), VICTIM_SPAWN_MODE = the placement's. Cells are read from the reference argv
files exactly as _ut_queue.py does: set 1 = cells("fx3mS") (seeds 9601-9616), set 2 = cells("fx3mS2").
  ARMS (D-6; tag = arm + placement, e.g. bpir, bpiu, bpiu2):
    bpi  identity: SEARCHER_TARGETING_FIX=0, UAV_DOCKED_NOT_OBSTACLE=0 (CUR, every new switch at 0)
    bpc  CUR at the new defaults (no new --set) = the gate reference
    bpl  SEARCHER_TARGETING=1 (LO)        bpd  SEARCHER_TARGETING=2 (BD)       bpf  SEARCHER_TARGETING=3 (BF)
    bpx  SEARCHER_TARGETING=3, SEARCHER_TARGETING_FIX=0 (BF, item 1 off)     bpp  SEARCHER_TARGETING=5 (FP)
    bpw  SEARCHER_TARGETING=4 (RW)        bpg  GLOBAL_PLANNER_MODE=1, SEARCHER_TARGETING=3 (GP)
  PLACEMENTS: r = VICTIM_SPAWN_MODE 0, set 1 (16 cells); u = VICTIM_SPAWN_MODE 1, set 1 (16 cells);
              u2 = VICTIM_SPAWN_MODE 1, set 2, ONLY the cell D_W (seed 9636).
  V1 (one cell A_E each): the recorded run's .json.argv mirrored EXACTLY - same probe layer, same own flags (CRN as
     recorded), same --set list - plus --instrument, --repo <worktree>, --set SEARCHER_TARGETING_FIX=0,
     --set UAV_DOCKED_NOT_OBSTACLE=0, and for the fb3 re-screen runs --set SEARCHER_UNTUNED=0:
       bpv1bd <- fb3bdr, bpv1bf <- fb3bfr, bpv1bd2 <- fb3bdr2, bpv1bf2 <- fb3bfr2, bpv1vs <- fb3vs3r, bpv1ut <- ut2bf
  V1b: bpnfr_A_E = bpfr_A_E's line WITHOUT --instrument; bpnpr_A_E = bppr_A_E's line without it.
  rb: outputs/_ut_q_all2.jsonl lines 41-44 (utRa/utRb/utRc/utRs) with the script and cwd pointed at the WORKTREE
      (outputs/_rblatch_campaign2.py inserts its own parent checkout at sys.path[0], line 18, and writes its JSON
      next to itself), the same --set SEARCHER_UNTUNED=1, tags bprba/bprbb/bprbc/bprbs.
TAG CHECK (fail loudly, before writing): for every tag of the wave, 0 files outputs/_sd_<tag>_*,
outputs/_ffr_<tag>_*, outputs/_rblatch_camp2_<tag>_* exist and none is tracked (git ls-files).
The analyzer (outputs/_bp_analyze.py) imports spec() / entries() from here: one owner of every expected argv.

FOLLOW-UP (maintainer rulings on outputs/bayesprep_report.txt section 10, 2026-10-04) - run at the FOLLOW-UP head
(R-4 source + the record-only probe additions), group "follow", never part of 'all':
  r5     identity at the follow-up head + ruling R-5's validation (7 lines): bp2cr / bp2cu = bpc A_E (r / u); bp5fr =
         bpf r B_S, bp5nfr = the same WITHOUT --instrument (V1b), bp5dr = bpd r C_S, bp5pr = bpp r D_S, bp5xr = bpx r
         D_S (the cells with the most drop_swept events of their arm in the screen). Each instrumented one must equal
         the screen run of the same line on every recorded field but the instrument / timing / the new mr record.
  lo2    ruling R-4's re-screen: bpe = SEARCHER_TARGETING=1 (LO with the edge geometry) in r, u (32) + the u2 cell D_W.
  follow r5 + lo2.
  mr1v   the MR1 record's validation (3 lines, its own later head - the probe's MR1 hook was added after the follow-up
         runs had started): bp7cr / bp7fr / bp7er = the bp2cr / bp5fr / bper_A_E lines; group "mr1v".
"""
from __future__ import annotations

import collections
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WT = r"E:\Projects\SAS_wt\bayesprep"
sys.path.insert(0, HERE)
from _fb3_queue import cells  # noqa: E402

OUT = os.path.join(WT, "outputs")          # every path WRITTEN into a line is built from the constant worktree path
PROBE = os.path.join(OUT, "_ut_probe.py")  # (canonical spelling: the pool .argv rule compares strings exactly)
RB_SCRIPT = os.path.join(OUT, "_rblatch_campaign2.py")
# arm -> (the arm's own --set entries, GLOBAL_PLANNER_MODE, label)
ARMS = (
    ("bpi", ("SEARCHER_TARGETING_FIX=0", "UAV_DOCKED_NOT_OBSTACLE=0"), 0, "ID (CUR, new switches 0)"),
    ("bpc", (), 0, "CUR"),
    ("bpl", ("SEARCHER_TARGETING=1",), 0, "LO"),
    ("bpd", ("SEARCHER_TARGETING=2",), 0, "BD"),
    ("bpf", ("SEARCHER_TARGETING=3",), 0, "BF"),
    ("bpx", ("SEARCHER_TARGETING=3", "SEARCHER_TARGETING_FIX=0"), 0, "BF fix-off"),
    ("bpp", ("SEARCHER_TARGETING=5",), 0, "FP"),
    ("bpw", ("SEARCHER_TARGETING=4",), 0, "RW"),
    ("bpg", ("SEARCHER_TARGETING=3",), 1, "GP (GPM 1 + BF)"),
)
ARM_NAMES = tuple(a[0] for a in ARMS)
# follow-up (rulings 2026-10-04): the same LO line as bpl, run at the follow-up head (R-4 edge geometry)
FOLLOW_ARMS = (("bpe", ("SEARCHER_TARGETING=1",), 0, "LO + R-4 edge geometry"),)
LABEL = {a[0]: a[3] for a in ARMS + FOLLOW_ARMS}
# (tag, arm, placement, cell, instrument, reference tag): the reference is the screen run of the same line (b505d036),
# for bp5nfr its instrumented twin bp5fr
FOLLOW_TWINS = (("bp2cr", "bpc", "r", "A_E", True, "bpcr"), ("bp2cu", "bpc", "u", "A_E", True, "bpcu"),
                ("bp5fr", "bpf", "r", "B_S", True, "bpfr"), ("bp5nfr", "bpf", "r", "B_S", False, "bp5fr"),
                ("bp5dr", "bpd", "r", "C_S", True, "bpdr"), ("bp5pr", "bpp", "r", "D_S", True, "bppr"),
                ("bp5xr", "bpx", "r", "D_S", True, "bpxr"))
# the MR1 record's validation at its own head (tag, arm, placement, cell, instrument, reference = the follow-up twin)
MR1V_TWINS = (("bp7cr", "bpc", "r", "A_E", True, "bp2cr"), ("bp7fr", "bpf", "r", "B_S", True, "bp5fr"),
              ("bp7er", "bpe", "r", "A_E", True, "bper"))
# placement -> (VICTIM_SPAWN_MODE, reference seed set, cells kept or None = all 16)
PLACES = (("r", 0, "fx3mS", None), ("u", 1, "fx3mS", None), ("u2", 1, "fx3mS2", ("D_W",)))
U2_SEED = "9636"
V1 = (("bpv1bd", "fb3bdr", True), ("bpv1bf", "fb3bfr", True), ("bpv1bd2", "fb3bdr2", True),
      ("bpv1bf2", "fb3bfr2", True), ("bpv1vs", "fb3vs3r", True), ("bpv1ut", "ut2bf", False))
V1_KEY = "A_E"
V1_NEW_OFF = ("SEARCHER_TARGETING_FIX=0", "UAV_DOCKED_NOT_OBSTACLE=0")
V1B = (("bpnfr", "bpf", "r"), ("bpnpr", "bpp", "r"),          # (tag, arm, placement) of the A_E twin
       # review 3 MINOR-2 (added while the screen ran, before any run was read): a fresh with/without twin for every
       # belief mode - LO (measure only), BD (mode 2 with the fix), GP - so the item-3 risk rule has a fallback for each
       ("bpndr", "bpd", "r"), ("bpnlr", "bpl", "r"), ("bpngr", "bpg", "r"))
V1B_ADDED = ("bpndr", "bpnlr", "bpngr")                           # their own wave 'v1bx' (the pool runs 'all' as committed)
V1B_KEY = "A_E"
RB = (("bprba", "utRa", "east"), ("bprbb", "utRb", "east"), ("bprbc", "utRc", "east"), ("bprbs", "utRs", "south"))
RB_SOURCE = "_ut_q_all2.jsonl"
RB_LINES = (41, 42, 43, 44)                                   # 1-based line numbers of utRa .. utRs


def _same_path(a, b):
    return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))


def _guard():
    if not _same_path(REPO, WT):
        raise SystemExit("REFUSED: this generator belongs to the bayesprep worktree %s, it runs from %s" % (WT, REPO))


def _cells():
    sets = {"fx3mS": cells("fx3mS"), "fx3mS2": cells("fx3mS2")}
    d_w = [c for c in sets["fx3mS2"] if c[0] == "D_W"]
    if len(d_w) != 1 or d_w[0][3] != U2_SEED:
        raise SystemExit("set 2 D_W is %r, not seed %s" % (d_w, U2_SEED))
    return sets


def _entry(group, tag, key, argv, out, crn, instrument, **extra):
    e = {"group": group, "tag": tag, "key": key, "crn": crn, "instrument": instrument,
         "line": {"name": "%s_%s" % (tag, key) if key else tag, "argv": argv, "out": out, "cwd": WT}}
    e.update(extra)
    return e


def screen_entry(arm, place, cell, tag=None, instrument=True, group="screen"):
    """One screen probe line: arm x placement x cell (tag = arm + placement unless given)."""
    sets, gp = {a[0]: (a[1], a[2]) for a in ARMS + FOLLOW_ARMS}[arm]
    spawn = {p[0]: p[1] for p in PLACES}[place]
    key, scen, wind, seed = cell
    tag = tag or arm + place
    out = os.path.join(OUT, "_sd_%s_%s.json" % (tag, key))
    sd = ["--repo", WT, "--scenario", scen, "--wind", wind, "--seed", seed,
          "--set", "GLOBAL_PLANNER_MODE=%d" % gp, "--set", "VICTIM_SPAWN_MODE=%d" % spawn]
    for s in sets:
        sd += ["--set", s]
    sd += ["--steps", "360", "--set", "BATCH_SIZE=360", "--out", out, "--tag", "%s_%s" % (tag, key)]
    argv = [PROBE, "--crn", "--hazard"] + (["--instrument"] if instrument else []) + ["--"] + sd
    return _entry(group, tag, key, argv, out, True, instrument, arm=arm, place=place, layer="ut",
                  follow=group == "follow")


def screen_entries(arms, sets=None):
    sets = sets or _cells()
    res = []
    for arm in arms:
        for place, _spawn, ref, keep in PLACES:
            for c in sets[ref]:
                if keep is None or c[0] in keep:
                    res.append(screen_entry(arm, place, c))
    return res


def v1_entries():
    """V1: mirror the recorded run's .json.argv EXACTLY and add the instrument, the worktree and the new switches."""
    res = []
    for tag, ref, untuned0 in V1:
        src = os.path.join(HERE, "_sd_%s_%s.json.argv" % (ref, V1_KEY))
        rec = json.load(open(src, encoding="utf-8"))
        a = list(rec["argv"])
        script = os.path.basename(a[0])
        if script not in ("_fb3_probe.py", "_ut_probe.py"):
            raise SystemExit("V1 %s: recorded probe layer %r is not _fb3_probe / _ut_probe" % (ref, script))
        i = a.index("--")
        own = a[1:i]
        sd = a[i + 1:]
        if "--repo" in sd or "--instrument" in own:
            raise SystemExit("V1 %s: the recorded argv already carries --repo / --instrument" % ref)
        out = os.path.join(OUT, "_sd_%s_%s.json" % (tag, V1_KEY))
        sd[sd.index("--out") + 1] = out
        sd[sd.index("--tag") + 1] = "%s_%s" % (tag, V1_KEY)
        extra = list(V1_NEW_OFF) + (["SEARCHER_UNTUNED=0"] if untuned0 else [])
        sd = ["--repo", WT] + sd
        for s in extra:
            sd += ["--set", s]
        argv = [os.path.join(OUT, script)] + own + ["--instrument", "--"] + sd
        res.append(_entry("v1", tag, V1_KEY, argv, out, "--crn" in own, True, ref=ref, ref_key=V1_KEY,
                          layer="ut" if script == "_ut_probe.py" else "fb3", recorded_argv=rec["argv"],
                          added_sets=extra))
    return res


def v1b_entries(sets=None):
    """V1b: the same arm and seed as a screen run (bpfr_A_E / bppr_A_E), WITHOUT --instrument."""
    sets = sets or _cells()
    res = []
    for tag, arm, place in V1B:
        cell = [c for c in sets[{p[0]: p[2] for p in PLACES}[place]] if c[0] == V1B_KEY][0]
        twin = screen_entry(arm, place, cell)
        argv = list(twin["line"]["argv"])
        argv.remove("--instrument")
        out = os.path.join(OUT, "_sd_%s_%s.json" % (tag, V1B_KEY))
        sd = argv[argv.index("--") + 1:]
        argv[argv.index("--") + 1 + sd.index("--out") + 1] = out
        argv[argv.index("--") + 1 + sd.index("--tag") + 1] = "%s_%s" % (tag, V1B_KEY)
        res.append(_entry("v1b", tag, V1B_KEY, argv, out, True, False, ref=twin["tag"], ref_key=V1B_KEY,
                          arm=arm, place=place, layer="ut"))
    return res


def rb_entries():
    path = os.path.join(HERE, RB_SOURCE)
    with open(path, encoding="utf-8") as fh:
        lines = [ln for ln in fh]
    res = []
    for (tag, src_name, wind), ln_no in zip(RB, RB_LINES):
        item = json.loads(lines[ln_no - 1])
        if item["name"] != src_name:
            raise SystemExit("%s line %d is %r, not %s" % (RB_SOURCE, ln_no, item["name"], src_name))
        argv = list(item["argv"])
        if os.path.basename(argv[0]) != "_rblatch_campaign2.py" or argv[argv.index("--tag") + 1] != src_name:
            raise SystemExit("%s: unexpected rb line %r" % (RB_SOURCE, item))
        if argv[argv.index("--wind") + 1] != wind:
            raise SystemExit("%s: %s wind is not %s" % (RB_SOURCE, src_name, wind))
        if "SEARCHER_UNTUNED=1" not in argv:
            raise SystemExit("%s: %s does not carry --set SEARCHER_UNTUNED=1" % (RB_SOURCE, src_name))
        argv[0] = RB_SCRIPT
        argv[argv.index("--tag") + 1] = tag
        out = os.path.join(OUT, os.path.basename(item["out"]).replace("_%s_" % src_name, "_%s_" % tag))
        if out == os.path.join(OUT, os.path.basename(item["out"])):
            raise SystemExit("rb %s: the out name did not change" % tag)
        res.append(_entry("rb", tag, None, argv, out, False, False, ref=src_name, wind=wind,
                          ref_out=os.path.join(OUT, os.path.basename(item["out"]))))
    return res


def follow_entries(sets=None):
    """The follow-up lines (rulings 2026-10-04): (r5, lo2)."""
    sets = sets or _cells()
    ref_set = {p[0]: p[2] for p in PLACES}
    r5 = []
    for tag, arm, place, key, instrument, ref in FOLLOW_TWINS:
        cell = [c for c in sets[ref_set[place]] if c[0] == key][0]
        r5.append(dict(screen_entry(arm, place, cell, tag=tag, instrument=instrument, group="follow"), ref=ref,
                       ref_key=key))
    lo2 = []
    for arm, _sets, _gp, _label in FOLLOW_ARMS:
        for place, _spawn, ref, keep in PLACES:
            for c in sets[ref]:
                if keep is None or c[0] in keep:
                    lo2.append(screen_entry(arm, place, c, group="follow"))
    return r5, lo2


def mr1v_entries(sets=None):
    sets = sets or _cells()
    ref_set = {p[0]: p[2] for p in PLACES}
    res = []
    for tag, arm, place, key, instrument, ref in MR1V_TWINS:
        cell = [c for c in sets[ref_set[place]] if c[0] == key][0]
        res.append(dict(screen_entry(arm, place, cell, tag=tag, instrument=instrument, group="mr1v"), ref=ref,
                        ref_key=key))
    return res


def waves():
    sets = _cells()
    v1b = v1b_entries(sets)
    first = screen_entries(("bpi",), sets) + v1_entries() + [e for e in v1b if e["tag"] not in V1B_ADDED]
    rb = rb_entries()
    arms = screen_entries(tuple(a for a in ARM_NAMES if a != "bpi"), sets)
    twins = [e for e in arms if (e["arm"], e["place"], e["key"]) in {(a, p, V1B_KEY) for _t, a, p in V1B}]
    v1bx = [e for e in v1b if e["tag"] in V1B_ADDED]
    r5, lo2 = follow_entries(sets)
    return {"first": first, "arms": arms, "rb": rb, "all": first + rb + arms + v1bx, "twins": twins, "v1bx": v1bx,
            "r5": r5, "lo2": lo2, "follow": r5 + lo2, "mr1v": mr1v_entries(sets)}


def entries():
    """Every expected run of the screen: {(tag, key): entry} for the probe runs, {tag: entry} for the rb shards."""
    w = waves()
    probe = {(e["tag"], e["key"]): e for e in w["all"] + w["follow"] + w["mr1v"] if e["group"] != "rb"}
    rb = {e["tag"]: e for e in w["rb"]}
    return probe, rb


def validate(e):
    """The line-level rules of this round; returns a list of problems (empty = valid)."""
    bad = []
    ln = e["line"]
    argv = ln["argv"]
    if not _same_path(ln.get("cwd"), WT):
        bad.append("cwd is not the worktree")
    if not _same_path(os.path.dirname(ln["out"]), HERE):
        bad.append("out is not in the worktree's outputs/")
    if not _same_path(os.path.dirname(argv[0]), HERE):
        bad.append("script is not the worktree's")
    if e["group"] == "rb":
        if "--repo" in argv or "--instrument" in argv:
            bad.append("rb line carries a probe flag")
        if "SEARCHER_UNTUNED=1" not in argv:
            bad.append("rb line without SEARCHER_UNTUNED=1")
        return bad
    i = argv.index("--")
    own, sd = argv[1:i], argv[i + 1:]
    if sd.count("--repo") != 1 or not _same_path(sd[sd.index("--repo") + 1], WT):
        bad.append("--repo is not exactly once the worktree")
    if ("--instrument" in own) != e["instrument"]:
        bad.append("--instrument presence is not as intended")
    if ("--crn" in own) != e["crn"]:
        bad.append("--crn presence is not as intended")
    if e["group"] in ("screen", "follow", "mr1v"):
        if sd[sd.index("--steps") + 1] != "360" or "BATCH_SIZE=360" not in sd:
            bad.append("not 360 steps / BATCH_SIZE=360")
    if not _same_path(sd[sd.index("--out") + 1], ln["out"]):
        bad.append("--out differs from the line's out")
    return bad


def tag_check(es, resume=False):
    """0 files _sd_<tag>_* / _ffr_<tag>_* / _rblatch_camp2_<tag>_* and none tracked; returns problem lines. With
    resume, existing UNTRACKED files are allowed only when they belong to one of this wave's own lines (the out JSON
    and its .argv / .poollog / .stdout.txt / tmp companions)."""
    tracked = subprocess.run(["git", "-C", REPO, "ls-files", "--", "outputs"], capture_output=True, text=True,
                             timeout=120)
    if tracked.returncode != 0:
        raise SystemExit("git ls-files failed: %s" % tracked.stderr.strip())
    top = [p.split("/", 1)[1] for p in tracked.stdout.splitlines() if p.count("/") == 1]
    own = tuple(os.path.basename(e["line"]["out"])[:-len(".json")] + "." for e in es)
    problems = []
    n_exist = 0
    for tag in sorted({e["tag"] for e in es}):
        pre = ("_sd_%s_" % tag, "_ffr_%s_" % tag, "_rblatch_camp2_%s_" % tag)
        exist = sorted(os.path.basename(f) for p in pre for f in glob.glob(os.path.join(HERE, glob.escape(p) + "*")))
        trk = sorted(f for f in top if f.startswith(pre))
        n_exist += len(exist)
        if trk:
            problems.append("TAG %s: %d TRACKED files, e.g. %s" % (tag, len(trk), trk[:3]))
        foreign = [f for f in exist if not (resume and f.startswith(own))]
        if foreign:
            problems.append("TAG %s: %d files already exist%s, e.g. %s" % (
                tag, len(foreign), " that belong to no line of this wave" if resume else "", foreign[:3]))
    return problems, n_exist


def totals(es):
    c = collections.Counter()
    for e in es:
        if e["group"] in ("screen", "follow", "mr1v"):
            c["%s %s" % (e["tag"] if e["tag"] != e["arm"] + e["place"] else e["arm"], e["place"])] += 1
        else:
            c[e["group"]] += 1
    return c


def main() -> int:
    _guard()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    resume = "--resume" in sys.argv[1:]
    unknown = [a for a in sys.argv[1:] if a.startswith("--") and a != "--resume"]
    if len(args) != 1 or unknown:
        print(__doc__)
        return 2
    wave = args[0]
    w = waves()
    if wave not in w:
        raise SystemExit("unknown wave %r (first / arms / rb / all / twins / v1bx / r5 / lo2 / follow / mr1v)" % wave)
    es = w[wave]
    names = [e["line"]["name"] for e in es]
    if len(set(names)) != len(names):
        raise SystemExit("DUPLICATE NAMES IN WAVE %s" % wave)
    outs = [e["line"]["out"] for e in es]
    if len(set(outs)) != len(outs):
        raise SystemExit("DUPLICATE OUT PATHS IN WAVE %s" % wave)
    bad = [(e["line"]["name"], p) for e in es for p in validate(e)]
    if bad:
        for b in bad:
            print("INVALID LINE %s: %s" % b, file=sys.stderr)
        raise SystemExit("%d invalid lines - nothing written" % len(bad))
    problems, n_exist = tag_check(es, resume)
    if problems:
        for p in problems:
            print("TAG CHECK FAILED - %s" % p, file=sys.stderr)
        raise SystemExit("TAG CHECK FAILED (%d problems) - nothing written" % len(problems))
    path = os.path.join(HERE, "_bp_q_%s.jsonl" % wave)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for e in es:
            fh.write(json.dumps(e["line"]) + "\n")
    tot = totals(es)
    print("%s: %d lines | tag check: %d tags, 0 tracked, %d existing files%s" % (
        path, len(es), len({e["tag"] for e in es}), n_exist, " (--resume)" if resume else ""))
    for k in sorted(tot):
        print("  %-10s %3d" % (k, tot[k]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
