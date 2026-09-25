"""Read-only: summarise tag/repo/steps/params/extra_params/uav_actions/fm2p for reference arms."""
import json, os, sys, glob, collections

OUT = r"E:\Projects\SAS\outputs"
arms = sys.argv[1:] or ["ugD", "uhD", "ugKD", "ugKC", "ugC", "uhC", "ugmD", "uhY", "ugY", "ugKY"]


def names(prefix):
    pre = "_ffr_%s_" % prefix
    # non-recursive: os.listdir of outputs only; skip the quarantine by name
    return sorted(n for n in os.listdir(OUT) if n.startswith(pre) and n.endswith(".json"))


for arm in arms:
    ns = names(arm)
    summ = collections.Counter()
    ex = None
    for n in ns:
        with open(os.path.join(OUT, n), "r", encoding="utf-8") as f:
            d = json.load(f)
        ua = d.get("uav_actions")
        key = (
            d.get("repo"),
            d.get("steps"),
            json.dumps(d.get("extra_params"), sort_keys=True),
            json.dumps(d.get("params"), sort_keys=True),
            "ua=None" if ua is None else "ua=%d" % len(ua),
            "fm2p" if "fm2p" in d else "-",
            len(d.get("victim_steps") or []),
            len(d.keys()),
        )
        summ[key] += 1
    print("==", arm, len(ns))
    for k, v in summ.items():
        print("  x%d" % v)
        for i, x in enumerate(k):
            print("     ", ["repo", "steps", "extra", "params", "ua", "fm2p", "nvic", "nkeys"][i], x)
