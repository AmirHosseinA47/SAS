"""MVG round, wave W3: THE FROZEN SCRIPT that generates the per-death attribution queue from the W2 records
(outputs/urgency_part1d.txt amendment 1d.13.2 - the causal safety clause L4 - and 1d.13.3: "the W3 queue is generated
mechanically from the W2 records by a frozen script"). It GENERATES A QUEUE ONLY - it never starts a run, and it reads
no outcome but the firefighters' death steps and the fixes' ACTED events of the W2 records.

usage (from the mvg worktree root, with E:/Projects/SAS/.venv/Scripts/python.exe):
  python outputs/_mvg_w3_queue.py build --head SHA --part2-notes PATH
                                               the analyzer's provenance / validity check of the 192 W2 records first
                                               (below; both arguments REQUIRED, the same values the analyzer is run
                                               with), then read the frozen W2 queue (outputs/_mvg_q_w2.jsonl) and its
                                               192 records, compute 1d.13.2's candidates and knockout set, and write the
                                               FROZEN outputs/_mvg_q_w3.jsonl and outputs/_mvg_w3_candidates.json (LF;
                                               creates outputs/_mvg_w3/ for the replay records). Existing files must be
                                               identical to the regenerated ones, else STOP (never re-frozen).
  python outputs/_mvg_w3_queue.py check [--resume]   regenerate, compare with the frozen files, run the tag check.
  python outputs/_mvg_w3_queue.py show         print the regenerated lines (no write).
  python outputs/_mvg_w3_queue.py selftest     the known-answer self-test on synthetic records (no file is read or
                                               written outside a temporary directory).
W2 MUST BE VALID BEFORE W3 IS FROZEN (review A-4): build imports outputs/_mvg_analyze.py and runs its w2_gate(--head,
--part2-notes) - the analyzer's section 0 (hashed sections, verbatim / module checks, the Part 2d notes, the mutation
record at --head) and section 1's validity of all 192 W2 records exactly as the analysis will read them (the queue line,
the .argv signature, the head rule, the recorded source and instrument shas at --head, CRN, the instrument's errors,
schemas and guard bookkeeping), printed masked, no outcome. It REFUSES (STOP, nothing written) unless every W2 record is
present and valid; a crashed record is not a refusal (its cell-arm becomes UNCOMPUTABLE below). Without this, a W3 built
from a W2 record the analyzer later finds INVALID could never be re-derived (the frozen pair is never re-written). The
script then re-checks the record-level validity itself (the run line, CRN draws, the instrument's version and error
lists) and STOPs on any problem: W3 is never generated from a W2 that is missing or INVALID. `check` and `show` only
regenerate and compare; they do not run the analyzer's check.

THE RULE (1d.13.2, verbatim in substance). Per fresh cell (sets 5-6) and arm X in {G, N} against arm 0 (CRN; the unit
ids are the same in every arm), from each record's rows_ff (a unit's death step = the first step whose row has the
dead flag; rows_ff index t = the state after step t + 1, so step = index + 1):
  (A) X-DEATH: unit U dies at step t in X and is ALIVE at step t in arm 0 (it survives there, or dies later);
  (B) 0-DEATH: unit U dies at step t in arm 0 and is ALIVE at step t in X;
  a death at the same step in X and in arm 0 is neither ('same': reported with review 1.3's C-NONE check).
  REPLAYS (outputs/_mvg_replay.py on X's own W2 run line; only --out and --tag change; boards on):
    - R0 for every cell-arm with an (A) or (B) candidate (no knockout);
    - (A): KO-OWN  {"unit": U, "kinds": "ab", "from": 0, "to": t};
           KO-LAST {"unit": U, "kinds": "ab", "from": s, "to": s}, s = U's last live fix decision before t;
           KO-OTHERS {"unit": "!U", "kinds": "ab", "from": 0, "to": t};
           in G also KO-GUARD {"unit": U, "kinds": "g", "from": 0, "to": t} (U's vetoed decisions taken as fix steps);
    - (B): KO-OWN and KO-OTHERS with t = U's arm-0 death step.
    A LIVE FIX DECISION is an ACTED event of fix (a) / (b) whose step RAN (d["mv_events"] 'ran': the fix's switch on and
    the guard - in G - did not veto it): a knockout acts on the GUARDED decision, and in G a vetoed decision is already
    today's step. A knockout whose decision set is EMPTY in X's record (no live fix decision of U - KO-OWN, KO-LAST -
    or of any other unit - KO-OTHERS - at steps <= t, resp. before t; for KO-GUARD no veto of U at steps <= t) is NOT
    RUN: it equals R0, and R0's outcome is used (the analyzer applies that).
  A record that crashed or stopped early (no complete rows) makes its cell-arm UNCOMPUTABLE: no line is generated, the
  cell-arm is listed, and the analyzer cannot pass L4 on it (a hard clause never passes on missing evidence).
NAMES: mvgrp_<X's W2 name>_R0 and mvgrp_<X's W2 name>_f<n>_KO{own,last,others,guard} (ff_unit_<n> -> f<n>), records
  outputs/_mvg_w3/_sd_<name>.json, boards outputs/_mvg_w3/_bd_<name>.json. The candidates file records, with the
  candidates and the planned replays, the sha256 of the W2 queue and of every W2 record it read: the analyzer refuses a
  W3 whose candidates differ from its own recomputation or whose W2 inputs changed.
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
import _mvg_queue as Q  # noqa: E402  (WT, OUT, W3_DIR, tag_check, queue_bytes, _lf, _rel, stop)

VERSION = "mvg_w3_queue v1"
MVG_PROBE = "mvg_probe v1"
REPLAY = os.path.join(Q.OUT, "_mvg_replay.py")
Q_W2 = os.path.join(Q.OUT, "_mvg_q_w2.jsonl")
Q_W3 = os.path.join(Q.OUT, "_mvg_q_w3.jsonl")
CANDS = os.path.join(Q.OUT, "_mvg_w3_candidates.json")
H = 360
ARM_OF_DIGIT = {"0": "0", "1": "G", "2": "N"}
X_ARMS = ("G", "N")
KO_A = ("KOown", "KOlast", "KOothers", "KOguard")
KO_B = ("KOown", "KOothers")
_W2_NAME = re.compile(r"^mvg([012])([ru])([56])_([A-D]_[NSEW])$")


# ------------------------------------------------------------------------------------------------- pure functions
def compact(d):
    """The W3 inputs of one record (pure): {usable, why, steps, units, ff_dead {unit: first dead step}, events [[step,
    unit, kind, ran, vetoed]] - fix (a) / (b) ACTED events}. usable = complete rows (not crashed, chain exit code 0 or
    None, stopped at its last step or terminal)."""
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
    events = sorted([int(e["step"]), str(e["unit"]), str(e["kind"]), bool(e.get("ran")), bool(e.get("vetoed"))]
                    for e in d.get("mv_events") or [] if e.get("kind") in ("a", "b"))
    return {"usable": why is None, "why": why, "steps": len(rows_ff), "units": sorted(units), "ff_dead": ff_dead,
            "events": events}


def cell_candidates(dead0, deadx):
    """1d.13.2's candidates of one cell-arm: {"A": [[unit, t, t0]], "B": [[unit, t, tx]], "same": [[unit, t]]} with t
    the candidate's step (X's death for A, arm 0's for B), t0 / tx the unit's death in the other arm (None = survives).
    dead0 / deadx: {unit: first death step} of arm 0 / X."""
    res = {"A": [], "B": [], "same": []}
    for u in sorted(set(dead0) | set(deadx)):
        t0, tx = dead0.get(u), deadx.get(u)
        if tx is not None and t0 == tx:
            res["same"].append([u, tx])
        elif tx is not None and (t0 is None or t0 > tx):
            res["A"].append([u, tx, t0])
        elif t0 is not None and (tx is None or tx > t0):
            res["B"].append([u, t0, tx])
    return res


def rule(unit, kinds, lo, hi):
    return [{"unit": unit, "kinds": kinds, "from": int(lo), "to": int(hi)}]


def ko_plan(kind, unit, t, events, arm):
    """The knockouts of one candidate (kind 'A' or 'B'), {suffix: rules or None}; None = the decision set is EMPTY in X's
    record, so the replay equals R0 and is not run. events: [[step, unit, kind, ran, vetoed]] of X."""
    own = [e for e in events if e[1] == unit and e[3] and e[0] <= t]
    others = [e for e in events if e[1] != unit and e[3] and e[0] <= t]
    plan = collections.OrderedDict()
    plan["KOown"] = rule(unit, "ab", 0, t) if own else None
    if kind == "A":
        before = [e for e in own if e[0] < t]
        s = max(e[0] for e in before) if before else None
        plan["KOlast"] = rule(unit, "ab", s, s) if s is not None else None
    plan["KOothers"] = rule("!" + unit, "ab", 0, t) if others else None
    if kind == "A" and arm == "G":
        vetoes = [e for e in events if e[1] == unit and e[4] and e[0] <= t]
        plan["KOguard"] = rule(unit, "g", 0, t) if vetoes else None
    return plan


def unit_short(unit):
    return str(unit).replace("ff_unit_", "f")


def cell_of(name):
    """W2 line name -> (cell id 'set5/ring/A_N', arm '0' / 'G' / 'N'), or None."""
    m = _W2_NAME.match(name)
    if not m:
        return None
    return "set%s/%s/%s" % (m.group(3), "ring" if m.group(2) == "r" else "uniform", m.group(4)), ARM_OF_DIGIT[m.group(1)]


def w2_cells(w2_lines):
    """{cell id: {"0": line, "G": line, "N": line}} in queue order; STOP on a foreign line or an incomplete cell."""
    cells = collections.OrderedDict()
    for ln in w2_lines:
        c = cell_of(ln["name"])
        if c is None:
            Q.stop("W2 queue line %r is not a mvg<a><p><5|6>_<S>_<W> line" % ln["name"])
        cells.setdefault(c[0], {})[c[1]] = ln
    for cid, arms in cells.items():
        if set(arms) != {"0", "G", "N"}:
            Q.stop("W2 cell %s has arms %s" % (cid, sorted(arms)))
    return cells


def replay_line(xline, suffix, rules):
    """A W3 queue line: X's W2 line through outputs/_mvg_replay.py with boards, optional --ko, --out / --tag replaced."""
    name = "mvgrp_%s_%s" % (xline["name"], suffix)
    out = os.path.join(Q.W3_DIR, "_sd_%s.json" % name)
    boards = os.path.join(Q.W3_DIR, "_bd_%s.json" % name)
    probe = list(xline["argv"][1:])
    if os.path.normcase(xline["argv"][0]) != os.path.normcase(os.path.join(Q.OUT, "_mvg_probe.py")):
        Q.stop("%s: not a _mvg_probe.py line" % xline["name"])
    for flag, val in (("--out", out), ("--tag", name)):
        if probe.count(flag) != 1:
            Q.stop("%s: %s not present exactly once" % (xline["name"], flag))
        probe[probe.index(flag) + 1] = val
    argv = [REPLAY, "--boards", boards]
    if rules:
        argv += ["--ko", json.dumps(rules, separators=(",", ":"))]
    argv += ["--"] + probe
    return {"name": name, "argv": argv, "out": out, "cwd": xline.get("cwd") or Q.WT}


def build_plan(w2_lines, compacts):
    """(candidates document without the input hashes, W3 lines) from the W2 lines and {W2 name: compact(record)}."""
    entries, uncomputable, lines = [], [], []
    for cid, arms in w2_cells(w2_lines).items():
        z = compacts[arms["0"]["name"]]
        for arm in X_ARMS:
            xl = arms[arm]
            x = compacts[xl["name"]]
            if not (z["usable"] and x["usable"]):
                uncomputable.append({"cell": cid, "arm": arm, "x": xl["name"], "zero": arms["0"]["name"],
                                     "why": "arm 0: %s; %s: %s" % (z["why"] or "ok", arm, x["why"] or "ok")})
                continue
            if z["units"] != x["units"]:
                Q.stop("%s: the unit ids of %s and %s differ" % (cid, arms["0"]["name"], xl["name"]))
            cand = cell_candidates(z["ff_dead"], x["ff_dead"])
            if not (cand["A"] or cand["B"] or cand["same"]):
                continue
            entry = {"cell": cid, "set": cid.split("/")[0], "arm": arm, "x": xl["name"], "zero": arms["0"]["name"],
                     "A": [], "B": [], "same": [{"unit": u, "t": t} for u, t in cand["same"]], "replays": []}
            if cand["A"] or cand["B"]:
                lines.append(replay_line(xl, "R0", []))
                entry["replays"].append({"name": lines[-1]["name"], "suffix": "R0", "rules": []})
            for kind in ("A", "B"):
                for u, t, other in cand[kind]:
                    plan = ko_plan(kind, u, t, x["events"], arm)
                    item = {"unit": u, "t": t, ("t0" if kind == "A" else "tx"): other, "ko": {}}
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
    names = [ln["name"] for ln in lines]
    if len(set(names)) != len(names):
        Q.stop("duplicate W3 line names: %s" % sorted(n for n in names if names.count(n) > 1)[:6])
    doc = {"version": VERSION, "rule": "outputs/urgency_part1d.txt 1d.13.2", "entries": entries,
           "uncomputable": uncomputable,
           "counts": {"cell_arms_with_a_candidate": sum(1 for e in entries if e["A"] or e["B"]),
                      "A": sum(len(e["A"]) for e in entries), "B": sum(len(e["B"]) for e in entries),
                      "same": sum(len(e["same"]) for e in entries), "lines": len(lines),
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


def record_problems(d, line):
    """Record-level validity of one W2 record against its line (a W3 is generated only from a valid W2)."""
    why = []
    sd = line["argv"][line["argv"].index("--") + 1:]
    arg = lambda flag: sd[sd.index(flag) + 1] if flag in sd[:-1] else None          # noqa: E731
    if d.get("dp_only"):
        return why                         # a crash: compact() makes the cell-arm uncomputable
    if d.get("argv") != sd:
        why.append("sd argv differs from the W2 line")
    if (str(d.get("scenario")), str(d.get("wind")), str(d.get("seed"))) != (arg("--scenario"), arg("--wind"),
                                                                            arg("--seed")):
        why.append("scenario / wind / seed %s/%s/%s differ from the line" % (d.get("scenario"), d.get("wind"),
                                                                             d.get("seed")))
    if d.get("extra_params") != parse_sets(sd):
        why.append("extra_params differ from the line's --set values")
    crn = (d.get("fb3") or {}).get("crn") or {}
    if not d.get("crashed") and not (crn.get("on") and int(crn.get("crn_draws") or 0) > 0):
        why.append("CRN on %s with crn_draws %s" % (crn.get("on"), crn.get("crn_draws")))
    for sec in ("ud", "mvg"):
        if (d.get(sec) or {}).get("probe") != MVG_PROBE:
            why.append("%s.probe %r" % (sec, (d.get(sec) or {}).get("probe")))
    for sec in ("dp", "ud", "mvg"):
        if (d.get(sec) or {}).get("errors"):
            why.append("instrument errors %s.errors" % sec)
    if not isinstance(d.get("mv_events"), list):
        why.append("no d['mv_events']")
    return why


def sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def read_w2():
    """(W2 lines, {name: compact}, {name: sha256}, W2 queue sha256) from the frozen W2 queue and its records; STOP on
    a missing record or a record-level problem."""
    if not os.path.exists(Q_W2):
        Q.stop("%s is not frozen" % Q_W2)
    with open(Q_W2, "rb") as fh:
        raw = Q._lf(fh.read(), Q._rel(Q_W2))
    w2 = [json.loads(x) for x in raw.decode("utf-8").splitlines() if x.strip()]
    if len(w2) != 192:
        Q.stop("the W2 queue has %d lines, 192 expected" % len(w2))
    compacts, shas, bad = {}, {}, []
    for ln in w2:
        p = ln["out"]
        if not os.path.exists(p):
            bad.append("MISSING %s" % ln["name"])
            continue
        shas[ln["name"]] = sha256_file(p)
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        why = record_problems(d, ln)
        if why:
            bad.append("INVALID %s: %s" % (ln["name"], "; ".join(why)))
        compacts[ln["name"]] = compact(d)
        d = None
    if bad:
        Q.stop("W2 is not complete and valid - W3 is never generated from it:\n  " + "\n  ".join(bad[:40]))
    return w2, compacts, shas, hashlib.sha256(raw).hexdigest()


def full_doc(doc, shas, w2_sha):
    out = dict(doc)
    out["inputs"] = {"w2_queue": "outputs/_mvg_q_w2.jsonl", "w2_queue_sha256": w2_sha, "records_sha256": shas}
    return out


def doc_bytes(doc):
    return (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("utf-8")


def regenerate():
    w2, compacts, shas, w2_sha = read_w2()
    doc, lines = build_plan(w2, compacts)
    return full_doc(doc, shas, w2_sha), lines


def analyzer_gate(head, notes):
    """The analyzer's provenance / validity check of the 192 W2 records (outputs/_mvg_analyze.py w2_gate; imported
    here, not at module level: the analyzer imports this module for the frozen rule). Returns (ok, problems)."""
    import _mvg_analyze as UA  # noqa: E402
    return UA.w2_gate(head, notes)


def build(head=None, notes=None, gate=None) -> int:
    """Freeze W3 (see the module docstring). REFUSES (STOP, nothing written) without --head and --part2-notes or when
    the analyzer's W2 check fails. gate (head, notes) -> (ok, problems): the analyzer's w2_gate by default (the
    analyzer self-test passes its section-1 check on synthetic records)."""
    Q._here_check()
    if not head or not notes:
        Q.stop("build needs --head <Part 2d commit> and --part2-notes <path> (the analyzer's W2 provenance / validity "
               "check runs first, with the same values)")
    ok, problems = (gate or analyzer_gate)(head, notes)
    if not ok:
        Q.stop("the analyzer's provenance / validity check of the W2 records failed - W3 is never generated from "
               "it:\n  " + "\n  ".join(str(p) for p in list(problems)[:40]))
    print("analyzer W2 check (--head %s, --part2-notes %s): every W2 record present and valid" % (head, notes))
    doc, lines = regenerate()
    qb, cb = Q.queue_bytes(lines), doc_bytes(doc)
    states = []
    for path, data in ((Q_W3, qb), (CANDS, cb)):
        if os.path.exists(path):
            with open(path, "rb") as fh:
                if Q._lf(fh.read(), Q._rel(path)) != data:
                    Q.stop("%s exists and differs from the regenerated one (frozen; never re-written)" % path)
            states.append("unchanged (frozen)")
        else:
            states.append(None)
    if None in states:
        if any(s is not None for s in states):
            Q.stop("one of %s / %s exists without the other" % (Q_W3, CANDS))
        bad = Q.tag_check(lines)
        if bad:
            Q.stop("TAG CHECK FAILED:\n  " + "\n  ".join(bad[:60]))
        os.makedirs(Q.W3_DIR, exist_ok=True)
        for path, data in ((Q_W3, qb), (CANDS, cb)):
            with open(path, "wb") as fh:
                fh.write(data)
        states = ["written", "written"]
    c = doc["counts"]
    print("W3: %d cell-arms with a candidate | A %d, B %d, same-step %d | %d lines | uncomputable %d" % (
        c["cell_arms_with_a_candidate"], c["A"], c["B"], c["same"], c["lines"], c["uncomputable"]))
    print("%s sha256 %s %s" % (Q._rel(Q_W3), hashlib.sha256(qb).hexdigest()[:16], states[0]))
    print("%s sha256 %s %s" % (Q._rel(CANDS), hashlib.sha256(cb).hexdigest()[:16], states[1]))
    return 0


def check(resume: bool) -> int:
    Q._here_check()
    doc, lines = regenerate()
    for path, data in ((Q_W3, Q.queue_bytes(lines)), (CANDS, doc_bytes(doc))):
        if not os.path.exists(path):
            Q.stop("%s is not frozen yet (run build)" % path)
        with open(path, "rb") as fh:
            if Q._lf(fh.read(), Q._rel(path)) != data:
                Q.stop("%s differs from the regenerated one" % path)
    if not os.path.exists(REPLAY):
        Q.stop("script missing: %s" % REPLAY)
    bad = Q.tag_check(lines, resume=resume)
    if bad:
        Q.stop("TAG CHECK FAILED:\n  " + "\n  ".join(bad[:60]))
    print("w3: %d lines, frozen files identical to the regeneration, script present, tags unused" % len(lines))
    print("pool: <py> %s %s %s --maxpar 12 --min-free-gb 3" % (
        os.path.join(Q.OUT, "_mf2_pool.py"), Q_W3, os.path.join(Q.OUT, "_mf2_pool_mvg_w3.log")))
    return 0


def show() -> int:
    doc, lines = regenerate()
    for e in doc["entries"]:
        print("%-22s %s  A %s  B %s  same %s" % (e["cell"], e["arm"], [(a["unit"], a["t"]) for a in e["A"]],
                                                 [(b["unit"], b["t"]) for b in e["B"]],
                                                 [(s["unit"], s["t"]) for s in e["same"]]))
    for ln in lines:
        a = ln["argv"]
        print("  %-36s %s" % (ln["name"], a[a.index("--ko") + 1] if "--ko" in a else "(no knockout)"))
    print(json.dumps(doc["counts"]))
    return 0


# ----------------------------------------------------------------------------------------------------- self-test
def selftest() -> int:
    """Known answers for the rule on synthetic records (no W2 file is read; nothing is written but a temp dir)."""
    fails, lines_out = [], []

    def case(name, cond, detail=""):
        lines_out.append("%-4s %s%s" % ("PASS" if cond else "FAIL", name, ("  | " + str(detail)[:300]) if detail else ""))
        if not cond:
            fails.append(name)

    def rec(deaths, events, steps=360, crashed=None):
        rows = []
        for t in range(1, steps + 1):
            rows.append([["ff_unit_%d" % i, 1, 1, "x", 0, 0, int(deaths.get("ff_unit_%d" % i) is not None
                                                                   and t >= deaths["ff_unit_%d" % i]), 0, None, None,
                          0, None] for i in range(3)])
        ev = [{"step": s, "unit": u, "kind": k, "ran": r, "vetoed": v, "live": True} for s, u, k, r, v in events]
        return {"rows_ff": rows, "mv_events": ev, "steps": 360, "steps_done": steps, "terminal_step": None,
                "crashed": crashed, "dp": {"rc_chain": 0}}

    U0, U1, U2 = "ff_unit_0", "ff_unit_1", "ff_unit_2"
    c0 = compact(rec({U0: 60, U2: 30}, []))
    ev_g = [(10, U0, "a", True, False), (20, U0, "a", False, True), (25, U0, "b", True, False),
            (12, U1, "a", True, False), (45, U1, "a", True, False), (50, U0, "a", True, False)]
    cg = compact(rec({U0: 40, U2: 50}, ev_g))
    case("W3-1 compact: death steps from the dead flag (step = index + 1), ACTED events of (a) / (b) with ran / vetoed",
         c0["ff_dead"] == {U0: 60, U2: 30} and cg["ff_dead"] == {U0: 40, U2: 50} and cg["usable"]
         and cg["events"][0] == [10, U0, "a", True, False] and len(cg["events"]) == 6, (c0, cg["ff_dead"]))
    cand = cell_candidates(c0["ff_dead"], cg["ff_dead"])
    case("W3-2 candidates: a death moved EARLIER (60 -> 40) is (A) at 40; a death POSTPONED (30 -> 50) is (B) at 30",
         cand == {"A": [[U0, 40, 60]], "B": [[U2, 30, 50]], "same": []}, cand)
    cand2 = cell_candidates({U1: 33}, {U0: 70, U1: 33})
    cand3 = cell_candidates({U0: 70}, {})
    case("W3-3 a NEW death (alive throughout arm 0) is (A); a death at the same step is neither ('same'); a death "
         "the arm prevented outright is (B) with tx None",
         cand2 == {"A": [[U0, 70, None]], "B": [], "same": [[U1, 33]]}
         and cand3 == {"A": [], "B": [[U0, 70, None]], "same": []}, (cand2, cand3))
    plan = ko_plan("A", U0, 40, cg["events"], "G")
    case("W3-4 (A) in G at t = 40: KO-OWN 0..40 (U's ran steps 10, 25); KO-LAST = its last ran decision before 40 "
         "(25, kinds 'ab' as the urgency review); KO-OTHERS !U 0..40 (ff_unit_1 ran at 12); KO-GUARD 0..40 (U's veto at "
         "20); events after t do not count",
         plan == {"KOown": rule(U0, "ab", 0, 40), "KOlast": rule(U0, "ab", 25, 25),
                  "KOothers": rule("!" + U0, "ab", 0, 40), "KOguard": rule(U0, "g", 0, 40)}, dict(plan))
    plan_n = ko_plan("A", U0, 40, cg["events"], "N")
    plan_b = ko_plan("B", U2, 30, cg["events"], "G")
    case("W3-5 arm N has no KO-GUARD; a (B) candidate has KO-OWN and KO-OTHERS only, with t = arm 0's death step "
         "(ff_unit_2 never ran a fix step: KO-OWN EMPTY -> not run; others ran before 30 -> KO-OTHERS 0..30)",
         list(plan_n) == ["KOown", "KOlast", "KOothers"] and plan_b == {"KOown": None,
                                                                       "KOothers": rule("!" + U2, "ab", 0, 30)},
         (dict(plan_n), dict(plan_b)))
    only_veto = [(15, U1, "a", False, True), (16, U1, "a", False, True)]
    p_v = ko_plan("A", U1, 30, only_veto, "G")
    p_e = ko_plan("A", U1, 30, [(30, U1, "a", True, False)], "G")
    case("W3-6 a unit whose decisions were all VETOED in G: KO-OWN and KO-LAST empty (a vetoed decision is already "
         "today's step), KO-OTHERS empty, KO-GUARD runs; a ran decision AT t is in KO-OWN but not KO-LAST ('before t')",
         p_v == {"KOown": None, "KOlast": None, "KOothers": None, "KOguard": rule(U1, "g", 0, 30)}
         and p_e["KOown"] == rule(U1, "ab", 0, 30) and p_e["KOlast"] is None, (dict(p_v), dict(p_e)))
    tmp = tempfile.mkdtemp(prefix="mvg_w3_selftest_")
    try:
        w2 = []
        for a in (0, 1, 2):
            ln = Q.probe_line("mvg%dr5" % a, "A_N", "A", "north", "135961", Q.arm_sets(a, 0))
            w2.append(ln)
        for a in (0, 1, 2):
            w2.append(Q.probe_line("mvg%du5" % a, "B_S", "B", "south", "135966", Q.arm_sets(a, 1)))
        comp = {w2[0]["name"]: c0, w2[1]["name"]: cg, w2[2]["name"]: compact(rec({U0: 60, U2: 30}, [])),
                w2[3]["name"]: compact(rec({}, [])), w2[4]["name"]: compact(rec({}, [], steps=200, crashed={"type": "X"})),
                w2[5]["name"]: compact(rec({}, []))}
        doc, lines = build_plan(w2, comp)
        names = [ln["name"] for ln in lines]
        r0 = lines[0]
        a = r0["argv"]
        probe_args = a[a.index("--") + 1:]
        case("W3-7 lines: one R0 per cell-arm with a candidate (G of A_N; arm N equals arm 0 there -> no line), then "
             "each non-empty knockout; names mvgrp_<W2 name>_<suffix>; the cell whose G run crashed is UNCOMPUTABLE "
             "(no line, listed)",
             names == ["mvgrp_mvg1r5_A_N_R0", "mvgrp_mvg1r5_A_N_f0_KOown", "mvgrp_mvg1r5_A_N_f0_KOlast",
                       "mvgrp_mvg1r5_A_N_f0_KOothers", "mvgrp_mvg1r5_A_N_f0_KOguard", "mvgrp_mvg1r5_A_N_f2_KOothers"]
             and doc["uncomputable"] and doc["uncomputable"][0]["cell"] == "set5/uniform/B_S"
             and doc["uncomputable"][0]["arm"] == "G" and doc["counts"]["A"] == 1 and doc["counts"]["B"] == 1,
             (names, doc["uncomputable"]))
        case("W3-8 a line is X's W2 run line through _mvg_replay.py with --boards (no --ko for R0), only --out / --tag "
             "replaced (the probe arguments otherwise identical), records in outputs/_mvg_w3/",
             a[0] == REPLAY and a[1] == "--boards" and "--ko" not in a
             and probe_args[:probe_args.index("--out")] == w2[1]["argv"][1:w2[1]["argv"].index("--out")]
             and probe_args[probe_args.index("--tag") + 1] == "mvgrp_mvg1r5_A_N_R0"
             and os.path.dirname(r0["out"]) == Q.W3_DIR and r0["cwd"] == Q.WT, a)
        ko_line = lines[1]["argv"]
        case("W3-9 a knockout line carries --ko as compact JSON, the rule exactly as _mvg_replay.py parses it",
             ko_line[ko_line.index("--ko") + 1] == '[{"unit":"ff_unit_0","kinds":"ab","from":0,"to":40}]', ko_line)
        e = doc["entries"][0]
        case("W3-10 the candidates document records each candidate's knockouts by name (None = empty, not run) and "
             "the planned replays with their rules",
             e["A"][0]["ko"] == {"KOown": "mvgrp_mvg1r5_A_N_f0_KOown", "KOlast": "mvgrp_mvg1r5_A_N_f0_KOlast",
                                 "KOothers": "mvgrp_mvg1r5_A_N_f0_KOothers", "KOguard": "mvgrp_mvg1r5_A_N_f0_KOguard"}
             and e["B"][0]["ko"] == {"KOown": None, "KOothers": "mvgrp_mvg1r5_A_N_f2_KOothers"}
             and len(e["replays"]) == 6, e)
        bad_line = dict(w2[1], argv=[a_ for a_ in w2[1]["argv"]])
        d_ok = {"argv": w2[1]["argv"][w2[1]["argv"].index("--") + 1:], "scenario": "A", "wind": "north",
                "seed": 135961, "extra_params": parse_sets(w2[1]["argv"]), "fb3": {"crn": {"on": True, "crn_draws": 7}},
                "ud": {"probe": MVG_PROBE, "errors": []}, "mvg": {"probe": MVG_PROBE, "errors": []},
                "dp": {"errors": []}, "mv_events": []}
        p_ok = record_problems(d_ok, bad_line)
        p_bad = record_problems(dict(d_ok, fb3={"crn": {"on": True, "crn_draws": 0}},
                                     mvg={"probe": MVG_PROBE, "errors": ["x"]}), bad_line)
        case("W3-11 record-level validity: a valid record passes; 0 CRN draws and an instrument error do not",
             not p_ok and len(p_bad) == 2, (p_ok, p_bad))
        with open(os.path.join(tmp, "q.jsonl"), "wb") as fh:
            fh.write(Q.queue_bytes(lines))
        with open(os.path.join(tmp, "q.jsonl"), "rb") as fh:
            back = [json.loads(x) for x in fh.read().decode("utf-8").splitlines()]
        case("W3-12 the queue bytes round-trip (LF JSON lines)", back == lines)
        stops = []
        for args in ((None, None, None), ("6ebeadc6", None, None),
                     ("6ebeadc6", "notes.txt", lambda h, n: (False, ["INVALID G set5/ring/A_N: no .argv"]))):
            try:
                build(*args)
                stops.append(None)
            except SystemExit as exc:
                stops.append(str(exc))
        case("W3-13 build REFUSES without --head or --part2-notes, and when the analyzer's W2 check fails (STOP before "
             "the W2 records are read or anything is written; the analyzer self-test runs the real check on an INVALID "
             "W2 record)",
             all(s is not None and "needs --head" in s for s in stops[:2]) and stops[2] is not None
             and "provenance / validity check of the W2 records failed" in stops[2] and "no .argv" in stops[2], stops)
    finally:
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        os.rmdir(tmp)
    lines_out.append("")
    lines_out.append("W3 QUEUE SELF-TEST %s (%d cases, %d failed)" % ("PASS" if not fails else "FAIL", sum(
        1 for x in lines_out if x.startswith(("PASS", "FAIL"))), len(fails)))
    print("\n".join(lines_out))
    return 1 if fails else 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "build":
        argv = sys.argv[2:]
        opt = lambda flag: argv[argv.index(flag) + 1] if flag in argv[:-1] else None          # noqa: E731
        return build(opt("--head"), opt("--part2-notes"))
    if cmd == "check":
        return check("--resume" in sys.argv)
    if cmd == "show":
        return show()
    if cmd == "selftest":
        return selftest()
    Q.stop("unknown command %r" % cmd)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
