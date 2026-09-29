"""fix2, the item-2 follow-up (outputs/fix2_part3_prereg.txt amendment 4): the waves.

Writes outputs/_mf2_q_r.jsonl for outputs/_mf2_pool.py (every switch set explicitly):
  mf2rS  every switch 1 except STAGGERED_LAUNCH_BATTERY 0; STATIONARY_YIELD_FIX 1   16  the candidate
  mf2rX  as mf2rS with STATIONARY_YIELD_FIX 0                                         16  identity == mf2cX
  mf2rZ  every fix2 switch 0                                                          16  identity == mf2Z
  mf2rM  as mf2rS with UAV_HOLD_STATIONARY 0 (the moving-hold fallback)               16
  mf2rC  as mf2rS with YIELD_ONLY_WHEN_CONTENDING 1 (the offered rule 4)              16
  rbgate mf2gY (= mf2rS settings), mf2gM (= mf2rM settings): the four P3-10 shards each.
"""
import json
import os
import sys

REPO = r"E:\Projects\SAS"
OUT = os.path.join(REPO, "outputs")
SW = ["GLOBAL_ANALYZER_FIRE_SOURCE_FIX", "FAILSAFE_REAL_ALARMS", "UAV_HOLD_STATIONARY",
      "SEARCHER_WIND_COVERAGE_FIX", "SEARCHER_GATE_NEAR_FIELD", "STAGGERED_LAUNCH_BATTERY", "STAGGER_COMPACT",
      "STATIONARY_YIELD_FIX", "YIELD_ONLY_WHEN_CONTENDING"]


def arm(default, **over):
    d = {s: default for s in SW}
    d.update(over)
    return d


SHIPPED = arm(1, STAGGERED_LAUNCH_BATTERY=0, YIELD_ONLY_WHEN_CONTENDING=0)
ARMS = {
    "mf2rS": dict(SHIPPED),
    "mf2rX": dict(SHIPPED, STATIONARY_YIELD_FIX=0),
    "mf2rZ": arm(0),
    "mf2rM": dict(SHIPPED, UAV_HOLD_STATIONARY=0),
    "mf2rC": dict(SHIPPED, YIELD_ONLY_WHEN_CONTENDING=1),
}
RB = {"mf2gY": ARMS["mf2rS"], "mf2gM": ARMS["mf2rM"]}


def sets(values):
    out = []
    for k, v in values.items():
        out += ["--set", "%s=%s" % (k, v)]
    return out


def probe_line(name_arm, cfg, sw, steps=None, out_dir=OUT):
    with open(os.path.join(OUT, "_sd_mf1P_%s.json.argv" % cfg), encoding="utf-8") as fh:
        a = list(json.load(fh)["argv"][1:])
    name = "%s_%s" % (name_arm, cfg)
    out = os.path.join(out_dir, "_sd_%s.json" % name)
    a[a.index("--out") + 1] = out
    a[a.index("--tag") + 1] = name
    if steps is not None:
        a[a.index("--steps") + 1] = str(steps)
    return {"name": name, "argv": [os.path.join(OUT, "_mf2_probe.py"), "--"] + a + sets(sw), "out": out}


def main():
    cfg16 = ["%s_%s" % (s, w) for s in "ABCD" for w in "ENSW"]
    q = []
    for name in ("mf2rS", "mf2rC", "mf2rM"):
        q += [probe_line(name, c, ARMS[name]) for c in cfg16]
    shards = [("a", "east", "101,202,303,404,505"), ("b", "east", "606,707,808,909"),
              ("c", "east", "111,222,333,444"), ("s", "south", "101,202,303,404,505")]
    for name, sw in RB.items():
        for sh, w, seeds in shards:
            tag = "%s%s" % (name, sh)
            out = os.path.join(OUT, "_rblatch_camp2_%s_D_%s.json" % (tag, w))
            argv = [os.path.join(OUT, "_rblatch_campaign2.py"), "--scenario", "D", "--wind", w,
                    "--steps", "240", "--seeds", seeds, "--tag", tag] + sets(sw)
            q.append({"name": tag, "cwd": REPO, "argv": argv, "out": out})
    for name in ("mf2rX", "mf2rZ"):
        q += [probe_line(name, c, ARMS[name]) for c in cfg16]
    with open(os.path.join(OUT, "_mf2_q_r.jsonl"), "w", encoding="utf-8", newline="\n") as fh:
        for ln in q:
            fh.write(json.dumps(ln) + "\n")
    for a in ARMS:
        with open(os.path.join(OUT, "_mf2_an_%s.jsonl" % a), "w", encoding="utf-8", newline="\n") as fh:
            for ln in q:
                if ln["name"].startswith(a + "_"):
                    fh.write(json.dumps({"name": ln["name"]}) + "\n")
    print("wrote %d lines to _mf2_q_r.jsonl" % len(q))


if __name__ == "__main__":
    sys.exit(main())
