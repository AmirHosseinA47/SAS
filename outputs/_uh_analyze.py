"""Ungated round, horizon measurement - analysis (outputs/ungated_horizon_prereg.txt).
Read-only. -> outputs/_uh_analysis.txt

  P1 provenance       every uh run's repo / extra_params / tuple / steps == its arm's
  P2 prefix identity  each uh run's first 240 steps == its recorded 240-step ug run
                      (per-step series and every event list restricted to step <= 240)
  outcomes            rescued / dead / still-unresolved at step 240 (read from the uh run's
                      own step-240 victim statuses) and at 360, arms uhC / uhD / uhY
  the 11              each victim lost at 240 (ugC rescued, ugD not): fate at 360 and the
                      step it resolved (rescue = its completion step, death = first step
                      its status is dead)
  cost at 360         loss = R(uhC) - R(uhD); limit = (2/68) x R(uhC) + 3
  after 240           every victim status change and every firefighter death after 240
  decision            the maintainer's rule: >= 6 of the 11 rescued by 360 AND loss <= limit
"""
from __future__ import annotations

import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _ug_analyze as U  # noqa: E402  (U30, labels, victims(); its loader checks ug arms)

H = 360
FLIP = "e:/projects/sas"
CTRL = "e:/projects/sas_wt/base11c3661"
ARMS = {
    "uhC": ("ugC", CTRL, {"BATCH_SIZE": 360}),
    "uhD": ("ugD", FLIP, {"BATCH_SIZE": 360}),
    "uhY": ("ugY", FLIP, {"BATCH_SIZE": 360, "FF_FIREFIGHT_DRY_RUN": 1}),
}
SERIES = ("fire_digests", "victim_steps", "ff_steps", "ff_bind_steps", "uav_steps", "uav_actions",
          "partition_steps")
EVENTS = ("assigns", "unassigns", "completions", "recycles", "firefight_log", "retargets",
          "exit_starts", "unreachable_marks", "planner", "absence_log", "victim_flee_log",
          "victim_lateral_log", "unreachable_escape_log", "victim_holds", "rescue_failed")
# lists whose entries carry the step under another key
EVENTS_KEYED = {"recycle_to_next_assign": "recycle_step"}
COMPARED = collections.Counter()   # event list -> number of runs in which it was compared
ELEVEN = [
    (("east", "half", 1433805104), "victim_0"), (("east", "half", 1252362635), "victim_0"),
    (("east", "half", 1252362635), "victim_2"), (("east", "half", 1532569567), "victim_0"),
    (("east", "half", 498896028), "victim_0"), (("east", "half", 1401495347), "victim_0"),
    (("east", "half", 133894353), "victim_0"), (("south", "half", 706299103), "victim_3"),
    (("south", "half", 903347495), "victim_3"), (("east", "default", 2038269169), "victim_0"),
    (("east", "default", 1420331661), "victim_0"),
]
OUT = []
REFUSED = []
SKIPPED = set()


def say(s=""):
    OUT.append(str(s))
    print(s)


def path(tag, t):
    rr = "def" if t[1] == "default" else t[1]
    return os.path.join(HERE, "_ffr_%s_%s_%s_%d.json" % (tag, t[0], rr, t[2]))


def norm(p):
    return str(p or "").replace("\\", "/").rstrip("/").lower()


def load_uh(tag, t):
    p = path(tag, t)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    _ref, repo, sets = ARMS[tag]
    why = []
    if norm(d.get("repo")) != repo:
        why.append("repo %r" % d.get("repo"))
    if (d.get("extra_params") or {}) != sets:
        why.append("extra_params %r" % d.get("extra_params"))
    if (d.get("wind"), d.get("roles"), d.get("seed"), d.get("steps")) != (t[0], t[1], t[2], H):
        why.append("tuple %r" % ((d.get("wind"), d.get("roles"), d.get("seed"), d.get("steps")),))
    if d.get("fm2p"):
        why.append("fm2p block present")
    if len(d.get("victim_steps") or []) != H:
        why.append("victim_steps length %d" % len(d.get("victim_steps") or []))
    if why:
        REFUSED.append((tag, U.label(t), "; ".join(why)))
        return None
    return d


def ev_step(e):
    return e.get("step") if isinstance(e, dict) else None


def prefix_diff(long_d, short_d):
    diffs = []
    for k in SERIES:
        a, b = long_d.get(k), short_d.get(k)
        if b is None and a is None:
            continue
        if not isinstance(a, list) or not isinstance(b, list):
            if a != b:
                diffs.append(k + " (type)")
            continue
        if len(b) != 240:
            diffs.append("%s (ref length %d)" % (k, len(b)))
        elif a[:240] != b:
            first = next(i + 1 for i, (x, y) in enumerate(zip(a[:240], b)) if x != y)
            diffs.append("%s (first differs at step %d)" % (k, first))
    for k in EVENTS + tuple(EVENTS_KEYED):
        key = EVENTS_KEYED.get(k, "step")
        la, lb = long_d.get(k), short_d.get(k)
        if not isinstance(la, list) or not isinstance(lb, list):
            if (la is None) != (lb is None):
                diffs.append(k + " (present in one run only)")
            continue
        if any(not isinstance(e, dict) or e.get(key) is None for e in la + lb):
            SKIPPED.add(k)          # entries without a step cannot be cut at 240
            continue
        COMPARED[k] += 1
        a = [e for e in la if e[key] <= 240]
        if a != lb:
            diffs.append("%s (%d vs %d events <= 240)" % (k, len(a), len(lb)))
    return diffs


def statuses_at(d, step):
    row = (d.get("victim_steps") or [])[step - 1]
    return {v[0]: v[2] for v in row}


def fate(d, vid):
    vs = d.get("victim_steps") or []
    final = statuses_at(d, len(vs))[vid]
    comp = next((c["step"] for c in (d.get("completions") or []) if c.get("victim") == vid), None)
    died = next((i + 1 for i, row in enumerate(vs) for v in row if v[0] == vid and v[2] == "dead"), None)
    if final == "rescued":
        return "RESCUED", comp
    if final == "dead":
        return "DEAD", died
    if final == "unreachable":
        first = next((i + 1 for i, row in enumerate(vs) for v in row if v[0] == vid and v[2] == "unreachable"), None)
        why = next((m.get("reason") for m in (d.get("unreachable_marks") or []) if m.get("vid") == vid), "?")
        return "UNREACHABLE (%s)" % why, first
    return "UNRESOLVED (%s)" % final, None


def ff_deaths_after(d, step0):
    out = []
    seen = set()
    for i, row in enumerate(d.get("ff_steps") or []):
        for ff, p, st, asg, ex, dead in row:
            if dead and ff not in seen:
                seen.add(ff)
                if i + 1 > step0:
                    out.append((ff, i + 1))
    return out


def main():
    sys.stdout.reconfigure(newline="\n")
    say("HORIZON MEASUREMENT - analysis (pre-registration outputs/ungated_horizon_prereg.txt)")
    runs = {}
    for tag in ARMS:
        for t in U.U30:
            d = load_uh(tag, t)
            if d is not None:
                runs[(tag, t)] = d
    say("")
    say("P1 PROVENANCE: " + ", ".join("%s %d/30" % (tag, sum(1 for (tg, _t) in runs if tg == tag)) for tag in ARMS))
    for r in REFUSED:
        say("  REFUSED %s %s: %s" % r)
    p1 = not REFUSED and len(runs) == 90
    say("  P1 %s" % ("PASS" if p1 else "FAIL"))

    say("")
    say("P2 PREFIX IDENTITY (steps 1-240 of each uh run == its recorded 240-step ug run)")
    bad = 0
    for (tag, t), d in sorted(runs.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        ref = U.load(ARMS[tag][0], t)
        diffs = prefix_diff(d, ref)
        if diffs:
            bad += 1
            say("  DIFFERS %s %s: %s" % (tag, U.label(t), "; ".join(diffs)))
    say("  %d/%d runs prefix-identical on %s and on %s (events <= 240)" % (
        len(runs) - bad, len(runs), ", ".join(SERIES),
        ", ".join(k for k in EVENTS + tuple(EVENTS_KEYED) if k not in SKIPPED)))
    partial = ["%s %d" % (k, n) for k, n in sorted(COMPARED.items()) if n != len(runs)]
    if partial:
        say("  compared in fewer than %d runs (list absent from both runs of a pair): %s" % (
            len(runs), ", ".join(partial)))
    if SKIPPED:
        say("  not cut at 240 (entries carry no step): %s" % ", ".join(sorted(SKIPPED)))
    p2 = bad == 0 and len(runs) == 90
    say("  P2 %s%s" % ("PASS" if p2 else "FAIL", "" if p2 else " - STOP: the horizon changed steps 1-240; outcomes are NOT read"))
    if not p2:
        return finish()

    say("")
    say("OUTCOMES, U30, 120 victims per arm: rescued / dead / still assigned / unreachable / other")
    tot = {}
    for tag in ARMS:
        for step in (240, H):
            c = collections.Counter()
            for t in U.U30:
                c.update(statuses_at(runs[(tag, t)], step).values())
            tot[(tag, step)] = c
            other = sum(v for k, v in c.items() if k not in ("rescued", "dead", "assigned", "unreachable"))
            say("  %-4s at step %3d   rescued %3d  dead %3d  assigned %2d  unreachable %2d  other %2d" % (
                tag, step, c["rescued"], c["dead"], c["assigned"], c["unreachable"], other))
    say("  firefighter deaths (eval, at 360): " + ", ".join("%s %d" % (tag, sum(runs[(tag, t)]["eval"]["firefighter_deaths"] for t in U.U30)) for tag in ARMS))

    say("")
    say("THE 11 VICTIMS LOST AT STEP 240 (ugC rescued, ugD not) - fate at step %d" % H)
    rescued11 = 0
    for t, vid in ELEVEN:
        fd, sd = fate(runs[("uhD", t)], vid)
        fy, sy = fate(runs[("uhY", t)], vid)
        fc, sc = fate(runs[("uhC", t)], vid)
        rescued11 += fd == "RESCUED"
        say("  %-26s %-9s shipped: %-26s step %-4s | positioning-only: %-24s step %-4s | control: %s at %s" % (
            U.label(t), vid, fd, sd, fy, sy, fc, sc))
    say("  RESCUED BY STEP %d IN THE SHIPPED ARM: %d of 11" % (H, rescued11))

    say("")
    rc, rd = tot[("uhC", H)]["rescued"], tot[("uhD", H)]["rescued"]
    ry = tot[("uhY", H)]["rescued"]
    loss = rc - rd
    limit = 2.0 / 68 * rc + 3
    say("COST AT STEP %d: control %d -> shipped %d, loss %+d; limit (2/68) x %d + 3 = %.2f -> %s" % (
        H, rc, rd, loss, rc, limit, "WITHIN" if loss <= limit else "EXCEEDS"))
    say("  (at step 240, from the same runs: control %d -> shipped %d, loss %+d; limit %.2f)" % (
        tot[("uhC", 240)]["rescued"], tot[("uhD", 240)]["rescued"],
        tot[("uhC", 240)]["rescued"] - tot[("uhD", 240)]["rescued"], 2.0 / 68 * tot[("uhC", 240)]["rescued"] + 3))
    say("  positioning only at %d: control %d -> %d, loss %+d (reported, not in the decision)" % (H, rc, ry, rc - ry))

    say("")
    say("EVERY VICTIM STATUS CHANGE AFTER STEP 240, and firefighter deaths after 240")
    for tag in ARMS:
        ch = []
        for t in U.U30:
            d = runs[(tag, t)]
            a, b = statuses_at(d, 240), statuses_at(d, H)
            for vid in sorted(a):
                if a[vid] != b[vid]:
                    f, s = fate(d, vid)
                    ch.append("%s %s %s -> %s (step %s)" % (U.label(t), vid, a[vid], b[vid], s))
            for ff, s in ff_deaths_after(d, 240):
                ch.append("%s FIREFIGHTER %s died at step %d" % (U.label(t), ff, s))
        say("  %s: %d change(s)" % (tag, len(ch)))
        for c in ch:
            say("      " + c)

    addenda(runs)

    say("")
    most = rescued11 >= 6
    within = loss <= limit
    say("DECISION RULE (maintainer, pre-registered): >= 6 of the 11 rescued by step %d AND loss <= limit" % H)
    say("  rescued of the 11: %d (%s)   cost: %+d vs %.2f (%s)" % (
        rescued11, "most" if most else "NOT most", loss, limit, "within" if within else "exceeds"))
    say("  => %s" % ("(a) - the -8 was a horizon artifact" if (most and within) else "(b) - the cost is genuine"))
    return finish()


GRID = 50   # common_fixed_variables WIDTH = HEIGHT = 50 (the run JSON's dim key is null)


def rescued_count(runs, tag, step):
    return sum(1 for t in U.U30 for s in statuses_at(runs[(tag, t)], step).values() if s == "rescued")


def completion_steps(d):
    return {c["victim"]: c["step"] for c in d.get("completions") or []}


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def edge_dist(p):
    return min(p[0], p[1], GRID - 1 - p[0], GRID - 1 - p[1])


def exit_legs(d):
    """(victim, exit start step, completion step, manhattan start -> fixed exit target) per
    completion; start = the victim's last exit_start at or before its completion."""
    out = []
    for c in d.get("completions") or []:
        st = [e for e in d.get("exit_starts") or [] if e.get("victim") == c["victim"] and e["step"] <= c["step"]]
        if st:
            out.append((c["victim"], st[-1]["step"], c["step"], manhattan(st[-1]["ff_pos"], c["exit_target"] or c["pos"])))
    return out


def work_left_240(d, vid):
    """The pre-registered remaining-work bound at step 240: manhattan unit -> victim + victim ->
    nearest edge, or unit -> nearest edge when already carrying (exit_start after the last assign)."""
    asg = [a for a in d.get("assigns") or [] if a.get("vid") == vid and a["step"] <= 240]
    if not asg:
        return None
    ff, since = asg[-1]["ff"], asg[-1]["step"]
    upos = next(r[1] for r in d["ff_steps"][239] if r[0] == ff)
    vpos = next(r[1] for r in d["victim_steps"][239] if r[0] == vid)
    carrying = any(e.get("victim") == vid and since <= e["step"] <= 240 for e in d.get("exit_starts") or [])
    if carrying or vpos is None:
        return edge_dist(upos)
    return manhattan(upos, vpos) + edge_dist(vpos)


def addenda(runs):
    """Added after the independent verification pass (outputs/_uh_report_verify.txt)."""
    say("")
    say("ADDENDA (added after the verification pass; read-only, same runs)")
    say("  COST TRAJECTORY, shipped vs control (limit = (2/68) x control + 3):")
    for step in (240, 270, 300, 330, 360):
        rc, rd, ry = (rescued_count(runs, tg, step) for tg in ("uhC", "uhD", "uhY"))
        say("    step %3d  control %3d  shipped %3d  positioning-only %3d   loss %d (limit %.2f)   positioning-only loss %d" % (
            step, rc, rd, ry, rc - rd, 2.0 / 68 * rc + 3, rc - ry))

    say("  THE -8 -> -2 DECOMPOSITION (per-victim flips, control -> shipped):")
    for step in (240, H):
        lost, gained = [], []
        for t in U.U30:
            a, b = statuses_at(runs[("uhC", t)], step), statuses_at(runs[("uhD", t)], step)
            for vid in sorted(a):
                if a[vid] == "rescued" and b[vid] != "rescued":
                    lost.append("%s %s" % (U.label(t), vid))
                elif b[vid] == "rescued" and a[vid] != "rescued":
                    gained.append("%s %s (control %s)" % (U.label(t), vid, a[vid]))
        say("    at %d: lost %d, gained %d, net %+d; gained: %s" % (step, len(lost), len(gained), len(gained) - len(lost), "; ".join(gained)))

    say("  TIMING vs the control (completion step, victims rescued in BOTH arms by %d):" % H)
    for tag in ("uhD", "uhY"):
        diffs = []
        for t in U.U30:
            cc, cx = completion_steps(runs[("uhC", t)]), completion_steps(runs[(tag, t)])
            sa, sb = statuses_at(runs[("uhC", t)], H), statuses_at(runs[(tag, t)], H)
            diffs += [cx[v] - cc[v] for v in cc if v in cx and sa.get(v) == "rescued" and sb.get(v) == "rescued"]
        diffs.sort()
        say("    %s: %d victims; earlier %d, later %d, same %d; mean %+.1f, median %+.1f steps" % (
            tag, len(diffs), sum(x < 0 for x in diffs), sum(x > 0 for x in diffs), sum(x == 0 for x in diffs),
            sum(diffs) / len(diffs), (diffs[len(diffs) // 2] + diffs[(len(diffs) - 1) // 2]) / 2.0))
    lag = []
    for t, vid in ELEVEN:
        a, b = completion_steps(runs[("uhC", t)]).get(vid), completion_steps(runs[("uhD", t)]).get(vid)
        if a is not None and b is not None and statuses_at(runs[("uhD", t)], H)[vid] == "rescued":
            lag.append(b - a)
    lag.sort()
    say("    the %d of the 11 rescued late: shipped minus control %s steps (mean %.1f)" % (
        len(lag), lag, sum(lag) / len(lag)))

    say("  EXIT LEGS (exit start -> completion) longer than their manhattan distance to the fixed exit cell + 5:")
    for tag in ARMS:
        n, slow = 0, []
        for t in U.U30:
            for vid, s0, s1, dist in exit_legs(runs[(tag, t)]):
                n += 1
                if s1 - s0 > dist + 5:
                    slow.append("%s %s %d steps for %d cells (%d-%d)" % (U.label(t), vid, s1 - s0, dist, s0, s1))
        say("    %s: %d of %d legs%s" % (tag, len(slow), n, "".join("\n        " + s for s in slow)))

    say("  WORK LEFT AT 240 (pre-registered manhattan bound) vs steps actually needed after 240:")
    for tag in ARMS:
        rows = []
        for t in U.U30:
            d = runs[(tag, t)]
            comp = completion_steps(d)
            for vid, st in sorted(statuses_at(d, 240).items()):
                if st == "assigned":
                    w = work_left_240(d, vid)
                    got = comp.get(vid)
                    rows.append("%s %s bound %s, needed %s" % (U.label(t), vid, w, (got - 240) if got else "not done by %d" % H))
        say("    %s: %s" % (tag, "".join("\n        " + r for r in rows)))

    say("  NOT RESCUED AT %d, from eval: dead / unreachable (never_detected, geographically_isolated, other) / candidate / horizon_unresolved" % H)
    for tag in ARMS:
        e = collections.Counter()
        for t in U.U30:
            ev = runs[(tag, t)]["eval"]
            for k in ("dead", "unreachable", "never_detected", "geographically_isolated", "unreachable_other",
                      "candidate", "horizon_unresolved"):
                e[k] += ev.get(k) or 0
        say("    %s: %d / %d (%d, %d, %d) / %d / %d   -> not rescued %d" % (
            tag, e["dead"], e["unreachable"], e["never_detected"], e["geographically_isolated"], e["unreachable_other"],
            e["candidate"], e["horizon_unresolved"], e["dead"] + e["unreachable"] + e["candidate"]))

    say("  FIRE: runs whose fire_digests equal the control's at all %d steps; shipped runs with no fire write" % H)
    for tag in ("uhD", "uhY"):
        same = sum(runs[(tag, t)]["fire_digests"] == runs[("uhC", t)]["fire_digests"] for t in U.U30)
        say("    %s == uhC: %d/30" % (tag, same))
    nowrite = [U.label(t) for t in U.U30 if not any(e.get("wrote") for e in runs[("uhD", t)].get("firefight_log") or [])]
    say("    uhD tuples with no fire write in %d steps: %s" % (H, ", ".join(nowrite) or "none"))

    say("  FIREFIGHTER DEATHS in the tuples of the 4 genuine losses (unit, step):")
    for t, vid in ELEVEN:
        if statuses_at(runs[("uhD", t)], H)[vid] == "rescued":
            continue
        say("    %s %s: %s" % (U.label(t), vid, "; ".join(
            "%s %s" % (tag, ", ".join("%s@%d" % x for x in ff_deaths_after(runs[(tag, t)], 0)) or "none") for tag in ARMS)))


def finish():
    with open(os.path.join(HERE, "_uh_analysis.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(OUT) + "\n")
    return 0


if __name__ == "__main__":
    main()
