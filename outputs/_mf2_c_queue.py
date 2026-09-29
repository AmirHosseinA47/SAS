"""fix2, the compact-stagger follow-up (outputs/fix2_part3_prereg.txt amendment 3): the waves.

Writes outputs/_mf2_q_c.jsonl for outputs/_mf2_pool.py:
  mf2cZ  every fix2 switch 0 (incl. STAGGER_COMPACT)            16 configs  identity == mf2Z == mf1P
  mf2cE  item 4 alone, EVEN   (STAGGERED 1, COMPACT 0)            8 (S/E)   identity == mf2A4
  mf2cK  item 4 alone, COMPACT (STAGGERED 1, COMPACT 1)          16         the decisive arm
  mf2cS  every switch 1, COMPACT                                 16         shipped candidate 1
  mf2cX  every switch 1 except STAGGERED_LAUNCH_BATTERY 0        16         shipped candidate 2
  rbgate mf2gC (= mf2cS settings), mf2gX (= mf2cX settings): the four P3-10 shards each.
Every arm sets all seven switches explicitly, so the JSONs record what ran whatever the defaults.
"""
import json
import os
import sys

REPO = r"E:\Projects\SAS"
OUT = os.path.join(REPO, "outputs")
SW7 = ["GLOBAL_ANALYZER_FIRE_SOURCE_FIX", "FAILSAFE_REAL_ALARMS", "UAV_HOLD_STATIONARY",
       "SEARCHER_WIND_COVERAGE_FIX", "SEARCHER_GATE_NEAR_FIELD", "STAGGERED_LAUNCH_BATTERY", "STAGGER_COMPACT"]


def arm(default, **over):
    d = {s: default for s in SW7}
    d.update(over)
    return d


ARMS = {
    "mf2cZ": arm(0),
    "mf2cE": arm(0, STAGGERED_LAUNCH_BATTERY=1, STAGGER_COMPACT=0),
    "mf2cK": arm(0, STAGGERED_LAUNCH_BATTERY=1, STAGGER_COMPACT=1),
    "mf2cS": arm(1),
    "mf2cX": arm(1, STAGGERED_LAUNCH_BATTERY=0),
}
RB = {"mf2gC": arm(1), "mf2gX": arm(1, STAGGERED_LAUNCH_BATTERY=0)}


def sets(values):
    out = []
    for k, v in values.items():
        out += ["--set", "%s=%s" % (k, v)]
    return out


def probe_line(name_arm, cfg, sw):
    with open(os.path.join(OUT, "_sd_mf1P_%s.json.argv" % cfg), encoding="utf-8") as fh:
        a = list(json.load(fh)["argv"][1:])
    name = "%s_%s" % (name_arm, cfg)
    out = os.path.join(OUT, "_sd_%s.json" % name)
    a[a.index("--out") + 1] = out
    a[a.index("--tag") + 1] = name
    return {"name": name, "argv": [os.path.join(OUT, "_mf2_probe.py"), "--"] + a + sets(sw), "out": out}


def main():
    cfg16 = ["%s_%s" % (s, w) for s in "ABCD" for w in "ENSW"]
    cfg8 = ["%s_%s" % (s, w) for s in "ABCD" for w in "SE"]
    q = []
    # the decisive arm and the shipped candidates first, then the identity arms
    for name in ("mf2cK", "mf2cS", "mf2cX"):
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
    q += [probe_line("mf2cZ", c, ARMS["mf2cZ"]) for c in cfg16]
    q += [probe_line("mf2cE", c, ARMS["mf2cE"]) for c in cfg8]
    with open(os.path.join(OUT, "_mf2_q_c.jsonl"), "w", encoding="utf-8", newline="\n") as fh:
        for ln in q:
            fh.write(json.dumps(ln) + "\n")
    for a in ARMS:
        names = [ln["name"] for ln in q if ln["name"].startswith(a + "_")]
        with open(os.path.join(OUT, "_mf2_an_%s.jsonl" % a), "w", encoding="utf-8", newline="\n") as fh:
            for n in names:
                fh.write(json.dumps({"name": n}) + "\n")
    print("wrote %d lines to _mf2_q_c.jsonl" % len(q))


if __name__ == "__main__":
    sys.exit(main())
