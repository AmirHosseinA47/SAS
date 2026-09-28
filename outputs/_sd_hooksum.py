"""sysdebug round: aggregate the runtime-confirmation hooks of _sd_K_*.json (outputs/_sd_hooks.py).

usage: _sd_hooksum.py <queue.jsonl>   (lines with script "hooks" are read)
Prints every hook counter summed over runs (and per run where it matters), the scoped
exception census, the per-step invariant counters and the recorded events. Read-only.
"""
import collections
import json
import os
import sys

REPO = r"E:\Projects\SAS"


def main():
    rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
    names = [r["name"] for r in rows if r.get("script") == "hooks"]
    tot = collections.defaultdict(collections.Counter)
    per_run = collections.defaultdict(dict)
    scoped = collections.Counter()
    scoped_ex = {}
    events = collections.defaultdict(list)
    for n in names:
        p = os.path.join(REPO, "outputs", "_sd_%s.json" % n)
        if not os.path.exists(p):
            print("MISSING", n)
            continue
        d = json.load(open(p, encoding="utf-8"))
        h = d.get("hooks")
        if not h:
            print("NO HOOKS RECORD", n)
            continue
        ev = d["eval"] or {}
        print("%-8s %s/%s seed=%s steps=%d crashed=%s rescued=%s dead=%s unr=%s ffd=%s" % (
            n, d["scenario"], d["wind"], d["seed"], d["steps_done"], (d["crashed"] or {}).get("type"),
            ev.get("rescued"), ev.get("dead"), ev.get("unreachable"), ev.get("firefighter_deaths")))
        for k, c in h["counters"].items():
            tot[k].update(c)
            per_run[k][n] = c
        for k, c in ((h.get("scoped_exc") or {}).get("counts") or {}).items():
            scoped[k] += c
        scoped_ex.update((h.get("scoped_exc") or {}).get("examples") or {})
        for k, v in (h.get("events") or {}).items():
            events[k] += [[n] + list(x) for x in v]
    print("\n=== HOOK COUNTERS (summed over %d runs) ===" % len(names))
    for k in sorted(tot):
        print("%s:" % k)
        for kk, vv in tot[k].most_common(40):
            print("    %-90s %d" % (kk, vv))
    print("\n=== PER-RUN: H_FINAL_xpull / H_FINAL_ypull / H_GATE_replaced / H_SURV ===")
    for k in ("H_FINAL_xpull", "H_FINAL_ypull", "H_FINAL_commit", "H_GATE_replaced", "H_SURV", "H_MOVE"):
        for n, c in per_run.get(k, {}).items():
            print("  %-16s %-8s %s" % (k, n, json.dumps(c)[:600]))
    print("\n=== SCOPED EXCEPTION CENSUS (exceptions raised inside the swallow-handler functions) ===")
    if not scoped:
        print("  none")
    for k, c in scoped.most_common():
        print("  %6d  %s   e.g. %s" % (c, k, scoped_ex.get(k)))
    print("\n=== EVENTS ===")
    for k, v in events.items():
        print("%s (%d):" % (k, len(v)))
        for row in v[:25]:
            print("    %s" % json.dumps(row)[:400])


if __name__ == "__main__":
    main()
