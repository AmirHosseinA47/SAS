"""Base vs F1 (mode 1) stall count on the SHIPPED-config recorded arms, using the
preserved replay's own functions (imported, not copied). Read-only; run with -B."""
import os
import sys
from collections import defaultdict

REPLAY = r"E:/Projects/SAS/outputs/_cl_replay"
sys.path.insert(0, REPLAY)
import fs_counterfactual as fc  # noqa: E402
from fs_env import Env  # noqa: E402

OUT = r"E:/Projects/SAS/outputs"
C13 = {("east", "half", s) for s in ("101", "202", "303", "404", "505")} | \
      {("south", "half", s) for s in ("101", "202", "303", "404", "505")} | \
      {("east", "def", s) for s in ("101", "202", "303")}
import re  # noqa: E402
u30 = set()
for line in open(os.path.join(OUT, "_ug_seeds.txt"), encoding="utf-8"):
    m = re.match(r"^(east|south)\|(half|def|default)\s+seed (\d+)", line.strip())
    if m:
        u30.add(m.group(3))
assert len(u30) == 30, len(u30)


def seedset(name):
    parts = name[:-5].split("_")  # _ffr_TAG_wind_roles_seed
    wind, roles, seed = parts[-3], parts[-2], parts[-1]
    if (wind, roles, seed) in C13:
        return "C13"
    if seed in u30:
        return "U30"
    return "other"


def main(tags):
    names = sorted(n for n in os.listdir(OUT)
                   if n.endswith(".json") and any(n.startswith("_ffr_%s_" % t) for t in tags))
    agg = defaultdict(lambda: defaultdict(int))
    for name in names:
        d = fc.load(name)
        tag = name.split("_")[2]
        ss = seedset(name)
        key = (tag, ss)
        agg[key]["runs"] += 1
        if d is None or "burn_intervals" not in d:
            agg[key]["skipped"] += 1
            continue
        env = Env(d, f_guess=8)
        for leg in fc.legs(d):
            rec = leg["s1"] - leg["s0"]
            b = fc.replay(env, leg, "base")
            f = fc.replay(env, leg, "F1")
            agg[key]["legs"] += 1
            agg[key]["rec_stalled"] += rec > leg["dist"] + 5
            bn, fn = b.get("n"), f.get("n")
            if bn is None or fn is None:
                agg[key]["none"] += 1
                continue
            agg[key]["base_stalled"] += bn > leg["dist"] + 5
            agg[key]["F1_stalled"] += fn > leg["dist"] + 5
            if fn != bn:
                agg[key]["changed"] += 1
                print("  CHG %-44s %s %s s0=%d dist=%d rec=%d base=%s F1=%s %s" % (
                    name, leg["victim"], leg["ff"], leg["s0"], leg["dist"], rec, bn, fn,
                    "STILL-STALLED" if fn > leg["dist"] + 5 else "ok"))
    for key in sorted(agg):
        print(key, dict(agg[key]))


if __name__ == "__main__":
    main(sys.argv[1:])
