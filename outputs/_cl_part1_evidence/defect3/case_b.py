import json, sys, os

OUT = r"E:\Projects\SAS\outputs"


def load(tag, wind="east", roles="def", seed=101):
    p = os.path.join(OUT, "_ffr_%s_%s_%s_%s.json" % (tag, wind, roles, seed))
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "f2cDRY"
    lo = int(sys.argv[2]) if len(sys.argv) > 2 else 140
    hi = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    d = load(tag)
    print("keys:", sorted(d.keys())[:200])
    print("steps", d.get("steps"), "eval", json.dumps(d.get("eval"))[:800])
    print("unreachable_escape_log", d.get("unreachable_escape_log"))
    print("unreachable_marks", d.get("unreachable_marks"))
    print("exit_starts", d.get("exit_starts"))
    print("completions", d.get("completions"))
    print("unassigns", [u for u in d.get("unassigns", [])])
    print("assigns", [a for a in d.get("assigns", [])])
    print("rescue_failed", d.get("rescue_failed"))
    ffs = d["ff_steps"]
    binds = d["ff_bind_steps"]
    vs = d["victim_steps"]
    for i in range(lo - 1, min(hi, len(ffs))):
        step = i + 1
        ffrow = " ".join(
            "%s@%s/%s/a%d/e%d/d%d" % (r[0][-6:], tuple(r[1]) if r[1] else None, r[2], r[3], r[4], r[5])
            for r in ffs[i]
        )
        brow = " ".join("%s->%s" % (r[0][-6:], r[1]) for r in binds[i])
        vrow = " ".join("%s@%s/%s" % (r[0], tuple(r[1]) if r[1] else None, r[2]) for r in vs[i])
        print(step, "|", ffrow, "|", brow, "|", vrow)


main()
