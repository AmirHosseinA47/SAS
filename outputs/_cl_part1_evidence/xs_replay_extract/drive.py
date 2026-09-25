"""Read-only driver over the fix-scope agent's offline replay (copied from the
e5e891da scratchpad). Reproduces its base/F1/F5 rows and adds F1F5 (= F5 with the
F1 completion test, i.e. the proposed mode 2). Opens only explicit outputs/ file
names from the list files; never walks a directory."""
import os
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fs_env import Env  # noqa: E402
from fs_rules import move_toward, bfs_first_step, on_boundary, md  # noqa: E402
from fs_counterfactual import load, legs, replay as orig_replay  # noqa: E402

OUT = r"E:/Projects/SAS/outputs"
CUTOFF = time.mktime((2026, 9, 21, 21, 25, 0, 0, 0, -1))


def replay2(env, leg, rule, horizon=300):
    """F1F5 and instrumented F5. Same loop as fs_counterfactual.replay."""
    pos, tgt = leg["p0"], leg["exit"]
    hist = [pos]
    adj_steps = smoke_steps = rev = fb = bfs = 0
    for k in range(leg["s0"] + 1, leg["s0"] + horizon):
        if rule == "F1F5" and on_boundary(pos):
            return dict(n=k - leg["s0"], adj=adj_steps, smoke=smoke_steps, rev=rev, end=pos, fb=fb, bfs=bfs)
        if pos == tgt:
            return dict(n=k - leg["s0"], adj=adj_steps, smoke=smoke_steps, rev=rev, end=pos, fb=fb, bfs=bfs)
        nxt = bfs_first_step(env, pos, k)
        if nxt is None:
            fb += 1
            nxt, _t = move_toward(env, pos, tgt, k)
        else:
            bfs += 1
            if rule == "F5" and on_boundary(nxt):
                tgt = nxt
        if nxt is None:
            if env.burning(pos, k):
                return dict(n=None, dead=k)
            nxt = pos
        if len(hist) >= 2 and nxt == hist[-2] and nxt != pos:
            rev += 1
        pos = nxt
        hist.append(pos)
        adj_steps += env.adj(pos, k)
        smoke_steps += env.smoky(pos, k)
    return dict(n=None, timeout=True)


def run(listfile, fg=8, show=False):
    files = [l.strip() for l in open(os.path.join(HERE, listfile), encoding="utf-8") if l.strip()]
    C = defaultdict(Counter)
    meta = Counter()
    late = []
    diffs = []
    for name in files:
        p = os.path.join(OUT, name)
        if os.path.isfile(p) and os.path.getmtime(p) > CUTOFF:
            late.append((name, time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(p)))))
        d = load(name)
        if d is None or "burn_intervals" not in d:
            meta["skipped"] += 1
            meta["skipped:" + name] += 1
            continue
        meta["files_used"] += 1
        env = Env(d, f_guess=fg)
        for leg in legs(d):
            rec = leg["s1"] - leg["s0"]
            res = {r: orig_replay(env, leg, r) for r in ("base", "F1", "F5")}
            res["F5i"] = replay2(env, leg, "F5")
            res["F1F5"] = replay2(env, leg, "F1F5")
            b = res["base"]["n"]
            meta["legs"] += 1
            meta["base==rec"] += b == rec
            rec_st = rec > leg["dist"] + 5
            base_st = b is not None and b > leg["dist"] + 5
            meta["rec_stall"] += rec_st
            meta["rec_stall&base_stall"] += rec_st and base_st
            meta["base_stall&!rec_stall"] += base_st and not rec_st
            meta["F5==F5i"] += res["F5"].get("n") == res["F5i"].get("n")
            f5 = res["F5i"]
            if f5.get("n") is not None:
                meta["F5_end_not_orig_exit"] += f5["end"] != leg["exit"]
                meta["F5_fallback_steps"] += f5["fb"]
                meta["F5_bfs_steps"] += f5["bfs"]
                meta["F5_legs_with_fallback"] += f5["fb"] > 0
            if res["F1F5"].get("n") != res["F5"].get("n"):
                diffs.append((name, leg["victim"], leg["s0"], rec, leg["dist"], b, res["F5"].get("n"), res["F1F5"].get("n")))
            for r in ("base", "F1", "F5", "F1F5"):
                n = res[r].get("n")
                c = C[r]
                c["legs"] += 1
                if n is None:
                    c["dead" if "dead" in res[r] else "timeout"] += 1
                    continue
                c["steps"] += n
                c["stalled"] += n > leg["dist"] + 5
                c["adj"] += res[r]["adj"]
                c["smoke"] += res[r]["smoke"]
                if b is not None:
                    c["shorter"] += n < b
                    c["longer"] += n > b
    print("==", listfile, "F_GUESS", fg, dict(meta))
    if late:
        print("  FILES MODIFIED AFTER cf_census (2026-09-21 21:25):", late)
    for r in ("base", "F1", "F5", "F1F5"):
        c = C[r]
        print("  %-5s legs %3d steps %5d stalled %3d dead %d tmo %d shorter %3d longer %d adj %3d smoke %3d" % (
            r, c["legs"], c["steps"], c["stalled"], c["dead"], c["timeout"], c["shorter"], c["longer"], c["adj"], c["smoke"]))
    if show:
        for row in diffs:
            print("   F1F5!=F5", row)


if __name__ == "__main__":
    fg = int(os.environ.get("F_GUESS", "8"))
    show = "-v" in sys.argv
    for lf in [a for a in sys.argv[1:] if a != "-v"]:
        run(lf, fg, show)
