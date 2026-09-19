"""firemech round 2, Part 1: PROBE-ARM ANALYZER. Read-only; runs no simulation.

usage:
  _fm2_analyze.py [--sample canonical|fresh|both] [--arms f2GD,f2GW,...] [--out FILE]
  _fm2_analyze.py --self-test [--out FILE]

DATA. Explicit paths only: outputs/_ffr_<tag>_<wind>_<rr>_<seed>.json, rr half|def.
No glob of any kind; outputs/_firemech_rewound_20260914/ is never touched.
A run is READ only if it is complete:
  - the .json exists, and neither <json>.tmp (harness write) nor <json>.fm2p.tmp
    (probe-record rewrite) exists
  - outputs/_ffr_logs/<tag>_<wind>_<rr>_<seed>.out exists and contains "seed="
    (the harness prints that line last; the pool's stdout is flushed at exit)
  - if its queue line sets any FM2P_* key: the JSON carries the "fm2p" record
    (the wrapper adds it AFTER the harness wrote the file)
  - the JSON parses
Otherwise it is PENDING (counted, never read as zero). A complete run whose
tag/wind/roles/seed, 240-step series, or queue --set values disagree with its
file name / queue line is INVALID: excluded and listed.

ARMS AND REFERENCES (outputs/_fm2_queue.py; expected coverage from
outputs/_fm2probe_queue.txt, cross-checked against _fm2_queue.ARMS)
  f2IDD  == fmDRY value for value (identity; canonical only)
  f2U0D f2U1D f2L3D f2L8D f2GD   vs fmOFF and fmDRY   (DRY: fire == fmOFF 240/240)
  f2GW   vs fmOFF and fmEFS     f2GF   vs fmOFF and fmF   (gate arms, wet)
  f2cES  f2cF  vs f2cOFF        (CRN fire; compared with CRN arms only)

DEFINITIONS - imported, not re-implemented: outputs/_firemech_analyze.py
run_summary() gives rescued/dead/ffd/never_detected/terminal, ever/cleared/intact/
burning@240, first write, engaged rows, the death classification (engaged / prev /
streak / preempted / after_terminal / enclosure) and E1/E2 through
_dcd4_analyze.summarize. Added here:
  final victim status  last victim_steps row, per victim id; a FLIP is a victim
                       whose final status differs from the reference's
  intact direction     per run, arm intact - reference intact: up / down / unchanged
  engaged before/after engaged log rows with step <= terminal_step / > terminal_step;
                       rows of runs with terminal_step None are "nonterm"
                       (after == _firemech_analyze's after_term)
  first row            first firefight_log row step (any unit; for a gate arm the
                       first advance with the gate open and a context to act on)
  fm2p counters        fm2p.counters of the probe record (0 when absent)
IDENTITY (f2IDD vs fmDRY): deep equality of every JSON field except tag, repo,
  wall_s. json.load gives dicts, and dict equality ignores key order, so
  burn_intervals / first_burn_step / fire_ground_final compare as VALUES
  (key-order differences are counted separately, informationally). For a
  differing list the first differing index is reported as a step: index+1 for
  a 240-entry per-step series, the element's "step" for event lists.
BY-CONSTRUCTION CHECKS
  gate (f2GD f2GW f2GF)  eval rescued and dead == fmOFF on every run; ff_steps ==
                         fmOFF for every step s < first row (ff_steps[i] is the
                         state after step i+1, so indices 0..first_row-2); a run
                         with no row compares all 240
  CRN (f2cES f2cF)       fire_digests == f2cOFF for steps < first write step, and
                         differ AT it; a run with no write == 240/240
  DRY (f2U0D f2U1D f2L3D f2L8D f2GD, f2IDD)  fire_digests == fmOFF 240/240
DE-DUPLICATION: east/def and east/half with the same seed share the OFF fire, so
the de-duplicated view excludes east/def tuples.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _firemech_analyze as FA  # noqa: E402  (definitions; its main() is not run)
import _dcd4_analyze as AN  # noqa: E402

STEPS = 240
CANONICAL = list(FA.CANONICAL)
FRESH = list(FA.FRESH)
QUEUE_TXT = os.path.join(HERE, "_fm2probe_queue.txt")
EXCLUDE_ID = ("tag", "repo", "wall_s")
PER_STEP = ("fire_digests", "ff_steps", "ff_bind_steps", "victim_steps", "uav_steps",
            "uav_actions", "partition_steps")
FM2P_COUNTERS = ("leash_dropped", "gate_closed_calls", "engage_only_blocked_calls",
                 "dry_forced_calls", "crn_draws")

# name -> (refs, kind, description)
ARM_SPECS = collections.OrderedDict([
    ("f2IDD", (["fmDRY"], "identity", "fmDRY through the probe wrapper, no FM2P key")),
    ("f2U0D", (["fmOFF", "fmDRY"], "dry", "fmDRY, only ff_unit_0 may engage")),
    ("f2U1D", (["fmOFF", "fmDRY"], "dry", "fmDRY, only ff_unit_1 may engage")),
    ("f2L3D", (["fmOFF", "fmDRY"], "dry", "fmDRY, commitment limit 3")),
    ("f2L8D", (["fmOFF", "fmDRY"], "dry", "fmDRY, commitment limit 8")),
    ("f2GD", (["fmOFF", "fmDRY"], "gate_dry", "fmDRY, engage only when no victim unresolved")),
    ("f2GW", (["fmOFF", "fmEFS"], "gate", "fmEFS + the gate (fire writes on)")),
    ("f2GF", (["fmOFF", "fmF"], "gate", "fmF + the gate (firebreak only)")),
    ("f2cOFF", ([], "crn_control", "feature off, CRN fire")),
    ("f2cES", (["f2cOFF"], "crn", "E + S, CRN fire")),
    ("f2cF", (["f2cOFF"], "crn", "F, CRN fire")),
])

OUT = []


def say(*a):
    line = " ".join(str(x) for x in a)
    OUT.append(line)
    print(line)


def label(t):
    return FA.label(t)


def rr_of(t):
    return "def" if t[1] == "default" else t[1]


def run_name(tag, t):
    return "%s_%s_%s_%d" % (tag, t[0], rr_of(t), t[2])


def json_path(tag, t):
    return os.path.join(HERE, "_ffr_%s.json" % run_name(tag, t))


def log_path(tag, t):
    return os.path.join(HERE, "_ffr_logs", "%s.out" % run_name(tag, t))


# ------------------------------------------------------------------ queue ------
def read_queue():
    """{(tag, tuple): {"sets": {K: V}}} from _fm2probe_queue.txt (LF or CRLF)."""
    q = collections.OrderedDict()
    if not os.path.exists(QUEUE_TXT):
        return q
    with open(QUEUE_TXT, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip("\r\n").strip()
            if not line:
                continue
            tag, _repo, wind, roles, seed, extra = line.split("|", 5)
            sets = dict(m.split("=", 1) for m in re.findall(r"--set\s+(\S+)", extra))
            q[(tag, (wind, roles, int(seed)))] = {"sets": sets}
    return q


def queue_crosscheck(q):
    """Compare the queue text with _fm2_queue.py's declared arms; list mismatches."""
    try:
        import _fm2_queue as QM
    except Exception as exc:  # pragma: no cover
        return ["_fm2_queue import failed: %r" % (exc,)]
    want = collections.OrderedDict()
    for tag in QM.CANONICAL_ARMS:
        for w, r, s in QM.CANONICAL:
            want[(tag, (w, r, s))] = True
    for tag in QM.FRESH_ARMS:
        for w, r, s in QM.FRESH:
            want[(tag, (w, r, s))] = True
    problems = []
    if set(want) != set(q):
        problems.append("queue text vs _fm2_queue.py: %d only in text, %d only in module" % (
            len(set(q) - set(want)), len(set(want) - set(q))))
    for (tag, t), v in q.items():
        exp = dict(m.split("=", 1) for m in re.findall(r"--set\s+(\S+)", " ".join(QM.ARMS.get(tag, []))))
        if exp != v["sets"]:
            problems.append("%s %s: --set differs from _fm2_queue.ARMS" % (tag, label(t)))
    return problems


# ------------------------------------------------------------------ loading ----
def _same_value(recorded, queued):
    """A recorded --set value equals its queue text (the harness parses int/float/bool)."""
    if str(recorded) == queued:
        return True
    try:
        return float(recorded) == float(queued)
    except (TypeError, ValueError):
        return False


def run_status(tag, t, queue):
    """('complete', data) | ('pending', why) | ('invalid', why). Loads one JSON."""
    p = json_path(tag, t)
    if not os.path.exists(p):
        return "pending", "no json"
    for suffix in (".tmp", ".fm2p.tmp"):
        if os.path.exists(p + suffix):
            return "pending", "%s present" % suffix
    lp = log_path(tag, t)
    if not os.path.exists(lp):
        return "pending", "no log"
    with open(lp, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-16", "replace") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", "replace")
    if "seed=" not in text:
        return "pending", "log has no seed= line"
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except (ValueError, OSError) as exc:
        return "pending", "json unreadable (%s)" % type(exc).__name__
    qline = queue.get((tag, t))
    fm2p_keys = {k: v for k, v in (qline or {}).get("sets", {}).items() if k.startswith("FM2P_")}
    if fm2p_keys and "fm2p" not in d:
        return "pending", "fm2p record not yet written"
    why = []
    if d.get("tag") != tag:
        why.append("tag %r" % d.get("tag"))
    if d.get("wind") != t[0] or d.get("roles") != t[1] or int(d.get("seed", -1)) != t[2]:
        why.append("wind/roles/seed %r/%r/%r" % (d.get("wind"), d.get("roles"), d.get("seed")))
    for k in ("fire_digests", "ff_steps", "victim_steps"):
        if len(d.get(k) or []) != STEPS:
            why.append("%s has %d entries" % (k, len(d.get(k) or [])))
    if not isinstance(d.get("eval"), dict):
        why.append("no eval")
    if qline is not None:
        ep = d.get("extra_params") or {}
        for k, v in qline["sets"].items():
            if not _same_value(ep.get(k), v):
                why.append("extra_params[%s]=%r, queue %s" % (k, ep.get(k), v))
        if fm2p_keys:
            cfg = (d.get("fm2p") or {}).get("config") or {}
            for k, v in fm2p_keys.items():
                if not _same_value(cfg.get(k), v):
                    why.append("fm2p.config[%s]=%r, queue %s" % (k, cfg.get(k), v))
        elif "fm2p" in d:
            why.append("fm2p record present but the queue line sets no FM2P key")
    if why:
        return "invalid", "; ".join(why)
    return "complete", d


def reduce_run(d):
    """Small per-run record; the JSON itself is dropped by the caller."""
    S = FA.run_summary(d, None)
    R = {k: S[k] for k in ("rescued", "dead", "ffd", "nd", "unreach", "burnt", "terminal", "ever",
                           "cleared", "intact", "burning240", "first_write", "ext", "clear", "engaged",
                           "after_term", "rows", "deaths", "e1n", "e1d", "e2n", "e2d")}
    term = R["terminal"]
    log = d.get("firefight_log") or []
    eng = [r for r in log if r.get("engaged")]
    R["eng_before"] = sum(1 for r in eng if term is not None and r["step"] <= term)
    R["eng_after"] = sum(1 for r in eng if term is not None and r["step"] > term)
    R["eng_nonterm"] = sum(1 for r in eng if term is None)
    R["first_row"] = min((r["step"] for r in log), default=None)
    R["first_engaged"] = min((r["step"] for r in eng), default=None)
    R["victims"] = {str(v[0]): v[2] for v in (d.get("victim_steps") or [[]])[-1]}
    R["digests"] = list(d.get("fire_digests") or [])
    R["ff_steps"] = [json.dumps(row, sort_keys=True) for row in (d.get("ff_steps") or [])]
    fm = d.get("fm2p") or {}
    R["fm2p"] = {k: int((fm.get("counters") or {}).get(k) or 0) for k in FM2P_COUNTERS}
    R["fm2p_present"] = "fm2p" in d
    R["fm2p_events"] = len(fm.get("events") or [])
    return R


class Store:
    """Reduced records, one JSON in memory at a time."""

    def __init__(self, queue):
        self.queue = queue
        self.rec = {}
        self.status = {}

    def get(self, tag, t):
        key = (tag, tuple(t))
        if key not in self.status:
            st, payload = run_status(tag, t, self.queue)
            self.status[key] = (st, payload if st != "complete" else "")
            if st == "complete":
                self.rec[key] = reduce_run(payload)
            del payload
        return self.rec.get(key)

    def st(self, tag, t):
        self.get(tag, t)
        return self.status[(tag, tuple(t))]


def expected_tuples(tag, tuples, queue, selftest=False):
    if selftest or tag not in ARM_SPECS:
        return list(tuples)
    return [t for t in tuples if (tag, t) in queue]


# ------------------------------------------------------------------ aggregate --
SUM_KEYS = ("rescued", "dead", "ffd", "nd", "unreach", "burnt", "ever", "cleared", "intact", "burning240",
            "e1n", "e1d", "e2n", "e2d", "engaged", "eng_before", "eng_after", "eng_nonterm", "after_term",
            "ext", "clear", "rows")


def agg(recs):
    A = collections.OrderedDict()
    A["runs"] = len(recs)
    for k in SUM_KEYS:
        A[k] = sum(r[k] for r in recs)
    terms = [r["terminal"] for r in recs if r["terminal"] is not None]
    A["nonterm"] = len(recs) - len(terms)
    A["mean_term"] = (sum(terms) / len(terms)) if terms else None
    D = [x for r in recs for x in r["deaths"]]
    A["deaths"] = len(D)
    A["d_engaged"] = sum(1 for x in D if x["engaged"])
    A["d_prev"] = sum(1 for x in D if x["engaged_prev"])
    A["d_streak"] = sum(1 for x in D if x["streak_engaged"])
    A["d_preempted"] = sum(1 for x in D if x["preempted"])
    A["d_after_terminal"] = sum(1 for x in D if x["after_terminal"])
    A["d_full"] = sum(1 for x in D if x["enclosure"] == "full")
    A["d_free"] = sum(1 for x in D if x["enclosure"] != "full")
    A["write_runs"] = sum(1 for r in recs if r["first_write"] is not None)
    for c in FM2P_COUNTERS:
        A["fm2p_" + c] = sum(r["fm2p"][c] for r in recs)
    return A


def flips(ra, rb):
    """[(victim, ref_status, arm_status)] for victims whose final status differs."""
    ids = sorted(set(ra["victims"]) | set(rb["victims"]))
    return [(v, rb["victims"].get(v), ra["victims"].get(v)) for v in ids
            if ra["victims"].get(v) != rb["victims"].get(v)]


def direction(ra, rb):
    d = ra["intact"] - rb["intact"]
    return "up" if d > 0 else ("down" if d < 0 else "unchanged")


def mt(x):
    return "-" if x is None else "%.1f" % x


def pct(n, d):
    return AN.pct(n, d)


def cover(n, e):
    return "%d/%d%s" % (n, e, "" if n == e else " INCOMPLETE")


def first_div(a, b):
    """First step (1-based) at which two per-step lists differ, None if equal."""
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i + 1
    if len(a) != len(b):
        return min(len(a), len(b)) + 1
    return None


# ------------------------------------------------------------------ checks -----
def check_dry(store, arm, ref, tuples):
    ident, viol, paired = 0, [], 0
    for t in tuples:
        ra, rb = store.get(arm, t), store.get(ref, t)
        if ra is None or rb is None:
            continue
        paired += 1
        dv = first_div(ra["digests"], rb["digests"])
        if dv is None:
            ident += 1
        else:
            viol.append("%s fire differs from step %d" % (label(t), dv))
    return {"paired": paired, "identical": ident, "violations": viol}


def check_gate(store, arm, ref, tuples, force_no_row=False, row_override=None):
    """rescued/dead == ref; ff_steps == ref before the arm's first log row.
    row_override {tuple: step} replaces the first row (self-test boundary controls)."""
    out = {"paired": 0, "outcome_viol": [], "prefix_viol": [], "prefix_steps": 0, "rows": []}
    for t in tuples:
        ra, rb = store.get(arm, t), store.get(ref, t)
        if ra is None or rb is None:
            continue
        out["paired"] += 1
        if (ra["rescued"], ra["dead"]) != (rb["rescued"], rb["dead"]):
            out["outcome_viol"].append("%s rescued/dead %d/%d vs %s %d/%d" % (
                label(t), ra["rescued"], ra["dead"], ref, rb["rescued"], rb["dead"]))
        fr = None if force_no_row else ra["first_row"]
        if row_override is not None and t in row_override:
            fr = row_override[t]
        n = STEPS if fr is None else max(0, fr - 1)
        out["prefix_steps"] += n
        dv = first_div(ra["ff_steps"][:n], rb["ff_steps"][:n])
        if dv is not None:
            out["prefix_viol"].append("%s ff_steps differ at step %d (first row %s, compared steps 1-%d)" % (
                label(t), dv, fr, n))
        out["rows"].append((t, fr, ra["terminal"], rb["terminal"], ra["eng_before"], ra["first_engaged"]))
    return out


def check_crn(store, arm, ctrl, tuples):
    out = {"paired": 0, "identical": 0, "exact": 0, "violations": []}
    for t in tuples:
        ra, rb = store.get(arm, t), store.get(ctrl, t)
        if ra is None or rb is None:
            continue
        out["paired"] += 1
        fw = ra["first_write"]
        dv = first_div(ra["digests"], rb["digests"])
        if fw is None:
            if dv is None:
                out["identical"] += 1
            else:
                out["violations"].append("%s no write but fire differs from step %d" % (label(t), dv))
        elif dv == fw:
            out["exact"] += 1
        else:
            out["violations"].append("%s first write %d, fire first differs at %s" % (label(t), fw, dv))
    return out


ABSENT = "<absent>"


def _min_step(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, (list, tuple)):
        xs = [m for m in (_min_step(x) for x in v) if m is not None]
        return min(xs) if xs else None
    return None


def key_detail(k, va, vb):
    if isinstance(va, list) and isinstance(vb, list):
        i = first_div(va, vb)
        if k in PER_STEP:
            return "first differing step %s (len %d/%d)" % (i, len(va), len(vb))
        j = i - 1
        el = va[j] if j < len(va) else (vb[j] if j < len(vb) else None)
        st = el.get("step") if isinstance(el, dict) else None
        return "first differing element #%d%s (len %d/%d)" % (j, (" step %s" % st) if st is not None else "",
                                                            len(va), len(vb))
    if isinstance(va, dict) and isinstance(vb, dict):
        ks = sorted(x for x in set(va) | set(vb) if va.get(x, ABSENT) != vb.get(x, ABSENT))
        s = "%d differing sub-keys (%s%s)" % (len(ks), ", ".join(ks[:4]), ", ..." if len(ks) > 4 else "")
        if k in ("burn_intervals", "first_burn_step"):
            steps = [m for m in (_min_step([va.get(x), vb.get(x)]) for x in ks) if m is not None]
            if steps:
                s += "; earliest step on a differing cell %d" % min(steps)
        return s
    return "%s vs %s" % (json.dumps(va)[:60], json.dumps(vb)[:60])


def identity_pair(tag_a, tag_b, t, queue, exclude=EXCLUDE_ID):
    sa, da = run_status(tag_a, t, queue)
    if sa != "complete":
        return {"status": "%s %s: %s" % (tag_a, sa, da)}
    sb, db = run_status(tag_b, t, queue)
    if sb != "complete":
        return {"status": "%s %s: %s" % (tag_b, sb, db)}
    keys = sorted((set(da) | set(db)) - set(exclude))
    diff = [k for k in keys if da.get(k, ABSENT) != db.get(k, ABSENT)]
    order = [k for k in keys if k not in diff and isinstance(da.get(k), dict)
             and list(da[k].keys()) != list(db[k].keys())]
    det = {k: key_detail(k, da.get(k, ABSENT), db.get(k, ABSENT)) for k in diff}
    return {"status": "complete", "diff": diff, "detail": det, "order": order}


def identity_block(tag_a, tag_b, tuples, queue, exclude=EXCLUDE_ID, quiet=False):
    same, rows, pending = 0, [], 0
    res = {}
    for t in tuples:
        r = identity_pair(tag_a, tag_b, t, queue, exclude)
        res[t] = r
        if r["status"] != "complete":
            pending += 1
            rows.append("    %-16s PENDING (%s)" % (label(t), r["status"]))
            continue
        if not r["diff"]:
            same += 1
            if r["order"]:
                rows.append("    %-16s identical (value); dict key order differs in %s" % (
                    label(t), ", ".join(r["order"])))
        else:
            rows.append("    %-16s DIFFERS in %s" % (label(t), ", ".join(r["diff"])))
            for k in r["diff"]:
                rows.append("        %-22s %s" % (k, r["detail"][k]))
    n = len(tuples) - pending
    verdict = "PASS" if n and same == n else ("NO DATA" if not n else "FAIL")
    if not quiet:
        say("  %-6s == %-6s  %s  %d/%d identical (%d complete pairs of %d expected; excluded %s)" % (
            tag_a, tag_b, verdict, same, n, n, len(tuples), ", ".join(exclude)))
        for x in rows:
            say(x)
    return {"verdict": verdict, "same": same, "complete": n, "pending": pending, "res": res}


# ------------------------------------------------------------------ tables -----
def views(tuples):
    return (("counted", list(tuples)),
            ("de-duplicated, east/def excluded", [t for t in tuples if t[1] != "default"]))


def compute(store, tuples, arms, specs, selftest=False):
    """{view: {arm: {...}}} - the numbers every table prints (and the self-test checks)."""
    res = collections.OrderedDict()
    for vname, tt in views(tuples):
        res[vname] = collections.OrderedDict()
        for arm in arms:
            exp = expected_tuples(arm, tt, store.queue, selftest)
            if not exp:
                continue
            present = [t for t in exp if store.get(arm, t) is not None]
            E = {"expected": len(exp), "present": present, "A": agg([store.get(arm, t) for t in present]),
                 "refs": collections.OrderedDict()}
            for ref in specs.get(arm, ([], "", ""))[0]:
                paired = [t for t in present if store.get(ref, t) is not None]
                ra = [store.get(arm, t) for t in paired]
                rb = [store.get(ref, t) for t in paired]
                dirs = collections.Counter(direction(a, b) for a, b in zip(ra, rb))
                per = collections.OrderedDict()
                for t, a, b in zip(paired, ra, rb):
                    per[t] = {"flips": flips(a, b), "d_rescued": a["rescued"] - b["rescued"],
                              "d_dead": a["dead"] - b["dead"], "d_ffd": a["ffd"] - b["ffd"],
                              "d_deaths": len(a["deaths"]) - len(b["deaths"]),
                              "d_intact": a["intact"] - b["intact"], "d_e1n": a["e1n"] - b["e1n"],
                              "dir": direction(a, b)}
                E["refs"][ref] = {"paired": paired, "A": agg(ra), "B": agg(rb), "dirs": dirs, "per": per}
            res[vname][arm] = E
    return res


def print_tables(name, res, store):
    say("")
    say("=" * 110)
    say("SAMPLE %s" % name)
    say("=" * 110)
    for vname, arms in res.items():
        say("")
        say("-- %s --" % vname.upper())
        say("OUTCOMES   (ref rows: the reference on the arm's own present runs; delta = arm - ref)")
        say("  %-8s %-16s %7s %5s %4s %6s %7s %9s" % ("arm", "runs", "rescued", "dead", "ffd", "nevdet",
                                                    "nonterm", "mean_term"))
        for arm, E in arms.items():
            A = E["A"]
            if not E["present"]:
                say("  %-8s %-16s no complete run yet" % (arm, cover(0, E["expected"])))
                continue
            say("  %-8s %-16s %7d %5d %4d %6d %7d %9s" % (arm, cover(len(E["present"]), E["expected"]), A["rescued"],
                                                        A["dead"], A["ffd"], A["nd"], A["nonterm"], mt(A["mean_term"])))
            for ref, R in E["refs"].items():
                B, P = R["B"], R["A"]
                nflip = sum(1 for p in R["per"].values() if p["flips"])
                say("    %-6s %-16s %7d %5d %4d %6d %7d %9s   delta %+d / %+d / %+d / %+d / %+d   runs with a victim flip %d" % (
                    ref, "paired %d" % B["runs"], B["rescued"], B["dead"], B["ffd"], B["nd"], B["nonterm"],
                    mt(B["mean_term"]), P["rescued"] - B["rescued"], P["dead"] - B["dead"], P["ffd"] - B["ffd"],
                    P["nd"] - B["nd"], P["nonterm"] - B["nonterm"], nflip))
        say("")
        say("FIRE END STATE   intact = 2500 - ever_burned - cleared per run")
        say("  %-8s %-16s %7s %7s %7s %7s %11s" % ("arm", "runs", "burnt", "ever", "cleared", "intact", "burning@240"))
        for arm, E in arms.items():
            A = E["A"]
            if not E["present"]:
                say("  %-8s %-16s no complete run yet" % (arm, cover(0, E["expected"])))
                continue
            say("  %-8s %-16s %7d %7d %7d %7d %11d" % (arm, cover(len(E["present"]), E["expected"]), A["burnt"],
                                                     A["ever"], A["cleared"], A["intact"], A["burning240"]))
            for ref, R in E["refs"].items():
                B, P = R["B"], R["A"]
                say("    %-6s %-16s %7d %7d %7d %7d %11d   intact %+d   per run up/down/unchanged %d/%d/%d" % (
                    ref, "paired %d" % B["runs"], B["burnt"], B["ever"], B["cleared"], B["intact"], B["burning240"],
                    P["intact"] - B["intact"], R["dirs"]["up"], R["dirs"]["down"], R["dirs"]["unchanged"]))
        say("")
        say("DRONE STEPS ON A BURNING CELL   E1 searcher-only | E2 all-UAV  (_dcd4_analyze.summarize)")
        for arm, E in arms.items():
            A = E["A"]
            if not E["present"]:
                say("  %-8s %-16s no complete run yet" % (arm, cover(0, E["expected"])))
                continue
            say("  %-8s %-16s E1 %-22s E2 %s" % (arm, cover(len(E["present"]), E["expected"]),
                                                 pct(A["e1n"], A["e1d"]), pct(A["e2n"], A["e2d"])))
            for ref, R in E["refs"].items():
                B, P = R["B"], R["A"]
                say("    %-6s %-16s E1 %-22s E2 %-22s  numerators delta E1 %+d E2 %+d" % (
                    ref, "paired %d" % B["runs"], pct(B["e1n"], B["e1d"]), pct(B["e2n"], B["e2d"]),
                    P["e1n"] - B["e1n"], P["e2n"] - B["e2n"]))
        say("")
        say("FIREFIGHTER DEATHS (ff_steps dead flag, _firemech_analyze classification)")
        say("  %-8s %-16s %6s %7s %4s %6s %9s %8s %4s %9s" % ("arm", "runs", "deaths", "engaged", "prev", "streak",
                                                           "preempted", "after_T", "full", "free-exit"))
        for arm, E in arms.items():
            A = E["A"]
            if not E["present"]:
                say("  %-8s %-16s no complete run yet" % (arm, cover(0, E["expected"])))
                continue
            say("  %-8s %-16s %6d %7d %4d %6d %9d %8d %4d %9d" % (
                arm, cover(len(E["present"]), E["expected"]), A["deaths"], A["d_engaged"], A["d_prev"], A["d_streak"],
                A["d_preempted"], A["d_after_terminal"], A["d_full"], A["d_free"]))
            for ref, R in E["refs"].items():
                B = R["B"]
                say("    %-6s %-16s %6d %7d %4d %6d %9d %8d %4d %9d" % (
                    ref, "paired %d" % B["runs"], B["deaths"], B["d_engaged"], B["d_prev"], B["d_streak"],
                    B["d_preempted"], B["d_after_terminal"], B["d_full"], B["d_free"]))
        say("")
        say("ENGAGEMENT AND PROBE COUNTERS   engaged rows: <=terminal / >terminal / in non-terminal runs")
        say("  %-8s %-16s %7s %6s %6s %7s %6s %5s %5s | %7s %9s %9s %8s %9s" % (
            "arm", "runs", "engaged", "<=T", ">T", "nonterm", "wruns", "ext", "clear",
            "leash_dr", "gate_clsd", "eo_blockd", "dry_forc", "crn_draws"))
        for arm, E in arms.items():
            A = E["A"]
            if not E["present"]:
                say("  %-8s %-16s no complete run yet" % (arm, cover(0, E["expected"])))
                continue
            say("  %-8s %-16s %7d %6d %6d %7d %6d %5d %5d | %7d %9d %9d %8d %9d" % (
                arm, cover(len(E["present"]), E["expected"]), A["engaged"], A["eng_before"], A["eng_after"],
                A["eng_nonterm"], A["write_runs"], A["ext"], A["clear"], A["fm2p_leash_dropped"],
                A["fm2p_gate_closed_calls"], A["fm2p_engage_only_blocked_calls"], A["fm2p_dry_forced_calls"],
                A["fm2p_crn_draws"]))
            for ref, R in E["refs"].items():
                B = R["B"]
                say("    %-6s %-16s %7d %6d %6d %7d %6d %5d %5d" % (
                    ref, "paired %d" % B["runs"], B["engaged"], B["eng_before"], B["eng_after"], B["eng_nonterm"],
                    B["write_runs"], B["ext"], B["clear"]))
    # flips listing, counted view only (a flip is a per-run fact)
    arms = res["counted"]
    say("")
    say("VICTIM FINAL-STATUS FLIPS AND PER-RUN DELTAS vs each reference (counted view; runs with any change)")
    for arm, E in arms.items():
        for ref, R in E["refs"].items():
            lines = []
            for t, p in R["per"].items():
                if p["flips"] or p["d_rescued"] or p["d_dead"] or p["d_ffd"] or p["d_deaths"]:
                    lines.append("%s r%+d d%+d ffd%+d%s" % (
                        label(t), p["d_rescued"], p["d_dead"], p["d_ffd"],
                        (" [" + ", ".join("%s %s->%s" % f for f in p["flips"]) + "]") if p["flips"] else ""))
            if not R["paired"]:
                say("  %-6s vs %-6s no complete pair yet" % (arm, ref))
                continue
            say("  %-6s vs %-6s (%d paired): %s" % (arm, ref, len(R["paired"]), "; ".join(lines) if lines else "none"))


def print_per_run(tuples, arms, specs, store):
    say("")
    say("PER RUN   arm r/d/ffd nd T=terminal i=intact row=first log row w=first write | vs ref: dr/dd/dffd di dir")
    for arm in arms:
        exp = [t for t in tuples if (arm, t) in store.queue or arm not in ARM_SPECS]
        if not exp:
            continue
        say("  %s (%s)" % (arm, specs.get(arm, ([], "", "reference"))[2]))
        notdone = collections.defaultdict(list)
        for t in exp:
            st, why = store.st(arm, t)
            if st != "complete":
                notdone["%s: %s" % (st.upper(), why)].append(label(t))
        for why, labs in notdone.items():
            say("    %d %s -> %s" % (len(labs), why, ", ".join(labs)))
        for t in exp:
            if store.get(arm, t) is None:
                continue
            r = store.get(arm, t)
            parts = []
            for ref in specs.get(arm, ([], "", ""))[0]:
                b = store.get(ref, t)
                if b is None:
                    parts.append("%s -" % ref)
                    continue
                parts.append("%s %+d/%+d/%+d i%+d %s%s" % (
                    ref, r["rescued"] - b["rescued"], r["dead"] - b["dead"], r["ffd"] - b["ffd"],
                    r["intact"] - b["intact"], direction(r, b),
                    (" [" + ", ".join("%s %s->%s" % f for f in flips(r, b)) + "]") if flips(r, b) else ""))
            say("    %-16s %d/%d/%d nd%d T%s i%d row@%s w@%s eng %d(<=T %d) | %s" % (
                label(t), r["rescued"], r["dead"], r["ffd"], r["nd"], r["terminal"], r["intact"], r["first_row"],
                r["first_write"], r["engaged"], r["eng_before"], " | ".join(parts)))


def print_deaths(tuples, arms, store):
    say("")
    say("DEATH LIST (complete runs)")
    for arm in arms:
        dd = [(t, x) for t in tuples for x in ((store.get(arm, t) or {}).get("deaths") or [])]
        if not dd:
            continue
        for t, x in dd:
            say("  %-7s %-16s %s step %3d cell %-9s engaged %-5s prev %-5s streak %-5s(%3d rows) preempted %-5s"
                "(assign %s) row %-8s nbrs %s (%s) before: %s after_terminal %s" % (
                    arm, label(t), x["ff"], x["step"], AN.fmt_cell(x["cell"]), x["engaged"], x["engaged_prev"],
                    x["streak_engaged"], x["streak_len"], x["preempted"], x["last_assign"], x["row"], x["nb"],
                    x["enclosure"], x["status_before"], x["after_terminal"]))


def print_checks(tuples, arms, store):
    say("")
    say("BY-CONSTRUCTION CHECKS (every complete pair in scope; n/m = passing runs / complete pairs)")
    for arm in arms:
        kind = ARM_SPECS.get(arm, ([], "", ""))[1]
        refs_needed = {"crn": ["f2cOFF"]}.get(kind, ["fmOFF"])
        if kind in ("dry", "gate_dry", "identity", "gate", "crn") and not any(
                store.get(arm, t) is not None and all(store.get(r, t) is not None for r in refs_needed)
                for t in tuples):
            say("  %-6s %-6s no complete pair yet (arm or %s pending)" % (kind.upper(), arm, "/".join(refs_needed)))
            continue
        if kind in ("dry", "gate_dry", "identity"):
            ref = "fmOFF"
            c = check_dry(store, arm, ref, tuples)
            say("  DRY    %-6s fire_digests == %s 240/240: %d/%d%s" % (
                arm, ref, c["identical"], c["paired"], ("  VIOLATIONS: " + "; ".join(c["violations"])) if c["violations"] else ""))
        if kind in ("gate", "gate_dry"):
            c = check_gate(store, arm, "fmOFF", tuples)
            say("  GATE   %-6s rescued/dead == fmOFF: %d/%d%s" % (
                arm, c["paired"] - len(c["outcome_viol"]), c["paired"],
                ("  VIOLATIONS: " + "; ".join(c["outcome_viol"])) if c["outcome_viol"] else ""))
            say("  GATE   %-6s ff_steps == fmOFF before the first log row: %d/%d runs (%d steps compared)%s" % (
                arm, c["paired"] - len(c["prefix_viol"]), c["paired"], c["prefix_steps"],
                ("  VIOLATIONS: " + "; ".join(c["prefix_viol"])) if c["prefix_viol"] else ""))
            for t, fr, term, oterm, before, fe in c["rows"]:
                say("         %-16s first row %-4s first engaged %-4s terminal %-4s (fmOFF %-4s) engaged rows <=terminal %d" % (
                    label(t), fr, fe, term, oterm, before))
        if kind == "crn":
            c = check_crn(store, arm, "f2cOFF", tuples)
            say("  CRN    %-6s vs f2cOFF: paired %d | no write & identical 240/240 %d | diverges exactly at first write %d | violations %d%s" % (
                arm, c["paired"], c["identical"], c["exact"], len(c["violations"]),
                (": " + "; ".join(c["violations"])) if c["violations"] else ""))


def coverage_report(tuples, arms, store):
    say("COVERAGE (complete / pending / invalid of expected, all tuples in scope)")
    for arm in arms:
        exp = [t for t in tuples if (arm, t) in store.queue]
        if not exp:
            continue
        cnt = collections.Counter(store.st(arm, t)[0] for t in exp)
        say("  %-7s complete %2d  pending %2d  invalid %d  of %d%s" % (
            arm, cnt["complete"], cnt["pending"], cnt["invalid"], len(exp),
            "" if cnt["complete"] == len(exp) else "  INCOMPLETE"))
        for t in exp:
            st, why = store.st(arm, t)
            if st == "invalid":
                say("      INVALID %s: %s" % (label(t), why))
    refs = sorted({r for a in arms for r in ARM_SPECS.get(a, ([], "", ""))[0]} - set(ARM_SPECS))
    for ref in refs:
        cnt = collections.Counter(store.st(ref, t)[0] for t in tuples)
        say("  ref %-6s complete %2d of %d%s" % (ref, cnt["complete"], len(tuples),
                                                "" if cnt["complete"] == len(tuples) else "  (missing runs limit pairing)"))


def main_probe(a):
    arms = [x for x in (a.arms.split(",") if a.arms else list(ARM_SPECS)) if x]
    bad = [x for x in arms if x not in ARM_SPECS]
    if bad:
        raise SystemExit("unknown probe arm(s): %s" % ", ".join(bad))
    queue = read_queue()
    store = Store(queue)
    say("FM2 PROBE-ARM ANALYSIS   queue %s (%d lines)" % (os.path.basename(QUEUE_TXT), len(queue)))
    for p in queue_crosscheck(queue):
        say("  QUEUE CROSS-CHECK: " + p)
    samples = {"canonical": [("canonical 13", CANONICAL)], "fresh": [("fresh 10", FRESH)],
               "both": [("canonical 13", CANONICAL), ("fresh 10", FRESH), ("canonical+fresh 23", CANONICAL + FRESH)]}[a.sample]
    scope = CANONICAL + FRESH if a.sample == "both" else samples[0][1]
    coverage_report(scope, arms, store)
    if "f2IDD" in arms:
        say("")
        say("IDENTITY f2IDD vs fmDRY (canonical 13; every field except tag, repo, wall_s; dicts by value)")
        identity_block("f2IDD", "fmDRY", [t for t in scope if ("f2IDD", t) in queue], queue)
    print_checks(scope, arms, store)
    for name, tuples in samples:
        print_tables(name, compute(store, tuples, arms, ARM_SPECS), store)
    print_per_run(scope, arms, ARM_SPECS, store)
    print_deaths(scope, arms, store)


# ------------------------------------------------------------------ self-test --
R1_ANALYSIS = os.path.join(HERE, "_firemech_both_analysis.txt")
R1_ARMS = ["fmOFF", "fmF", "fmFS", "fmES", "fmEFS", "fmDRY"]
# round-1 arms standing in for probe arms: the writing arms play gate arms with the
# probe arms' two-reference layout (fmOFF, fmDRY), fmDRY plays a DRY probe arm
SELF_SPECS = collections.OrderedDict([
    ("fmOFF", ([], "control", "round-1 control")),
    ("fmF", (["fmOFF", "fmDRY"], "gate", "stand-in gate arm (fmF)")),
    ("fmFS", (["fmOFF", "fmDRY"], "gate", "stand-in (fmFS)")),
    ("fmES", (["fmOFF", "fmDRY"], "gate", "stand-in (fmES)")),
    ("fmEFS", (["fmOFF", "fmDRY"], "gate", "stand-in (fmEFS)")),
    ("fmDRY", (["fmOFF"], "dry", "stand-in DRY probe arm (fmDRY)")),
])
SAMPLE_NAMES = (("canonical 13", CANONICAL), ("fresh 10", FRESH), ("canonical+fresh 23", CANONICAL + FRESH))

# firemech_report.txt, transcribed. 3.2: burnt, ever, clear, intact, burning@240, intact vs OFF
REPORT_32 = {
    "canonical 13": {"fmOFF": (16053, 22648, 0, 9852, 1395, None), "fmF": (14351, 19929, 828, 11743, 613, 1891),
                     "fmFS": (14657, 20268, 826, 11406, 708, 1554), "fmES": (15062, 21203, 0, 11297, 920, 1445),
                     "fmEFS": (14622, 20338, 831, 11331, 665, 1479), "fmDRY": (16053, 22648, 0, 9852, 1395, 0)},
    "fresh 10": {"fmOFF": (10996, 15088, 0, 9912, 659, None), "fmF": (10019, 13730, 589, 10681, 424, 769),
                 "fmFS": (10043, 13756, 528, 10716, 463, 804), "fmES": (9783, 13666, 0, 11334, 513, 1422),
                 "fmEFS": (10265, 14123, 465, 10412, 518, 500), "fmDRY": (10996, 15088, 0, 9912, 659, 0)},
    "canonical+fresh 23": {"fmOFF": (27049, 37736, 0, 19764, 2054, None), "fmF": (24370, 33659, 1417, 22424, 1037, 2660),
                           "fmFS": (24700, 34024, 1354, 22122, 1171, 2358), "fmES": (24845, 34869, 0, 22631, 1433, 2867),
                           "fmEFS": (24887, 34461, 1296, 21743, 1183, 1979), "fmDRY": (27049, 37736, 0, 19764, 2054, 0)},
}
REPORT_32_DEDUP_INTACT = {"fmEFS": 1389, "fmF": 1783, "fmES": 2402}
REPORT_32_DIR = {"canonical 13": {"fmF": (11, 2, 0), "fmFS": (11, 2, 0), "fmEFS": (11, 2, 0), "fmES": (7, 6, 0)},
                 "fresh 10": {"fmF": (5, 1, 4), "fmFS": (5, 1, 4), "fmEFS": (5, 1, 4), "fmES": (4, 2, 4)}}
# 3.3 engaged rows, engaged after terminal (canonical+fresh 23)
REPORT_33 = {"fmF": (4675, 2751), "fmFS": (4732, 2550), "fmES": (3349, 1741), "fmEFS": (4607, 2589), "fmDRY": (4440, 2542)}
# 5: rescued, dead, ffd, nevdet, nonterm, mean terminal
REPORT_5 = {
    ("canonical 13", "counted"): {"fmOFF": (39, 10, 6, 1, 1, "151.9"), "fmF": (38, 11, 6, 1, 1, "143.2"),
                                  "fmFS": (36, 12, 6, 1, 2, "135.6"), "fmES": (38, 12, 6, 0, 1, "139.5"),
                                  "fmEFS": (38, 11, 6, 1, 1, "140.8"), "fmDRY": (38, 10, 6, 1, 2, "134.2")},
    ("fresh 10", "counted"): {"fmOFF": (29, 6, 4, 4, 1, "175.6"), "fmF": (28, 7, 2, 3, 2, "158.8"),
                              "fmFS": (28, 6, 2, 3, 3, "164.3"), "fmES": (29, 6, 3, 3, 2, "171.0"),
                              "fmEFS": (28, 6, 3, 2, 4, "157.2"), "fmDRY": (28, 5, 5, 4, 3, "164.7")},
    ("canonical+fresh 23", "counted"): {"fmOFF": (68, 16, 10, 5, 2, "162.0"), "fmES": (67, 18, 9, 3, 3, None),
                                        "fmF": (66, 18, 8, 4, 3, None), "fmEFS": (66, 17, 9, 3, 5, "146.3"),
                                        "fmFS": (64, 18, 8, 4, 5, None), "fmDRY": (66, 15, 11, 5, 5, "146.1")},
    ("canonical+fresh 23", "dedup"): {"fmOFF": (59, 14, 10, 4, 2, "159.8"), "fmES": (60, 15, 8, 3, 2, "150.7"),
                                      "fmF": (57, 16, 7, 3, 3, "142.3"), "fmEFS": (57, 15, 8, 2, 5, "139.5"),
                                      "fmFS": (57, 15, 7, 3, 4, "143.7"), "fmDRY": (58, 13, 10, 4, 4, "144.1")},
}
# 5: rescued decomposition, positioning (DRY - OFF) and writes (arm - DRY)
REPORT_5_DECOMP = {
    ("canonical 13", "counted"): {"fmF": (-1, 0), "fmFS": (-1, -2), "fmES": (-1, 0), "fmEFS": (-1, 0)},
    ("fresh 10", "counted"): {"fmF": (-1, 0), "fmFS": (-1, 0), "fmES": (-1, 1), "fmEFS": (-1, 0)},
    ("canonical+fresh 23", "dedup"): {"fmF": (-1, -1), "fmFS": (-1, -1), "fmES": (-1, 2), "fmEFS": (-1, -1)},
}
REPORT_5_POSITIONING = {"east/half/101": -1, "south/half/404": -1, "east/def/101": -1, "east/half/404": 1,
                        "south/half/202": 1, "south/half/909": -1}
REPORT_5_WRITES = {"south/half/404": -1, "east/def/101": 1}
# 6: deaths, engaged, prev, streak, preempted, after_terminal, full_enclosure (canonical+fresh 23)
REPORT_6 = {"fmOFF": (10, 0, 0, 0, 0, 5, 10), "fmF": (8, 0, 0, 0, 4, 0, 8), "fmFS": (8, 0, 0, 0, 4, 0, 8),
            "fmES": (9, 0, 0, 3, 2, 1, 9), "fmEFS": (9, 0, 0, 0, 5, 0, 9), "fmDRY": (11, 0, 0, 4, 3, 2, 11)}
REPORT_6_DEDUP = {"fmOFF": 10, "fmF": 7, "fmFS": 7, "fmES": 8, "fmEFS": 8, "fmDRY": 10}
_ADD4 = ["south/half/404", "south/half/808", "south/half/909", "east/def/303"]
REPORT_6_RUNS = {
    "fmDRY": {**{k: 1 for k in _ADD4}, "east/half/101": -1, "south/half/202": -1, "east/half/606": -1},
    "fmEFS": {**{k: 1 for k in _ADD4}, "south/half/202": -1, "south/half/303": -1, "east/half/606": -1,
              "east/half/909": -1, "south/half/1010": -1},
    "fmF": {**{k: 1 for k in _ADD4}, "south/half/202": -1, "south/half/303": -1, "east/half/606": -1,
            "east/half/909": -1, "south/half/1010": -1, "south/half/606": -1},
}
# 7: E1 %, E2 %
REPORT_7 = {
    "canonical 13": {"fmOFF": ("5.04", "3.52"), "fmF": ("4.31", "2.60"), "fmFS": ("4.62", "3.04"),
                     "fmES": ("3.64", "2.92"), "fmEFS": ("4.44", "2.80"), "fmDRY": ("4.75", "3.37")},
    "fresh 10": {"fmOFF": ("3.25", "1.94"), "fmF": ("3.08", "2.22"), "fmFS": ("3.00", "2.18"),
                 "fmES": ("2.62", "1.75"), "fmEFS": ("3.19", "2.21"), "fmDRY": ("3.15", "1.89")},
    "canonical+fresh 23": {"fmOFF": ("4.21", "2.83"), "fmF": ("3.74", "2.44"), "fmFS": ("3.87", "2.66"),
                           "fmES": ("3.17", "2.41"), "fmEFS": ("3.86", "2.55"), "fmDRY": ("4.00", "2.73")},
}
REPORT_7_SPLIT = {"canonical 13": (-16, -17), "fresh 10": (-5, 2), "canonical+fresh 23": (-21, -15)}

CHECKS = []


def chk(source, item, got, want):
    ok = got == want
    CHECKS.append((source, item, ok, got, want))
    say("  %s [%s] %s got=%s want=%s" % ("PASS" if ok else "FAIL", source, item, got, want))
    return ok


def parse_round1(path):
    P = {}
    sample = section = view = None
    header = None
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            m = re.match(r"SAMPLE (.+) \(\d+ runs\)$", line)
            if m:
                sample = m.group(1)
                P[sample] = {"counted": {}, "dedup": {}, "e": {}, "deaths": {}, "mech": {}, "per_run": {}}
                section = None
                continue
            if sample is None:
                continue
            if line.startswith("OUTCOMES ("):
                section, view = "out", ("counted" if "(counted)" in line else "dedup")
                continue
            if line.startswith("FIRE END STATE ("):
                section, view = "fire", ("counted" if "(counted)" in line else "dedup")
                continue
            for prefix, sec in (("FIRE DIGEST", None), ("MECHANISM", "mech"), ("DRONE STEPS", "e"),
                                ("FIREFIGHTER DEATHS", "deaths"), ("WALL TIME", None), ("PER RUN", "per_run")):
                if line.startswith(prefix):
                    section = sec
                    header = None
                    break
            else:
                pass
            if section == "out":
                m = re.match(r"^  (fm\w+)\s+" + r"(\d+)\s+" * 7 + r"(\S+)$", line)
                if m:
                    g = m.groups()
                    P[sample][view].setdefault(g[0], {}).update(
                        runs=int(g[1]), rescued=int(g[2]), dead=int(g[3]), ffd=int(g[4]), nd=int(g[5]),
                        unreach=int(g[6]), nonterm=int(g[7]), mean_term=g[8])
            elif section == "fire":
                m = re.match(r"^  (fm\w+)\s+" + r"(\d+)\s+" * 5 + r"(\d+)\s*(.*)$", line)
                if m:
                    g = m.groups()
                    e = P[sample][view].setdefault(g[0], {})
                    e.update(burnt=int(g[2]), ever=int(g[3]), cleared=int(g[4]), intact=int(g[5]), burning240=int(g[6]))
                    md = re.match(r"([+-]\d+) / ([+-]\d+) / ([+-]\d+)\s+\(paired (\d+)\)", g[7])
                    if md:
                        e.update(d_burnt=int(md.group(1)), d_ever=int(md.group(2)), d_intact=int(md.group(3)))
            elif section == "mech":
                toks = line.split()
                if toks and toks[0] == "arm":
                    header = toks
                elif header and toks and re.match(r"^fm\w+$", toks[0]) and len(toks) == len(header):
                    P[sample]["mech"][toks[0]] = dict(zip(header[1:], (int(x) for x in toks[1:])))
            elif section == "e":
                m = re.match(r"^  (fm\w+)\s+E1 (\d+)/(\d+) = \S+\s+E2 (\d+)/(\d+)", line)
                if m:
                    P[sample]["e"][m.group(1)] = tuple(int(x) for x in m.groups()[1:])
            elif section == "deaths":
                m = re.match(r"^  (fm\w+)\s+deaths (\d+)\s+engaged-at-death (\d+)\s+engaged-prev (\d+)\s+"
                             r"idle-streak-engaged (\d+)\s+preempted-rescue (\d+)\s+after-terminal (\d+)\s+"
                             r"full-enclosure (\d+)\s+free-exit (\d+)", line)
                if m:
                    P[sample]["deaths"][m.group(1)] = tuple(int(x) for x in m.groups()[1:])
            elif section == "per_run":
                m = re.match(r"^  (\w+/\w+/\d+)\s+(.*)$", line)
                if m:
                    row = {}
                    for part in m.group(2).split(" | "):
                        mp = re.match(r"(fm\w+) (\d+)/(\d+)/(\d+) b(\d+) e(\d+) c(\d+) i(\d+) w(\d+)/(\d+)@(\S+)", part)
                        if mp:
                            g = mp.groups()
                            row[g[0]] = tuple(int(x) for x in g[1:10]) + (None if g[10] == "None" else int(g[10]),)
                    P[sample]["per_run"][m.group(1)] = row
    return P


def main_selftest(_a):
    queue = read_queue()
    store = Store(queue)
    say("SELF-TEST: round-1 arms as stand-ins, through the same code paths as the probe tables")
    say("  expected values: parsed from %s, and transcribed from firemech_report.txt sections 1, 2, 3.1-3.3, 5, 6, 7"
        % os.path.basename(R1_ANALYSIS))
    P = parse_round1(R1_ANALYSIS)
    say("  parsed samples: %s" % ", ".join("%s (%d per-run lines)" % (k, len(v["per_run"])) for k, v in P.items()))
    all23 = CANONICAL + FRESH
    for arm in R1_ARMS + ["fmREF"]:
        cnt = collections.Counter(store.st(arm, t)[0] for t in all23)
        chk("data", "%s complete runs" % arm, cnt["complete"], 23)

    R = {name: compute(store, tuples, R1_ARMS, SELF_SPECS, selftest=True) for name, tuples in SAMPLE_NAMES}
    vkey = {"counted": "counted", "de-duplicated, east/def excluded": "dedup"}

    say("")
    say("A. TABLE NUMBERS vs %s" % os.path.basename(R1_ANALYSIS))
    for name, _tt in SAMPLE_NAMES:
        for vname, arms in R[name].items():
            want = P[name][vkey[vname]]
            for arm in R1_ARMS:
                A, w = arms[arm]["A"], want[arm]
                got = (A["runs"], A["rescued"], A["dead"], A["ffd"], A["nd"], A["unreach"], A["nonterm"], mt(A["mean_term"]),
                       A["burnt"], A["ever"], A["cleared"], A["intact"], A["burning240"])
                exp = (w["runs"], w["rescued"], w["dead"], w["ffd"], w["nd"], w["unreach"], w["nonterm"], w["mean_term"],
                       w["burnt"], w["ever"], w["cleared"], w["intact"], w["burning240"])
                chk("analysis", "%s %s %s runs/r/d/ffd/nd/unr/nonterm/meanT/burnt/ever/clr/intact/b240" % (
                    name, vkey[vname], arm), got, exp)
                if arm != "fmOFF":
                    Rf = arms[arm]["refs"]["fmOFF"]
                    chk("analysis", "%s %s %s vs fmOFF delta burnt/ever/intact" % (name, vkey[vname], arm),
                        (Rf["A"]["burnt"] - Rf["B"]["burnt"], Rf["A"]["ever"] - Rf["B"]["ever"],
                         Rf["A"]["intact"] - Rf["B"]["intact"]), (w["d_burnt"], w["d_ever"], w["d_intact"]))
        C = R[name]["counted"]
        for arm in R1_ARMS:
            A = C[arm]["A"]
            chk("analysis", "%s %s E1n/E1d/E2n/E2d" % (name, arm), (A["e1n"], A["e1d"], A["e2n"], A["e2d"]), P[name]["e"][arm])
            chk("analysis", "%s %s deaths/eng/prev/streak/preempt/afterT/full/free" % (name, arm),
                (A["deaths"], A["d_engaged"], A["d_prev"], A["d_streak"], A["d_preempted"], A["d_after_terminal"],
                 A["d_full"], A["d_free"]), P[name]["deaths"][arm])
            mech = P[name]["mech"][arm]
            chk("analysis", "%s %s engaged rows / after terminal / ext / clear" % (name, arm),
                (A["engaged"], A["eng_after"], A["ext"], A["clear"]),
                (mech["engaged"], mech["after_ter"], mech["ext"], mech["clear"]))
        # per-run records
        bad = []
        for t in dict(SAMPLE_NAMES)[name]:
            row = P[name]["per_run"].get(label(t), {})
            for arm in R1_ARMS:
                r = store.get(arm, t)
                got = (r["rescued"], r["dead"], r["ffd"], r["burnt"], r["ever"], r["cleared"], r["intact"], r["ext"],
                       r["clear"], r["first_write"])
                if row.get(arm) != got:
                    bad.append("%s %s got %s want %s" % (label(t), arm, got, row.get(arm)))
        chk("analysis", "%s per-run r/d/ff/b/e/c/i/ext/clear/first-write (%d runs x %d arms)" % (
            name, len(dict(SAMPLE_NAMES)[name]), len(R1_ARMS)), bad, [])

    say("")
    say("B. TABLE NUMBERS vs firemech_report.txt (transcribed)")
    for name in REPORT_32:
        C = R[name]["counted"]
        for arm, w in REPORT_32[name].items():
            A = C[arm]["A"]
            d = None if arm == "fmOFF" else C[arm]["refs"]["fmOFF"]["A"]["intact"] - C[arm]["refs"]["fmOFF"]["B"]["intact"]
            chk("report 3.2", "%s %s burnt/ever/clear/intact/b240/intact-vs-OFF" % (name, arm),
                (A["burnt"], A["ever"], A["cleared"], A["intact"], A["burning240"], d), w)
    D23 = R["canonical+fresh 23"]["de-duplicated, east/def excluded"]
    for arm, w in REPORT_32_DEDUP_INTACT.items():
        Rf = D23[arm]["refs"]["fmOFF"]
        chk("report 3.2", "dedup 20 %s intact vs OFF" % arm, Rf["A"]["intact"] - Rf["B"]["intact"], w)
    for name, per in REPORT_32_DIR.items():
        for arm, w in per.items():
            dd = R[name]["counted"][arm]["refs"]["fmOFF"]["dirs"]
            chk("report 3.2", "%s %s intact direction up/down/unchanged" % (name, arm), (dd["up"], dd["down"], dd["unchanged"]), w)
    perF = R["canonical+fresh 23"]["counted"]["fmF"]["refs"]["fmOFF"]["per"]
    ch = [p["d_intact"] for p in perF.values() if p["d_intact"]]
    downs = sorted(x for x in ch if x < 0)
    chk("report 3.2", "fmF 23: changed runs / up / down range", (len(ch), sum(1 for x in ch if x > 0), downs[0], downs[-1]),
        (19, 16, -9, -7))
    C23 = R["canonical+fresh 23"]["counted"]
    for arm, w in REPORT_33.items():
        chk("report 3.3", "23 %s engaged rows / after terminal" % arm, (C23[arm]["A"]["engaged"], C23[arm]["A"]["eng_after"]), w)
    for (name, vk), per in REPORT_5.items():
        vname = "counted" if vk == "counted" else "de-duplicated, east/def excluded"
        for arm, w in per.items():
            A = R[name][vname][arm]["A"]
            got = (A["rescued"], A["dead"], A["ffd"], A["nd"], A["nonterm"], mt(A["mean_term"]) if w[5] is not None else None)
            chk("report 5", "%s %s %s r/d/ffd/nd/nonterm/meanT" % (name, vk, arm), got, w)
    for (name, vk), per in REPORT_5_DECOMP.items():
        vname = "counted" if vk == "counted" else "de-duplicated, east/def excluded"
        V = R[name][vname]
        for arm, w in per.items():
            pos = V["fmDRY"]["A"]["rescued"] - V["fmOFF"]["A"]["rescued"]
            wr = V[arm]["refs"]["fmDRY"]["A"]["rescued"] - V[arm]["refs"]["fmDRY"]["B"]["rescued"]
            chk("report 5", "%s %s %s rescued positioning / writes" % (name, vk, arm), (pos, wr), w)
    perD = R["canonical+fresh 23"]["counted"]["fmDRY"]["refs"]["fmOFF"]["per"]
    chk("report 5", "per-run rescued DRY - OFF", {label(t): p["d_rescued"] for t, p in perD.items() if p["d_rescued"]},
        REPORT_5_POSITIONING)
    for arm in ("fmEFS", "fmF"):
        perW = R["canonical+fresh 23"]["counted"][arm]["refs"]["fmDRY"]["per"]
        chk("report 5", "per-run rescued %s - DRY" % arm, {label(t): p["d_rescued"] for t, p in perW.items() if p["d_rescued"]},
            REPORT_5_WRITES)
    s404 = [p["flips"] for t, p in R["canonical+fresh 23"]["counted"]["fmEFS"]["refs"]["fmDRY"]["per"].items()
            if label(t) == "south/half/404"][0]
    chk("report 5", "south/half/404 fmEFS vs fmDRY flipped victims", sorted(f[0] for f in s404 if f[1] == "rescued"), ["victim_2"])
    for arm, w in REPORT_6.items():
        A = C23[arm]["A"]
        chk("report 6", "23 %s deaths/engaged/prev/streak/preempted/afterT/full" % arm,
            (A["deaths"], A["d_engaged"], A["d_prev"], A["d_streak"], A["d_preempted"], A["d_after_terminal"], A["d_full"]), w)
    for arm, w in REPORT_6_DEDUP.items():
        chk("report 6", "dedup 20 %s deaths" % arm, D23[arm]["A"]["deaths"], w)
    for arm, w in REPORT_6_RUNS.items():
        per = C23[arm]["refs"]["fmOFF"]["per"]
        chk("report 6", "per-run death-count change %s vs OFF" % arm, {label(t): p["d_deaths"] for t, p in per.items() if p["d_deaths"]}, w)
    for name, per in REPORT_7.items():
        C = R[name]["counted"]
        for arm, w in per.items():
            A = C[arm]["A"]
            chk("report 7", "%s %s E1%% / E2%%" % (name, arm),
                ("%.2f" % (100.0 * A["e1n"] / A["e1d"]), "%.2f" % (100.0 * A["e2n"] / A["e2d"])), w)
        pos = C["fmDRY"]["A"]["e1n"] - C["fmOFF"]["A"]["e1n"]
        wr = C["fmEFS"]["refs"]["fmDRY"]["A"]["e1n"] - C["fmEFS"]["refs"]["fmDRY"]["B"]["e1n"]
        chk("report 7", "%s fmEFS searcher burning frames positioning / writes" % name, (pos, wr), REPORT_7_SPLIT[name])

    say("")
    say("C. CHECK FUNCTIONS - positive and negative controls")
    for name, tuples in SAMPLE_NAMES:
        want = {"canonical 13": (0, 13), "fresh 10": (3, 7), "canonical+fresh 23": (3, 20)}[name]
        for arm in ("fmF", "fmFS", "fmES", "fmEFS"):
            c = check_crn(store, arm, "fmOFF", tuples)
            chk("report 3.1", "%s CRN-attribution code on %s vs fmOFF: identical/exact/violations" % (name, arm),
                (c["identical"], c["exact"], len(c["violations"])), want + (0,))
    c = check_dry(store, "fmDRY", "fmOFF", all23)
    chk("report 3.1", "DRY check fmDRY vs fmOFF identical", (c["identical"], len(c["violations"])), (23, 0))
    c = check_dry(store, "fmEFS", "fmOFF", all23)
    chk("control", "DRY check detects fmEFS vs fmOFF (non-identical runs = write runs)", len(c["violations"]), 20)
    c = check_crn(store, "fmES", "fmF", all23)
    chk("control", "CRN check detects a wrong control (fmES vs fmF): violations > 0", len(c["violations"]) > 0, True)
    say("      e.g. %s" % "; ".join(c["violations"][:3]))
    c = check_gate(store, "fmREF", "fmOFF", all23)
    chk("control", "gate check fmREF as gate arm vs fmOFF: outcome / prefix violations, steps compared",
        (len(c["outcome_viol"]), len(c["prefix_viol"]), c["prefix_steps"]), (0, 0, 23 * STEPS))
    rd_diff = sorted(lab for lab, row in P["canonical+fresh 23"]["per_run"].items()
                     if row["fmF"][:2] != row["fmOFF"][:2])
    c = check_gate(store, "fmF", "fmOFF", all23)
    chk("control", "gate check on ungated fmF flags exactly the runs whose r/d differ (analysis per-run lines)",
        sorted(v.split()[0] for v in c["outcome_viol"]), rd_diff)
    for arm in ("fmF", "fmFS", "fmES", "fmEFS", "fmDRY"):
        c = check_gate(store, arm, "fmOFF", all23)
        chk("control", "ff_steps prefix before first log row, %s vs fmOFF (by construction for any feature arm): "
            "violations (steps compared %d)" % (arm, c["prefix_steps"]), len(c["prefix_viol"]), 0)
    c = check_gate(store, "fmDRY", "fmOFF", all23, force_no_row=True)
    chk("control", "ff_steps check with the row limit removed detects fmDRY positioning: violations > 0",
        len(c["prefix_viol"]) > 0, True)
    say("      e.g. %s" % "; ".join(c["prefix_viol"][:3]))
    say("      NOTE: every round-1 feature arm logs its first row at step 1 on every run, so the by-construction")
    say("      prefix controls above compare 0 steps; the non-vacuous controls are fmREF (240 steps per run) and")
    say("      the boundary controls below.")
    # boundary controls on a SYNTHETIC in-memory record (no round-1 run diverges after step
    # 1): a copy of fmREF east/half/101 with ff_steps and fire_digests altered from step 100
    t0 = CANONICAL[0]
    base = store.get("fmREF", t0)
    syn = dict(base)
    syn["ff_steps"] = list(base["ff_steps"])
    syn["digests"] = list(base["digests"])
    for i in range(99, STEPS):
        syn["ff_steps"][i] = syn["ff_steps"][i] + "x"
        syn["digests"][i] = syn["digests"][i] + "x"
    store.rec[("_syn", t0)] = syn
    store.status[("_syn", t0)] = ("complete", "")
    c1 = check_gate(store, "_syn", "fmOFF", [t0], row_override={t0: 100})
    c2 = check_gate(store, "_syn", "fmOFF", [t0], row_override={t0: 101})
    say("      synthetic (differs from step 100): row 100 -> %s | row 101 -> %s" % (
        c1["prefix_viol"] or "no violation", c2["prefix_viol"]))
    chk("control", "prefix boundary: first row 100 passes (steps 1-99), first row 101 fails at step 100",
        (len(c1["prefix_viol"]), c1["prefix_steps"], len(c2["prefix_viol"]),
         bool(c2["prefix_viol"]) and "at step 100 " in c2["prefix_viol"][0]), (0, 99, 1, True))
    res_crn = []
    for fw in (100, 101, 99, None):
        syn["first_write"] = fw
        c = check_crn(store, "_syn", "fmOFF", [t0])
        res_crn.append((c["exact"], c["identical"], len(c["violations"])))
    chk("control", "CRN boundary on synthetic divergence at 100: first write 100 / 101 / 99 / None -> exact,identical,viol",
        res_crn, [(1, 0, 0), (0, 0, 1), (0, 0, 1), (0, 0, 1)])
    del store.rec[("_syn", t0)], store.status[("_syn", t0)]

    say("")
    say("D. IDENTITY CODE")
    ib = identity_block("fmOFF", "fmREF", all23, queue)
    chk("report 1", "fmOFF == fmREF (tag/repo/wall_s excluded)", (ib["same"], ib["complete"]), (23, 23))
    nord = sum(1 for r in ib["res"].values() if r.get("order") == ["burn_intervals"])
    chk("report 1", "runs whose burn_intervals key order differs (values equal)", nord, 22)
    for a_, b_ in (("fmS", "fmOFF"), ("fmE", "fmOFF"), ("fmEF", "fmF")):
        ib = identity_block(a_, b_, CANONICAL, queue, quiet=True)
        keys = sorted({k for r in ib["res"].values() for k in r.get("diff", [])})
        say("      %s vs %s differing keys with only tag/repo/wall_s excluded: %s" % (a_, b_, keys))
        chk("report 2", "%s vs %s: runs complete, differing keys a subset of {params, extra_params}" % (a_, b_),
            (ib["complete"], set(keys) <= {"params", "extra_params"}), (13, True))
        ib = identity_block(a_, b_, CANONICAL, queue, exclude=EXCLUDE_ID + ("params", "extra_params"), quiet=True)
        chk("report 2", "%s == %s with params/extra_params excluded" % (a_, b_), (ib["same"], ib["complete"]), (13, 13))
    ib = identity_block("fmDRY", "fmOFF", CANONICAL[:1], queue)
    chk("control", "identity code detects fmDRY vs fmOFF (east/half/101): not identical", ib["same"], 0)

    fails = [c for c in CHECKS if not c[2]]
    say("")
    say("SELF-TEST SUMMARY: %d checks, %d PASS, %d FAIL" % (len(CHECKS), len(CHECKS) - len(fails), len(fails)))
    by = collections.Counter(c[0] for c in fails)
    for src, n in sorted(by.items()):
        say("  FAIL by source %-12s %d" % (src, n))
    for c in fails:
        say("  FAIL [%s] %s got=%s want=%s" % (c[0], c[1], c[3], c[4]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="both", choices=["canonical", "fresh", "both"])
    ap.add_argument("--arms", default="")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if a.self_test:
        main_selftest(a)
    else:
        main_probe(a)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
