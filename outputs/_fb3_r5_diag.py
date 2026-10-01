"""fix3b re-screen (read-only): the R-5 flagged seeds - a firefighter-oscillation / drift rise on a seed that also
lost a rescue. Per victim: first detection, terminal status and step, the firefighter that served it; per
firefighter: oscillation episodes with its status during them. Answers whether the lost rescue is the
oscillating firefighter's victim and whether the episode precedes the death.

usage (repo root): .venv/Scripts/python.exe -B outputs/_fb3_r5_diag.py [ref:arm:seed ... | --losses]
"""
import collections
import sys

sys.path.insert(0, r"E:\Projects\SAS\outputs")
TRIPLES, sys.argv = sys.argv[1:], sys.argv[:1]
import _fb3_analyze as A  # noqa: E402

DEFAULT = ["fx3mS2:fb3bdr2:D_W", "fx3mS2:fb3bfr2:D_W", "fb3vs0:fb3vs3r:D_W"]


def victims(d):
    det = A.det_times(d)
    first_term, served = {}, {}
    for t, row in enumerate(d["rows_vic"]):
        for v in row:
            if v[3] in ("rescued", "dead") and v[0] not in first_term:
                first_term[v[0]] = (v[3], t + 1)
            if v[5]:
                served[v[0]] = v[5]
    return {v: (det.get(v), first_term.get(v), served.get(v)) for v in det}


def ff_info(d):
    eps = collections.defaultdict(list)
    for fid, s0, s1, n in A.ff_episodes(d):
        st = collections.Counter(str(f[3]) for t in range(s0 - 1, s1) for f in d["rows_ff"][t] if f[0] == fid)
        eps[fid].append((s0, s1, n, dict(st)))
    return eps


if TRIPLES[:1] == ["--losses"]:
    # both directions: victims rescued by CUR but not by the arm (LOST) and the reverse (GAINED), with first
    # detection in both arms (much later in the arm = search order; within a few steps = downstream of detection)
    for ref, arm in (("fx3mS", "fb3bdr"), ("fx3mS", "fb3bfr"), ("fx3mS2", "fb3bdr2"), ("fx3mS2", "fb3bfr2"),
                     ("fb3vs0", "fb3vs3r")):
        ra, rb = A.load(ref), A.load(arm)
        for k in sorted(set(ra) & set(rb)):
            a, b = ra[k], rb[k]
            va, vb = victims(a), victims(b)
            lost = [(v, va[v][0], vb[v][0], vb[v][1], vb[v][2]) for v in va
                    if (va[v][1] or ("",))[0] == "rescued" and (vb[v][1] or ("",))[0] != "rescued"]
            won = [(v, va[v][0], vb[v][0], va[v][1], va[v][2]) for v in va
                   if (vb[v][1] or ("",))[0] == "rescued" and (va[v][1] or ("",))[0] != "rescued"]
            if lost:
                print("%-7s %-4s rescued %d -> %d | LOST (victim, det CUR, det arm, arm terminal, arm ff): %s" % (
                    arm, k, a["eval"]["rescued"], b["eval"]["rescued"], lost))
            if won:
                print("%-7s %-4s rescued %d -> %d | GAINED (victim, det CUR, det arm, CUR terminal, CUR ff): %s" % (
                    arm, k, a["eval"]["rescued"], b["eval"]["rescued"], won))
    sys.exit(0)

for trip in TRIPLES or DEFAULT:
    ref, arm, seed = trip.split(":")
    a, b = A.load(ref)[seed], A.load(arm)[seed]
    print("=" * 100)
    print("%s vs %s seed %s | rescued %s -> %s | dead %s -> %s | ff deaths %s -> %s | terminal %s -> %s" % (
        ref, arm, seed, a["eval"]["rescued"], b["eval"]["rescued"], a["eval"]["dead"], b["eval"]["dead"],
        a["eval"]["firefighter_deaths"], b["eval"]["firefighter_deaths"], a.get("terminal_step"), b.get("terminal_step")))
    va, vb = victims(a), victims(b)
    for v in sorted(va):
        print("  %-9s REF det %-4s %-18s by %-10s | ARM det %-4s %-18s by %-10s" % (
            v, va[v][0], va[v][1], va[v][2], vb[v][0], vb[v][1], vb[v][2]))
    for name, d in (("REF", a), ("ARM", b)):
        for fid, eps in sorted(ff_info(d).items()):
            print("  %s ff episodes %-10s %s" % (name, fid, eps))
    print("  DRIFT alarms REF %d ARM %d" % (A._alarms(a), A._alarms(b)))
