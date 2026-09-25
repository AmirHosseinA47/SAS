"""Closed-loop counterfactual replay of carrying legs under candidate rules, fire and
smoke held at the recorded history (fs_env, validated against the probe windows).
Read-only: opens explicit _ffr_<tag>_<wind>_<roles>_<seed>.json paths only.

Limits: (1) the fire is held fixed - exact for fire-mechanic-OFF runs (no FF writes),
approximate for ON runs (other units' writes could shift with the carrier's timing);
(2) only the leg itself is replayed - an earlier completion's downstream effects (next
dispatch, absence, recycle) are not; (3) smoke on never-burnt-out cells uses a guessed
initial fuel (F_GUESS), bracketed at 7 and 10.
"""
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fs_env import Env, nbrs  # noqa: E402
from fs_rules import move_toward, bfs_first_step, on_boundary, md  # noqa: E402

OUT = r"E:/Projects/SAS/outputs"
QUAR = "_firemech_rewound_20260914"


def load(name):
    assert QUAR not in name and "/" not in name and "\\" not in name
    p = os.path.join(OUT, name)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def legs(d):
    out = []
    starts = d.get("exit_starts") or []
    for c in d.get("completions") or []:
        st = [e for e in starts if e.get("victim") == c.get("victim") and e.get("step", 10 ** 9) <= c.get("step", -1)]
        if not st or not c.get("exit_target") or not st[-1].get("ff_pos"):
            continue
        s = st[-1]
        out.append(dict(victim=c["victim"], ff=c.get("ff"), s0=s["step"], s1=c["step"], p0=tuple(s["ff_pos"]),
                        exit=tuple(c["exit_target"]), dist=md(s["ff_pos"], c["exit_target"])))
    return out


def nearest_clean_boundary(env, pos, k):
    best = None
    for x in range(50):
        for y in (0, 49):
            for c in ((x, y), (y, x)):
                if env.burning(c, k) or env.adj(c, k) or env.smoky(c, k):
                    continue
                key = (md(pos, c), c)
                if best is None or key < best:
                    best = key
    return best[1] if best else None


def replay(env, leg, rule, horizon=300):
    pos, tgt, last = leg["p0"], leg["exit"], None
    hist = [pos]
    adj_steps = smoke_steps = rev = 0
    for k in range(leg["s0"] + 1, leg["s0"] + horizon):
        if rule in ("F1", "F1F4", "F1F6", "F1F4s") and on_boundary(pos):
            return dict(n=k - leg["s0"], adj=adj_steps, smoke=smoke_steps, rev=rev, end=pos)
        if pos == tgt:
            return dict(n=k - leg["s0"], adj=adj_steps, smoke=smoke_steps, rev=rev, end=pos)
        if rule in ("F2", "F2a"):
            if rule == "F2a" or env.burning(tgt, k) or env.adj(tgt, k) or env.smoky(tgt, k):
                nt = nearest_clean_boundary(env, pos, k)
                if nt is not None:
                    tgt = nt
            nxt, _t = move_toward(env, pos, tgt, k)
        elif rule == "F5":
            nxt = bfs_first_step(env, pos, k)
            if nxt is None:
                nxt, _t = move_toward(env, pos, tgt, k)
            elif on_boundary(nxt):
                tgt = nxt
        else:
            base = {"F1": "base", "F1F4": "F4", "F1F6": "F6", "F1F4s": "F4s"}.get(rule, rule)
            nxt, _t = move_toward(env, pos, tgt, k, rule=base, last=last)
        if nxt is None:
            if env.burning(pos, k):
                return dict(n=None, dead=k)
            nxt = pos
        if len(hist) >= 2 and nxt == hist[-2] and nxt != pos:
            rev += 1
        if nxt != pos:
            last = pos
        pos = nxt
        hist.append(pos)
        adj_steps += env.adj(pos, k)
        smoke_steps += env.smoky(pos, k)
    return dict(n=None, timeout=True)


RULES = ["base", "F1", "F2", "F2a", "F3", "F3t", "F4", "F1F4", "F4s", "F1F4s", "F4b", "F6", "F1F6", "F5"]

GROUPS = {
    "uh": ["uhC", "uhD", "uhY"],
    "ugK": ["ugKC", "ugKD", "ugKY"],
    "ug": ["ugC", "ugD", "ugY"],
    "fm": ["fmOFF", "fmEFS", "fmDRY"],
    "f2c": ["f2cOFF", "f2cEFS", "f2cDRY"],
}


def tuples_for(tag):
    """Tuples from the census's own matched lists are not in the text; derive from the
    recorded queue/runs by trying the known seeds present for the uh group."""
    return None


if __name__ == "__main__":
    fg = int(os.environ.get("F_GUESS", "8"))
    files = [l.strip() for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
    per_rule = defaultdict(Counter)
    detail = []
    for name in files:
        d = load(name)
        if d is None or "burn_intervals" not in d:
            per_rule["_"]["skipped"] += 1
            continue
        env = Env(d, f_guess=fg)
        for leg in legs(d):
            rec = leg["s1"] - leg["s0"]
            res = {r: replay(env, leg, r) for r in RULES}
            b = res["base"]["n"]
            row = (name, leg["victim"], leg["ff"], leg["s0"], rec, leg["dist"], {r: res[r].get("n") for r in RULES},
                   {r: res[r].get("adj") for r in RULES})
            detail.append(row)
            for r in RULES:
                n = res[r].get("n")
                C = per_rule[r]
                C["legs"] += 1
                if n is None:
                    C["dead" if "dead" in res[r] else "timeout"] += 1
                    continue
                C["steps"] += n
                C["stalled"] += n > leg["dist"] + 5
                C["adj_steps"] += res[r]["adj"]
                C["smoke_steps"] += res[r]["smoke"]
                if b is not None:
                    C["changed_vs_base"] += n != b
                    C["shorter"] += n < b
                    C["longer"] += n > b
            per_rule["_"]["base_matches_recorded"] += (b == rec)
            per_rule["_"]["legs"] += 1
    print("F_GUESS", fg, "files", len(files), dict(per_rule["_"]))
    print("%-6s %5s %6s %7s %5s %5s %8s %7s %6s %6s %9s %9s" % (
        "rule", "legs", "steps", "stalled", "dead", "tmo", "changed", "shorter", "longer", "", "adj_steps", "smk_steps"))
    for r in RULES:
        C = per_rule[r]
        print("%-6s %5d %6d %7d %5d %5d %8d %7d %6d %6s %9d %9d" % (
            r, C["legs"], C["steps"], C["stalled"], C["dead"], C["timeout"], C["changed_vs_base"], C["shorter"], C["longer"], "",
            C["adj_steps"], C["smoke_steps"]))
    if "-v" in sys.argv:
        for row in detail:
            name, v, ff, s0, rec, dist, ns, adjs = row
            if rec > dist + 5 or any((ns[r] or 999) != ns["base"] for r in RULES):
                print("  %-44s %s %s s0=%d rec=%d dist=%d | %s" % (name, v, ff, s0, rec, dist,
                      " ".join("%s=%s" % (r, ns[r]) for r in RULES)))
