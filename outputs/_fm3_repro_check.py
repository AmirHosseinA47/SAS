"""Validate outputs/_fm3_repro_queue.py: do the r3* lines reproduce round 2's recorded f3*
runs at the current tree? Read-only. -> outputs/_fm3_repro_check.txt

  harness runs  r3OFF / r3GATE / r3RES east/half/101 vs f3OFF / f3GATE / f3RES
                east/half/101: value identity on every recorded key except tag, repo,
                wall_s, params, extra_params (the round's standard definition)
  gate shard    r3RBGc vs f3RBGc (east/half 111, 222, 333, 444): every per-seed eval
                field equal except wall_s (wall-clock time), and every route_blocked
                counter and event list of the shard equal

A PASS means the recipe (every FF switch explicit + BASE_STATION_FIREPROOF=0 +
VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX=0) reproduces round 2 value for value.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXCLUDE = {"tag", "repo", "wall_s", "params", "extra_params"}
OUT = []


def say(s=""):
    OUT.append(str(s))
    print(s)


def load(p):
    with open(os.path.join(HERE, p), encoding="utf-8") as f:
        return json.load(f)


def main():
    sys.stdout.reconfigure(newline="\n")
    ok = True
    say("ROUND-2 REPRODUCTION CHECK (outputs/_fm3_repro_queue.py)")
    for arm in ("OFF", "GATE", "RES"):
        a = load("_ffr_r3%s_east_half_101.json" % arm)
        b = load("_ffr_f3%s_east_half_101.json" % arm)
        keys = (set(a) | set(b)) - EXCLUDE
        diff = sorted(k for k in keys if a.get(k, "<absent>") != b.get(k, "<absent>"))
        ok = ok and not diff
        say("  r3%-5s == f3%-5s east/half/101: %s   (rescued %s / %s, extra_params %s)" % (
            arm, arm, "VALUE-IDENTICAL" if not diff else "DIFFERS in " + ", ".join(diff),
            a["eval"]["rescued"], b["eval"]["rescued"], a.get("extra_params")))
    a = load("_rblatch_camp2_r3RBGc_D_east.json")
    b = load("_rblatch_camp2_f3RBGc_D_east.json")
    ea = {int(e["seed"]): e for e in a.get("evals") or []}
    eb = {int(e["seed"]): e for e in b.get("evals") or []}
    for s in sorted(set(ea) | set(eb)):
        # wall_s is wall-clock time, excluded as in every identity check in this project
        x = {k: v for k, v in (ea.get(s) or {}).items() if k != "wall_s"}
        y = {k: v for k, v in (eb.get(s) or {}).items() if k != "wall_s"}
        same = x == y
        ok = ok and same
        diff = "" if same else " DIFFERS in %s" % sorted(k for k in set(x or {}) | set(y or {}) if (x or {}).get(k) != (y or {}).get(k))
        say("  r3RBGc == f3RBGc seed %d: %s%s" % (s, "IDENTICAL eval" if same else "", diff))
    for k in ("stats", "exact", "fires", "recoveries", "assigns", "latched", "deaths",
              "exact_fires", "exact_recoveries"):
        same = a.get(k) == b.get(k)
        ok = ok and same
        say("  shard %-16s %s" % (k, "IDENTICAL" if same else "DIFFER"))
    say("VERDICT: %s" % ("PASS - the recipe reproduces round 2 value for value" if ok else "FAIL"))
    with open(os.path.join(HERE, "_fm3_repro_check.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(OUT) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
