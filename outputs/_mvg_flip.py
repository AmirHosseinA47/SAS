"""MVG round, THE FLIP's identity check (outputs/urgency_part1d.txt 1d.6.3: "flip identity against mvg1 on 4 + 4 cells";
both fixes ship, so the reference is mvg1 itself).

usage (from the mvg worktree root, with E:/Projects/SAS/.venv/Scripts/python.exe -B):
  python outputs/_mvg_flip.py write      writes the FROZEN queue outputs/_mvg_q_flip.jsonl (8 lines; refuses to
                                         re-write a different one)
  python outputs/_mvg_flip.py compare    compares each flip run with its mvg1 W2 record; exit 0 iff all 8 identical

THE CELLS (rule fixed before any flip run, at the flip commit 980d9338): per fresh set (5, then 6), the first 4 mvg1
lines of the frozen W2 queue outputs/_mvg_q_w2.jsonl, in its order, whose W2 record has at least one fix (a) step that
RAN, one fix (b) step that RAN and one VETO (d["mv_events"]: "ran" / "vetoed") - so every flipped switch, the guard
included, acts in every compared run. The rule gives FLIP_CELLS below; write re-derives it and STOPS on a difference.

THE RUN LINE: the mvg1 W2 line minus its two "--set FF_APPROACH_PATH=1 --set FF_RETREAT_KEEP_APPROACH=1" pairs (the
flipped defaults now supply them), with --out outputs/_mvg_flip/_sd_<tag>.json and --tag mvgf<p><k>_<S>_<W>.

THE COMPARISON (as the isTrue round's gates, outputs/isTrue_report.txt 4.4): every recorded field equal except labels
and wall-clock - top-level argv, tag, head, src_sha, extra_params, wall_s, python, mesa, repo; every section's
src_sha / probe_sha / timing; the instrument's wall-clock columns (d["mv"] fix_ms / inst_ms, guard rows ms_* ones, the
kick ms fields); d["params"] without the two fix switches (set by --set in mvg1, by the defaults here). The switches
the run READ (d["ud"]["switches"], d["mvg"]["switches"], raw values included) must be equal. The model's stdout
(<stem>.stdout.txt) is compared byte for byte (LF-normalised).
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
W2_QUEUE = os.path.join(HERE, "_mvg_q_w2.jsonl")
QUEUE = os.path.join(HERE, "_mvg_q_flip.jsonl")
OUT_DIR = os.path.join(HERE, "_mvg_flip")
FIX_SETS = ("FF_APPROACH_PATH=1", "FF_RETREAT_KEEP_APPROACH=1")
FIX_KEYS = ("FF_APPROACH_PATH", "FF_RETREAT_KEEP_APPROACH")
FLIP_CELLS = ("mvg1r5_A_E", "mvg1r5_B_S", "mvg1r5_C_W", "mvg1r5_D_N",
              "mvg1r6_A_N", "mvg1r6_B_N", "mvg1u6_C_N", "mvg1u6_C_S")
TOP_SKIP = {"argv", "tag", "head", "src_sha", "extra_params", "wall_s", "python", "mesa", "repo"}
SEC_SKIP_KEYS = {"src_sha", "probe_sha", "timing", "u1_shadow_path"}
MS_COLS = ("fix_ms", "inst_ms")


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def w2_lines():
    with open(W2_QUEUE, encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def select_cells(lines):
    sel = {"5": [], "6": []}
    for ln in lines:
        name = ln["name"]
        if not name.startswith("mvg1"):
            continue
        ev = _load(ln["out"]).get("mv_events") or []
        ran_a = any(e.get("kind") == "a" and e.get("ran") for e in ev)
        ran_b = any(e.get("kind") == "b" and e.get("ran") for e in ev)
        veto = any(e.get("vetoed") for e in ev)
        if ran_a and ran_b and veto and len(sel[name[5]]) < 4:
            sel[name[5]].append(name)
    return tuple(sel["5"] + sel["6"])


def flip_line(ln):
    argv = list(ln["argv"])
    for s in FIX_SETS:
        i = argv.index(s)
        assert argv[i - 1] == "--set", (ln["name"], s)
        del argv[i - 1:i + 1]
    tag = "mvgf" + ln["name"][4:]
    out = os.path.join(OUT_DIR, "_sd_%s.json" % tag)
    argv[argv.index("--out") + 1] = out
    argv[argv.index("--tag") + 1] = tag
    return {"name": tag, "argv": argv, "out": out, "cwd": ln["cwd"], "ref": ln["out"]}


def write():
    lines = w2_lines()
    cells = select_cells(lines)
    if cells != FLIP_CELLS:
        print("STOP: the rule gives %s, not FLIP_CELLS %s" % (cells, FLIP_CELLS))
        return 2
    by = {ln["name"]: ln for ln in lines}
    text = "".join(json.dumps(flip_line(by[c])) + "\n" for c in FLIP_CELLS)
    if os.path.exists(QUEUE):
        with open(QUEUE, encoding="utf-8") as fh:
            if fh.read() != text:
                print("STOP: %s exists and differs (frozen; never re-written)" % QUEUE)
                return 2
        print("unchanged (frozen): %s" % QUEUE)
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(QUEUE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote %s (%d lines)" % (QUEUE, len(FLIP_CELLS)))
    return 0


def _strip(d):
    """The comparable view of a record (see the module docstring)."""
    out = {}
    for k, v in d.items():
        if k in TOP_SKIP:
            continue
        if k == "params" and isinstance(v, dict):
            v = {pk: pv for pk, pv in v.items() if pk not in FIX_KEYS}
        if isinstance(v, dict):
            v = {sk: sv for sk, sv in v.items() if sk not in SEC_SKIP_KEYS}
        out[k] = v
    mv = out.get("mv")
    if isinstance(mv, dict) and "cols" in mv:
        keep = [i for i, c in enumerate(mv["cols"]) if c not in MS_COLS]
        out["mv"] = {"cols": [mv["cols"][i] for i in keep], "rows": [[r[i] for i in keep] for r in mv["rows"]]}
    g = (out.get("mvg") or {}).get("guard")
    if isinstance(g, dict) and "cols" in g:
        keep = [i for i, c in enumerate(g["cols"]) if not c.startswith("ms")]
        out["mvg"] = dict(out["mvg"], guard={"cols": [g["cols"][i] for i in keep],
                                              "rows": [[r[i] for i in keep] for r in g["rows"]]})
    ud = out.get("ud")
    if isinstance(ud, dict) and isinstance(ud.get("kicks"), list):
        out["ud"] = dict(ud, kicks=[{kk: kv for kk, kv in kick.items() if not kk.endswith("ms")}
                                    if isinstance(kick, dict) else kick for kick in ud["kicks"]])
    return out


def _diff(a, b, path="", acc=None, cap=20):
    acc = [] if acc is None else acc
    if len(acc) >= cap:
        return acc
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                acc.append("%s.%s present on one side only" % (path, k))
            else:
                _diff(a[k], b[k], "%s.%s" % (path, k), acc, cap)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            acc.append("%s length %d vs %d" % (path, len(a), len(b)))
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                _diff(x, y, "%s[%d]" % (path, i), acc, cap)
    elif a != b:
        acc.append(path)
    return acc


def _stdout(path):
    stem = path[:-5] if path.endswith(".json") else path
    with open(stem + ".stdout.txt", "rb") as fh:
        return fh.read().replace(b"\r\n", b"\n")


def compare():
    with open(QUEUE, encoding="utf-8") as fh:
        lines = [json.loads(ln) for ln in fh if ln.strip()]
    bad = 0
    for ln in lines:
        f, r = _load(ln["out"]), _load(ln["ref"])
        why = []
        if f.get("crashed") is not None or f.get("steps_done") != 360:
            why.append("flip run incomplete")
        for sec in ("ud", "mvg"):
            if (f.get(sec) or {}).get("switches") != (r.get(sec) or {}).get("switches"):
                why.append("%s.switches differ" % sec)
        sw = (f.get("mvg") or {}).get("switches") or {}
        if not (sw.get("FF_APPROACH_PATH") is True and sw.get("FF_RETREAT_KEEP_APPROACH") is True
                and sw.get("FF_FIX_STRANDING_GUARD") is True):
            why.append("the flip run did not read all three switches ON")
        if any(k in (f.get("extra_params") or {}) for k in FIX_KEYS):
            why.append("the flip run set a fix switch explicitly")
        why += _diff(_strip(f), _strip(r))
        if _stdout(ln["out"]) != _stdout(ln["ref"]):
            why.append("stdout differs")
        print("%-14s vs %-12s %s" % (ln["name"], os.path.basename(ln["ref"])[4:-5],
                                     "IDENTICAL" if not why else "DIFFERS: %s" % why[:8]))
        bad += bool(why)
    print("FLIP IDENTITY: %d / %d identical => %s" % (len(lines) - bad, len(lines), "PASS" if not bad else "FAIL"))
    return 0 if not bad else 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.exit({"write": write, "compare": compare}.get(cmd, lambda: (print(__doc__), 2)[1])())
