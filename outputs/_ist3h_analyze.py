"""isTrue round Part 3: the HARNESS identity gates (Part 1 5.1 G1-c / 5.2 G2) over outputs/_ist3h_q.jsonl.

usage: _ist3h_analyze.py [--partial]

Reads outputs/_ist3h_q.jsonl (re-derived by outputs/_ist3h_queue.py first: STOP on any difference),
outputs/_ist3h_launch.json (the hashes of the harness-run files at launch; compared with now), each line's --out JSON,
its <stem>.stdout.txt (the model's console output as the harness captured it) and the pool's <out>.poollog, and
Part 1's census records outputs/_ist_<cid>.json (f686e932 code, probe v1 / v2, record-only by Part 1 3.0 (c)).

The harness JSON has no MR1 field (MR1 is read by nothing the harness records), so EVERY gate is a full identity:
  H-V   per run: JSON present, steps 360, repo == the arm's checkout, extra_params == the line's --set dict
  H-A   B vs F12   every field equal (the whole round changes nothing the harness records)
  H-B   F1 vs F12  every field equal (F-2)
  H-C   B vs F1    every field equal (F-1)
  H-K   B vs K     every field equal (both kill switches)
  H-OUT the four arms' <stem>.stdout.txt byte-identical (raw bytes)
  H-LOG the four arms' pool logs equal (tag, wall-clock tokens and checkout paths normalised)
  H-P1  B vs Part 1's census record of the same configuration (and, for S_east_101, the bare run and the S2 repeat):
        every field equal - the harness is deterministic across the two rounds
IGNORED: wall_s, tag, repo; params / extra_params are compared without the two isTrue switch keys.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IGNORED = {"wall_s", "tag", "repo"}
ARM_KEYS = {"MR1_TRUTHINESS_FIX", "NUMPY_SCALAR_FLAGS"}
LAUNCH_FILES = ("_ffr_harness.py", "_mf2_pool.py", "_ist3h_queue.py", "_ist3h_q.jsonl")
WALL_RE = re.compile(r"wall=\S+")


def _sha(path) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def _parse(v: str):
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    return v


def strip(d: dict) -> dict:
    out = {k: v for k, v in d.items() if k not in IGNORED}
    for k in ("params", "extra_params"):
        if isinstance(out.get(k), dict):
            out[k] = {x: v for x, v in out[k].items() if x not in ARM_KEYS}
    return out


def diff(a: dict, b: dict) -> list[str]:
    sa, sb = strip(a), strip(b)
    return [k for k in sorted(set(sa) | set(sb)) if sa.get(k, "<absent>") != sb.get(k, "<absent>")]


def poollog(path, tag, repos) -> list[str]:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return ["<missing poollog>"]
    out = []
    for ln in lines:
        if ln.startswith(tag + " "):           # the harness summary line starts with its --tag
            ln = "<TAG>" + ln[len(tag):]
        for r in repos:
            ln = ln.replace(r, "<REPO>").replace(r.replace("\\", "/"), "<REPO>")
        out.append(WALL_RE.sub("<t>", ln))
    return out


def main() -> int:
    sys.stdout.reconfigure(newline="\n")
    partial = "--partial" in sys.argv[1:]
    spec = importlib.util.spec_from_file_location("q", os.path.join(HERE, "_ist3h_queue.py"))
    Q = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(Q)
    with open(Q.QUEUE, encoding="utf-8") as f:
        if f.read() != Q.text():
            print("STOP: outputs/_ist3h_q.jsonl differs from its generator")
            return 3
    problems = []
    try:
        launch = json.load(open(os.path.join(HERE, "_ist3h_launch.json"), encoding="utf-8"))
        now = {f: _sha(os.path.join(HERE, f)) for f in LAUNCH_FILES}
        if launch.get("sha") != now:
            problems.append("launch hashes %s != now %s" % (launch.get("sha"), now))
    except OSError:
        problems.append("outputs/_ist3h_launch.json missing")
    print("H QUEUE OK: %d lines; launch record %s" % (len(Q.lines()), "OK" if not problems else problems))
    runs, logs, outs, missing = {}, {}, {}, []
    for ln in Q.lines():
        try:
            d = json.load(open(ln["out"], encoding="utf-8"))
        except (OSError, ValueError):
            missing.append(ln["name"])
            continue
        after = ln["argv"][1:]
        sets = {}
        for i, tok in enumerate(after):
            if tok == "--set":
                k, v = after[i + 1].split("=", 1)
                sets[k] = _parse(v)
        if d.get("steps") != 360 or os.path.normcase(str(d.get("repo"))) != os.path.normcase(ln["cwd"]) or \
                d.get("extra_params") != sets:
            problems.append("H-V %s: steps %s repo %s extra_params %s (want %s)" % (
                ln["name"], d.get("steps"), d.get("repo"), d.get("extra_params"), sets))
        runs[ln["name"]] = d
        stem = ln["out"][:-5]
        try:
            outs[ln["name"]] = open(stem + ".stdout.txt", "rb").read()
        except OSError:
            problems.append("H-V %s: stdout.txt missing" % ln["name"])
        logs[ln["name"]] = poollog(ln["out"] + ".poollog", ln["argv"][ln["argv"].index("--tag") + 1],
                                   (Q.WT, Q.BASE))
    print("RUNS present %d / %d; H-V / launch problems %d" % (len(runs), len(Q.lines()), len(problems)))
    for p in problems:
        print("  PROBLEM", p)
    if missing and not partial:
        print("STOP: %d runs missing (e.g. %s)" % (len(missing), missing[:3]))
        return 3
    gates = {g: [0, 0] for g in ("H-A", "H-B", "H-C", "H-K", "H-OUT", "H-LOG", "H-P1")}
    fails = []
    for cid, *_rest in Q.CONFIGS:
        n = {a: "ist3h_%s_%s" % (a, cid) for a in ("B", "F12", "F1", "K")}

        def gate(g, ok, why=""):
            gates[g][0 if ok else 1] += 1
            if not ok:
                fails.append("%s %s: %s" % (g, cid, why))

        for g, x, y in (("H-A", "B", "F12"), ("H-B", "F1", "F12"), ("H-C", "B", "F1"), ("H-K", "B", "K")):
            if n[x] in runs and n[y] in runs:
                dd = diff(runs[n[x]], runs[n[y]])
                gate(g, not dd, "fields differ: %s" % dd)
                if n[x] in outs and n[y] in outs:
                    gate("H-OUT", outs[n[x]] == outs[n[y]], "%s vs %s stdout.txt bytes differ" % (x, y))
                gate("H-LOG", logs[n[x]] == logs[n[y]], "%s vs %s pool log differs" % (x, y))
        if n["B"] in runs:
            refs = [os.path.join(HERE, "_ist_%s.json" % cid)]
            if cid == "S_east_101":
                refs += [os.path.join(HERE, "_ist_bare_east_101.json"), os.path.join(HERE, "_ist_S2_east_101.json")]
            for ref in refs:
                try:
                    r = json.load(open(ref, encoding="utf-8"))
                except OSError:
                    gate("H-P1", False, "Part 1 record %s missing" % os.path.basename(ref))
                    continue
                dd = diff(runs[n["B"]], r)
                gate("H-P1", not dd, "B vs %s: %s" % (os.path.basename(ref), dd))
    print("\nGATES (pass / fail):")
    for g, (p, f) in gates.items():
        print("  %-6s %3d / %d" % (g, p, f))
    for f in fails:
        print("  FAIL", f)
    if runs:
        ex = next(iter(runs.values()))
        print("fields compared per run: %d (all but %s; params / extra_params without %s)"
              % (len(strip(ex)), sorted(IGNORED), sorted(ARM_KEYS)))
        for cid, *_rest in Q.CONFIGS:
            d = runs.get("ist3h_F12_%s" % cid)
            if d:
                ev = d.get("eval") or {}
                print("  %-13s rescued %s dead %s terminal %s stdout_sha256 %s fire_final_digest %s" % (
                    cid, ev.get("rescued"), ev.get("dead"), d.get("terminal_step"), str(d.get("stdout_sha256"))[:12],
                    str(d.get("fire_final_digest"))[:12]))
    ok = not problems and not missing and not any(f for _p, f in gates.values())
    print("\nVERDICT:", "ALL GATES PASS" if ok else ("INCOMPLETE" if missing else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
