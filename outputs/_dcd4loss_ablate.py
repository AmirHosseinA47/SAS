"""dcd4loss: controls C1-C3 and reading rules R1-R3 of outputs/dcd4loss_prereg.txt.

Read-only. For each of the four tuples, compares the new ablation arms
  dlS  D's settings at BASE_STATION_MODE=1 (spawn only)
  dlF  dlS + BASE_STATION_SPAWN_FIREFIGHTERS=0
against drhD (dcD) and drhZ (mode 0). Controls are printed and evaluated before
any outcome line; an arm whose control fails is reported VOID for that tuple.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TUPLES = [("east", 707), ("south", 101), ("south", 202), ("south", 404)]
STREAMS = ("uav_steps", "ff_steps", "ff_bind_steps", "victim_steps", "uav_actions")


def load(tag, w, s):
    with open(os.path.join(HERE, "_ffr_%s_%s_half_%s.json" % (tag, w, s)), encoding="utf-8") as fh:
        return json.load(fh)


def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def final(d):
    return {v[0]: v[2] for v in d["victim_steps"][-1]}


def main():
    sys.stdout.reconfigure(newline="\n")
    ok_all = True
    rows = []
    for w, s in TUPLES:
        D, Z = load("drhD", w, s), load("drhZ", w, s)
        S, F = load("dlS", w, s), load("dlF", w, s)
        print("=== %s/%s" % (w, s))
        # first index at which any D UAV has a base_state
        trig = next((i for i, row in enumerate(D["uav_steps"]) if any(u[5] for u in row)), None)
        rtb_first = min(t["trigger_step"] for trips in D["rtb_log"].values() for t in trips) if D["rtb_log"] else None
        print("  D first base_state at step %s (index %s); min rtb trigger_step %s" % (
            None if trig is None else trig + 1, trig, rtb_first))
        # C1
        c1 = True
        for key in STREAMS:
            fd = first_diff(D[key], S[key])
            pre_ok = fd is None or (trig is not None and fd >= trig)
            c1 &= pre_ok
            print("  C1 dlS vs drhD %-13s first diff step %s -> %s" % (
                key, None if fd is None else fd + 1, "OK (not before D's first return)" if pre_ok else "FAIL"))
        nonblind = any(first_diff(D[k], S[k]) is not None for k in ("uav_steps",))
        print("  C1 non-blind: dlS uav_steps differ from drhD after the return: %s" % nonblind)
        c1 &= nonblind
        # C2
        c2a = F["uav_steps"][0] == D["uav_steps"][0]
        c2b = F["ff_steps"][0] == Z["ff_steps"][0]
        c2c = S["ff_steps"][0] == D["ff_steps"][0]
        print("  C2 dlF uav_steps[0]==drhD: %s ; dlF ff_steps[0]==drhZ: %s (dlS ff_steps[0]==drhD: %s)" % (c2a, c2b, c2c))
        c2 = c2a and c2b
        # C3
        c3s = S["fire_digests"] == Z["fire_digests"]
        c3f = F["fire_digests"] == Z["fire_digests"]
        print("  C3 fire_digests dlS==drhZ: %s ; dlF==drhZ: %s" % (c3s, c3f))
        # params sanity
        for tag, X in (("dlS", S), ("dlF", F)):
            p = {k: v for k, v in X["params"].items() if k.startswith("BASE") or k.startswith("UAV_RET")}
            print("  params %s %s" % (tag, p))
        validS = c1 and c3s
        validF = c2 and c3f
        ok_all &= validS and validF
        print("  CONTROLS dlS %s ; dlF %s" % ("PASS" if validS else "VOID", "PASS" if validF else "VOID"))
        rows.append((w, s, D, Z, S, F, validS, validF))
    print()
    print("READINGS (only for arms whose controls passed)")
    for w, s, D, Z, S, F, validS, validF in rows:
        fz, fd, fs, ff = final(Z), final(D), final(S), final(F)
        ev = lambda d: "r%d d%d u%d nd%d ffd%d" % (d["eval"]["rescued"], d["eval"]["dead"], d["eval"]["unreachable"],
                                                 d["eval"]["never_detected"], d["eval"]["firefighter_deaths"])
        print("=== %s/%s   Z %s | D %s | dlS %s | dlF %s" % (w, s, ev(Z), ev(D), ev(S) if validS else "VOID", ev(F) if validF else "VOID"))
        for vid in sorted(fz):
            print("  %s  Z=%-10s D=%-10s dlS=%-10s dlF=%-10s" % (vid, fz[vid], fd[vid], fs[vid] if validS else "VOID", ff[vid] if validF else "VOID"))
        lost = [v for v in fz if fz[v] == "rescued" and fd[v] != "rescued"]
        for v in lost:
            if not validS:
                print("  LOST %s: R1 not readable (dlS VOID)" % v)
                continue
            if fs[v] == "rescued":
                print("  LOST %s: R1 FIRES - rescued at mode 1: return/recharge/reserve implicated" % v)
                continue
            r1 = "R1: lost at mode 1 too - spawn alone sufficient"
            if not validF:
                print("  LOST %s: %s; R2 not readable (dlF VOID)" % (v, r1))
            elif ff[v] == "rescued":
                print("  LOST %s: %s; R2: rescued with FFs at mode-0 spawn - FIREFIGHTER spawn necessary" % (v, r1))
            else:
                print("  LOST %s: %s; R2: lost with FFs at mode-0 spawn - UAV spawn alone sufficient" % (v, r1))
        other = [v for v in fz if v not in lost and (fs[v] != fd[v] or ff[v] != fd[v])]
        for v in other:
            print("  R3 other victim differs: %s Z=%s D=%s dlS=%s dlF=%s" % (v, fz[v], fd[v], fs[v], ff[v]))
    print()
    print("ALL CONTROLS %s" % ("PASS" if ok_all else "NOT ALL PASS"))


if __name__ == "__main__":
    main()
