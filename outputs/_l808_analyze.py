"""Analysis over _l808_*.json traces. Read-only."""
from __future__ import annotations
import argparse, collections, json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))


def load(tag):
    with open(os.path.join(BASE, "_l808_%s.json" % tag)) as f:
        return json.load(f)


def ffmap(snap):
    return {f["id"]: f for f in snap["ff"]}


def vmap(snap):
    return {v["id"]: v for v in snap["victims"]}


def uavmap(snap):
    return {u["id"]: u for u in snap["uavs"]}


def cmd_summary(d):
    print("== %s  mode=%s seed=%s ==" % (d["tag"], d["mode"], d["seed"]))
    e = d["eval"]
    for k in ("rescued", "dead", "never_detected", "firefighter_deaths", "unreachable"):
        if k in e:
            print("   %-20s %s" % (k, e[k]))
    print("   terminal_step        %s" % d["terminal_step"])
    print("   latched              %s" % d["latched"])
    kinds = collections.Counter(x["kind"] for x in d["events"])
    print("   events               %s" % dict(kinds))
    print("   route_blocked fires:")
    for x in d["events"]:
        if x["kind"] == "route_blocked_fire":
            print("     step %3d %-10s pos=%-10s tgt=%-10s reach=%-5s nbrsfire=%-5s "
                  "exiting=%-5s assigned=%-5s bound=%s" % (
                      x["step"], x["ff"], x["pos"], x["target"], x["reachable"],
                      x["neighbors_all_fire"], x["exiting"], x["assigned"], x["bound_victim"]))
    print("   victim terminal timeline:")
    prev = {}
    for s in d["trace"]:
        for v in s["victims"]:
            if prev.get(v["id"]) != (v["status"], v["needs"]):
                print("     step %3d %-10s status=%-12s needs=%s pos=%s" % (
                    s["step"], v["id"], v["status"], v["needs"], v["pos"]))
                prev[v["id"]] = (v["status"], v["needs"])
    print("   rescue cmds:")
    for x in d["events"]:
        if x["kind"] == "rescue_cmd" and x.get("ok"):
            print("     step %3d %-8s %-10s vid=%-10s reason=%-24s src=%-10s tgt=%-10s reach=%s" % (
                x["step"], x["action"], x.get("ff", x["ff_id"]), x["vid"], x["reason"],
                x.get("src"), x.get("target"), x.get("reachable_at_assign")))
    print("   releases:")
    for x in d["events"]:
        if x["kind"] == "release_other_claimants":
            print("     step %3d vid=%-10s keep=%-10s reason=%-20s released=%s work_left=%s changed=%s" % (
                x["step"], x["vid"], x["keep"], x["reason"], x["released"],
                x["work_left_before"], x["changed"]))


def cmd_ffstory(d, ffid):
    print("== %s: %s ==" % (d["tag"], ffid))
    prev = None
    for s in d["trace"]:
        f = ffmap(s).get(ffid)
        if f is None:
            continue
        key = (f["pos"], f["status"], f["assigned"], f["exiting"], f["dead"], f["target"], f["bound"])
        if key != prev:
            print("  step %3d pos=%-10s status=%-14s assigned=%-5s exiting=%-5s dead=%-5s tgt=%-10s bound=%s" % (
                s["step"], f["pos"], f["status"], f["assigned"], f["exiting"], f["dead"],
                f["target"], f["bound"]))
            prev = key
    print("  -- reval decisions mentioning %s --" % ffid)
    agg = collections.Counter()
    first = {}
    for x in d["events"]:
        if x["kind"] != "reval":
            continue
        for u in x["per_unit"]:
            if u["ff"] != ffid:
                continue
            agg[u["outcome"]] += 1
            first.setdefault(u["outcome"], (x["step"], u.get("pos"), x.get("victim_cells")))
    for k, v in agg.most_common():
        print("     %-32s x%-5d first at step %s pos=%s victim_cells=%s" % (
            k, v, first[k][0], first[k][1], first[k][2]))


def cmd_reval(d, ffid=None, limit=400):
    n = 0
    for x in d["events"]:
        if x["kind"] != "reval":
            continue
        units = [u for u in x["per_unit"] if ffid is None or u["ff"] == ffid]
        if not units:
            continue
        n += 1
        if n > limit:
            print("   ... truncated")
            break
        print("  step %3d gate=%-28s changed=%s" % (x["step"], x["gate"], x.get("changed")))
        for u in units:
            print("      %-10s %-30s pos=%s" % (u["ff"], u["outcome"], u.get("pos")))
        if x.get("victim_cells") is not None:
            print("      victim_cells=%s" % x["victim_cells"])


def cmd_diverge(a, b, upto=None):
    """First step where the seed-matched runs differ, field by field."""
    ta, tb = a["trace"], b["trace"]
    n = min(len(ta), len(tb))
    print("== first divergence %s vs %s ==" % (a["tag"], b["tag"]))
    found = 0
    for i in range(n):
        sa, sb = ta[i], tb[i]
        diffs = []
        fa, fb = ffmap(sa), ffmap(sb)
        for k in sorted(set(fa) | set(fb)):
            x, y = fa.get(k), fb.get(k)
            if x != y:
                for fld in ("pos", "status", "assigned", "exiting", "dead", "target", "bound"):
                    if (x or {}).get(fld) != (y or {}).get(fld):
                        diffs.append("ff:%s.%s %s -> %s" % (k, fld, (x or {}).get(fld), (y or {}).get(fld)))
        va, vb = vmap(sa), vmap(sb)
        for k in sorted(set(va) | set(vb)):
            x, y = va.get(k), vb.get(k)
            if x != y:
                for fld in ("pos", "status", "needs"):
                    if (x or {}).get(fld) != (y or {}).get(fld):
                        diffs.append("victim:%s.%s %s -> %s" % (k, fld, (x or {}).get(fld), (y or {}).get(fld)))
        ua, ub = uavmap(sa), uavmap(sb)
        for k in sorted(set(ua) | set(ub)):
            x, y = ua.get(k), ub.get(k)
            if x != y:
                for fld in ("pos", "bat", "base", "role"):
                    if (x or {}).get(fld) != (y or {}).get(fld):
                        diffs.append("uav:%s.%s %s -> %s" % (k, fld, (x or {}).get(fld), (y or {}).get(fld)))
        if diffs:
            found += 1
            print("  step %3d  (%d diffs)" % (sa["step"], len(diffs)))
            for dd in diffs[:40]:
                print("      %s" % dd)
            if found >= (upto or 3):
                break
    if not found:
        print("  identical over %d steps" % n)


def cmd_uavtimeline(d, limit=None):
    prev = {}
    for s in d["trace"]:
        for u in s["uavs"]:
            k = u["id"]
            cur = (u["base"],)
            if prev.get(k) != cur:
                print("  step %3d uav %-3s base=%-12s pos=%-10s bat=%s" % (
                    s["step"], k, u["base"] or "-", u["pos"], u["bat"]))
                prev[k] = cur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--tag", default="m3")
    ap.add_argument("--other", default="m0")
    ap.add_argument("--ff", default=None)
    ap.add_argument("--n", type=int, default=3)
    a = ap.parse_args()
    d = load(a.tag)
    if a.cmd == "summary":
        cmd_summary(d)
    elif a.cmd == "ffstory":
        cmd_ffstory(d, a.ff)
    elif a.cmd == "reval":
        cmd_reval(d, a.ff)
    elif a.cmd == "diverge":
        cmd_diverge(load(a.other), d, a.n)
    elif a.cmd == "uav":
        cmd_uavtimeline(d)
    else:
        raise SystemExit("unknown cmd")


main()
