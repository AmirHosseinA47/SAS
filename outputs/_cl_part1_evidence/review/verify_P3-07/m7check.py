"""Read-only: (a) is the replay's adj count the same quantity as M7's end-of-step
adjacency? (b) is M7's in-fire term (exiting and alive rows) structurally 0?
Imports the replay modules from outputs/_cl_replay without writing bytecode."""
import sys
sys.dont_write_bytecode = True
import os
from collections import Counter

REPLAY = r"E:/Projects/SAS/outputs/_cl_replay"
sys.path.insert(0, REPLAY)
from fs_env import Env  # noqa: E402
from fs_counterfactual import load, legs, replay  # noqa: E402


def pos_of(d, ff, k):
    if k < 1 or k > len(d["ff_steps"]):
        return None
    for row in d["ff_steps"][k - 1]:
        if row[0] == ff:
            return tuple(row[1]) if row[1] is not None else None
    return None


def row_of(d, ff, k):
    if k < 1 or k > len(d["ff_steps"]):
        return None
    for row in d["ff_steps"][k - 1]:
        if row[0] == ff:
            return row
    return None


def main(listfile):
    files = [l.strip() for l in open(os.path.join(REPLAY, listfile), encoding="utf-8") if l.strip()]
    C = Counter()
    mism = []
    for name in files:
        d = load(name)
        if d is None or "burn_intervals" not in d:
            C["skipped"] += 1
            continue
        env = Env(d, f_guess=8)
        # (b) in-fire of exiting & alive rows, whole run
        for i, row in enumerate(d["ff_steps"]):
            k = i + 1
            for r in row:
                ffid, cell, status, assigned, exiting, dead = r
                if cell is None:
                    continue
                c = tuple(cell)
                if exiting and not dead and status != "dead":
                    C["exit_alive_rows"] += 1
                    if env.burning(c, k):
                        C["exit_alive_in_fire"] += 1
                    if env.adj(c, k):
                        C["exit_alive_adj"] += 1
                if dead:
                    prev = row_of(d, ffid, k - 1)
                    if prev is not None and not prev[5] and prev[4]:
                        C["death_after_exiting"] += 1
                        C["death_row_exiting_flag_%s" % bool(exiting)] += 1
                        C["death_row_cell_burning_%s" % env.burning(c, k)] += 1
        # (a) per completed leg: replay base adj vs recorded end-of-step adjacency
        for leg in legs(d):
            rec = leg["s1"] - leg["s0"]
            b = replay(env, leg, "base")
            if b.get("n") is None:
                continue
            rec_adj = 0
            rec_adj_with_pickup = 0
            for k in range(leg["s0"], leg["s1"]):
                p = pos_of(d, leg["ff"], k)
                if p is None:
                    continue
                a = int(env.adj(p, k))
                rec_adj_with_pickup += a
                if k >= leg["s0"] + 1:
                    rec_adj += a
            C["legs"] += 1
            C["replay_base_adj"] += b["adj"]
            C["rec_adj_s0p1_to_s1m1"] += rec_adj
            C["rec_adj_s0_to_s1m1"] += rec_adj_with_pickup
            if b["n"] == rec:
                C["base_matches"] += 1
                C["m_replay_adj"] += b["adj"]
                C["m_rec_adj"] += rec_adj
                if b["adj"] != rec_adj:
                    mism.append((name, leg["victim"], leg["s0"], b["adj"], rec_adj))
    print(listfile, dict(C))
    print("matched-leg adj mismatches:", len(mism), mism[:10])


if __name__ == "__main__":
    for lf in sys.argv[1:]:
        main(lf)
