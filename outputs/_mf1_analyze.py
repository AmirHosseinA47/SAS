"""fix1 (mf1) Part 3 analysis - the pre-registered checks P3-1..P3-5 (read-only).

usage: _mf1_analyze.py [--out outputs/_mf1_analysis.txt]
Reads outputs/_ffr_mf1*.json (harness), outputs/_sd_mf1*.json (probe). Every comparison is
seed-matched by run name; a missing file is reported as MISSING, never skipped silently.
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

OUT = os.path.dirname(os.path.abspath(__file__))
IGNORE = {"tag", "repo", "wall_s"}
# extra_params is the --set dict a run was given; it is ignored ONLY where the arms differ
# in a switch value by construction (passed through ignore_top), never in P3-1.
NEW_EVAL = {"no_firefighter_available", "long_undetected", "long_undetected_detected", "long_undetected_rescued"}
LINES: list = []


def say(msg=""):
    LINES.append(msg)
    print(msg)


def load(name):
    p = os.path.join(OUT, "_ffr_%s.json" % name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def load_stdout(name):
    p = os.path.join(OUT, "_ffr_%s.stdout.txt" % name)
    return open(p, encoding="utf-8").read().splitlines() if os.path.exists(p) else None


def living_free(ff_row):
    _ff, pos, status, assigned, exiting, dead = ff_row
    return (not dead) and status != "dead" and (not exiting) and pos is not None


def check_item5_relabel(z, entry):
    """True iff no free living firefighter existed on every step of the 30-step streak."""
    step = int(entry["step"])
    streak = int(entry.get("streak") or 0)
    for t in range(step - streak + 1, step + 1):
        if t < 1 or t > len(z["ff_steps"]):
            return False
        if any(living_free(r) for r in z["ff_steps"][t - 1]):
            return False
    return True


def diff_keys(a, b, ignore=IGNORE):
    keys = (set(a) | set(b)) - set(ignore)
    return sorted(k for k in keys if a.get(k, "<absent>") != b.get(k, "<absent>"))


LAUNCH = ("UAV_LAUNCH_BATTERY_FRACTION",)
ROLE_KEYS = ("NUM_FIRE_TRACKERS", "NUM_VICTIM_SEARCHERS", "ROLE_SPLIT_HALF_RULE")


def identity(ref_name, new_name, *, ignore_params=LAUNCH, ignore_top=()):
    """P3-1 rule: every field equal but tag/repo/wall_s, the new eval keys (0 or relabel),
    and item-5 relabels verified against ff_steps. `ignore_params` / `ignore_top` name the
    params and top-level keys the two arms differ in BY CONSTRUCTION (a switch value, the
    --roles label) - listed in the note, never silently. Returns (ok, notes)."""
    r, z = load(ref_name), load(new_name)
    if r is None or z is None:
        return False, ["MISSING %s" % (ref_name if r is None else new_name)]
    notes = []
    ok = True
    for k in diff_keys(r, z, IGNORE | set(ignore_top)):
        if k == "params":
            pr = {x: v for x, v in r["params"].items() if x not in ignore_params}
            pz = {x: v for x, v in z["params"].items() if x not in ignore_params}
            if pr != pz:
                ok = False
                notes.append("params differ: %s" % diff_keys(pr, pz, ()))
            else:
                notes.append("params differ only in %s (by construction)" % sorted(
                    x for x in set(r["params"]) | set(z["params"])
                    if r["params"].get(x, "<absent>") != z["params"].get(x, "<absent>")))
        elif k == "eval":
            er, ez = r["eval"], z["eval"]
            dk = diff_keys(er, ez, ())
            relabel = [x for x in dk if x not in NEW_EVAL]
            new_nonzero = [x for x in dk if x in NEW_EVAL and ez.get(x)]
            if new_nonzero:
                notes.append("new eval keys non-zero: %s" % {x: ez[x] for x in new_nonzero})
            if relabel:
                notes.append("eval differs on %s" % relabel)
                allowed = {"geographically_isolated", "unreachable_other", "unreachable_causes"}
                if not set(relabel) <= allowed:
                    ok = False
        elif k == "unreachable_escape_log":
            lr, lz = r[k], z[k]
            if len(lr) != len(lz):
                ok = False
                notes.append("escape log length %d vs %d" % (len(lr), len(lz)))
                continue
            for er_, ez_ in zip(lr, lz):
                base_r = {x: er_[x] for x in er_ if x not in ("cause", "reason")}
                base_z = {x: ez_[x] for x in ez_ if x not in ("cause", "reason", "firefighters_alive")}
                if base_r != base_z:
                    ok = False
                    notes.append("escape entry differs beyond the cause: %s / %s" % (er_, ez_))
                elif er_["cause"] != ez_["cause"]:
                    good = (ez_["cause"] == "no_firefighter_available" and er_["cause"] == "geographically_isolated"
                            and check_item5_relabel(z, ez_))
                    notes.append("item-5 relabel %s step %s %s -> %s (%s)" % (
                        ez_["victim_id"], ez_["step"], er_["cause"], ez_["cause"],
                        "verified: no free rescuer on every streak step" if good else "NOT VERIFIED"))
                    ok = ok and good
        elif k == "rescue_failed":
            strip = lambda L: [{x: v for x, v in e.items() if x not in ("reason", "meta")} for e in L]
            if strip(r[k]) != strip(z[k]):
                ok = False
                notes.append("rescue_failed differs beyond reasons")
            else:
                notes.append("rescue_failed: reason text only (item-5 relabel)")
        elif k == "stdout_sha256":
            sr, sz = load_stdout(ref_name), load_stdout(new_name)
            if sr is None or sz is None or len(sr) != len(sz):
                ok = False
                notes.append("stdout differs in length")
                continue
            bad = [(a, b) for a, b in zip(sr, sz) if a != b and not (
                a.replace("geographically_isolated", "X") == b.replace("no_firefighter_available", "X"))]
            if bad:
                ok = False
                notes.append("stdout differs: %s" % bad[:2])
            else:
                notes.append("stdout: only item-5 cause text")
        elif k == "roles_effective":
            ok = False
            notes.append("roles_effective %s vs %s" % (r.get(k), z.get(k)))
        else:
            ok = False
            notes.append("DIFFERS: %s" % k)
    return ok, notes


def first_uav_diff(a, b):
    for t, (ra, rb) in enumerate(zip(a["uav_steps"], b["uav_steps"]), start=1):
        if ra != rb:
            who = [x[0] for x, y in zip(ra, rb) if x != y]
            roles = {x[0]: x[2] for x in ra}
            return t, [(u, roles.get(u)) for u in who]
    return None, []


def rtb_trips(d):
    return {u: [(t["trigger_step"], round(t["trigger_level"], 1), t["trigger_distance"], t["arrival_step"])
                for t in v] for u, v in d["rtb_log"].items()}


def main() -> int:
    out_path = os.path.join(OUT, "_mf1_analysis.txt")
    if "--out" in sys.argv:
        out_path = sys.argv[sys.argv.index("--out") + 1]
    sys.path.insert(0, OUT)
    import _mf1_queue as q  # noqa: E402

    def nm(arm, t):
        return "%s_%s_%s_%s_%d" % (arm, t[0], t[1], t[2], t[3])

    # ---------------------------------------------------------------- P3-1
    say("=" * 100)
    say("P3-1 ALL SWITCHES OFF (mf1Z, fix1) == 51c5165 (mf1R), canonical sample: %d tuples" % len(q.P31))
    n_ok = 0
    for t in q.P31:
        ok, notes = identity(nm("mf1R", t), nm("mf1Z", t))
        n_ok += ok
        say("  %-40s %s  %s" % (nm("", t)[1:], "IDENTICAL" if ok else "FAIL", "; ".join(notes) if notes else ""))
    say("  P3-1: %d/%d %s" % (n_ok, len(q.P31), "PASS" if n_ok == len(q.P31) else "FAIL"))

    # ---------------------------------------------------------------- P3-2
    say("=" * 100)
    say("P3-2 ITEM 2 ALONE (mf1Bt) vs ALL OFF (mf1Z)")
    for t in q.P32:
        b, z = load(nm("mf1Bt", t)), load(nm("mf1Z", t))
        if b is None or z is None:
            say("  %s MISSING" % nm("", t)[1:])
            continue
        if t[0] != "B":
            ok, notes = identity(nm("mf1Z", t), nm("mf1Bt", t), ignore_params=LAUNCH + ("REDUCED_LAUNCH_BATTERY",),
                                 ignore_top=("extra_params",))
            say("  %-28s A/C/D unaffected: %s  %s" % (nm("", t)[1:], "IDENTICAL" if ok else "DIFFERS",
                                                     "; ".join(notes)))
            continue
        start = [r[4] for r in b["uav_steps"][0]]
        trips = rtb_trips(b)
        ztrips = rtb_trips(z)
        n2 = all(len(v) == 2 for v in trips.values())
        first_ok = all(v and v[0][0] <= 40 and v[0][2] > 0 for v in trips.values())
        arrived = all(tr[3] is not None for v in trips.values() for tr in v)
        minb = min(r[4] for step in b["uav_steps"] for r in step if r[5] in ("", "returning"))
        say("  %-28s start %s  trips/UAV %s (off %s)  first<=40 in flight %s  all arrive %s  min in-flight battery %.1f"
            % (nm("", t)[1:], start, [len(v) for v in trips.values()], [len(v) for v in ztrips.values()],
               first_ok, arrived, minb))
        say("      trips %s" % trips)
        ev, ez = b["eval"], z["eval"]
        say("      outcome (reported, not gated): rescued %d->%d dead %d->%d never_detected %d->%d terminal %s->%s"
            % (ez["rescued"], ev["rescued"], ez["dead"], ev["dead"], ez.get("never_detected", 0),
               ev.get("never_detected", 0), ez["terminal_step"], ev["terminal_step"]))

    # ---------------------------------------------------------------- P3-3
    say("=" * 100)
    say("P3-3 ITEM 3 ALONE (mf1Rl)")
    for t in q.P33:
        rl = load(nm("mf1Rl", t))
        if rl is None:
            say("  %s MISSING" % nm("", t)[1:])
            continue
        n_search = len(rl["partition_steps"][0].get("searchers") or [])
        line = "  %-28s roles_effective %s, searchers at step 1: %d" % (nm("", t)[1:], rl["roles_effective"], n_search)
        if t[0] in "AB":
            if t[2] == "default":
                ok, notes = identity(nm("mf1Z", t), nm("mf1Rl", t), ignore_params=LAUNCH + ROLE_KEYS,
                                     ignore_top=("extra_params",))
                line += "  vs mf1Z: %s %s" % ("IDENTICAL" if ok else "DIFFERS", "; ".join(notes))
            else:
                ok, notes = identity(nm("mf1Rl", (t[0], t[1], "default", t[3])), nm("mf1Rl", t),
                                     ignore_params=ROLE_KEYS, ignore_top=("roles",))
                line += "  vs its own --roles default: %s %s" % ("IDENTICAL" if ok else "DIFFERS", "; ".join(notes))
        elif t[0] == "D":
            ok, notes = identity(nm("mf1Z", ("D", "east", "half", t[3])), nm("mf1Rl", t),
                                 ignore_params=LAUNCH + ROLE_KEYS, ignore_top=("roles", "extra_params"))
            line += "  vs mf1Z east/HALF: %s %s" % ("IDENTICAL" if ok else "DIFFERS", "; ".join(notes))
        elif t[0] == "C" and t[2] == "half":
            ok, notes = identity(nm("mf1Rl", (t[0], t[1], "default", t[3])), nm("mf1Rl", t),
                                 ignore_params=ROLE_KEYS, ignore_top=("roles",))
            line += "  vs its own --roles default: %s %s" % ("IDENTICAL" if ok else "DIFFERS", "; ".join(notes))
        else:
            z = load(nm("mf1Z", t))
            if z is not None:
                t1, who = first_uav_diff(z, rl)
                line += "  vs mf1Z (4+1): first UAV row diff at step %s; rescued %d->%d" % (
                    t1, z["eval"]["rescued"], rl["eval"]["rescued"])
        say(line)

    # ---------------------------------------------------------------- P3-5
    say("=" * 100)
    say("P3-5 ITEM 6 ALONE (mf1Ct, instrumented) vs ALL OFF (mf1Zc, instrumented; mf1Z plain)")
    for t in q.P35:
        ct, zc, zp = load(nm("mf1Ct", t)), load(nm("mf1Zc", t)), load(nm("mf1Z", t))
        if ct is None or zc is None or zp is None:
            say("  %s MISSING" % nm("", t)[1:])
            continue
        ok_pass, notes = identity(nm("mf1Z", t), nm("mf1Zc", t))
        cc = json.load(open(os.path.join(OUT, "_ffr_%s.json.counters.json" % nm("mf1Ct", t)), encoding="utf-8"))
        zcc = json.load(open(os.path.join(OUT, "_ffr_%s.json.counters.json" % nm("mf1Zc", t)), encoding="utf-8"))
        t1, who = first_uav_diff(zp, ct)
        say("  %-26s instrumentation pass-through %s | Ct max advances/step %s | Zc max advances/step %s"
            % (nm("", t)[1:], "IDENTICAL" if ok_pass else "DIFFERS " + "; ".join(notes),
               cc["max_advances_per_step"], zcc["max_advances_per_step"]))
        say("      calls/step Ct %s" % {k: v["mean_calls"] for k, v in cc["calls_per_step"].items()})
        say("      first differing UAV row: step %s, UAVs %s | rescued %d->%d, first-detection shift reported below"
            % (t1, who, zp["eval"]["rescued"], ct["eval"]["rescued"]))

    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(LINES) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
