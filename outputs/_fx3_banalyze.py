"""fix3a - scenario-B battery analysis of _sd_probe JSONs (read-only). Used for the Part 1 prototypes
(_fx3_bproto.py arms) and pre-registered for Part 3.

usage: _fx3_banalyze.py <base_tag> <arm_tag> [<arm_tag> ...]
  reads outputs/_sd_<tag>_B_<W>_<seed>.json (prototype naming) or _sd_<tag>_B_<W>.json.

Per arm (summed over its runs) and per UAV role:
  gap           steps with no victim searcher flying (every searcher returning or docked) -
                FULL (all 360 steps) and PRE (steps 1 .. terminal_step - 1; all 360 without a terminal)
  returns       rtb_active rising edges, per UAV (mean) and the distribution
  first return  trigger step / level per UAV (the rtb rows), arrival level
  s_retleg      searcher return-leg UAV-steps (rtb_active and not docked)
  s_flying      searcher flying UAV-steps (neither returning nor docked)
  min_ret       lowest battery any UAV had while on a return leg; min_air the lowest airborne battery
  stranded      a UAV at battery 0, or a return leg still open at the horizon (reported with its level)
  delays        B3 firings (bproto 'delays' rows: UAV-steps on which the return was delayed; episodes)
  low/crit      LOW_BATTERY / CRITICAL_BATTERY trigger instances (rows_trig), battery fail-safe
                reasons and emergency-mode steps (rows_dec)
  outcomes      rescued / dead / never_detected / runs with no terminal step
Pairwise vs <base_tag> (seed-matched), the fix2 D-9 rule on the COMMON pre-terminal window
(steps 1 .. min(T_base, T_arm) - 1; T = 361 without a terminal step):
  G_pre = gap closed (base gap - arm gap), C_pre = searcher flying steps lost (base - arm).
"""
from __future__ import annotations

import collections
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load_arm(tag):
    out = {}
    for f in glob.glob(os.path.join(HERE, "_sd_%s_B_*.json" % tag)):
        m = re.match(r"_sd_%s_(B_[NSEW](?:_\d+)?)\.json$" % re.escape(tag), os.path.basename(f))
        if not m:
            continue
        out[m.group(1)] = json.load(open(f, encoding="utf-8"))
    return out


def per_run(d, window=None):
    rows = d["rows_uav"]
    T = len(rows)
    term = d.get("terminal_step")
    pre_end = (term - 1) if term else T
    if window is not None:
        pre_end = min(pre_end, window)
    st = collections.Counter()
    returns = collections.Counter()
    prev = {}
    roles = {}
    first = {}
    min_ret = min_air = 999.0
    trips = []
    open_leg = {}
    for t, row in enumerate(rows):
        s = [u for u in row if u[3] == "victim_searcher"]
        fly = [u for u in s if not u[5] and not u[6]]
        pre = t + 1 <= pre_end
        if s and not fly:
            st["gap_full"] += 1
            if pre:
                st["gap_pre"] += 1
        for u in row:
            uid, x, y, role, bat, rtb, dock = u[0], u[1], u[2], u[3], u[4], u[5], u[6]
            roles[uid] = role
            if role == "victim_searcher":
                if rtb and not dock:
                    st["s_retleg_full"] += 1
                    if pre:
                        st["s_retleg_pre"] += 1
                if not rtb and not dock:
                    st["s_flying_full"] += 1
                    if pre:
                        st["s_flying_pre"] += 1
            if rtb and not prev.get(uid):
                returns[uid] += 1
                first.setdefault(uid, (t + 1, bat))
                open_leg[uid] = (t + 1, bat)
            if rtb and not dock:
                min_ret = min(min_ret, bat)
            if not dock:
                min_air = min(min_air, bat)
            if dock and uid in open_leg:
                s0, b0 = open_leg.pop(uid)
                trips.append((uid, role, s0, b0, t + 1, bat))
            if bat <= 0.0:
                st["zero_battery_steps"] += 1
            prev[uid] = bool(rtb)
    stranded = [(uid, s0, b0, [u[4] for u in rows[-1] if u[0] == uid][0]) for uid, (s0, b0) in open_leg.items()]
    trig = collections.Counter()
    for tr in d.get("rows_trig") or []:
        for k, v in (tr or {}).items():
            if "BATTERY" in k:
                trig[k] += v
    bat_reasons = emerg = 0
    for dec in d.get("rows_dec") or []:
        why = " ".join(str(w) for w in (dec.get("why") or []))
        if "battery" in why:
            bat_reasons += 1
        if str(dec.get("mode", "")) == "emergency":
            emerg += 1
    delays = (d.get("bproto") or {}).get("delays") or []
    ep = 0
    last = {}
    for row in delays:
        if row and row[0] == "ERR":
            st["delay_err"] += 1
            continue
        s, uid = row[0], row[1]
        if last.get(uid) != s - 1:
            ep += 1
        last[uid] = s
    e = d.get("eval") or {}
    return {"st": st, "returns": returns, "roles": roles, "first": first, "trips": trips,
            "min_ret": min_ret, "min_air": min_air, "stranded": stranded, "trig": trig,
            "bat_reasons": bat_reasons, "emerg": emerg, "delay_steps": len(delays), "delay_eps": ep,
            "delay_min_bat": min((r[2] for r in delays if r and r[0] != "ERR"), default=None),
            "rescued": e.get("rescued"), "dead": e.get("dead"), "nd": e.get("never_detected"),
            "term": d.get("terminal_step")}


def summary(tag, runs):
    agg = collections.Counter()
    ret_by_role = collections.defaultdict(list)
    first_by_role = collections.defaultdict(list)
    min_ret = min_air = 999.0
    stranded = []
    trig = collections.Counter()
    out = collections.Counter()
    for k, d in sorted(runs.items()):
        r = per_run(d)
        agg.update(r["st"])
        for uid, role in r["roles"].items():
            ret_by_role[role].append(r["returns"].get(uid, 0))
            if uid in r["first"]:
                first_by_role[role].append(r["first"][uid])
        min_ret = min(min_ret, r["min_ret"])
        min_air = min(min_air, r["min_air"])
        stranded += [(k,) + s for s in r["stranded"]]
        trig.update(r["trig"])
        out["bat_reasons"] += r["bat_reasons"]
        out["emerg"] += r["emerg"]
        out["delay_steps"] += r["delay_steps"]
        out["delay_eps"] += r["delay_eps"]
        out["rescued"] += r["rescued"] or 0
        out["dead"] += r["dead"] or 0
        out["nd"] += r["nd"] or 0
        out["no_term"] += r["term"] is None
    print("== %s (%d runs)" % (tag, len(runs)))
    print("   gap PRE %d FULL %d | searcher flying PRE %d FULL %d | searcher return-leg PRE %d FULL %d" % (
        agg["gap_pre"], agg["gap_full"], agg["s_flying_pre"], agg["s_flying_full"], agg["s_retleg_pre"],
        agg["s_retleg_full"]))
    for role, v in sorted(ret_by_role.items()):
        fr = first_by_role[role]
        print("   returns %-15s mean %.2f dist %s | first return step %s" % (
            role, sum(v) / float(len(v)), dict(sorted(collections.Counter(v).items())),
            sorted(s for s, _ in fr)))
    print("   min battery on a return %.1f, airborne %.1f | stranded / open at horizon %s" % (
        min_ret, min_air, stranded))
    print("   B3 delays: %d UAV-steps, %d episodes | battery triggers %s | battery fail-safe reasons %d |"
          " emergency steps %d" % (out["delay_steps"], out["delay_eps"], dict(trig), out["bat_reasons"],
                                   out["emerg"]))
    print("   rescued %d dead %d never_detected %d | runs with no terminal step %d" % (
        out["rescued"], out["dead"], out["nd"], out["no_term"]))


def pairwise(base_tag, base, tag, runs):
    G = C = Gf = Cf = n = 0
    for k in sorted(set(base) & set(runs)):
        a, b = base[k], runs[k]
        ta = a.get("terminal_step") or 361
        tb = b.get("terminal_step") or 361
        w = min(ta, tb) - 1
        ra, rb = per_run(a, window=w), per_run(b, window=w)
        # per_run's PRE is bounded by each run's own terminal too; with window = common - 1 both agree
        G += ra["st"]["gap_pre"] - rb["st"]["gap_pre"]
        C += ra["st"]["s_flying_pre"] - rb["st"]["s_flying_pre"]
        Gf += ra["st"]["gap_full"] - rb["st"]["gap_full"]
        Cf += ra["st"]["s_flying_full"] - rb["st"]["s_flying_full"]
        n += 1
    verdict = "PASS (C_pre <= G_pre)" if C <= G else "STOP (C_pre > G_pre)"
    print("   vs %s (%d pairs): PRE (common window) G %d  C %d  -> %s | FULL G %d C %d" % (
        base_tag, n, G, C, verdict, Gf, Cf))


def main():
    base_tag = sys.argv[1]
    base = load_arm(base_tag)
    summary(base_tag, base)
    for tag in sys.argv[2:]:
        runs = load_arm(tag)
        summary(tag, runs)
        pairwise(base_tag, base, tag, runs)


if __name__ == "__main__":
    main()
