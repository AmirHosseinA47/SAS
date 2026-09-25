import collections
import os
import pickle
import sys

SCR = os.path.dirname(os.path.abspath(__file__))
D = pickle.load(open(os.path.join(SCR, "d1_legs.pkl"), "rb"))
ONLY_TRACKED = "--tracked" in sys.argv
comp = [r for r in D["comp"] if r["tracked"] or not ONLY_TRACKED]
broken = [r for r in D["broken"] if r["tracked"] or not ONLY_TRACKED]
print("file set:", "tracked at 80ca7b3 only" if ONLY_TRACKED else "all census-eligible (incl. untracked ugmD)")
print("broken-leg arm-occurrences:", len(broken), dict(collections.Counter(r["cls"] for r in broken)))

# end-step agreement with the census scan (which starts one row later)
dis = [r for r in broken if r["end"] != r["end_census"]]
print("end step differs from the census scan (break inside the start step):", len(dis))
for r in dis[:10]:
    print("   ", r["file"], r["vid"], r["ff"], r["s0"], r["end"], r["end_census"], r["cause"])


def bkey(r):
    end = r["end"] if r["end"] is not None else "H%d" % r["H"]
    return (r["wind"], r["roles"], r["seed"], r["cls"], r["vid"], r["ff"], r["s0"], end, r["p0"], r["cause"])


distinct = collections.OrderedDict()
for r in broken:
    distinct.setdefault(bkey(r), []).append(r)
print("\nDISTINCT broken carrying legs:", len(distinct))
# any key whose files disagree on cause?
for k, rs in distinct.items():
    cs = set(r["cause"] for r in rs)
    if len(cs) > 1:
        print("   CAUSE DISAGREES across files:", k, cs)


def fine(r):
    """Cause refined with the unassign record at the end step."""
    c = r["cause"]
    ua = r["ua_end"]
    if c == "died":
        if "replacement_after_blocked" in ua:
            return "died (same step as a route_blocked unassign)"
        return "died (%s)" % (",".join(sorted(set(ua))) or "no unassign of this pair at end step")
    if c == "route_blocked":
        return "route_blocked drop (%s)" % (",".join(sorted(set(ua))) or "no unassign")
    if c.startswith("released"):
        return "%s (%s)" % (c, ",".join(sorted(set(ua))) or "no unassign")
    if c == "horizon":
        return "horizon cut at %d" % r["H"]
    return c


for cls in ("OFF", "ON"):
    ks = [k for k in distinct if k[3] == cls]
    cc = collections.Counter(distinct[k][0]["cause"] for k in ks)
    cf = collections.Counter(fine(distinct[k][0]) for k in ks)
    occ = collections.Counter(r["cause"] for r in broken if r["cls"] == cls)
    print("\nFIRE MECHANIC %s: %d arm-occurrences, %d DISTINCT broken legs" % (cls, sum(occ.values()), len(ks)))
    print("  by cause (distinct):", dict(cc))
    print("  by cause (arm-occurrences):", dict(occ))
    print("  refined (distinct):")
    for c, v in sorted(cf.items(), key=lambda t: -t[1]):
        print("     %3d  %s" % (v, c))
    # horizon cuts: does the same carry (tuple, vid, ff, s0, p0) end some other way in a longer run?
    hz = [k for k in ks if distinct[k][0]["cause"] == "horizon"]
    other = collections.defaultdict(set)
    for r in comp:
        if r["cls"] == cls:
            other[(r["wind"], r["roles"], r["seed"], r["vid"], r["ff"], r["s0"], r["p0"])].add("completed@%d" % r["s1"])
    for r in broken:
        if r["cls"] == cls and r["cause"] != "horizon":
            other[(r["wind"], r["roles"], r["seed"], r["vid"], r["ff"], r["s0"], r["p0"])].add("%s@%s" % (r["cause"], r["end"]))
    print("  horizon cuts (distinct %d): start step, horizon, and what the same carry did in a longer run" % len(hz))
    for k in sorted(hz, key=lambda k: (str(k[0]), str(k[1]), k[2], k[6])):
        r = distinct[k][0]
        o = other.get((k[0], k[1], k[2], k[4], k[5], k[6], k[8]), set())
        print("     %s/%s/%s %s %s from %d at %s, cut at %d (carried %d steps), first boundary %s; tags %s; elsewhere: %s" % (
            k[0], k[1], k[2], k[4], k[5], k[6], list(k[8]), r["H"], r["H"] - k[6] + 1, r["first_b"],
            ",".join(sorted(set(x["tag"] for x in distinct[k]))[:6]) + ("..." if len(set(x["tag"] for x in distinct[k])) > 6 else ""),
            sorted(o) or "-"))
    print("  non-horizon broken legs (distinct %d):" % (len(ks) - len(hz)))
    for k in sorted([k for k in ks if k not in hz], key=lambda k: (str(k[0]), str(k[1]), k[2], k[6])):
        r = distinct[k][0]
        fb = r["first_b"]
        print("     %s/%s/%s %s %s from %d at %s, ended %s: %s; status %s; unassigns %s; unreach %s; victim %s%s; ff dead %s; first boundary %s%s; later completion %s; %d file(s) e.g. %s" % (
            k[0], k[1], k[2], k[4], k[5], k[6], list(k[8]), r["end"], fine(r), r["status_at_end"], r["ua"], r["um"],
            r["fate"], "" if r["victim_dead"] is None else " (dead %d)" % r["victim_dead"], r["ff_dead"],
            fb, "" if fb is None else " (%d before the end)" % (r["end"] - fb), r["later_comp"] or "-", len(distinct[k]),
            distinct[k][0]["tag"]))
    nh = [k for k in ks if k not in hz]
    fbn = sum(1 for k in nh if distinct[k][0]["first_b"] is not None)
    vd = sum(1 for k in nh if distinct[k][0]["victim_dead"] is not None)
    print("  non-horizon: carrier stood on a boundary cell during the carry before the break: %d of %d; victim dead by run end: %d of %d" % (fbn, len(nh), vd, len(nh)))
    fbh = sum(1 for k in hz if distinct[k][0]["first_b"] is not None)
    print("  horizon cuts: carrier stood on a boundary cell during the carry: %d of %d" % (fbh, len(hz)))

nocause = set(k[:9] for k in distinct)
print("\nDistinct broken legs keyed WITHOUT the cause:", len(nocause), " OFF", sum(1 for k in nocause if k[3] == "OFF"), " ON", sum(1 for k in nocause if k[3] == "ON"))
# first boundary contact inside the run only
for cls in ("OFF", "ON"):
    ks = [k for k in distinct if k[3] == cls]
    inrun = [k for k in ks if distinct[k][0]["first_b"] is not None and distinct[k][0]["first_b"] <= distinct[k][0]["H"]]
    print("  %s: distinct broken legs whose carrier stood on a boundary cell at the start of an in-run step before the end: %d of %d -> %s" % (
        cls, len(inrun), len(ks), [(k[0], k[1], k[2], k[4], k[5], k[6], k[9], distinct[k][0]["first_b"], k[7]) for k in inrun]))
# victim situations behind the completed legs (diagnosis: 909 from 349, 32 stalls from 24)
dl = collections.defaultdict(set)
for r in comp:
    k = (r["wind"], r["roles"], r["seed"], r["cls"], r["vid"], r["ff"], r["s0"], r["s1"], r["p0"], r["tgt"])
    dl[k].add(r["s1"] - r["s0"] > r["dist"] + 5)
for cls in ("OFF", "ON"):
    ks = [k for k in dl if k[3] == cls]
    sit = set(k[:5] for k in ks)
    sst = set(k[:5] for k in ks if True in dl[k])
    print("  %s completed: distinct legs %d from %d (wind, roles, seed, victim) situations; stalled %d from %d" % (
        cls, len(ks), len(sit), sum(1 for k in ks if True in dl[k]), len(sst)))
