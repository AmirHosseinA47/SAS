"""Carrying-leg round, Part 2 tooling: the SHARED HELPERS of the analyzer.

Spec: outputs/_cl_tooling_spec.txt sections A, C, D, H (design outputs/carryleg_part1.txt
9.1-9.4). Imported by outputs/_cl_analyze.py and by outputs/_cl_legs.py. Plain functions
over RECORDED run JSON: nothing here runs a simulation, lists a directory or writes a file.

FAILS LOUDLY (spec A5). Every provenance mismatch raises SystemExit("REFUSED: ...");
every broken internal assumption (a leg the rows contradict, a missing series) raises
SystemExit("ANALYZER DEFECT - STOP: ..."). Nothing is ever skipped silently.

QUARANTINE (spec A1). outputs/_firemech_rewound_20260914/ is never read, listed or
traversed: this module lists NO directory at all. Every path it opens is built from a
queue line or from a stated reference tag + tuple, and every path is checked against
the quarantine name before it is opened (_guard).

CONTENTS
  constants    OUT, ROOT, H (360), PREFIX (240), GRID (50), CUTS, MAIN_REPO, BASE_REPO,
               C13, RB7, RB_SHARDS, SERIES/EVENTS (the _uh_analyze P2 lists), ARMS
               (the pre-registered arm table), REFS (recorded reference tags)
  seeds        frozen_u30(), frozen_n30(), seed_sets(checked), set_of()
  queue        parse_extra(), read_queue(), stage_queues()
  paths        run_json(), sidecar_path(), rb_json(), label(), rr()
  provenance   typed_equal(), norm_repo(), cfv_declared(), check_arm_line(),
               check_ff_run(), pool_argv(), check_sidecar() (argv == the pool's command),
               check_rb_run() (no stray params), rb_base_diff() (base values == ugGD),
               load_ref(), load_rb_ref(),
               RunIndex (queue lines -> provenance-checked runs, LRU cache; the combination
               arms clA2/clKA2/clGA2 cross-checked to one switch set)
  rows         row_after(), row_at_start(), ff_row(), bind_row(), victim_row(), statuses()
  fire         Burn (burning-at-step from burn_intervals), neighbours(), on_boundary(),
               edge_dist(), exit_target(), md()
  divergence   first_diff(), first_diff_detail(), series_equal(), fire_identical()
  outcomes     cut_outcomes(), eval_crosscheck(), victim_fate(), ff_deaths(), completions_of()
  legs         legs() (H2 pairing, d, d_c, n, M1a/M1b/M1c, broken end causes, path,
               reversals), leg_key(), match_legs(), compare_legs(), unassigns_at()
  identity     diff_keys(), prefix_diff(), rb_diff()

ROW CONVENTION (spec H; design 9.3). An event stamped s happened DURING model step s.
ff_steps[s-1], ff_bind_steps[s-1], victim_steps[s-1] are the state AFTER step s (the
harness appends one row after each model.step()). The state at the START of step s is
therefore row s-2 (= row_after(d, key, s-1)); the state before step 1 is not recorded.
  ff_steps       [ff, [x,y]|None, status, assigned, exiting, dead]
  ff_bind_steps  [ff, bound victim id | "", available, rescue_completed, off_grid]
  victim_steps   [vid, [x,y]|None, status]
  burn_intervals {"x,y": [[a, b|None], ...]}: burning in the post-step observation of
                 steps a..b-1 (b None = still burning at the horizon).
A carrier's death row has exiting False: key "was it carrying" on the PREVIOUS row.

LEGS (spec H2). A leg is one exit_starts entry (unit F, victim v, pickup step s0, pickup
cell p0), paired with F's completion of v at a step s1 with s0 <= s1 < the step of v's
NEXT exit_start (any unit). n = s1 - s0. The minimum possible n is d_c + 1: the unit
stands on the pickup cell at s0, reaches the exit cell at s0 + d_c and completes on the
next step (verified on the recorded corpus: a 1-cell leg has n = 2).
  d    = manhattan(p0, exit target). For a completed leg the RECORDED exit_target
         (completions[].exit_target) is used and asserted to be at the nearest-boundary
         distance; for a broken leg the target is recomputed with agents.py's rule
         (exit_target()).
  d_c  = manhattan(p0, completions[].pos) (completed legs only).
  M1a  completed and n > d_c + 5        M1b  completed and n > d + 5
  M1c  (completed and M1a) or broken or (horizon and elapsed > d + 5)
  end  completed: s1. Otherwise the first step s >= s0 whose ff_steps row of F is
       missing or not exiting (broken), or None when F is still exiting at the last row
       (horizon; n = elapsed = steps - s0).
  cause of a broken leg: the unassigns of F stamped at the end step (those naming v
       first, list order): replacement_after_blocked -> "drop",
       firefighter_fire_casualty -> "died_in_custody", geographically_isolated ->
       "isolation_release", anything else or none -> "other". All reasons are kept.
  excess     completed: n - (d_c + 1) (steps beyond the minimum); else None
  path       [(step, cell)] of F over rows s0 .. last carrying row (end-1, or the last
             row at the horizon); cells None are skipped when counting reversals
  reversals  steps back to the cell of two rows earlier (fs_legs.classify's count)
Consistency asserted per leg (ANALYZER DEFECT on violation): the pickup row shows F
exiting at p0 (or dead: a carrier killed on its own pickup step is a broken leg with
end = s0, n = 0, end_cell = p0); a completed leg's first non-exiting row IS its completion
step; no two completions pair with one exit_start. All hold on the 397 recorded runs checked while
this module was written (uh*, ugK*, ug*, f2cEFS/DRY, fmEFS).
"""
from __future__ import annotations

import collections
import json
import os
import re
import shlex
import sys

OUT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(OUT)
if OUT not in sys.path:
    sys.path.insert(0, OUT)

QUAR = "_firemech_rewound_20260914"
H = 360                 # every ff run of the round: --steps 360
PREFIX = 240            # the recorded 240-step references (ugD, ugKD) and the rbgate horizon
GRID = 50               # common_fixed_variables WIDTH = HEIGHT = 50 (asserted per repo)
CUTS = (240, 270, 300, 330, 360)
STALL_MARGIN = 5        # M1: stalled iff n > distance + 5
MAIN_REPO = "E:/Projects/SAS"
BASE_REPO = "E:/Projects/SAS_wt/base6160438"
CTRL11_REPO = "E:/Projects/SAS_wt/base11c3661"
TERMINAL = ("rescued", "dead", "unreachable")

MODE, HOLD, SERVED = "FF_EXIT_LEG_MODE", "FF_EXIT_LEG_HOLD", "FF_EXIT_LEG_SERVED"
SWITCH_KEYS = (MODE, HOLD, SERVED)
EXEMPT_PREFIXES = ("FM2P_", "CLP_")   # not declared in common_fixed_variables (probe keys)

C13 = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("east", "default", s) for s in (101, 202, 303)])
RB7 = [("east", "half", s) for s in (111, 222, 333, 444, 606, 808, 909)]
# rbgate shard -> (wind, seeds string) - the ug round's partition (design 9.1 e)
RB_SHARDS = {"a": ("east", "101,202,303,404,505"), "b": ("east", "606,707,808,909"),
             "c": ("east", "111,222,333,444"), "s": ("south", "101,202,303,404,505")}
SET_NAMES = ("C13", "U30", "N30", "RB7")
G3_SETS = ("C13", "U30", "N30")

# The _uh_analyze P2 lists (per-step series; event lists cut by their step key).
SERIES = ("fire_digests", "victim_steps", "ff_steps", "ff_bind_steps", "uav_steps", "uav_actions",
          "partition_steps")
EVENTS = ("assigns", "unassigns", "completions", "recycles", "firefight_log", "retargets",
          "exit_starts", "unreachable_marks", "planner", "absence_log", "victim_flee_log",
          "victim_lateral_log", "unreachable_escape_log", "victim_holds", "rescue_failed")
EVENTS_KEYED = {"recycle_to_next_assign": "recycle_step"}
DIV_SERIES = ("fire_digests", "ff_steps")                       # spec H2 first divergence
DETAIL_SERIES = ("fire_digests", "ff_steps", "ff_bind_steps", "victim_steps", "uav_steps")

# ---------------------------------------------------------------- the arm table ----
# tag -> dict(instrument, repo, switches (the exact --set dict beyond the common flags,
# FM2P_CRN excluded), kind). kind: "control" | "fix" | "combo" | "probe".
# "combo" arms (clA2/clKA2) carry a subset of ALL3 with >= 2 switches, identical on
# every line of the arm; "probe" arms (spec L) carry CLP_KILL_AT + CLP_KILL_UNIT and
# SERVED 0 or 1 (value per tag).
_OFF = {"FF_FIREFIGHT_EXTINGUISH": 0, "FF_FIREFIGHT_FIREBREAK": 0}
ALL3 = {MODE: 2, HOLD: 1, SERVED: 1}
ARMS = {
    "clB":   dict(instrument="stock", repo=BASE_REPO, switches={}, kind="control"),
    "clC":   dict(instrument="stock", repo=MAIN_REPO, switches={}, kind="control"),
    "clE2":  dict(instrument="stock", repo=MAIN_REPO, switches={MODE: 2}, kind="fix"),
    "clH":   dict(instrument="stock", repo=MAIN_REPO, switches={HOLD: 1}, kind="fix"),
    "clSN":  dict(instrument="stock", repo=MAIN_REPO, switches={SERVED: 1}, kind="fix"),
    "clA":   dict(instrument="stock", repo=MAIN_REPO, switches=dict(ALL3), kind="fix"),
    "clE1":  dict(instrument="stock", repo=MAIN_REPO, switches={MODE: 1}, kind="fix"),
    "clA2":  dict(instrument="stock", repo=MAIN_REPO, switches=None, kind="combo"),
    "clOC":  dict(instrument="stock", repo=MAIN_REPO, switches=dict(_OFF), kind="control"),
    "clOA":  dict(instrument="stock", repo=MAIN_REPO, switches=dict(_OFF, **ALL3), kind="fix"),
    "clKC":  dict(instrument="crn", repo=MAIN_REPO, switches={}, kind="control"),
    "clKE2": dict(instrument="crn", repo=MAIN_REPO, switches={MODE: 2}, kind="fix"),
    "clKH":  dict(instrument="crn", repo=MAIN_REPO, switches={HOLD: 1}, kind="fix"),
    "clKA":  dict(instrument="crn", repo=MAIN_REPO, switches=dict(ALL3), kind="fix"),
    "clKE1": dict(instrument="crn", repo=MAIN_REPO, switches={MODE: 1}, kind="fix"),
    "clKA2": dict(instrument="crn", repo=MAIN_REPO, switches=None, kind="combo"),
    "clPS0": dict(instrument="stock", repo=MAIN_REPO, switches={}, kind="probe"),
    "clPS1": dict(instrument="stock", repo=MAIN_REPO, switches={SERVED: 1}, kind="probe"),
    "clKPS0": dict(instrument="crn", repo=MAIN_REPO, switches={}, kind="probe"),
    "clKPS1": dict(instrument="crn", repo=MAIN_REPO, switches={SERVED: 1}, kind="probe"),
}
# rb shard tag prefixes -> the switches of the arm they gate (tag = prefix + a|b|c|s)
RB_ARMS = {"clGC": {}, "clGE2": {MODE: 2}, "clGH": {HOLD: 1}, "clGSN": {SERVED: 1},
           "clGA": dict(ALL3), "clGE1": {MODE: 1}, "clGA2": None}
# the comparison each arm is judged against (same instrument), and its CRN twin
CONTROL_OF = {"clE2": "clC", "clH": "clC", "clSN": "clC", "clA": "clC", "clE1": "clC",
              "clA2": "clC", "clOA": "clOC", "clKE2": "clKC", "clKH": "clKC", "clKA": "clKC",
              "clKE1": "clKC", "clKA2": "clKC"}
CRN_OF = {"clE2": "clKE2", "clH": "clKH", "clA": "clKA", "clE1": "clKE1", "clA2": "clKA2",
          "clSN": None, "clOA": None}
RB_OF = {"clE2": "clGE2", "clH": "clGH", "clSN": "clGSN", "clA": "clGA", "clE1": "clGE1",
         "clA2": "clGA2", "clOA": None}
GATE_ARMS = ("clE2", "clH", "clSN", "clA", "clE1", "clA2", "clOA")   # GATE block rows, in order
COMBO_TAGS = ("clA2", "clKA2", "clGA2")   # one switch set, cross-checked by RunIndex

# Recorded references (not in any queue; loaded by explicit name, provenance-checked).
REFS = {
    "uhD": dict(repo=MAIN_REPO, sets={"BATCH_SIZE": 360}, steps=360, instrument="stock"),
    "uhC": dict(repo=CTRL11_REPO, sets={"BATCH_SIZE": 360}, steps=360, instrument="stock"),
    "uhY": dict(repo=MAIN_REPO, sets={"BATCH_SIZE": 360, "FF_FIREFIGHT_DRY_RUN": 1}, steps=360,
                instrument="stock"),
    "ugD": dict(repo=MAIN_REPO, sets={}, steps=240, instrument="stock"),
    "ugKD": dict(repo=MAIN_REPO, sets={"FM2P_CRN": 1}, steps=240, instrument="crn"),
}
RB_REFS = {"ugGD"}   # _rblatch_camp2_ugGD{a,b,c,s}_D_<wind>.json, recorded at ba58491


# ------------------------------------------------------------------ failure ----
def refuse(msg):
    """Provenance mismatch: SystemExit (spec A5)."""
    raise SystemExit("REFUSED: " + msg)


def defect(msg):
    """An internal assumption failed on recorded data: SystemExit (spec H2 'analyzer defect')."""
    raise SystemExit("ANALYZER DEFECT - STOP: " + msg)


def _guard(path):
    p = str(path).replace("\\", "/")
    if QUAR in p.split("/"):
        refuse("path inside the quarantine directory: %s" % path)
    return path


def load_json(path):
    """json.load of one explicit file (UTF-8). Refuses a quarantine path or a missing file."""
    _guard(path)
    if not os.path.isfile(path):
        refuse("missing file %s" % path)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except ValueError as exc:
        refuse("%s does not parse as JSON (%s)" % (path, exc))


# ------------------------------------------------------------------ labels ----
def rr(roles):
    return "def" if roles == "default" else roles


def label(tup):
    """(wind, roles, seed) -> 'east/half/101' ('def' for default roles)."""
    return "%s/%s/%d" % (tup[0], rr(tup[1]), tup[2])


def run_stem(tag, tup, outdir=None):
    return os.path.join(outdir or OUT, "_ffr_%s_%s_%s_%d" % (tag, tup[0], rr(tup[1]), tup[2]))


def run_json(tag, tup, outdir=None):
    return _guard(run_stem(tag, tup, outdir) + ".json")


def sidecar_path(tag, tup, outdir=None):
    """<out-without-.json>.clobs.json (spec F)."""
    return _guard(run_stem(tag, tup, outdir) + ".clobs.json")


def rb_json(tag, wind, outdir=None):
    return _guard(os.path.join(outdir or OUT, "_rblatch_camp2_%s_D_%s.json" % (tag, wind)))


# ------------------------------------------------------------------- seeds ----
_SEED_RE = re.compile(r"^(east|south)\|(half|default)\s+seed (\d+)")


def _parse_frozen(fname):
    out = []
    path = _guard(os.path.join(OUT, fname))
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = _SEED_RE.match(line)
            if m:
                out.append((m.group(1), m.group(2), int(m.group(3))))
    if len(out) != 30:
        refuse("%s parses to %d tuples, not 30" % (fname, len(out)))
    return out


def frozen_u30():
    """U30 in frozen order, from outputs/_ug_seeds.txt (the spec regex)."""
    return _parse_frozen("_ug_seeds.txt")


def frozen_n30():
    """N30 in frozen order, from outputs/_cl_seeds.txt (the spec regex); cross-checked with
    _cl_seeds.frozen_n30()."""
    out = _parse_frozen("_cl_seeds.txt")
    import _cl_seeds  # noqa: E402  (pure parse; no listing at import)
    alt = [(c.split("|")[0], c.split("|")[1], s) for c, s in _cl_seeds.frozen_n30()]
    if alt != out:
        refuse("outputs/_cl_seeds.txt: the spec-regex parse and _cl_seeds.frozen_n30() disagree")
    return out


def seed_sets(checked=None):
    """{"C13", "U30", "N30", "RB7"} -> tuples in frozen order.

    checked: the dict returned by _cl_seedcheck.run_checks() ({"U30": [...], "N30": [...]});
    when given it must equal the frozen files' parse. Asserts sizes 13/30/30/7, the
    13 east/half + 13 south/half + 4 east/default composition of U30 and N30, and that no
    tuple (and no U30/N30 seed) is in two sets."""
    sets = collections.OrderedDict()
    sets["C13"] = list(C13)
    sets["U30"] = frozen_u30()
    sets["N30"] = frozen_n30()
    sets["RB7"] = list(RB7)
    if checked is not None:
        for k in ("U30", "N30"):
            if [tuple(t) for t in checked.get(k, [])] != sets[k]:
                refuse("%s from _cl_seedcheck.run_checks() differs from the frozen file" % k)
    comp = [("east", "half")] * 13 + [("south", "half")] * 13 + [("east", "default")] * 4
    for k in ("U30", "N30"):
        if [(w, r) for w, r, _s in sets[k]] != comp:
            refuse("%s composition is not 13 east/half + 13 south/half + 4 east/default" % k)
    seen = {}
    for name, tuples in sets.items():
        for t in tuples:
            if t in seen:
                refuse("tuple %s is in both %s and %s" % (label(t), seen[t], name))
            seen[t] = name
    if {s for _w, _r, s in sets["U30"]} & {s for _w, _r, s in sets["N30"]}:
        refuse("U30 and N30 share a seed")
    return sets


def set_of(tup, sets):
    for name, tuples in sets.items():
        if tuple(tup) in tuples:
            return name
    return None


# ------------------------------------------------------------------- queue ----
def parse_value(raw):
    """The harness's own --set coercion (_dcd4_validate.parse_value, imported)."""
    from _dcd4_validate import parse_value as pv  # noqa: E402
    return pv(raw)


def parse_extra(extra, where=""):
    """Queue 'extra' field -> (sets dict, uav_actions). STRICT: an unknown token, a
    malformed or repeated --set is refused (the pool validator ignores them), and so is
    any shell quoting: the pool expands $extra UNQUOTED (bash word splitting, no quote
    removal), so the harness sees extra.split(); the two must agree for this parse and
    the sidecar argv check (pool_argv) to describe the command that ran."""
    try:
        toks = shlex.split(extra)
    except ValueError as exc:
        refuse("extra field does not tokenize (%s): %s" % (exc, where))
    if toks != extra.split():
        refuse("extra field carries shell quoting or escapes (the pool's unquoted $extra would "
               "pass %r, this parse reads %r): %s" % (extra.split(), toks, where))
    sets, uav, i = {}, False, 0
    while i < len(toks):
        t = toks[i]
        if t == "--set":
            if i + 1 >= len(toks) or "=" not in toks[i + 1]:
                refuse("malformed --set in extra: %s" % where)
            k, v = toks[i + 1].split("=", 1)
            k = k.strip()
            if k in sets:
                refuse("--set %s repeated: %s" % (k, where))
            sets[k] = parse_value(v)
            i += 2
            continue
        if t == "--uav-actions":
            if uav:
                refuse("--uav-actions repeated: %s" % where)
            uav = True
            i += 1
            continue
        refuse("unknown token %r in extra: %s" % (t, where))
    return sets, uav


def read_queue(path):
    """Queue file -> list of line dicts (spec D: kind|tag|repo|wind|roles|seeds|steps|extra).

    ff: {kind, tag, repo, wind, roles, seed, tup, steps, extra, sets, uav_actions, raw,
         queue, lineno}
    rb: {kind, tag, repo, wind, roles, seeds (string), seed_list, steps, extra, sets, raw,
         queue, lineno}
    CR is stripped (Python-written queue files may carry it). Blank and '#' lines skipped."""
    _guard(path)
    if not os.path.isfile(path):
        refuse("queue file missing: %s" % path)
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            ln = raw.replace("\r", "").rstrip("\n")
            if not ln.strip() or ln.startswith("#"):
                continue
            where = "%s:%d" % (os.path.basename(path), n)
            parts = ln.split("|", 7)
            if len(parts) != 8:
                refuse("queue line has %d fields, not 8: %s" % (len(parts), where))
            kind, tag, repo, wind, roles, seeds, steps, extra = parts
            if kind not in ("ff", "rb"):
                refuse("unknown kind %r: %s" % (kind, where))
            if wind not in ("east", "south", "west", "north") or roles not in ("half", "default"):
                refuse("bad wind/roles %r/%r: %s" % (wind, roles, where))
            if not re.match(r"^\d+$", steps):
                refuse("bad steps %r: %s" % (steps, where))
            sets, uav = parse_extra(extra, where)
            rec = dict(kind=kind, tag=tag, repo=repo, wind=wind, roles=roles, steps=int(steps),
                       extra=extra, sets=sets, raw=ln, queue=os.path.basename(path), lineno=n)
            if kind == "ff":
                if not re.match(r"^\d+$", seeds):
                    refuse("ff line seed %r is not one integer: %s" % (seeds, where))
                rec.update(seed=int(seeds), tup=(wind, roles, int(seeds)), uav_actions=uav)
            else:
                if roles != "half":
                    refuse("rb line with roles %r (the campaign is half-only): %s" % (roles, where))
                if uav:
                    refuse("rb line carries --uav-actions: %s" % where)
                if not re.match(r"^\d+(,\d+)*$", seeds):
                    refuse("rb line seeds %r not a comma list: %s" % (seeds, where))
                rec.update(seeds=seeds, seed_list=[int(s) for s in seeds.split(",")])
            out.append(rec)
    return out


STAGE_FILES = {1: ("_cl_s1_queue.txt", "_cl_s1_crn_queue.txt"),
               2: ("_cl_s2_queue.txt", "_cl_s2_crn_queue.txt"),
               3: ("_cl_s3_queue.txt", "_cl_s3_crn_queue.txt")}


def stage_queues(stage, outdir=None):
    """Queue paths of stages 1..stage (cumulative: every later stage is judged against the
    stage-1 controls), stock file first."""
    return [os.path.join(outdir or OUT, f) for s in range(1, stage + 1) for f in STAGE_FILES[s]]


def is_crn_queue(path):
    return "_crn_" in os.path.basename(path)


# -------------------------------------------------------------- provenance ----
def typed_equal(a, b):
    """Equality that also requires equal value TYPES (True != 1, 1 != 1.0), recursively
    over dicts and lists."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return set(a) == set(b) and all(typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b))
    return a == b


def norm_repo(p):
    return os.path.normcase(os.path.abspath(str(p or "")))


_CFV = {}


def cfv_declared(repo):
    """Names declared at column 0 ('^KEY = ...') in <repo>/common_fixed_variables.py.
    Import-free: the file text is parsed. Also asserts WIDTH = HEIGHT = GRID there."""
    key = norm_repo(repo)
    if key not in _CFV:
        path = os.path.join(repo, "common_fixed_variables.py")
        if not os.path.isfile(path):
            refuse("no common_fixed_variables.py at the arm's repo %s" % repo)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        names = set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)[ \t]*=(?!=)", text, re.M))
        for dim in ("WIDTH", "HEIGHT"):
            m = re.search(r"^%s[ \t]*=[ \t]*(\d+)" % dim, text, re.M)
            if not m or int(m.group(1)) != GRID:
                refuse("%s: %s is not %d - the analyzer's GRID constant does not hold" % (path, dim, GRID))
        _CFV[key] = names
    return _CFV[key]


def undeclared(sets, repo):
    """--set keys not declared in the repo's common_fixed_variables (FM2P_*/CLP_* exempt)."""
    names = cfv_declared(repo)
    return sorted(k for k in sets if not k.startswith(EXEMPT_PREFIXES) and k not in names)


def instrument_of(sets):
    return "crn" if "FM2P_CRN" in sets else "stock"


def check_arm_line(line, combos=None):
    """The queue line against the pre-registered arm table (ARMS / RB_ARMS) and the common
    flags. Returns a list of reasons (empty = conforms). combos: dict tag -> switches seen
    on the first line of a combo arm (filled in; every later line must repeat them)."""
    why = []
    s = dict(line["sets"])
    if s.get(SERVED) == 2:
        why.append("FF_EXIT_LEG_SERVED=2 (rung 2 not built, maintainer D-1)")
    for k in SWITCH_KEYS:
        if k in s and s[k] not in {MODE: (0, 1, 2), HOLD: (0, 1), SERVED: (0, 1)}[k]:
            why.append("%s=%r out of range" % (k, s[k]))
        if k in s and type(s[k]) is not int:
            why.append("%s=%r is not an int" % (k, s[k]))
    if line["kind"] == "rb":
        prefix = line["tag"][:-1]
        sfx = line["tag"][-1:]
        if prefix not in RB_ARMS or sfx not in RB_SHARDS:
            return why + ["rb tag %r is not a pre-registered shard (prefix in %s + a|b|c|s)"
                          % (line["tag"], sorted(RB_ARMS))]
        if (line["wind"], line["seeds"]) != RB_SHARDS[sfx]:
            why.append("shard %s is %s %s, the partition says %s %s" % (
                line["tag"], line["wind"], line["seeds"], RB_SHARDS[sfx][0], RB_SHARDS[sfx][1]))
        if line["steps"] != PREFIX:
            why.append("rb steps %d != %d" % (line["steps"], PREFIX))
        if any(k.startswith("FM2P_") for k in s):
            why.append("FM2P_ key on an rb line")
        want = RB_ARMS[prefix]
        if want is None:
            want = _combo_check(prefix, s, combos, why)
        if want is not None and not typed_equal(s, want):
            why.append("rb sets %r != the arm's %r" % (s, want))
        if norm_repo(line["repo"]) != norm_repo(MAIN_REPO):
            why.append("rb repo %r != %s" % (line["repo"], MAIN_REPO))
        return why
    tag = line["tag"]
    if tag not in ARMS:
        return why + ["tag %r is not in the pre-registered arm table (_cl_common.ARMS)" % tag]
    arm = ARMS[tag]
    if line["steps"] != H:
        why.append("steps %d != %d" % (line["steps"], H))
    if not line["uav_actions"]:
        why.append("--uav-actions missing")
    if s.pop("BATCH_SIZE", None) != 360 or type(line["sets"].get("BATCH_SIZE")) is not int:
        why.append("--set BATCH_SIZE=360 missing")
    crn = s.pop("FM2P_CRN", None)
    if arm["instrument"] == "crn":
        if crn != 1 or type(line["sets"].get("FM2P_CRN")) is not int:
            why.append("CRN arm without --set FM2P_CRN=1")
    elif crn is not None:
        why.append("stock arm with FM2P_CRN")
    if any(k.startswith("FM2P_") for k in s):
        why.append("FM2P_ key other than FM2P_CRN: %s" % sorted(k for k in s if k.startswith("FM2P_")))
    if norm_repo(line["repo"]) != norm_repo(arm["repo"]):
        why.append("repo %r != the arm's %s" % (line["repo"], arm["repo"]))
    if arm["kind"] == "probe":
        for k in ("CLP_KILL_AT", "CLP_KILL_UNIT"):
            if k not in s:
                why.append("probe line without %s" % k)
        if type(s.get("CLP_KILL_AT")) is not int:
            why.append("CLP_KILL_AT %r is not an int" % s.get("CLP_KILL_AT"))
        s = {k: v for k, v in s.items() if not k.startswith("CLP_")}
        want = arm["switches"]
    elif arm["kind"] == "combo":
        if any(k.startswith("CLP_") for k in s):
            why.append("CLP_ key on a non-probe line")
        want = _combo_check(tag, s, combos, why)
    else:
        if any(k.startswith("CLP_") for k in s):
            why.append("CLP_ key on a non-probe line")
        want = arm["switches"]
    if want is not None and not typed_equal(s, want):
        why.append("switch sets %r != the arm's %r" % (s, want))
    return why


def _combo_check(tag, s, combos, why):
    if not s or any(k not in ALL3 or s[k] != ALL3[k] for k in s) or len(s) < 2:
        why.append("combination arm %s sets %r: must be >= 2 of %r" % (tag, s, ALL3))
        return None
    if combos is not None:
        first = combos.setdefault(tag, dict(s))
        if not typed_equal(first, s):
            why.append("combination arm %s changes its switches between lines (%r vs %r)" % (tag, first, s))
    return dict(s)


def expected_switches(line):
    """The sidecar 'switches' a line must produce: mode int, hold bool, served int
    (the accessors' return types), 0 where not set."""
    s = line["sets"]
    return {"mode": s.get(MODE, 0), "hold": s.get(HOLD, 0) != 0, "served": s.get(SERVED, 0)}


def pool_argv(line):
    """The harness argv (sys.argv[1:], what the sidecar records) that outputs/_cl_pool.sh
    launch() runs for an ff queue line:
        --repo "$repo" --wind "$w" --roles "$r" --seed "$s" --steps "$steps"
        --out "${OUT_OF[$name]}" --tag "$tag" $extra
    built from the RAW queue fields; the unquoted $extra is bash word splitting
    (extra.split(); parse_extra refuses a line where shlex disagrees). The --out value is
    None here: its directory is the pool's OUTPFX, so check_sidecar compares its basename
    with _ffr_<tag>_<wind>_<rr>_<seed>.json."""
    _kind, tag, repo, wind, roles, seed, steps, extra = line["raw"].split("|", 7)
    return (["--repo", repo, "--wind", wind, "--roles", roles, "--seed", seed, "--steps", steps,
             "--out", None, "--tag", tag] + extra.split())


def _argv_mismatch(argv, want, out_name):
    """First difference between a sidecar argv and pool_argv() (None = equal)."""
    if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
        return "sidecar argv %r is not a list of strings" % (argv,)
    for i in range(max(len(argv), len(want))):
        got = argv[i] if i < len(argv) else "<end>"
        exp = want[i] if i < len(want) else "<end>"
        if exp is None:   # --out: compared by basename
            ok = i < len(argv) and got.replace("\\", "/").rsplit("/", 1)[-1] == out_name
            exp = ".../" + out_name
        else:
            ok = got == exp
        if not ok:
            flag = want[i - 1] if 0 < i <= len(want) else None
            of = (" (the value of %s)" % flag) if isinstance(flag, str) and flag.startswith("--") else ""
            return ("sidecar argv[%d] %r != the pool's %r%s - the recorded command is not the queue "
                    "line's (%d vs %d tokens)" % (i, got, exp, of, len(argv), len(want)))
    return None


def check_sidecar(sc, line, instrument):
    """Reasons the sidecar does not belong to this queue line (empty = OK). spec F/G.
    The recorded argv must be EXACTLY the pool's command for the line (pool_argv): an
    extra launch flag (--scenario, --dim-*, a second --set ...) or an --out of another
    name is refused - none of them reaches extra_params, so the argv is their only record."""
    why = []
    if not isinstance(sc, dict):
        return ["sidecar is not a JSON object"]
    if sc.get("version") != 1:
        why.append("sidecar version %r" % sc.get("version"))
    if sc.get("harness") != instrument:
        why.append("sidecar harness %r != instrument %r" % (sc.get("harness"), instrument))
    if norm_repo(sc.get("repo")) != norm_repo(line["repo"]):
        why.append("sidecar repo %r != line repo %r" % (sc.get("repo"), line["repo"]))
    mm = _argv_mismatch(sc.get("argv"), pool_argv(line),
                        os.path.basename(run_json(line["tag"], line["tup"])))
    if mm:
        why.append(mm)
    sw = sc.get("switches")
    if not isinstance(sw, dict) or set(sw) != {"mode", "hold", "served"}:
        why.append("sidecar switches %r" % (sw,))
    elif norm_repo(line["repo"]) == norm_repo(BASE_REPO):
        # the 6160438 worktree has no accessor: every switch must read ABSENT there
        if any(sw[k] != "ABSENT" for k in sw):
            why.append("base-worktree sidecar switches %r (expected ABSENT x3)" % sw)
    else:
        want = expected_switches(line)
        for k in ("mode", "hold", "served"):
            if not typed_equal(sw[k], want[k]):
                why.append("sidecar switch %s=%r != the line's %r" % (k, sw[k], want[k]))
    cnt = sc.get("counters") or {}
    if cnt.get("model_steps") != line["steps"]:
        why.append("sidecar model_steps %r != %d" % (cnt.get("model_steps"), line["steps"]))
    if cnt.get("models_built") != 1:
        why.append("sidecar models_built %r" % cnt.get("models_built"))
    if cnt.get("observer_errors") != 0:
        why.append("sidecar observer_errors %r" % cnt.get("observer_errors"))
    if cnt.get("hash_repr_addresses", 0) != 0:
        why.append("sidecar hashes carry memory addresses (%r): run-dependent" % cnt.get("hash_repr_addresses"))
    for k in ("transition_log_sha256", "movement_reason_sha256"):
        if not isinstance(sc.get(k), str) or len(sc.get(k)) != 64:
            why.append("sidecar %s missing" % k)
    return why


def _launch_state(d):
    """The harness's own record of launch flags that never reach extra_params: every run of
    the round (and every recorded reference) is scenario "D" (no --scenario) with no
    --dim-* hook ("dim" written, None). Checked on all 133 references (uhD/uhC/uhY/ugKD U30,
    ugD C13) when this was added."""
    why = []
    if d.get("scenario") != "D":
        why.append("scenario=%r, not the pool's default 'D' (a --scenario flag?)" % (d.get("scenario"),))
    if "dim" not in d or d["dim"] is not None:
        why.append("dim=%s: a --dim-* hook was active or the key is missing"
                   % ("<absent>" if "dim" not in d else type(d["dim"]).__name__))
    return why


def check_ff_run(line, d, instrument):
    """Reasons the harness JSON is not this queue line's run (empty = OK). spec H."""
    why = []
    if not isinstance(d, dict):
        return ["run JSON is not an object"]
    for key, want in (("tag", line["tag"]), ("wind", line["wind"]), ("roles", line["roles"]),
                      ("seed", line["seed"]), ("steps", line["steps"])):
        if not typed_equal(d.get(key), want):
            why.append("%s=%r, queue line %r" % (key, d.get(key), want))
    if norm_repo(d.get("repo")) != norm_repo(line["repo"]):
        why.append("repo %r != line repo %r" % (d.get("repo"), line["repo"]))
    why += _launch_state(d)
    if not typed_equal(d.get("extra_params"), line["sets"]):
        why.append("extra_params %r != the line's --set %r (types compared)" % (d.get("extra_params"), line["sets"]))
    params = d.get("params") or {}
    for k, v in line["sets"].items():
        if not typed_equal(params.get(k), v):
            why.append("params[%s]=%r != %r" % (k, params.get(k), v))
    for k in ("fire_digests", "ff_steps", "ff_bind_steps", "victim_steps", "uav_steps"):
        if not isinstance(d.get(k), list) or len(d[k]) != line["steps"]:
            why.append("%s length %s != %d" % (k, len(d[k]) if isinstance(d.get(k), list) else None, line["steps"]))
    if line.get("uav_actions") and (not isinstance(d.get("uav_actions"), list)
                                    or len(d["uav_actions"]) != line["steps"]):
        why.append("uav_actions missing although --uav-actions")
    if not isinstance(d.get("eval"), dict):
        why.append("no eval")
    fm2p_sets = {k: v for k, v in line["sets"].items() if k.startswith("FM2P_")}
    if instrument == "crn":
        cfg = (d.get("fm2p") or {}).get("config") if isinstance(d.get("fm2p"), dict) else None
        if not fm2p_sets or not typed_equal(cfg, fm2p_sets):
            why.append("fm2p.config %r != the line's FM2P keys %r" % (cfg, fm2p_sets))
    else:
        if "fm2p" in d:
            why.append("stock run WITH an fm2p block")
        if fm2p_sets:
            why.append("stock line with FM2P keys %r" % fm2p_sets)
    bad = undeclared(line["sets"], line["repo"])
    if bad:
        why.append("--set keys not declared in %s/common_fixed_variables.py: %s" % (line["repo"], bad))
    return why


def rb_base_keys():
    """The rbgate campaign's own params keys (outputs/_dcd4rb_validate.RB_BASE_KEYS, imported:
    the pool validator's definition, so the two checks cannot drift apart)."""
    from _dcd4rb_validate import RB_BASE_KEYS  # noqa: E402  (no listing at import)
    return frozenset(RB_BASE_KEYS)


def check_rb_run(line, d):
    """Reasons an rbgate shard JSON is not this rb line's (empty = OK). As strict as the pool
    validator (_dcd4rb_validate.rb_check (b)/(c)/(d)): params carry every --set of the line
    with its type, WIND_DIRECTION == the line's wind, and NO key outside the campaign's
    base keys + the line's --set keys (a shard run with a switch the line lacks is refused)."""
    why = []
    if not isinstance(d, dict):
        return ["rb JSON is not an object"]
    for key, want in (("tag", line["tag"]), ("scenario", "D"), ("wind", line["wind"]),
                      ("steps", line["steps"]), ("seeds", line["seeds"])):
        if d.get(key) != want:
            why.append("%s=%r, line %r" % (key, d.get(key), want))
    params = d.get("params")
    if not isinstance(params, dict):
        why.append("no params object")
        params = {}
    if params.get("WIND_DIRECTION") != line["wind"]:
        why.append("params WIND_DIRECTION=%r, line wind %r" % (params.get("WIND_DIRECTION"), line["wind"]))
    for k, v in line["sets"].items():
        if not typed_equal(params.get(k), v):
            why.append("params[%s]=%r != %r" % (k, params.get(k), v))
    stray = set(params) - rb_base_keys() - set(line["sets"])
    if stray:
        why.append("params has keys the line did not set: %s" % sorted(stray))
    evals = d.get("evals")
    if not isinstance(evals, list) or [e.get("seed") for e in evals] != line["seed_list"]:
        why.append("evals seeds != %r" % line["seed_list"])
    return why


def load_ref(tag, tup, outdir=None):
    """A RECORDED reference run (REFS) by explicit name, provenance-checked (refuses on any
    mismatch: repo, extra_params with types, tuple, steps, series lengths, fm2p state)."""
    if tag not in REFS:
        refuse("%s is not a registered reference tag" % tag)
    ref = REFS[tag]
    p = run_json(tag, tup, outdir)
    d = load_json(p)
    why = []
    for key, want in (("tag", tag), ("wind", tup[0]), ("roles", tup[1]), ("seed", tup[2]),
                      ("steps", ref["steps"])):
        if not typed_equal(d.get(key), want):
            why.append("%s=%r want %r" % (key, d.get(key), want))
    if norm_repo(d.get("repo")) != norm_repo(ref["repo"]):
        why.append("repo %r want %s" % (d.get("repo"), ref["repo"]))
    why += _launch_state(d)
    if not typed_equal(d.get("extra_params"), ref["sets"]):
        why.append("extra_params %r want %r" % (d.get("extra_params"), ref["sets"]))
    for k in ("fire_digests", "ff_steps", "victim_steps"):
        if len(d.get(k) or []) != ref["steps"]:
            why.append("%s length %d" % (k, len(d.get(k) or [])))
    if ref["instrument"] == "crn":
        cfg = (d.get("fm2p") or {}).get("config")
        if not typed_equal(cfg, {"FM2P_CRN": 1}):
            why.append("fm2p.config %r" % (cfg,))
    elif "fm2p" in d:
        why.append("stock reference with an fm2p block")
    if why:
        refuse("reference %s %s: %s" % (tag, label(tup), "; ".join(why)))
    return d


def load_rb_ref(tag_prefix, shard, outdir=None):
    """A recorded rbgate shard (_rblatch_camp2_<prefix><shard>_D_<wind>.json)."""
    if tag_prefix not in RB_REFS or shard not in RB_SHARDS:
        refuse("%s%s is not a registered rb reference" % (tag_prefix, shard))
    wind, seeds = RB_SHARDS[shard]
    d = load_json(rb_json(tag_prefix + shard, wind, outdir))
    line = dict(tag=tag_prefix + shard, wind=wind, steps=PREFIX, seeds=seeds,
                seed_list=[int(s) for s in seeds.split(",")], sets={})
    why = check_rb_run(line, d)
    if why:
        refuse("rb reference %s%s: %s" % (tag_prefix, shard, "; ".join(why)))
    return d


_RB_BASE_REF = {}


def rb_base_diff(line, d):
    """Base-value check of a queued rb shard: every campaign base key the line does not
    --set must equal (value and type) the recorded ugGD shard of the same letter (read from
    outputs/, as H1 (e) reads it). Returns reasons (empty = OK)."""
    sfx = line["tag"][-1:]
    if sfx not in _RB_BASE_REF:
        _RB_BASE_REF[sfx] = dict(load_rb_ref("ugGD", sfx).get("params") or {})
    ref = _RB_BASE_REF[sfx]
    params = d.get("params") if isinstance(d.get("params"), dict) else {}
    why = []
    for k in sorted(rb_base_keys() - set(line["sets"])):
        if not typed_equal(params.get(k, "<absent>"), ref.get(k, "<absent>")):
            why.append("params[%s]=%r != ugGD%s's base value %r" % (k, params.get(k, "<absent>"), sfx,
                                                                   ref.get(k, "<absent>")))
    return why


class RunIndex:
    """Every line of the given queue files; runs are loaded on demand, provenance-checked.

    queues   list of queue paths. A file whose name contains "_crn_" must hold only CRN
             lines (FM2P_CRN=1), any other file only stock lines (spec D).
    sets     seed_sets() - every ff tuple must belong to exactly one set.
    outdir   where the run files live (outputs/; a self-test may point elsewhere).

    ff[(tag, tup)] -> line dict (+ "set", "instrument"); rb[tag] -> line dict.
    verify_all() loads every run and sidecar once (full provenance, SystemExit on the
    first mismatch, listing every reason for that run) and every rb shard.
    load(tag, tup) / sidecar(tag, tup): LRU-cached, checked on first load.
    """

    def __init__(self, queues, sets, outdir=None, cache_size=48):
        self.outdir = outdir or OUT
        self.sets = sets
        self.ff = collections.OrderedDict()
        self.rb = collections.OrderedDict()
        self.queues = list(queues)
        self._cache = collections.OrderedDict()
        self._sc = {}
        self._cache_size = cache_size
        self._checked = set()
        combos = {}
        for q in self.queues:
            crn_file = is_crn_queue(q)
            for line in read_queue(q):
                where = "%s:%d" % (line["queue"], line["lineno"])
                why = check_arm_line(line, combos)
                if why:
                    refuse("%s %s: %s" % (where, line["raw"], "; ".join(why)))
                if line["kind"] == "rb":
                    if crn_file:
                        refuse("rb line in a CRN queue: %s" % where)
                    bad = undeclared(line["sets"], line["repo"])
                    if bad:
                        refuse("%s: --set keys not declared in %s/common_fixed_variables.py: %s"
                               % (where, line["repo"], bad))
                    old = self.rb.get(line["tag"])
                    if old is not None and old["raw"] != line["raw"]:
                        refuse("rb shard %s appears twice with different lines (%s)" % (line["tag"], where))
                    self.rb[line["tag"]] = line
                    continue
                inst = instrument_of(line["sets"])
                if inst != ARMS[line["tag"]]["instrument"] or (inst == "crn") != crn_file:
                    refuse("instrument mismatch: %s line in %s (%s)" % (inst, line["queue"], where))
                name = set_of(line["tup"], sets)
                if name is None:
                    refuse("tuple %s is in no frozen set (C13/U30/N30/RB7): %s" % (label(line["tup"]), where))
                line["set"] = name
                line["instrument"] = inst
                key = (line["tag"], line["tup"])
                old = self.ff.get(key)
                if old is not None and old["raw"] != line["raw"]:
                    refuse("%s %s queued twice with different lines (%s, %s:%d)" % (
                        line["tag"], label(line["tup"]), where, old["queue"], old["lineno"]))
                if old is None:
                    self.ff[key] = line
                bad = undeclared(line["sets"], line["repo"])
                if bad:
                    refuse("%s: --set keys not declared in %s/common_fixed_variables.py: %s" % (where, line["repo"], bad))
        # The combination arm is ONE fix set measured three ways (stock clA2, CRN clKA2,
        # rbgate clGA2): each is checked line by line above, and here against each other.
        self.combos = combos
        seen = [(t, combos[t]) for t in COMBO_TAGS if t in combos]
        for t, sw in seen[1:]:
            if not typed_equal(sw, seen[0][1]):
                refuse("combination arms carry different switch sets: %s" % "; ".join(
                    "%s %r" % (x, y) for x, y in seen))

    # --------------------------------------------------------------- queries --
    def tags(self):
        return sorted({t for t, _u in self.ff})

    def has(self, tag, tup):
        return (tag, tuple(tup)) in self.ff

    def tuples(self, tag, set_name=None):
        """Tuples queued for `tag` (in the set's frozen order when set_name is given)."""
        mine = {u for t, u in self.ff if t == tag}
        if set_name is None:
            order = [u for n in SET_NAMES for u in self.sets[n]]
        else:
            order = self.sets[set_name]
        return [u for u in order if u in mine]

    def line(self, tag, tup):
        return self.ff[(tag, tuple(tup))]

    # ---------------------------------------------------------------- loading --
    def _check(self, tag, tup, d, sc):
        line = self.line(tag, tup)
        why = check_ff_run(line, d, line["instrument"])
        why += ["sidecar: " + w for w in check_sidecar(sc, line, line["instrument"])]
        tmp = run_json(tag, tup, self.outdir) + ".fm2p.tmp"
        if os.path.exists(tmp):
            why.append("leftover %s" % os.path.basename(tmp))
        if why:
            refuse("%s %s (%s:%d): %s" % (tag, label(tup), line["queue"], line["lineno"], "; ".join(why)))

    def load(self, tag, tup):
        key = (tag, tuple(tup))
        if key not in self.ff:
            refuse("%s %s is not in the loaded queues" % (tag, label(tup)))
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        d = load_json(run_json(tag, tup, self.outdir))
        if key not in self._checked:
            sc = self.sidecar(tag, tup)
            self._check(tag, tup, d, sc)
            self._checked.add(key)
        self._cache[key] = d
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return d

    def sidecar(self, tag, tup):
        key = (tag, tuple(tup))
        if key not in self._sc:
            self._sc[key] = load_json(sidecar_path(tag, tup, self.outdir))
        return self._sc[key]

    def load_rb(self, tag):
        line = self.rb[tag]
        d = load_json(rb_json(tag, line["wind"], self.outdir))
        why = check_rb_run(line, d) + rb_base_diff(line, d)
        if why:
            refuse("rb shard %s (%s:%d): %s" % (tag, line["queue"], line["lineno"], "; ".join(why)))
        return d

    def verify_all(self):
        """Load and check every queued run, sidecar and rb shard once. Returns counts."""
        for tag, tup in self.ff:
            self.load(tag, tup)
        for tag in self.rb:
            self.load_rb(tag)
        return {"ff": len(self.ff), "rb": len(self.rb)}


# -------------------------------------------------------------------- rows ----
def row_after(d, key, s):
    """The per-step row of series `key` AFTER step s (index s-1), or None out of range."""
    rows = d.get(key) or []
    return rows[s - 1] if 1 <= s <= len(rows) else None


def row_at_start(d, key, s):
    """The row describing the state at the START of step s: row s-2 (= after step s-1).
    None for s == 1 (the initial state is not recorded)."""
    return row_after(d, key, s - 1)


def _entry(row, ident):
    if row is None:
        return None
    for r in row:
        if r[0] == ident:
            return r
    return None


def ff_row(d, s, ff):
    """[ff, pos|None, status, assigned, exiting, dead] of unit ff AFTER step s."""
    return _entry(row_after(d, "ff_steps", s), ff)


def bind_row(d, s, ff):
    """[ff, bound vid|"", available, rescue_completed, off_grid] of unit ff AFTER step s."""
    return _entry(row_after(d, "ff_bind_steps", s), ff)


def victim_row(d, s, vid):
    """[vid, pos|None, status] AFTER step s."""
    return _entry(row_after(d, "victim_steps", s), vid)


def statuses(d, s):
    """{vid: status} AFTER step s."""
    return {v[0]: v[2] for v in (row_after(d, "victim_steps", s) or [])}


def cell(c):
    return None if c is None else (int(c[0]), int(c[1]))


# -------------------------------------------------------------------- fire ----
class Burn:
    """Burning-at-step from burn_intervals: burning(cell, s) is True iff the cell burns in
    the post-step observation of step s (a <= s < b for one of its intervals)."""

    INF = 10 ** 9

    def __init__(self, d):
        bi = d.get("burn_intervals")
        if not isinstance(bi, dict):
            defect("run %s has no burn_intervals" % _runlabel(d))
        self.iv = {}
        for key, lst in bi.items():
            x, y = (int(v) for v in key.split(","))
            self.iv[(x, y)] = [(int(a), int(b) if b is not None else self.INF) for a, b in lst]

    def burning(self, c, s):
        for a, b in self.iv.get(tuple(c), ()):
            if a <= s < b:
                return True
        return False

    def burning_neighbours(self, c, s):
        return [n for n in neighbours(c) if self.burning(n, s)]

    def ever_burning_by(self, c, s):
        return any(a <= s for a, _b in self.iv.get(tuple(c), ()))


def neighbours(c):
    """In-grid 4-neighbours, order +x, -x, +y, -y."""
    x, y = c
    out = []
    for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (x + ox, y + oy)
        if 0 <= n[0] < GRID and 0 <= n[1] < GRID:
            out.append(n)
    return out


def on_boundary(c):
    return c is not None and (c[0] in (0, GRID - 1) or c[1] in (0, GRID - 1))


def edge_dist(c):
    return min(c[0], c[1], GRID - 1 - c[0], GRID - 1 - c[1])


def exit_target(c):
    """agents.py's pickup rule: min over {(0,y): x, (H-1,y): H-1-x, (x,0): y, (x,W-1): W-1-y}
    in that insertion order (ties -> the first)."""
    x, y = c
    dists = {(0, y): x, (GRID - 1, y): GRID - 1 - x, (x, 0): y, (x, GRID - 1): GRID - 1 - y}
    return min(dists, key=dists.get)


def md(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


# -------------------------------------------------------------- divergence ----
def _series(d, key):
    v = d.get(key)
    if not isinstance(v, list):
        defect("run %s has no per-step series %r" % (_runlabel(d), key))
    return v


def first_diff(a, b, keys=DIV_SERIES, upto=None):
    """First step s (1-based) at which any series in `keys` differs between runs a and b,
    over steps 1..min(len, upto); None if identical there. Spec H2's first divergence is
    keys=("fire_digests", "ff_steps")."""
    sa = [_series(a, k) for k in keys]
    sb = [_series(b, k) for k in keys]
    n = min(min(len(x) for x in sa), min(len(x) for x in sb))
    if upto is not None:
        n = min(n, upto)
    for i in range(n):
        for x, y in zip(sa, sb):
            if x[i] != y[i]:
                return i + 1
    return None


def first_diff_detail(a, b, keys=DETAIL_SERIES, upto=None):
    """(first differing step over `keys`, [the keys that differ AT that step]) or (None, [])."""
    s = first_diff(a, b, keys, upto)
    if s is None:
        return None, []
    return s, [k for k in keys if _series(a, k)[s - 1] != _series(b, k)[s - 1]]


def series_equal(a, b, key, s0, s1):
    """Series `key` equal over steps s0..s1 inclusive (clamped to 1..min length)."""
    x, y = _series(a, key), _series(b, key)
    lo = max(1, s0)
    hi = min(s1, len(x), len(y))
    return x[lo - 1:hi] == y[lo - 1:hi]


def fire_identical(a, b, s0, s1):
    """fire_digests equal over steps s0..s1 inclusive."""
    return series_equal(a, b, "fire_digests", s0, s1)


# ---------------------------------------------------------------- outcomes ----
def _escape_by_victim(d, cut):
    out = collections.defaultdict(list)
    for e in d.get("unreachable_escape_log") or []:
        if int(e.get("step", 10 ** 9)) <= cut:
            out[e.get("victim_id")].append(e)
    return out


def ff_deaths(d, cut=None):
    """{ff: first step whose row shows dead} over steps 1..cut (default: all rows)."""
    rows = _series(d, "ff_steps")
    n = len(rows) if cut is None else min(cut, len(rows))
    out = {}
    for i in range(n):
        for r in rows[i]:
            if r[5] and r[0] not in out:
                out[r[0]] = i + 1
    return out


def terminal_step(d, cut=None):
    """First step whose victim_steps row has every victim rescued/dead/unreachable (the
    harness's terminal_step; reproduced on all 397 recorded runs checked), or None by cut."""
    rows = _series(d, "victim_steps")
    n = len(rows) if cut is None else min(cut, len(rows))
    for i in range(n):
        if rows[i] and all(v[2] in TERMINAL for v in rows[i]):
            return i + 1
    return None


def cut_outcomes(d, cut):
    """Spec H6 at step `cut`, from victim_steps / ff_steps / unreachable_escape_log only:
      rescued, dead, unreachable (status counts at the cut); unreachable split by the
      victim's LATEST escape-log cause with step <= cut into geographically_isolated /
      never_detected_status / unreachable_other; never_detected = distinct victims with an
      escape-log entry cause never_detected, step <= cut (the spec's literal definition; it
      also counts a victim marked never_detected who later died - eval does not);
      candidate = victims not rescued/dead/unreachable (non-terminal; never read as
      "undetected"); ff_deaths = units dead in the row at the cut; terminal_step (<= cut
      or None); all_terminal = candidate == 0."""
    if cut > len(_series(d, "victim_steps")):
        defect("run %s has %d steps, cut %d" % (_runlabel(d), len(d["victim_steps"]), cut))
    st = statuses(d, cut)
    esc = _escape_by_victim(d, cut)
    c = collections.Counter(st.values())
    geo = nds = oth = 0
    for vid, s in st.items():
        if s != "unreachable":
            continue
        cause = esc[vid][-1].get("cause") if esc.get(vid) else None
        if cause == "geographically_isolated":
            geo += 1
        elif cause == "never_detected":
            nds += 1
        else:
            oth += 1
    nd = sum(1 for vid, es in esc.items() if any(e.get("cause") == "never_detected" for e in es))
    cand = sum(1 for s in st.values() if s not in TERMINAL)
    return {"victims": len(st), "rescued": c["rescued"], "dead": c["dead"], "unreachable": c["unreachable"],
            "geographically_isolated": geo, "never_detected_status": nds, "unreachable_other": oth,
            "never_detected": nd, "candidate": cand,
            "ff_deaths": sum(1 for r in row_after(d, "ff_steps", cut) or [] if r[5]),
            "terminal_step": terminal_step(d, cut), "all_terminal": cand == 0}


def eval_crosscheck(d):
    """At the run's last step: cut_outcomes vs the recorded eval (spec H6 cross-check).
    Returns [(field, from rows, from eval)] for every disagreement.

    eval counts a victim's CURRENT status (managed_victims), so its never_detected is
    compared with never_detected_status (unreachable now, latest escape-log cause
    never_detected), not with the literal log count: a victim marked never_detected and
    later dead is in the literal count only (seen in recorded bs*/dc*/df* east/half/404).
    Checked on 2471 recorded runs: the only other disagreements are the six vmon/vmon2
    files of the retired victim-monitor harness."""
    n = len(_series(d, "victim_steps"))
    o = cut_outcomes(d, n)
    ev = d.get("eval") or {}
    pairs = (("rescued", o["rescued"], ev.get("rescued")), ("dead", o["dead"], ev.get("dead")),
             ("unreachable", o["unreachable"], ev.get("unreachable")),
             ("candidate", o["candidate"], ev.get("candidate")),
             ("geographically_isolated", o["geographically_isolated"], ev.get("geographically_isolated")),
             ("never_detected (status)", o["never_detected_status"], ev.get("never_detected")),
             ("unreachable_other+horizon_unresolved", o["unreachable_other"],
              (ev.get("unreachable_other") or 0) + (ev.get("horizon_unresolved") or 0)),
             ("firefighter_deaths", o["ff_deaths"], ev.get("firefighter_deaths")),
             ("terminal_step", o["terminal_step"], d.get("terminal_step")),
             ("all_terminal", o["all_terminal"], ev.get("all_terminal")))
    return [(k, a, b) for k, a, b in pairs if a != b]


def completions_of(d, vid=None, ff=None):
    return [c for c in d.get("completions") or []
            if (vid is None or c.get("victim") == vid) and (ff is None or c.get("ff") == ff)]


def victim_fate(d, vid, cut=None):
    """Fate of one victim at `cut` (default: last step):
    {"status", "step", "cause", "completion"}; step = the completion step for a rescue
    (<= cut), else the first step of the final run of rows with that status (dead: the
    first dead row); cause = the latest escape-log cause (<= cut) for unreachable;
    step None for a non-terminal status."""
    rows = _series(d, "victim_steps")
    cut = len(rows) if cut is None else cut
    st = statuses(d, cut).get(vid)
    if st is None:
        defect("victim %s absent from %s at step %d" % (vid, _runlabel(d), cut))
    comp = [c["step"] for c in completions_of(d, vid) if c["step"] <= cut]
    step = None
    if st in TERMINAL:
        s = cut
        while s >= 1 and statuses(d, s).get(vid) == st:
            s -= 1
        step = s + 1
        if st == "rescued" and comp:
            step = comp[-1]
    cause = None
    if st == "unreachable":
        es = _escape_by_victim(d, cut).get(vid)
        cause = es[-1].get("cause") if es else "unspecified"
    return {"status": st, "step": step, "cause": cause, "completion": comp[-1] if comp else None}


def fate_str(f):
    s = f["status"].upper()
    if f["cause"]:
        s += "(%s)" % f["cause"]
    return s + ("@%d" % f["step"] if f["step"] is not None else "")


# -------------------------------------------------------------------- legs ----
def _runlabel(d):
    try:
        return "%s %s/%s/%s" % (d.get("tag"), d.get("wind"), rr(d.get("roles")), d.get("seed"))
    except Exception:  # noqa: BLE001
        return "?"


def unassigns_at(d, s, ff=None, vid=None):
    return [u for u in d.get("unassigns") or []
            if int(u.get("step", -1)) == s and (ff is None or u.get("ff") == ff)
            and (vid is None or u.get("vid") == vid)]


CAUSE_OF_REASON = {"replacement_after_blocked": "drop",
                   "firefighter_fire_casualty": "died_in_custody",
                   "geographically_isolated": "isolation_release"}


def end_cause(d, ff, vid, s):
    """(cause, [all unassign reasons of ff at s]) for a carry of vid by ff ending at s."""
    us = unassigns_at(d, s, ff=ff)
    reasons = [u.get("reason") for u in us]
    mine = [u for u in us if u.get("vid") == vid] or us
    if not mine:
        return "other", reasons
    return CAUSE_OF_REASON.get(mine[0].get("reason"), "other"), reasons


def legs(d):
    """Every carrying leg of the run (see the module docstring, LEGS). Returns a list of
    dicts in exit_starts order:
      ff, victim, s0, p0 (tuple), next_start (step of the victim's next exit_start | None),
      completed (bool), end (step | None at the horizon), end_cell, n, d, d_c (None unless
      completed), exit_target (tuple), cause ("completed" | "drop" | "died_in_custody" |
      "isolation_release" | "other" | "horizon"), reasons (unassign reasons at the end
      step), dead_at_end, m1a, m1b, m1c, excess, path [(step, cell|None)], reversals."""
    steps = len(_series(d, "ff_steps"))
    starts = d.get("exit_starts") or []
    comps = d.get("completions") or []
    out = []
    seen = set()
    for i, e in enumerate(starts):
        ff, vid, s0 = e.get("ff"), e.get("victim"), int(e["step"])
        p0 = cell(e.get("ff_pos"))
        if p0 is None:
            defect("%s exit_start %r has no ff_pos" % (_runlabel(d), e))
        key = (ff, vid, s0, p0)
        if key in seen:
            defect("%s duplicate exit_start %r" % (_runlabel(d), e))
        seen.add(key)
        r0 = ff_row(d, s0, ff)
        died_on_pickup = bool(r0 is not None and r0[5] and not r0[4])
        if r0 is None or (not died_on_pickup and (not r0[4] or cell(r0[1]) != p0)):
            defect("%s exit_start %r but the row after step %d is %r" % (_runlabel(d), e, s0, r0))
        nxt = next((int(x["step"]) for x in starts[i + 1:] if x.get("victim") == vid), None)
        cs = [c for c in comps if c.get("ff") == ff and c.get("victim") == vid
              and s0 <= int(c["step"]) and (nxt is None or int(c["step"]) < nxt)]
        if len(cs) > 1:
            defect("%s exit_start %r pairs with %d completions" % (_runlabel(d), e, len(cs)))
        first_off = None
        for s in range(s0, steps + 1):
            r = ff_row(d, s, ff)
            if r is None or not r[4]:
                first_off = s
                break
        dd = edge_dist(p0)
        leg = dict(ff=ff, victim=vid, s0=s0, p0=p0, next_start=nxt, d=dd, d_c=None, excess=None,
                   reasons=[], dead_at_end=False)
        if cs:
            c = cs[0]
            s1 = int(c["step"])
            if first_off != s1:
                defect("%s leg %s/%s@%d completed at %d but its first non-exiting row is %r" % (
                    _runlabel(d), ff, vid, s0, s1, first_off))
            et = cell(c.get("exit_target"))
            if et is None or md(p0, et) != dd:
                defect("%s leg %s/%s@%d: recorded exit_target %r is not at the nearest-boundary "
                       "distance %d" % (_runlabel(d), ff, vid, s0, et, dd))
            leg.update(completed=True, end=s1, end_cell=cell(c.get("pos")), n=s1 - s0,
                       d_c=md(p0, cell(c.get("pos"))), exit_target=et, cause="completed")
            leg["excess"] = leg["n"] - (leg["d_c"] + 1)
            last_row = s1 - 1
        elif first_off is None:
            leg.update(completed=False, end=None, end_cell=cell(ff_row(d, steps, ff)[1]),
                       n=steps - s0, exit_target=exit_target(p0), cause="horizon")
            last_row = steps
        else:
            cause, reasons = end_cause(d, ff, vid, first_off)
            rend = ff_row(d, first_off, ff)
            prev = ff_row(d, first_off - 1, ff) if first_off > s0 else None
            leg.update(completed=False, end=first_off, end_cell=cell(prev[1]) if prev else p0,
                       n=first_off - s0, exit_target=exit_target(p0), cause=cause, reasons=reasons,
                       dead_at_end=bool(rend and rend[5]))
            last_row = first_off - 1
        path = [(s, cell(ff_row(d, s, ff)[1]) if ff_row(d, s, ff) else None)
                for s in range(s0, max(s0, last_row) + 1)]
        cells = [c for _s, c in path if c is not None]
        leg["path"] = path
        leg["reversals"] = sum(1 for k in range(2, len(cells))
                               if cells[k] == cells[k - 2] and cells[k] != cells[k - 1])
        leg["m1a"] = bool(leg["completed"] and leg["n"] > leg["d_c"] + STALL_MARGIN)
        leg["m1b"] = bool(leg["completed"] and leg["n"] > dd + STALL_MARGIN)
        leg["m1c"] = bool(leg["m1a"] or (not leg["completed"] and leg["cause"] != "horizon")
                          or (leg["cause"] == "horizon" and leg["n"] > dd + STALL_MARGIN))
        out.append(leg)
    return out


def leg_key(leg):
    """The spec's matching key: (unit, victim, pickup step, pickup cell)."""
    return (leg["ff"], leg["victim"], leg["s0"], leg["p0"])


def match_legs(ctrl_legs, arm_legs):
    """-> (pairs [(ctrl_leg, arm_leg)], ctrl_only [leg], arm_only [leg]) on leg_key."""
    ak = {leg_key(x): x for x in arm_legs}
    ck = {leg_key(x) for x in ctrl_legs}
    pairs = [(c, ak[leg_key(c)]) for c in ctrl_legs if leg_key(c) in ak]
    return (pairs, [c for c in ctrl_legs if leg_key(c) not in ak],
            [a for a in arm_legs if leg_key(a) not in ck])


def compare_legs(c, a):
    """A matched pair (clC leg c, arm leg a) -> (verdict, kind):
      ("CONVERSION", "<c cause>->completed")  c not completed, a completed (excluded from LONGER)
      ("LONGER", "completed-><a cause>")      c completed, a not (broken or horizon)
      ("LONGER", "n") / ("SHORTER", "n") / ("EQUAL", "n")      both completed, by n
      ("LONGER"|"SHORTER"|"EQUAL", "unfinished")               neither completed, by n
    (spec H2: arm n <= clC n, else LONGER; completed in clC and broken in the arm = LONGER)."""
    if not c["completed"] and a["completed"]:
        return "CONVERSION", "%s->completed" % c["cause"]
    if c["completed"] and not a["completed"]:
        return "LONGER", "completed->%s" % a["cause"]
    kind = "n" if c["completed"] else "unfinished"
    if a["n"] > c["n"]:
        return "LONGER", kind
    if a["n"] < c["n"]:
        return "SHORTER", kind
    return "EQUAL", kind


def leg_str(leg):
    if leg["completed"]:
        end = "completed@%d n=%d d=%d d_c=%d" % (leg["end"], leg["n"], leg["d"], leg["d_c"])
    elif leg["cause"] == "horizon":
        end = "horizon elapsed=%d d=%d" % (leg["n"], leg["d"])
    else:
        end = "%s@%d n=%d d=%d%s" % (leg["cause"], leg["end"], leg["n"], leg["d"],
                                     " (carrier dead)" if leg["dead_at_end"] else "")
    return "%s %s pickup %d@%s %s" % (leg["ff"], leg["victim"], leg["s0"], list(leg["p0"]), end)


# ---------------------------------------------------------------- identity ----
def diff_keys(a, b, exclude):
    """Top-level keys (union) whose values differ, excluding `exclude` (sorted)."""
    keys = (set(a) | set(b)) - set(exclude)
    return sorted(k for k in keys if a.get(k, "<absent>") != b.get(k, "<absent>"))


def _cut_recycle_gaps(entries, cut):
    """recycle_to_next_assign entries with recycle_step <= cut, as a run STOPPED at `cut`
    would have recorded them: a next assign after the cut did not exist there (the one
    derived field of the event lists; the harness computes it after the run)."""
    out = []
    for e in entries:
        if e.get("recycle_step") is None or e["recycle_step"] > cut:
            continue
        e = dict(e)
        if e.get("next_assign_step") is not None and e["next_assign_step"] > cut:
            e["next_assign_step"] = None
            e["gap"] = None
        out.append(e)
    return out


def prefix_diff(long_d, short_d, cut=PREFIX):
    """The _uh_analyze P2 method: every per-step SERIES [:cut] equal, and every EVENTS list
    of the long run cut at step <= cut equal to the short run's list (EVENTS_KEYED by its
    own step key; recycle_to_next_assign's derived next-assign fields cut too). The short
    run must have exactly `cut` rows. Returns (diffs [str], skipped [event list names whose
    entries carry no step and were not compared])."""
    diffs, skipped = [], []
    for k in SERIES:
        a, b = long_d.get(k), short_d.get(k)
        if a is None and b is None:
            continue
        if not isinstance(a, list) or not isinstance(b, list):
            diffs.append("%s (type)" % k)
            continue
        if len(b) != cut or len(a) < cut:
            diffs.append("%s (lengths %d / %d)" % (k, len(a), len(b)))
        elif a[:cut] != b:
            first = next(i + 1 for i, (x, y) in enumerate(zip(a[:cut], b)) if x != y)
            diffs.append("%s (first differs at step %d)" % (k, first))
    for k in EVENTS + tuple(EVENTS_KEYED):
        key = EVENTS_KEYED.get(k, "step")
        la, lb = long_d.get(k), short_d.get(k)
        if not isinstance(la, list) or not isinstance(lb, list):
            if (la is None) != (lb is None):
                diffs.append("%s (present in one run only)" % k)
            continue
        if any(not isinstance(e, dict) or e.get(key) is None for e in la + lb):
            skipped.append(k)
            continue
        if k == "recycle_to_next_assign":
            a = _cut_recycle_gaps(la, cut)
        else:
            a = [e for e in la if e[key] <= cut]
        if a != lb:
            diffs.append("%s (%d vs %d events <= %d)" % (k, len(a), len(lb), cut))
    return diffs, skipped


def rb_diff(a, b):
    """rbgate shard identity (spec H1 e): every top-level key except tag equal, and the
    evals equal element by element after dropping wall_s. Returns diffs [str]."""
    diffs = [k for k in diff_keys(a, b, ("tag", "evals"))]
    ea, eb = a.get("evals") or [], b.get("evals") or []
    if len(ea) != len(eb):
        diffs.append("evals (%d vs %d)" % (len(ea), len(eb)))
    else:
        for x, y in zip(ea, eb):
            x = {k: v for k, v in x.items() if k != "wall_s"}
            y = {k: v for k, v in y.items() if k != "wall_s"}
            if x != y:
                diffs.append("evals seed %s (%s)" % (x.get("seed"), ", ".join(diff_keys(x, y, ()))))
    return diffs


def rb_evals_equal(a, b):
    """Count of evals equal after dropping wall_s (for the 18/18 tally)."""
    ea, eb = a.get("evals") or [], b.get("evals") or []
    if len(ea) != len(eb):
        return 0
    return sum(1 for x, y in zip(ea, eb)
               if {k: v for k, v in x.items() if k != "wall_s"} == {k: v for k, v in y.items() if k != "wall_s"})
