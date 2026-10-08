"""Dispatch round 2, wave W3: THE FROZEN SCRIPT that generates the per-death attribution queue from the W2 (dq1) and W1
(dq0) records (outputs/dispatch2_part1.txt 11.1-11.3, 12.3, 14; amendment A1 section 19): "W3 runs after W2 and BEFORE
the verdict. Its queue is generated mechanically from the W2 records by a frozen script". A port of
outputs/_mvg_w3_queue.py.
It GENERATES A QUEUE ONLY - it never starts a run, and it reads no outcome but the firefighters' death steps and the dq1
records' J decisions and recorded counterfactual.

usage (any cwd; E:/Projects/SAS/.venv/Scripts/python.exe):
  python outputs/_dq_w3_queue.py build --head SHA --part2-notes PATH
        the analyzer's provenance / validity check of the W1 dq0 and W2 dq1 records first (outputs/_dq_analyze.py
        w2_gate(head, notes); both arguments REQUIRED, the values the analyzer is run with), then read the frozen
        queues outputs/_dq_q_w1.jsonl (its 64 dq0 lines) and outputs/_dq_q_w2.jsonl (64 dq1 lines) and their 128
        records, compute 11.1's candidates and 11.2's knockout plan, and write the FROZEN outputs/_dq_q_w3.jsonl and
        outputs/_dq_w3_candidates.json (LF; creates outputs/_dq_w3/ for the replay records and knockout logs). Existing
        files must be identical to the regenerated ones, else STOP (never re-frozen). New files are written only when
        the tag check of their lines passes.
  python outputs/_dq_w3_queue.py check [--resume] [--all-trees]
        regenerate, compare with the frozen files, the replay tool present, the tag check (_dq_queue.tag_check; the
        lines' own knockout logs are judged with their own outputs: absent, or with --resume untracked).
  python outputs/_dq_w3_queue.py show       print the regenerated plan and lines (no write).
  python outputs/_dq_w3_queue.py selftest   known answers on synthetic records (nothing read or written outside a
                                            temporary directory).
W1 AND W2 MUST BE VALID BEFORE W3 IS FROZEN: build calls the analyzer's w2_gate(head, notes) - which must check every
record this script reads (the 64 dq1 W2 records AND the 64 dq0 W1 records) as the analysis will read them - and REFUSES
(STOP, nothing written) unless it passes; a crashed record is not a refusal (its cell becomes UNCOMPUTABLE). The script
then re-checks the record-level validity itself (record_problems: the run line, CRN draws, the instrument versions and
error lists, the recorded dispatch switches against the arm, every J point recorded in dq1 and none in dq0, only known J
event kinds) and STOPs on any problem.

THE RULE (11.1, 11.2; frozen). Per fresh cell (sets 7-8 x ring / uniform x 16 = 64), dq1 (arm 1) against dq0 (arm 0),
CRN, the unit ids the same in both arms; a unit's death step = the first step whose rows_ff row has the dead flag
(rows_ff index i = the state after step i + 1, so step = i + 1):
  (A) dq1-DEATH: U dies at t in dq1 and is ALIVE at t in dq0 (survives there, or dies later);
  (B) dq0-DEATH: U dies at t in dq0 and is ALIVE at t in dq1;
  a death at the same step in both is neither ('same': reported with the C-NONE check).
REPLAYS (outputs/_dq_replay.py on dq1's own W2 run line; only --out and --tag change; --kolog always):
  - R0 for every cell with an (A) or (B) candidate (no knockout);
  - (A): KO-OWN    [{"unit": U, "from": 0, "to": t}];
         KO-LAST   [{"unit": U, "from": s, "to": s, "phase": p}], (s, p) = the LAST J point with step < t at which
                   KO-OWN's override changes a decision of U (pre before post within a step);
         KO-OTHERS [{"unit": "!U", "from": 0, "to": t}];
  - (B): KO-OWN and KO-OTHERS with t = U's dq0 death step.
  THE EMPTY-SET RULE (11.2): a knockout's decision set is the set of changes _dq_replay.jpoint_changes gives on the dq1
  record's J points in its range - J's recorded decisions (dp.j_events: stage-2 fills and stage-4 second fills, refused
  included; stage-3 REPLACE / LATCH-FILL, aborted included) against the recorded counterfactual (dp.j_calls 'legacy',
  11.2's legacy_pairs on J's own snapshot), with the replay's own precedence. An EMPTY set is NOT queued: the knockout
  equals R0 and R0's outcome stands (the analyzer applies that). The candidates file records, per knockout, the size of
  its decision set and its FIRST change (the KO-evidence key: it must be in the replay's ko_applied).
  A record that crashed or stopped early (no complete rows) makes its cell UNCOMPUTABLE: no line, the cell listed (a
  hard clause never passes on missing evidence: its (A) candidates count CAUSED, its (B) candidates not PREVENTED -
  11.3).
NAMES: dqrp_<dq1's W2 name>_R0 and dqrp_<dq1's W2 name>_f<n>_KO{own,last,others} (ff_unit_<n> -> f<n>), records
  outputs/_dq_w3/_sd_<name>.json, knockout logs outputs/_dq_w3/_ko_<name>.json. The candidates file records, with the
  candidates and the planned replays, the sha256 of the W1 and W2 queues and of every record it read: the analyzer
  refuses a W3 whose candidates differ from its own recomputation or whose inputs changed.
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _dq_queue as Q  # noqa: E402  (WT, OUT, PROBE, stop, _lf, _norm, queue_path, queue_bytes, tag_check, ...)
import _dq_replay as R  # noqa: E402  (parse_rules, jpoint_changes, first_change, change_order, PHASE_RANK)

VERSION = "dq_w3_queue v1"
DQ_PROBE = "dq_probe v1"
DP_PROBE = "dp_probe v3"
REPLAY = os.path.join(Q.OUT, "_dq_replay.py")
Q_W1 = Q.queue_path("w1")
Q_W2 = Q.queue_path("w2")
Q_W3 = os.path.join(Q.OUT, "_dq_q_w3.jsonl")
CANDS = os.path.join(Q.OUT, "_dq_w3_candidates.json")
W3_DIR = os.path.join(Q.OUT, "_dq_w3")
N_W1, N_W2 = 128, 64
KO_A = ("KOown", "KOlast", "KOothers")
KO_B = ("KOown", "KOothers")
STAGE_KINDS = {2: ("fill",), 3: ("replace", "latch_fill"), 4: ("second_fill",)}
_NAME = re.compile(r"^dq([R01])([ru])([78])_([A-D]_[NSEW])$")


# ------------------------------------------------------------------------------------------------- pure functions
def j_decisions(d):
    """J's recorded decisions per J point (pure): ([[step, phase, legacy, s2, s3, s4]] in J-point order, unknown event
    kinds). legacy = dp.j_calls' counterfactual [[victim, unit]]; s2 / s4 = stage-2 fill / stage-4 second-fill attempts
    [[victim, unit, ok]] (ok False = *_refused); s3 = stage-3 replacements [[kind, victim, new, [olds], ok]] (ok False =
    *_aborted); nearest_barred (stage 3) carries no bind and is skipped. Any other kind / stage is UNKNOWN."""
    dp = d.get("dp") if isinstance(d.get("dp"), dict) else {}
    by = {}

    def slot(step, phase):
        return by.setdefault((int(step), str(phase)), {"legacy": [], "s2": [], "s3": [], "s4": []})

    for c in dp.get("j_calls") or []:
        if len(c) > 4 and isinstance(c[4], dict) and c[4].get("legacy"):
            slot(c[0], c[1])["legacy"] = [[str(v), str(u)] for v, u in c[4]["legacy"]]
    unknown = []
    for e in dp.get("j_events") or []:
        kind, stage = str(e.get("kind")), e.get("stage")
        ok = not kind.endswith(("_refused", "_aborted"))
        base = kind if ok else kind[:-len("_refused")]
        if stage == 3 and kind == "nearest_barred":
            continue
        if type(stage) is not int or base not in STAGE_KINDS.get(stage, ()):
            unknown.append([e.get("step"), e.get("phase"), kind, stage])
            continue
        s = slot(e.get("step"), e.get("phase"))
        v, u = str(e.get("victim_id")), str(e.get("unit"))
        if stage == 3:
            s["s3"].append([base, v, u, [str(o) for o in e.get("old_units") or []], ok])
        else:
            s["s2" if stage == 2 else "s4"].append([v, u, ok])
    order = sorted(by, key=lambda k: (k[0], R.PHASE_RANK.get(k[1], 9)))
    return [[s, p, by[(s, p)]["legacy"], by[(s, p)]["s2"], by[(s, p)]["s3"], by[(s, p)]["s4"]] for s, p in order], \
        unknown


def compact(d):
    """The W3 inputs of one record (pure): {usable, why, steps, units, ff_dead {unit: first dead step}, jpoints
    (j_decisions), unknown_kinds}. usable = complete rows (not crashed, chain exit code 0 or None, stopped at its last
    step or terminal, one rows_ff row per step done)."""
    rows_ff = d.get("rows_ff") or []
    why = None
    rc = (d.get("dp") or {}).get("rc_chain") if isinstance(d.get("dp"), dict) else None
    stop_at, term = d.get("steps_done"), d.get("terminal_step")
    if d.get("dp_only") or not rows_ff:
        why = "no rows (crashed before the record was written)"
    elif d.get("crashed"):
        why = "crashed %s" % ((d.get("crashed") or {}).get("type"),)
    elif rc not in (0, None):
        why = "chain exit code %s" % rc
    elif not (stop_at == d.get("steps") or (term is not None and stop_at == term)):
        why = "stopped at step %s (terminal %s)" % (stop_at, term)
    elif len(rows_ff) != stop_at:
        why = "rows_ff holds %d steps, steps_done %s" % (len(rows_ff), stop_at)
    units, ff_dead = set(), {}
    for t, row in enumerate(rows_ff):
        for r in row:
            units.add(str(r[0]))
            if r[6] and str(r[0]) not in ff_dead:
                ff_dead[str(r[0])] = t + 1
    jp, unknown = j_decisions(d)
    return {"usable": why is None, "why": why, "steps": len(rows_ff), "units": sorted(units, key=R.id_index),
            "ff_dead": ff_dead, "jpoints": jp, "unknown_kinds": unknown}


def cell_candidates(dead0, dead1):
    """11.1's candidates of one cell: {"A": [[unit, t, t0]], "B": [[unit, t, t1]], "same": [[unit, t]]}, t the
    candidate's step (dq1's death for A, dq0's for B), t0 / t1 the unit's death in the other arm (None = survives).
    dead0 / dead1: {unit: first death step} of dq0 / dq1."""
    res = {"A": [], "B": [], "same": []}
    for u in sorted(set(dead0) | set(dead1), key=R.id_index):
        t0, t1 = dead0.get(u), dead1.get(u)
        if t1 is not None and t0 == t1:
            res["same"].append([u, t1])
        elif t1 is not None and (t0 is None or t0 > t1):
            res["A"].append([u, t1, t0])
        elif t0 is not None and (t1 is None or t1 > t0):
            res["B"].append([u, t0, t1])
    return res


def changes(jpoints, K, lo=0, hi=R.TO_MAX, at=None):
    """The override's changes (_dq_replay.jpoint_changes) over the recorded J points with lo <= step <= hi (and, with
    at = [step, phase], that J point only), in change_order."""
    out = []
    for step, phase, legacy, s2, s3, s4 in jpoints:
        if not lo <= step <= hi or (at is not None and [step, phase] != list(at)):
            continue
        out += R.jpoint_changes(step, phase, legacy, s2, s3, s4, K)
    return sorted(out, key=R.change_order)


def ko_plan(kind, unit, t, jpoints, units):
    """The knockouts of one candidate (kind 'A' or 'B'): ({suffix: rules or None}, {suffix: first change key or None},
    {suffix: decision-set size}). None = the decision set is EMPTY in dq1's record: equal to R0, not run."""
    plan, first, size = collections.OrderedDict(), collections.OrderedDict(), collections.OrderedDict()
    own = changes(jpoints, {unit}, 0, t)
    plan["KOown"] = [{"unit": unit, "from": 0, "to": int(t)}] if own else None
    first["KOown"], size["KOown"] = R.first_change(own), len(own)
    if kind == "A":
        pts = sorted({(c[0], c[1]) for c in own if c[0] < t}, key=lambda p: (p[0], R.PHASE_RANK[p[1]]))
        if pts:
            s, p = pts[-1]
            last = changes(jpoints, {unit}, s, s, at=[s, p])
            plan["KOlast"] = [{"unit": unit, "from": int(s), "to": int(s), "phase": p}]
            first["KOlast"], size["KOlast"] = R.first_change(last), len(last)
        else:
            plan["KOlast"], first["KOlast"], size["KOlast"] = None, None, 0
    others = changes(jpoints, set(units) - {unit}, 0, t)
    plan["KOothers"] = [{"unit": "!" + unit, "from": 0, "to": int(t)}] if others else None
    first["KOothers"], size["KOothers"] = R.first_change(others), len(others)
    return plan, first, size


def unit_short(unit):
    return str(unit).replace("ff_unit_", "f")


def cell_of(name):
    """Queue line name -> (cell id 'set7/ring/A_N', arm 'R' / '0' / '1'), or None."""
    m = _NAME.match(name)
    if not m:
        return None
    return "set%s/%s/%s" % (m.group(3), "ring" if m.group(2) == "r" else "uniform", m.group(4)), m.group(1)


def screen_cells(w1_lines, w2_lines):
    """{cell id: {"0": dq0 line, "1": dq1 line}} in W2's order; STOP on a foreign line or an incomplete cell."""
    cells = collections.OrderedDict()
    for ln in w2_lines:
        c = cell_of(ln["name"])
        if c is None or c[1] != "1":
            Q.stop("W2 queue line %r is not a dq1<p><7|8>_<S>_<W> line" % ln["name"])
        if c[0] in cells:
            Q.stop("W2 cell %s twice" % c[0])
        cells[c[0]] = {"1": ln}
    for ln in w1_lines:
        c = cell_of(ln["name"])
        if c is None or c[1] not in ("R", "0"):
            Q.stop("W1 queue line %r is not a dq<R|0><p><7|8>_<S>_<W> line" % ln["name"])
        if c[1] == "0":
            if c[0] not in cells or "0" in cells[c[0]]:
                Q.stop("W1 dq0 line %s has no W2 cell, or its cell has two" % ln["name"])
            cells[c[0]]["0"] = ln
    for cid, arms in cells.items():
        if set(arms) != {"0", "1"}:
            Q.stop("cell %s has arms %s" % (cid, sorted(arms)))
    return cells


def replay_line(xline, suffix, rules):
    """A W3 queue line: dq1's W2 line through outputs/_dq_replay.py with --kolog and optional --ko; --out / --tag
    replaced, every other probe argument identical."""
    name = "dqrp_%s_%s" % (xline["name"], suffix)
    out = os.path.join(W3_DIR, "_sd_%s.json" % name)
    kolog = os.path.join(W3_DIR, "_ko_%s.json" % name)
    if Q._norm(xline["argv"][0]) != Q._norm(Q.PROBE):
        Q.stop("%s: not a _dq_probe.py line" % xline["name"])
    probe = list(xline["argv"][1:])
    for flag, val in (("--out", out), ("--tag", name)):
        if probe.count(flag) != 1:
            Q.stop("%s: %s not present exactly once" % (xline["name"], flag))
        probe[probe.index(flag) + 1] = val
    argv = [REPLAY, "--kolog", kolog]
    if rules:
        text = json.dumps(rules, separators=(",", ":"))
        if R.parse_rules(text) != rules:
            Q.stop("%s: the rules do not round-trip through _dq_replay.parse_rules" % name)
        argv += ["--ko", text]
    argv += ["--"] + probe
    return {"name": name, "argv": argv, "out": out, "cwd": xline.get("cwd") or Q.WT}


def kolog_of(line):
    a = line["argv"]
    return a[a.index("--kolog") + 1]


def build_plan(w1_lines, w2_lines, compacts):
    """(candidates document without the input hashes, W3 lines) from the W1 / W2 lines and {name: compact(record)}."""
    entries, uncomputable, lines = [], [], []
    for cid, arms in screen_cells(w1_lines, w2_lines).items():
        zl, xl = arms["0"], arms["1"]
        z, x = compacts[zl["name"]], compacts[xl["name"]]
        if not (z["usable"] and x["usable"]):
            uncomputable.append({"cell": cid, "arm": "1", "x": xl["name"], "zero": zl["name"],
                                 "why": "dq0: %s; dq1: %s" % (z["why"] or "ok", x["why"] or "ok")})
            continue
        if z["units"] != x["units"]:
            Q.stop("%s: the unit ids of %s and %s differ" % (cid, zl["name"], xl["name"]))
        cand = cell_candidates(z["ff_dead"], x["ff_dead"])
        if not (cand["A"] or cand["B"] or cand["same"]):
            continue
        entry = {"cell": cid, "set": cid.split("/")[0], "arm": "1", "x": xl["name"], "zero": zl["name"],
                 "A": [], "B": [], "same": [{"unit": u, "t": t} for u, t in cand["same"]], "replays": []}
        if cand["A"] or cand["B"]:
            lines.append(replay_line(xl, "R0", []))
            entry["replays"].append({"name": lines[-1]["name"], "suffix": "R0", "rules": []})
        for kind in ("A", "B"):
            for u, t, other in cand[kind]:
                plan, first, size = ko_plan(kind, u, t, x["jpoints"], x["units"])
                item = {"unit": u, "t": t, ("t0" if kind == "A" else "t1"): other, "ko": {}, "first": dict(first),
                        "n_changes": dict(size)}
                for ko, rules in plan.items():
                    if rules is None:
                        item["ko"][ko] = None
                        continue
                    suffix = "%s_%s" % (unit_short(u), ko)
                    lines.append(replay_line(xl, suffix, rules))
                    item["ko"][ko] = lines[-1]["name"]
                    entry["replays"].append({"name": lines[-1]["name"], "suffix": suffix, "rules": rules})
                entry[kind].append(item)
        entries.append(entry)
    names = [ln["name"].lower() for ln in lines]
    if len(set(names)) != len(names):
        Q.stop("duplicate W3 line names: %s" % sorted(n for n in names if names.count(n) > 1)[:6])
    doc = {"version": VERSION, "rule": "outputs/dispatch2_part1.txt 11.1-11.3 (frozen), 12.3; amendment A1 section 19",
           "entries": entries, "uncomputable": uncomputable,
           "counts": {"cells_with_a_candidate": sum(1 for e in entries if e["A"] or e["B"]),
                      "A": sum(len(e["A"]) for e in entries), "B": sum(len(e["B"]) for e in entries),
                      "same": sum(len(e["same"]) for e in entries), "lines": len(lines),
                      "R0": sum(1 for ln in lines if ln["name"].endswith("_R0")),
                      "knockouts_empty_not_run": sum(1 for e in entries for k in ("A", "B") for c in e[k]
                                                     for v in c["ko"].values() if v is None),
                      "uncomputable": len(uncomputable)}}
    return doc, lines


# ---------------------------------------------------------------------------------------------------------- I/O
def parse_sets(argv):
    res = {}
    for i, tok in enumerate(argv[:-1]):
        if tok == "--set" and "=" in argv[i + 1]:
            k, v = argv[i + 1].split("=", 1)
            try:
                res[k] = int(v)
            except ValueError:
                try:
                    res[k] = float(v)
                except ValueError:
                    res[k] = v
    return res


def record_problems(d, line, arm, comp=None):
    """Record-level validity of one W1 dq0 / W2 dq1 record against its line (a W3 is generated only from valid ones)."""
    why = []
    sd = line["argv"][line["argv"].index("--") + 1:]
    arg = lambda flag: sd[sd.index(flag) + 1] if flag in sd[:-1] else None          # noqa: E731
    if d.get("dp_only"):
        return why                         # a crash: compact() makes the cell uncomputable
    if d.get("argv") != sd:
        why.append("sd argv differs from the queue line")
    if (str(d.get("scenario")), str(d.get("wind")), str(d.get("seed"))) != (arg("--scenario"), arg("--wind"),
                                                                            arg("--seed")):
        why.append("scenario / wind / seed %s/%s/%s differ from the line" % (d.get("scenario"), d.get("wind"),
                                                                             d.get("seed")))
    if d.get("extra_params") != parse_sets(sd):
        why.append("extra_params differ from the line's --set values")
    crn = (d.get("fb3") or {}).get("crn") or {}
    if not d.get("crashed") and not (crn.get("on") and int(crn.get("crn_draws") or 0) > 0):
        why.append("CRN on %s with crn_draws %s" % (crn.get("on"), crn.get("crn_draws")))
    for sec, want in (("dq", DQ_PROBE), ("ud", DQ_PROBE), ("mvg", DQ_PROBE), ("dp", DP_PROBE)):
        if (d.get(sec) or {}).get("probe") != want:
            why.append("%s.probe %r (want %r)" % (sec, (d.get(sec) or {}).get("probe"), want))
    for sec in ("dp", "ud", "mvg", "dq"):
        if (d.get(sec) or {}).get("errors"):
            why.append("instrument errors %s.errors" % sec)
    if not isinstance(d.get("mv_events"), list):
        why.append("no d['mv_events']")
    sw = (d.get("dq") or {}).get("switches") or {}
    on = arm == "1"
    if sw.get("joint_on") is not on or sw.get("reassign_on") is not on:
        why.append("recorded dispatch switches joint_on %r reassign_on %r, arm %s" % (sw.get("joint_on"),
                                                                                      sw.get("reassign_on"), arm))
    comp = comp or compact(d)
    if comp["unknown_kinds"]:
        why.append("unknown J event kinds %s" % comp["unknown_kinds"][:3])
    jc = [(c[0], c[1]) for c in ((d.get("dp") or {}).get("j_calls") or [])]
    if not on and jc:
        why.append("%d J calls recorded in a J-off arm" % len(jc))
    if on and comp["usable"]:
        want = [(s, p) for s in range(1, int(d.get("steps_done") or 0) + 1) for p in ("pre", "post")]
        if jc != want:
            why.append("J points recorded %d, expected pre + post at every step 1..%s (the counterfactual of every J "
                       "point must be in the record)" % (len(jc), d.get("steps_done")))
    return why


def sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _read_queue(path, wave, n):
    if not os.path.exists(path):
        Q.stop("%s is not frozen" % path)
    with open(path, "rb") as fh:
        raw = Q._lf(fh.read(), path)
    lines = [json.loads(x) for x in raw.decode("utf-8").splitlines() if x.strip()]
    if len(lines) != n:
        Q.stop("%s has %d lines, %d expected" % (path, len(lines), n))
    if raw != Q.queue_bytes(Q.wave_lines(wave)):
        Q.stop("%s is not the section-9 queue _dq_queue.py rebuilds" % path)
    return lines, hashlib.sha256(raw).hexdigest()


def read_inputs():
    """(W1 lines, W2 lines, {name: compact}, {name: sha256}, W1 sha256, W2 sha256) from the frozen W1 / W2 queues and
    the 128 records the rule reads (W1's dq0 lines, every W2 line); STOP on a missing record or a record-level
    problem."""
    w1, w1_sha = _read_queue(Q_W1, "w1", N_W1)
    w2, w2_sha = _read_queue(Q_W2, "w2", N_W2)
    wanted = [(ln, "0") for ln in w1 if (cell_of(ln["name"]) or (None, None))[1] == "0"] + [(ln, "1") for ln in w2]
    compacts, shas, bad = {}, {}, []
    for ln, arm in wanted:
        p = ln["out"]
        if not os.path.exists(p):
            bad.append("MISSING %s" % ln["name"])
            continue
        shas[ln["name"]] = sha256_file(p)
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        comp = compact(d)
        why = record_problems(d, ln, arm, comp)
        if why:
            bad.append("INVALID %s: %s" % (ln["name"], "; ".join(why)))
        compacts[ln["name"]] = comp
        d = None
    if bad:
        Q.stop("W1 / W2 are not complete and valid - W3 is never generated from them:\n  " + "\n  ".join(bad[:40]))
    return w1, w2, compacts, shas, w1_sha, w2_sha


def full_doc(doc, shas, w1_sha, w2_sha):
    out = dict(doc)
    out["inputs"] = {"w1_queue": "outputs/_dq_q_w1.jsonl", "w1_queue_sha256": w1_sha,
                     "w2_queue": "outputs/_dq_q_w2.jsonl", "w2_queue_sha256": w2_sha, "records_sha256": shas}
    return out


def doc_bytes(doc):
    return (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("utf-8")


def regenerate():
    w1, w2, compacts, shas, w1_sha, w2_sha = read_inputs()
    doc, lines = build_plan(w1, w2, compacts)
    return full_doc(doc, shas, w1_sha, w2_sha), lines


def tag_check(lines, resume=False, all_trees=False):
    """_dq_queue.tag_check on the W3 lines, with each line's KNOCKOUT LOG judged as one of its own outputs (_dq_queue
    knows the record, .argv, .poollog and stdout only): absent, or with --resume present and untracked. Returns (rows,
    details) as _dq_queue.tag_check."""
    rows, details = Q.tag_check(lines, resume=resume, all_trees=all_trees)
    own = {Q._norm(kolog_of(ln)) for ln in lines}
    tracked = {Q._norm(os.path.join(Q.WT, p.replace("/", os.sep))) for p in Q._git_paths("index")}
    keep, fixed = [], collections.Counter()
    for det in details:
        path = det.split(" ", 3)[-1] if det.startswith("TAG IN USE ") else det.split(" ", 1)[-1]
        if Q._norm(path) in own and resume and Q._norm(path) not in tracked and det.startswith("TAG IN USE "):
            fixed[Q._norm(os.path.dirname(path))] += 1
            continue
        keep.append(det)
    for r in rows:
        n = fixed.get(Q._norm(r[0]), 0)
        if n:
            r[2] = str(int(r[2]) - n)
            if r[2] == "0" and r[4] == "FAIL":
                r[4] = "PASS"
    n_ko = sum(1 for ln in lines if os.path.exists(kolog_of(ln)))
    rows.insert(1, ["own knockout logs (exact paths%s)" % (", --resume" if resume else ""), str(len(lines)),
                    str(n_ko if not resume else 0), "-", "PASS" if (resume or not n_ko) else "FAIL"])
    return rows, keep


def analyzer_gate(head, notes):
    """The analyzer's provenance / validity check of the records W3 reads (outputs/_dq_analyze.py w2_gate(head, notes)
    -> (ok, problems); imported here, not at module level). REFUSED when the analyzer has none."""
    try:
        import _dq_analyze as UA  # noqa: E402
    except Exception as exc:                 # noqa: BLE001 - no analyzer = no precondition = REFUSED
        return False, ["outputs/_dq_analyze.py cannot be imported (%r): the W3 generator's precondition cannot run"
                       % (exc,)]
    fn = getattr(UA, "w2_gate", None)
    if fn is None:
        return False, ["outputs/_dq_analyze.py has no w2_gate(head, notes): the W3 generator's precondition (the "
                       "analyzer's validity check of the W1 dq0 and W2 dq1 records) cannot run"]
    return fn(head, notes)


def _here_check():
    """This script, _dq_queue.py and _dq_replay.py must be the dispatch worktree's outputs/ files (the lines name the
    replay tool there, and the rule is _dq_replay's)."""
    Q._here_check()
    for mod in (sys.modules[__name__], R):
        if Q._norm(os.path.dirname(os.path.abspath(mod.__file__))) != Q._norm(Q.OUT):
            Q.stop("%s is not in %s" % (mod.__file__, Q.OUT))


def build(head=None, notes=None, gate=None) -> int:
    """Freeze W3 (see the module docstring). REFUSES (STOP, nothing written) without --head and --part2-notes or when
    the analyzer's check fails. gate (head, notes) -> (ok, problems): the analyzer's w2_gate by default."""
    _here_check()
    if not head or not notes:
        Q.stop("build needs --head <Part 2 commit> and --part2-notes <path> (the analyzer's W1 / W2 provenance / "
               "validity check runs first, with the same values)")
    ok, problems = (gate or analyzer_gate)(head, notes)
    if not ok:
        Q.stop("the analyzer's provenance / validity check of the W1 / W2 records failed - W3 is never generated from "
               "it:\n  " + "\n  ".join(str(p) for p in list(problems)[:40]))
    print("analyzer check (--head %s, --part2-notes %s): every W1 dq0 / W2 dq1 record present and valid"
          % (head, notes))
    doc, lines = regenerate()
    qb, cb = Q.queue_bytes(lines), doc_bytes(doc)
    states = []
    for path, data in ((Q_W3, qb), (CANDS, cb)):
        if os.path.exists(path):
            with open(path, "rb") as fh:
                if Q._lf(fh.read(), path) != data:
                    Q.stop("%s exists and differs from the regenerated one (frozen; never re-written)" % path)
            states.append("unchanged (frozen)")
        else:
            states.append(None)
    if None in states:
        if any(s is not None for s in states):
            Q.stop("one of %s / %s exists without the other" % (Q_W3, CANDS))
        rows, details = tag_check(lines)
        if any(not r[4].startswith("PASS") for r in rows):
            Q._print_table(rows)
            Q.stop("TAG CHECK FAILED - nothing written:\n  " + "\n  ".join(details[:60]))
        os.makedirs(W3_DIR, exist_ok=True)
        for path, data in ((Q_W3, qb), (CANDS, cb)):
            with open(path, "wb") as fh:
                fh.write(data)
        states = ["written", "written"]
    c = doc["counts"]
    print("W3: %d cells with a candidate | A %d, B %d, same-step %d | %d lines (%d R0) | empty knockouts not run %d | "
          "uncomputable %d" % (c["cells_with_a_candidate"], c["A"], c["B"], c["same"], c["lines"], c["R0"],
                               c["knockouts_empty_not_run"], c["uncomputable"]))
    print("%s sha256 %s %s" % (Q_W3, hashlib.sha256(qb).hexdigest()[:16], states[0]))
    print("%s sha256 %s %s" % (CANDS, hashlib.sha256(cb).hexdigest()[:16], states[1]))
    return 0


def check(resume: bool, all_trees: bool) -> int:
    _here_check()
    doc, lines = regenerate()
    for path, data in ((Q_W3, Q.queue_bytes(lines)), (CANDS, doc_bytes(doc))):
        if not os.path.exists(path):
            Q.stop("%s is not frozen yet (run build)" % path)
        with open(path, "rb") as fh:
            if Q._lf(fh.read(), path) != data:
                Q.stop("%s differs from the regenerated one" % path)
    if not os.path.exists(REPLAY):
        Q.stop("script missing: %s" % REPLAY)
    rows, details = tag_check(lines, resume=resume, all_trees=all_trees)
    Q._print_table(rows)
    for d_ in details[:60]:
        print("    " + d_)
    if any(not r[4].startswith("PASS") for r in rows):
        Q.stop("TAG CHECK FAILED")
    print("w3: %d lines, frozen files identical to the regeneration, replay tool present (sha256 %s), tags unused" % (
        len(lines), sha256_file(REPLAY)[:16]))
    print("pool: %s %s %s %s --maxpar 12 --min-free-gb 3" % (Q.PY, Q.POOL, Q_W3, os.path.join(Q.OUT,
                                                                                             "_mf2_pool_dq_w3.log")))
    return 0


def show() -> int:
    doc, lines = regenerate()
    for e in doc["entries"]:
        print("%-22s A %s  B %s  same %s" % (e["cell"], [(a["unit"], a["t"]) for a in e["A"]],
                                             [(b["unit"], b["t"]) for b in e["B"]],
                                             [(s["unit"], s["t"]) for s in e["same"]]))
    for ln in lines:
        a = ln["argv"]
        print("  %-40s %s" % (ln["name"], a[a.index("--ko") + 1] if "--ko" in a else "(no knockout)"))
    print(json.dumps(doc["counts"]))
    return 0


# ----------------------------------------------------------------------------------------------------- self-test
def _synthetic(deaths, jps, steps=360, crashed=None, units=3, j_on=True):
    """A minimal dq record: rows_ff with dead flags (deaths {unit: step}), dp.j_calls (every J point when j_on; the
    'legacy' dict where jps gives one) and dp.j_events from jps {(step, phase): {"legacy", "s2", "s3", "s4",
    "barred"}}."""
    names = ["ff_unit_%d" % i for i in range(units)]
    rows = []
    for t in range(1, steps + 1):
        rows.append([[u, 1, 1, "x", 0, 0, int(deaths.get(u) is not None and t >= deaths[u]), 0, None, None, 0, None]
                     for u in names])
    calls, events = [], []
    for t in range(1, steps + 1) if j_on else ():
        for p in ("pre", "post"):
            jp = jps.get((t, p)) or {}
            entry = [t, p, 0.1, 0]
            if jp.get("legacy"):
                entry.append({"legacy": sorted(jp["legacy"]), "j_fills": [], "stage3": [], "stage4": []})
            calls.append(entry)
            for v, u, ok in jp.get("s2", []):
                events.append({"step": t, "phase": p, "kind": "fill" if ok else "fill_refused", "stage": 2,
                               "victim_id": v, "unit": u, "old_units": []})
            for k, v, u, olds, ok in jp.get("s3", []):
                events.append({"step": t, "phase": p, "kind": k if ok else k + "_aborted", "stage": 3,
                               "victim_id": v, "unit": u, "old_units": olds})
            for v, inc in jp.get("barred", []):
                events.append({"step": t, "phase": p, "kind": "nearest_barred", "stage": 3, "victim_id": v,
                               "unit": inc, "old_units": [], "barred": ["x"]})
            for v, u, ok in jp.get("s4", []):
                events.append({"step": t, "phase": p, "kind": "second_fill" if ok else "second_fill_refused",
                               "stage": 4, "victim_id": v, "unit": u, "old_units": []})
    return {"rows_ff": rows, "steps": 360, "steps_done": steps, "terminal_step": None, "crashed": crashed,
            "dp": {"rc_chain": 0, "j_calls": calls, "j_events": events}}


def selftest() -> int:
    """Known answers for the rule on synthetic records (no W1 / W2 file is read; nothing is written but a temp dir)."""
    fails, out = [], []

    def case(name, cond, detail=""):
        out.append("%-4s %s%s" % ("PASS" if cond else "FAIL", name, ("  | " + str(detail)[:300]) if detail else ""))
        if not cond:
            fails.append(name)

    U0, U1, U2 = "ff_unit_0", "ff_unit_1", "ff_unit_2"
    swap = {"legacy": [["victim_2", U0], ["victim_3", U1]], "s2": [["victim_2", U1, True], ["victim_3", U0, True]]}
    same16 = {"legacy": [["victim_1", U2]], "s2": [["victim_1", U2, True]]}
    jps1 = {(15, "post"): swap, (16, "post"): same16,
            (20, "pre"): {"legacy": [["victim_4", U2]], "barred": [["victim_9", U1]]},
            (30, "post"): {"s3": [["replace", "victim_5", U1, [U2], True]], "s4": [["victim_6", U2, True]]},
            (50, "post"): {"legacy": [["victim_7", U0]], "s2": [["victim_7", U0, False]]}}
    d1 = _synthetic({U0: 40, U2: 60}, jps1)
    c1 = compact(d1)
    jp = {(s, p): (lg, s2, s3, s4) for s, p, lg, s2, s3, s4 in c1["jpoints"]}
    case("W3-1 compact: deaths from the dead flag (step = index + 1); J points from j_calls 'legacy' and j_events in "
         "J-point order (pre before post); refused / aborted kept with ok False; nearest_barred skipped",
         c1["ff_dead"] == {U0: 40, U2: 60} and c1["usable"] and list(jp) == [(15, "post"), (16, "post"), (20, "pre"),
                                                                           (30, "post"), (50, "post")]
         and jp[(15, "post")][1] == [["victim_2", U1, True], ["victim_3", U0, True]]
         and jp[(30, "post")][2] == [["replace", "victim_5", U1, [U2], True]] and jp[(30, "post")][3] == [
             ["victim_6", U2, True]] and jp[(50, "post")][1] == [["victim_7", U0, False]]
         and jp[(20, "pre")] == ([["victim_4", U2]], [], [], []) and not c1["unknown_kinds"], c1["jpoints"])
    bad_kind = _synthetic({}, {(3, "pre"): {"s2": [["victim_0", U0, True]]}}, steps=5)
    bad_kind["dp"]["j_events"].append({"step": 3, "phase": "pre", "kind": "ko_today", "stage": 2, "victim_id": "v",
                                       "unit": U1})
    bad_kind["dp"]["j_events"].append({"step": 3, "phase": "pre", "kind": "latch_fill", "stage": 2, "victim_id": "v",
                                       "unit": U1})
    case("W3-2 an unknown J event kind / stage (a ko_today of a replay record; a stage-2 latch_fill, round 1's) is "
         "listed, never read as a decision", len(compact(bad_kind)["unknown_kinds"]) == 2,
         compact(bad_kind)["unknown_kinds"])
    c0 = compact(_synthetic({U0: 70, U2: 30, U1: 90}, {}, j_on=False))
    cand = cell_candidates(c0["ff_dead"], {U0: 40, U2: 60, U1: 90})
    case("W3-3 candidates: a death moved EARLIER in dq1 (70 -> 40) is (A) at 40; a death POSTPONED (30 -> 60) is (B) "
         "at 30; a death at the same step is 'same'",
         cand == {"A": [[U0, 40, 70]], "B": [[U2, 30, 60]], "same": [[U1, 90]]}, cand)
    cand2 = cell_candidates({}, {U0: 70})
    cand3 = cell_candidates({U1: 70}, {})
    case("W3-4 a NEW dq1 death is (A) with t0 None; a death dq1 prevented outright is (B) with t1 None",
         cand2 == {"A": [[U0, 70, None]], "B": [], "same": []} and cand3 == {"A": [], "B": [[U1, 70, None]],
                                                                             "same": []}, (cand2, cand3))
    units = c1["units"]
    p_a, f_a, n_a = ko_plan("A", U0, 40, c1["jpoints"], units)
    case("W3-5 (A) U0 at t = 40: KO-OWN 0..40 (the swap at 15 post: 3 changes, first = U0's ko_today at v2); KO-LAST = "
         "15 post (the last J point < 40 where U0's override changes something; 50 is after t); KO-OTHERS !U0 0..40 "
         "(at 15 post U1's swap bind dropped, U1 bound ko_today to v3 and so U0's J bind on v3 dropped - the first "
         "change by unit order; U2's ko_today at 20 pre; the replacement at 30 (one change, its challenger) and U2's "
         "second fill there: 6 changes)",
         p_a == {"KOown": [{"unit": U0, "from": 0, "to": 40}],
                 "KOlast": [{"unit": U0, "from": 15, "to": 15, "phase": "post"}],
                 "KOothers": [{"unit": "!" + U0, "from": 0, "to": 40}]}
         and f_a["KOown"] == [15, "post", U0, "victim_2", "ko_today"] and n_a["KOown"] == 3
         and f_a["KOlast"] == f_a["KOown"] and n_a["KOlast"] == 3
         and f_a["KOothers"] == [15, "post", U0, "victim_3", "drop_victim"] and n_a["KOothers"] == 6,
         (dict(p_a), dict(f_a), dict(n_a)))
    p_e, f_e, n_e = ko_plan("A", U2, 18, c1["jpoints"], units)
    case("W3-6 THE EMPTY-SET RULE: U2's only J decision before 18 equals the counterfactual (16 post) -> KO-OWN and "
         "KO-LAST EMPTY (None, not run); KO-OTHERS non-empty (the swap of the other units)",
         p_e["KOown"] is None and p_e["KOlast"] is None and n_e["KOown"] == 0 and f_e["KOown"] is None
         and p_e["KOothers"] == [{"unit": "!" + U2, "from": 0, "to": 18}], (dict(p_e), dict(n_e)))
    p_b, f_b, n_b = ko_plan("B", U2, 25, c1["jpoints"], units)
    p_t, f_t, n_t = ko_plan("A", U2, 20, c1["jpoints"], units)
    case("W3-7 (B) has KO-OWN and KO-OTHERS only (U2 at t = 25: the counterfactual second claim at 20 pre is a "
         "change); a change AT t counts for KO-OWN, never for KO-LAST ('before t')",
         list(p_b) == ["KOown", "KOothers"] and p_b["KOown"] == [{"unit": U2, "from": 0, "to": 25}]
         and f_b["KOown"] == [20, "pre", U2, "victim_4", "ko_today"]
         and p_t["KOown"] == [{"unit": U2, "from": 0, "to": 20}] and p_t["KOlast"] is None, (dict(p_b), dict(p_t)))
    p_r, f_r, n_r = ko_plan("A", U2, 45, c1["jpoints"], units)
    case("W3-8 a K incumbent of a J REPLACE: drop_release, and its own second fill in that frame drop_bind; KO-LAST "
         "picks 30 post (later than 20 pre)",
         f_r["KOown"] == [20, "pre", U2, "victim_4", "ko_today"] and n_r["KOown"] == 3
         and p_r["KOlast"] == [{"unit": U2, "from": 30, "to": 30, "phase": "post"}]
         and changes(c1["jpoints"], {U2}, 30, 30) == [[30, "post", U2, "victim_5", "drop_release"],
                                                     [30, "post", U2, "victim_6", "drop_bind"]],
         changes(c1["jpoints"], {U2}, 0, 45))
    same_step = {(12, "pre"): {"legacy": [["victim_0", U1]]}, (12, "post"): {"legacy": [["victim_0", U1]]}}
    last2 = ko_plan("A", U1, 20, compact(_synthetic({}, same_step, steps=40))["jpoints"], units)[0]["KOlast"]
    case("W3-9 KO-LAST within one step: post is later than pre", last2 == [{"unit": U1, "from": 12, "to": 12,
                                                                           "phase": "post"}], last2)
    tmp = tempfile.mkdtemp(prefix="dq_w3_selftest_")
    try:
        w1 = [Q.probe_line("R", "r", 7, "A_N", "A", "north", "575201"),
              Q.probe_line("0", "r", 7, "A_N", "A", "north", "575201"),
              Q.probe_line("R", "u", 7, "B_S", "B", "south", "575206"),
              Q.probe_line("0", "u", 7, "B_S", "B", "south", "575206"),
              Q.probe_line("R", "r", 8, "C_E", "C", "east", "741152"),
              Q.probe_line("0", "r", 8, "C_E", "C", "east", "741152")]
        w2 = [Q.probe_line("1", "r", 7, "A_N", "A", "north", "575201"),
              Q.probe_line("1", "u", 7, "B_S", "B", "south", "575206"),
              Q.probe_line("1", "r", 8, "C_E", "C", "east", "741152")]
        comp = {w1[1]["name"]: compact(_synthetic({U0: 70, U2: 30}, {}, j_on=False)),
                w2[0]["name"]: c1,
                w1[3]["name"]: compact(_synthetic({}, {}, j_on=False)),
                w2[1]["name"]: compact(_synthetic({}, {}, steps=200, crashed={"type": "X"})),
                w1[5]["name"]: compact(_synthetic({U1: 50}, {}, j_on=False)),
                w2[2]["name"]: compact(_synthetic({U1: 50}, jps1))}
        doc, lines = build_plan(w1, w2, comp)
        names = [ln["name"] for ln in lines]
        case("W3-10 lines: one R0 per cell with an (A) or (B) candidate, then each non-empty knockout (empty ones not "
             "queued); a cell with only a same-step death has no line; the cell whose dq1 run crashed is "
             "UNCOMPUTABLE (no line, listed)",
             names == ["dqrp_dq1r7_A_N_R0", "dqrp_dq1r7_A_N_f0_KOown", "dqrp_dq1r7_A_N_f0_KOlast",
                       "dqrp_dq1r7_A_N_f0_KOothers", "dqrp_dq1r7_A_N_f2_KOown", "dqrp_dq1r7_A_N_f2_KOothers"]
             and doc["uncomputable"] == [{"cell": "set7/uniform/B_S", "arm": "1", "x": "dq1u7_B_S",
                                          "zero": "dq0u7_B_S", "why": "dq0: ok; dq1: crashed X"}]
             and doc["counts"]["A"] == 1 and doc["counts"]["B"] == 1 and doc["counts"]["same"] == 1
             and doc["counts"]["R0"] == 1, (names, doc["uncomputable"], doc["counts"]))
        r0 = lines[0]
        a = r0["argv"]
        probe_args = a[a.index("--") + 1:]
        x_args = w2[0]["argv"][1:]
        case("W3-11 a line is dq1's W2 run line through _dq_replay.py with --kolog (no --ko for R0), only --out / "
             "--tag replaced; record and knockout log in outputs/_dq_w3/; cwd = the W2 line's",
             a[0] == REPLAY and a[1:3] == ["--kolog", os.path.join(W3_DIR, "_ko_dqrp_dq1r7_A_N_R0.json")]
             and "--ko" not in a and len(probe_args) == len(x_args)
             and [t for i, t in enumerate(probe_args) if probe_args[i - 1] not in ("--out", "--tag")]
             == [t for i, t in enumerate(x_args) if x_args[i - 1] not in ("--out", "--tag")]
             and probe_args[probe_args.index("--tag") + 1] == "dqrp_dq1r7_A_N_R0"
             and r0["out"] == os.path.join(W3_DIR, "_sd_dqrp_dq1r7_A_N_R0.json")
             and probe_args[probe_args.index("--out") + 1] == r0["out"] and r0["cwd"] == w2[0]["cwd"], a)
        ko_args = lines[2]["argv"]
        ko_text = ko_args[ko_args.index("--ko") + 1]
        case("W3-12 a knockout line carries --ko as compact JSON that _dq_replay.parse_rules accepts unchanged",
             ko_text == '[{"unit":"ff_unit_0","from":15,"to":15,"phase":"post"}]'
             and R.parse_rules(ko_text) == [{"unit": U0, "from": 15, "to": 15, "phase": "post"}], ko_text)
        e = doc["entries"][0]
        case("W3-13 the candidates document records each candidate's knockouts by name (None = empty, not run), "
             "their decision-set sizes and first change keys, and the planned replays with their rules",
             e["A"][0]["ko"] == {"KOown": "dqrp_dq1r7_A_N_f0_KOown", "KOlast": "dqrp_dq1r7_A_N_f0_KOlast",
                                 "KOothers": "dqrp_dq1r7_A_N_f0_KOothers"}
             and e["A"][0]["first"]["KOown"] == [15, "post", U0, "victim_2", "ko_today"]
             and e["B"][0]["ko"] == {"KOown": "dqrp_dq1r7_A_N_f2_KOown", "KOothers": "dqrp_dq1r7_A_N_f2_KOothers"}
             and e["B"][0]["t1"] == 60 and len(e["replays"]) == 6 and e["same"] == []
             and doc["entries"][1]["same"] == [{"unit": U1, "t": 50}] and not doc["entries"][1]["replays"], e)
        line = w2[0]
        sd = line["argv"][line["argv"].index("--") + 1:]
        good = {"argv": sd, "scenario": "A", "wind": "north", "seed": 575201, "extra_params": parse_sets(sd),
                "fb3": {"crn": {"on": True, "crn_draws": 7}}, "dq": {"probe": DQ_PROBE, "errors": [],
                                                                      "switches": {"joint_on": True,
                                                                                   "reassign_on": True}},
                "ud": {"probe": DQ_PROBE, "errors": []}, "mvg": {"probe": DQ_PROBE, "errors": []},
                "mv_events": [], "steps_done": 2, "steps": 2, "rows_ff": [[[U0] + [0] * 11]] * 2,
                "dp": {"probe": DP_PROBE, "errors": [], "rc_chain": 0,
                       "j_calls": [[1, "pre"], [1, "post"], [2, "pre"], [2, "post"]], "j_events": []}}
        p_ok = record_problems(good, line, "1")
        p_bad = record_problems(dict(good, fb3={"crn": {"on": True, "crn_draws": 0}},
                                     dq=dict(good["dq"], errors=["x"], switches={"joint_on": False}),
                                     dp=dict(good["dp"], j_calls=[[1, "pre"], [2, "post"]])), line, "1")
        p_zero = record_problems(good, w1[1], "0")
        case("W3-14 record-level validity: a valid dq1 record passes; 0 CRN draws, an instrument error, switches "
             "not the arm's and a missing J point do not; a dq1-shaped record on a dq0 line fails (argv, switches, J "
             "calls in a J-off arm)",
             not p_ok and len(p_bad) == 4 and len(p_zero) >= 3, (p_ok, p_bad, p_zero))
        with open(os.path.join(tmp, "q.jsonl"), "wb") as fh:
            fh.write(Q.queue_bytes(lines))
        with open(os.path.join(tmp, "q.jsonl"), "rb") as fh:
            back = [json.loads(x) for x in fh.read().decode("utf-8").splitlines()]
        case("W3-15 the queue bytes round-trip (LF JSON lines, _mf2_pool.py's format)", back == lines
             and all(sorted(ln) == ["argv", "cwd", "name", "out"] for ln in back))
        stops = []
        for args in ((None, None, None), ("71cfe796", None, None),
                     ("71cfe796", "notes.txt", lambda h, n: (False, ["INVALID dq1r7_A_N: no .argv"]))):
            try:
                build(*args)
                stops.append(None)
            except SystemExit as exc:
                stops.append(str(exc))
        case("W3-16 build REFUSES without --head or --part2-notes, and when the analyzer's check fails (STOP before "
             "any record is read or anything is written)",
             all(s is not None and "needs --head" in s for s in stops[:2]) and stops[2] is not None
             and "validity check of the W1 / W2 records failed" in stops[2] and "no .argv" in stops[2], stops)
        try:
            screen_cells(w1[:1], w2[:1])
            st = None
        except SystemExit as exc:
            st = str(exc)
        case("W3-17 a cell without its dq0 line STOPs", st is not None and "has arms" in st, st)
        # the tag check's knockout-log handling, on a stubbed _dq_queue.tag_check (no listing, no git)
        ko_path = kolog_of(lines[0])
        other = os.path.join(W3_DIR, "_sd_dqrp_dq1r7_A_N_R0_stale.json")
        saved = Q.tag_check, Q._git_paths
        verdicts = []
        try:
            for resume, tracked, hits in ((True, False, [ko_path, other]), (False, False, [ko_path, other]),
                                          (True, True, [ko_path, other]), (True, False, [ko_path])):
                Q.tag_check = lambda ls, resume=False, all_trees=False, h=hits: (
                    [["own outputs", "1", "0", "-", "PASS"], [W3_DIR, "3", str(len(h)), "-", "FAIL"]],
                    ["TAG IN USE " + p for p in h])
                Q._git_paths = (lambda kind, t=tracked: [os.path.relpath(ko_path, Q.WT).replace(os.sep, "/")]
                                if t else [])
                rows, det = tag_check(lines[:1], resume=resume)
                verdicts.append([[r[2], r[4]] for r in rows if r[0] == W3_DIR] + [len(det)])
        finally:
            Q.tag_check, Q._git_paths = saved
        case("W3-18 tag check: a line's own knockout log is judged with its own outputs - with --resume and untracked "
             "it is not a hit (a stale foreign file still is; alone, the row passes); without --resume, or tracked, it "
             "stays a hit", verdicts == [[["1", "FAIL"], 1], [["2", "FAIL"], 2], [["2", "FAIL"], 2],
                                         [["0", "PASS"], 0]], verdicts)
    finally:
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        os.rmdir(tmp)
    out.append("")
    out.append("DQ W3 QUEUE SELF-TEST %s (%d cases, %d failed)" % ("PASS" if not fails else "FAIL", sum(
        1 for x in out if x[:4] in ("PASS", "FAIL")), len(fails)))
    print("\n".join(out))
    return 1 if fails else 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    argv = sys.argv[2:]
    opt = lambda flag: argv[argv.index(flag) + 1] if flag in argv[:-1] else None          # noqa: E731
    if cmd == "build":
        return build(opt("--head"), opt("--part2-notes"))
    if cmd == "check":
        return check("--resume" in argv, "--all-trees" in argv)
    if cmd == "show":
        return show()
    if cmd == "selftest":
        return selftest()
    Q.stop("unknown command %r" % cmd)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
