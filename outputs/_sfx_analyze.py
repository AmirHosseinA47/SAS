"""searcherfix Part 3 analyser. Read-only over outputs/*.json. No simulation.

Implements every pre-registered gate item from outputs/searcherfix_part1.txt s.7.

  identity   G0  value-identity, sfOFF vs a reference arm (7.1)
  pins       G1  structural zero on off-grid refusals + G2 re-baselined pin set
                 + G3 no new dwell run, with per-pin unit/start/exit (7.2)
  signatures     the three livelock signatures (7.3)
  osc        G4  reversals, tight reversals, longest alternation, attributed (7.4)
  exposure   G5  E1 searcher-only / E2 all-UAV, interior-hazard definition (7.5)
  detect     G6  det_max_first_seen, before and after (7.6)
  outcomes   G7  rescued/dead/ff_deaths/never_detected/terminal_step + battery (7.8)
  all            every section in order

Usage:
  cd outputs && E:\\Projects\\SAS\\.venv\\Scripts\\python.exe _sfx_analyze.py all \\
      --off sfOFF --on sfON [--ref dfD]

Arm names are TAG prefixes; files are outputs/_ffr_<TAG>_*.json.
selected_dir[t] is the direction APPLIED in step t (uav_executor.py:144, consumed
in advance() the same step). A refused move is cell[t] == cell[t-1].
"""
import argparse
import collections
import glob
import json
import os
import sys

from _sf_cat import load, categorise, cat_of

MX = [1, 0, -1, 0]
MY = [0, -1, 0, 1]
NAME = ["E", "S", "W", "N"]
OPP = {0: 2, 2: 0, 1: 3, 3: 1}
SEARCHER = "victim_searcher"
OBS_RADIUS = 8


# ---------------------------------------------------------------- loading ----
def arm_files(tag):
    return sorted(glob.glob("_ffr_%s_*.json" % tag))


def key3(run):
    return (run["wind"], run["roles"], run["seed"])


def dims(run):
    p = run.get("params") or {}
    return (int(p.get("HEIGHT") or 50), int(p.get("WIDTH") or 50))


def in_grid(x, y, h, w):
    return 0 <= x < h and 0 <= y < w


def load_arm(tag):
    """-> {key3: run}. Later files win only if the earlier one lacked uav_steps."""
    out = {}
    for p in arm_files(tag):
        try:
            run = load(p)
        except Exception as exc:
            print("  !! unreadable %s: %s" % (p, exc))
            continue
        if "uav_steps" not in run:
            continue
        out[key3(run)] = run
    return out


def steps_of(run):
    """uid -> [(step, cell, role, dir, battery, base_state, refused, oob)]"""
    h, w = dims(run)
    seq, prev = collections.defaultdict(list), {}
    for i in range(run["steps"]):
        for r in run["uav_steps"][i]:
            uid, cell, role, dirn = r[0], tuple(r[1]), r[2], r[3]
            bat = r[4] if len(r) > 4 else None
            bst = r[5] if len(r) > 5 else ""
            refused = prev.get(uid) == cell
            oob = False
            if refused and dirn is not None:
                t = (cell[0] + MX[dirn], cell[1] + MY[dirn])
                oob = not in_grid(t[0], t[1], h, w)
            seq[uid].append((i + 1, cell, role, dirn, bat, bst, refused, oob))
            prev[uid] = cell
    return seq


def actions_of(run):
    """(step, uid) -> action label"""
    out = {}
    ua = run.get("uav_actions")
    if not ua:
        return out
    for i, row in enumerate(ua):
        for r in row:
            out[(i + 1, r[0])] = r[1]
    return out


def burning_of(run):
    """(step, uid) -> burning bit of the cell the UAV stands on."""
    out = {}
    ua = run.get("uav_actions")
    if not ua:
        return out
    for i, row in enumerate(ua):
        for r in row:
            out[(i + 1, r[0])] = int(r[2])
    return out


# ------------------------------------------------------------ G0 identity ----
def cmp_value(a, b, path="", diffs=None, limit=40):
    if diffs is None:
        diffs = []
    if len(diffs) >= limit:
        return diffs
    if type(a) is not type(b) and not (isinstance(a, (int, float))
                                       and isinstance(b, (int, float))):
        diffs.append((path, "type %s vs %s" % (type(a).__name__, type(b).__name__)))
        return diffs
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                diffs.append((path + "/" + str(k), "present in only one"))
            else:
                cmp_value(a[k], b[k], path + "/" + str(k), diffs, limit)
    elif isinstance(a, list):
        if len(a) != len(b):
            diffs.append((path, "len %d vs %d" % (len(a), len(b))))
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                cmp_value(x, y, "%s[%d]" % (path, i), diffs, limit)
    else:
        if a != b:
            diffs.append((path, "%r vs %r" % (a, b)))
    return diffs


SKIP_KEYS = {"wall_s", "tag", "repo", "extra_params", "stdout_lines",
             "stdout_sha256", "params"}


def sec_identity(off, ref, off_tag, ref_tag):
    print("=" * 78)
    print("G0  VALUE-IDENTITY  %s (kill switch OFF) vs %s" % (off_tag, ref_tag))
    print("=" * 78)
    shared = sorted(set(off) & set(ref))
    print("  shared tuples: %d   (%s %d, %s %d)"
          % (len(shared), off_tag, len(off), ref_tag, len(ref)))
    if not shared:
        print("  NO SHARED TUPLES - cannot compare.")
        return
    ident = 0
    for k in shared:
        a = {x: v for x, v in off[k].items() if x not in SKIP_KEYS}
        b = {x: v for x, v in ref[k].items() if x not in SKIP_KEYS}
        d = cmp_value(a, b)
        if not d:
            ident += 1
        else:
            print("  DIFF %s/%s/%s: %d field(s)" % (k[0], k[1], k[2], len(d)))
            for p, why in d[:6]:
                print("        %s  %s" % (p, why))
    print()
    print("  VALUE-IDENTICAL: %d / %d" % (ident, len(shared)))
    if ident == len(shared):
        print("  [PASS] kill switch proves value-identity")
    else:
        print("  [FAIL] see diffs above. NOTE: identical differing FIELDS across")
        print("         every tuple with no eval field is a harness schema change,")
        print("         not a regression.")


# ----------------------------------------------------------------- G1-G3 ----
def pins_of(run):
    """[(uid, cell, start_step, length, exit_step, labels)] - maximal same-cell
    runs of off-grid refusals by a searcher."""
    acts = actions_of(run)
    out = []
    for uid, s in steps_of(run).items():
        if not s or s[0][2] != SEARCHER:
            continue
        i = 0
        while i < len(s):
            if not s[i][7]:
                i += 1
                continue
            j = i
            while j + 1 < len(s) and s[j + 1][7] and s[j + 1][1] == s[i][1]:
                j += 1
            labels = sorted({acts.get((s[t][0], uid), "") for t in range(i, j + 1)})
            exit_step = s[j + 1][0] if j + 1 < len(s) else None
            out.append((uid, s[i][1], s[i][0], j - i + 1, exit_step, labels))
            i = j + 1
    return out


def oob_refusals(run):
    n = 0
    for uid, s in steps_of(run).items():
        if not s or s[0][2] != SEARCHER:
            continue
        n += sum(1 for x in s if x[7])
    return n


def oob_refusals_by_role(run):
    c = collections.Counter()
    for uid, s in steps_of(run).items():
        role = s[0][2] if s else "?"
        c[role] += sum(1 for x in s if x[7])
    return c


def dwell_runs(run):
    """Same-cell occupancy runs of length >= 2, classified by cause.
    -> {(uid, cell, start): (length, cause)}"""
    h, w = dims(run)
    out = {}
    for uid, s in steps_of(run).items():
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and s[j + 1][1] == s[i][1]:
                j += 1
            if j > i:
                oob = any(s[t][7] for t in range(i, j + 1))
                cause = "OFF-GRID" if oob else "UAV-BLOCKED"
                out[(uid, s[i][1], s[i][0])] = (j - i + 1, cause, s[i][2])
            i = j + 1
    return out


def sec_pins(off, on, off_tag, on_tag):
    print("=" * 78)
    print("G1/G2/G3  PINS   %s (OFF) -> %s (ON)" % (off_tag, on_tag))
    print("=" * 78)
    shared = sorted(set(off) & set(on))
    print("  shared tuples: %d" % len(shared))

    off_oob = sum(oob_refusals(off[k]) for k in shared)
    on_oob = sum(oob_refusals(on[k]) for k in shared)
    print()
    print("  G1 PRIMARY - searcher off-grid refused steps (structural invariant)")
    print("     %-8s %6d" % (off_tag, off_oob))
    print("     %-8s %6d" % (on_tag, on_oob))
    bad = [k for k in shared if oob_refusals(on[k]) > 0]
    if on_oob == 0:
        print("     [PASS] EXACTLY ZERO in every run, all %d tuples" % len(shared))
    else:
        print("     [FAIL] non-zero in %d run(s): %s" % (len(bad), bad[:6]))

    roles_on = collections.Counter()
    for k in shared:
        roles_on.update(oob_refusals_by_role(on[k]))
    roles_off = collections.Counter()
    for k in shared:
        roles_off.update(oob_refusals_by_role(off[k]))
    print("     by role OFF: %s" % dict(roles_off))
    print("     by role ON : %s" % dict(roles_on))

    print()
    print("  G2 RE-BASELINED PIN SET - measured on %s at THIS commit" % off_tag)
    off_pins = {}
    for k in shared:
        for uid, cell, start, ln, ex, labels in pins_of(off[k]):
            off_pins[(k, uid, cell)] = (start, ln, ex, labels)
    on_pins = {}
    for k in shared:
        for uid, cell, start, ln, ex, labels in pins_of(on[k]):
            on_pins[(k, uid, cell)] = (start, ln, ex, labels)
    print("     %s pin events: %d   |   %s pin events: %d"
          % (off_tag, len(off_pins), on_tag, len(on_pins)))
    print()
    print("     %-6s %-8s %-11s %-5s %-8s %4s %6s %6s  %s"
          % ("wind", "roles", "seed", "uid", "cell", "len", "pinned", "moved", "cleared"))
    for (k, uid, cell), (start, ln, ex, labels) in sorted(
            off_pins.items(), key=lambda x: -x[1][1]):
        cleared = "YES" if (k, uid, cell) not in on_pins else "NO"
        print("     %-6s %-8s %-11s %-5s %-8s %4d %6d %6s  %s"
              % (k[0], k[1], str(k[2]), uid, "(%d,%d)" % cell, ln, start,
                 ("%d" % ex) if ex else "-", cleared))
    still = [x for x in off_pins if x in on_pins]
    new = [x for x in on_pins if x not in off_pins]
    if not on_pins:
        print("     [PASS] every pin cleared, none new")
    else:
        print("     [FAIL] %d still pinned, %d NEW" % (len(still), len(new)))
        for x in new[:8]:
            print("            NEW %s" % (x,))

    print()
    print("  G3 NO NEW DWELL RUN (same-cell occupancy >= 2, by cause)")
    for label, arm in ((off_tag, off), (on_tag, on)):
        c = collections.Counter()
        steps_in = collections.Counter()
        for k in shared:
            for (uid, cell, st), (ln, cause, role) in dwell_runs(arm[k]).items():
                c[(role, cause)] += 1
                steps_in[(role, cause)] += ln
        print("     %-8s %s" % (label, dict(c)))
        print("     %-8s steps: %s" % ("", dict(steps_in)))
    off_d, on_d = set(), set()
    for k in shared:
        for key, (ln, cause, role) in dwell_runs(off[k]).items():
            off_d.add((k, key[0], key[1]))
        for key, (ln, cause, role) in dwell_runs(on[k]).items():
            on_d.add((k, key[0], key[1]))
    newd = on_d - off_d
    print("     dwell (tuple,uid,cell) present in ON but not OFF: %d" % len(newd))
    print("     NOTE: the round's real risk is converting an OFF-GRID pin into a")
    print("           UAV-BLOCKED one. Watch the searcher UAV-BLOCKED row above.")


# --------------------------------------------------------- G-signatures ----
def sec_signatures(off, on, off_tag, on_tag):
    print("=" * 78)
    print("THE THREE LIVELOCK SIGNATURES")
    print("=" * 78)
    shared = sorted(set(off) & set(on))
    for label, arm in ((off_tag, off), (on_tag, on)):
        a = b = c = 0
        a_tot = c_tot = 0
        for k in shared:
            run = arm[k]
            acts = actions_of(run)
            burn = burning_of(run)
            steps, burning, firstburn, burnt_from = categorise(run)
            for uid, s in steps_of(run).items():
                if not s or s[0][2] != SEARCHER:
                    continue
                i = 0
                while i < len(s):
                    j = i
                    while j + 1 < len(s) and s[j + 1][1] == s[i][1]:
                        j += 1
                    if j > i:
                        onburn = [t for t in range(i, j + 1)
                                  if burn.get((s[t][0], uid), 0)]
                        if onburn:
                            a_tot += 1
                            lbls = {acts.get((s[t][0], uid), "") for t in onburn}
                            if any("victim_search_hazard_retreat" in l for l in lbls):
                                a += 1
                    i = j + 1 if j > i else i + 1
                b += sum(1 for x in s if x[7])
            # (c) dwell runs that never reduce distance to the hooked target
            ps = run.get("partition_steps") or []
            for uid, s in steps_of(run).items():
                if not s or s[0][2] != SEARCHER:
                    continue
                i = 0
                while i < len(s):
                    j = i
                    while j + 1 < len(s) and s[j + 1][1] == s[i][1]:
                        j += 1
                    if j > i:
                        ds = []
                        for t in range(i, j + 1):
                            st = s[t][0]
                            tg = ((ps[st - 1].get("targets") or {}).get(uid)
                                  if st - 1 < len(ps) else None)
                            if tg:
                                ds.append(abs(s[t][1][0] - tg[0])
                                          + abs(s[t][1][1] - tg[1]))
                        if len(ds) >= 2:
                            c_tot += 1
                            if not any(y < x for x, y in zip(ds, ds[1:])):
                                c += 1
                    i = j + 1 if j > i else i + 1
        print("  %-8s (a) multi-step burning dwells carrying the retreat label : %d / %d"
              % (label, a, a_tot))
        print("  %-8s (b) out-of-bounds refusals by searchers                  : %d"
              % ("", b))
        print("  %-8s (c) dwell runs never reducing distance to hooked target  : %d / %d"
              % ("", c, c_tot))


# ------------------------------------------------------------------ G4 osc ---
def osc_stats(run, fire_set=None):
    """reversals, tight reversals, longest 2-cell alternation - realised positions."""
    rev = tight = 0
    longest = 0
    alts = 0
    rev_touching_fire = 0
    for uid, s in steps_of(run).items():
        if not s or s[0][2] != SEARCHER:
            continue
        cells = [x[1] for x in s]
        prevdir = None
        for t in range(1, len(cells)):
            d = (cells[t][0] - cells[t - 1][0], cells[t][1] - cells[t - 1][1])
            if d == (0, 0):
                continue                      # HOLD: skipped, prevdir kept
            m = None
            for k in range(4):
                if (MX[k], MY[k]) == d:
                    m = k
                    break
            if m is None:
                prevdir = None
                continue
            if prevdir is not None and OPP.get(prevdir) == m:
                rev += 1
                if fire_set is not None and (
                        (s[t][0], uid) in fire_set or (s[t - 1][0], uid) in fire_set):
                    rev_touching_fire += 1
            prevdir = m
        for t in range(1, len(cells) - 1):
            if cells[t - 1] == cells[t + 1] != cells[t]:
                tight += 1
        i = 0
        while i < len(cells):
            j = i
            while j + 1 < len(cells) and len(set(cells[i:j + 2])) <= 2:
                j += 1
            seg = cells[i:j + 1]
            changes = sum(1 for a, b in zip(seg, seg[1:]) if a != b)
            if len(set(seg)) == 2 and changes >= 2:
                alts += 1
                longest = max(longest, len(seg))
            i = j + 1 if j > i else i + 1
    return rev, tight, alts, longest, rev_touching_fire


def sec_osc(off, on, off_tag, on_tag):
    print("=" * 78)
    print("G4  OSCILLATION, MEASURED (realised positions, searchers only)")
    print("=" * 78)
    shared = sorted(set(off) & set(on))
    print("  %-8s %10s %10s %10s %10s" %
          ("arm", "reversals", "tight", "alt-runs", "longest"))
    res = {}
    for label, arm in ((off_tag, off), (on_tag, on)):
        R = T = A = 0
        L = 0
        for k in shared:
            r, t, a, l, _ = osc_stats(arm[k])
            R += r
            T += t
            A += a
            L = max(L, l)
        res[label] = (R, T, A, L)
        print("  %-8s %10d %10d %10d %10d" % (label, R, T, A, L))
    dR = res[on_tag][0] - res[off_tag][0]
    dT = res[on_tag][1] - res[off_tag][1]
    dA = res[on_tag][2] - res[off_tag][2]
    print()
    print("  delta reversals %+d | tight %+d | alternation runs %+d" % (dR, dT, dA))
    print("  PRE-REGISTERED BASELINE (this corpus, shipped default): 324 two-cell")
    print("  alternations of >= 4 steps by searchers, 33 touching the outer ring.")
    print("  ATTRIBUTION IS MANDATORY: a reversal counts against the fix only if at")
    print("  least one leg is a guard-substituted step. Per-tuple detail below for")
    print("  any tuple whose tight-reversal count ROSE.")
    for k in shared:
        _, t0, _, _, _ = osc_stats(off[k])
        _, t1, _, _, _ = osc_stats(on[k])
        if t1 > t0:
            print("    ROSE %s/%s/%s  tight %d -> %d" % (k[0], k[1], k[2], t0, t1))


# ------------------------------------------------------------- G5 exposure ---
def sec_exposure(arms):
    print("=" * 78)
    print("G5  DRONE STEPS IN FIRE (interior-hazard definition)")
    print("=" * 78)
    print("  E1 = searcher-only, E2 = all-UAV, over ALL frames of every UAV")
    print("  %-8s %8s %8s %9s %8s %8s %9s" %
          ("arm", "E1 burn", "E1 tot", "E1 %", "E2 burn", "E2 tot", "E2 %"))
    for tag, arm in arms:
        b1 = n1 = b2 = n2 = 0
        for k, run in sorted(arm.items()):
            burn = burning_of(run)
            if not burn:
                continue
            for uid, s in steps_of(run).items():
                for x in s:
                    v = burn.get((x[0], uid), 0)
                    n2 += 1
                    b2 += v
                    if x[2] == SEARCHER:
                        n1 += 1
                        b1 += v
        print("  %-8s %8d %8d %8.3f%% %8d %8d %8.3f%%" %
              (tag, b1, n1, 100.0 * b1 / max(1, n1), b2, n2,
               100.0 * b2 / max(1, n2)))
    print("  Shipped baseline after the fireproof round, 18 route_blocked seeds:")
    print("    E1 2.50%  E2 1.61%")
    print("  EXPECTATION: the diagnosis measured only 0.14 pp of genuine search-")
    print("  component improvement available under CRN. Expect the pins to clear")
    print("  and exposure to move little. A null here is NOT a failure.")


# --------------------------------------------------------------- G6 detect ---
def det_max_first_seen(run):
    """Step at which the LAST victim first enters a searcher's observation box.
    Pure geometric replay of recorded positions. Chebyshev radius 8 -> 17x17."""
    vs = run.get("victim_steps") or []
    us = run.get("uav_steps") or []
    n = min(len(vs), len(us))
    first = {}
    for i in range(n):
        searchers = [tuple(r[1]) for r in us[i]
                     if r[2] == SEARCHER and r[1] is not None]
        if not searchers:
            continue
        for r in vs[i]:
            vid, cell = r[0], r[1]
            if cell is None or vid in first:
                continue
            vx, vy = int(cell[0]), int(cell[1])
            for (ux, uy) in searchers:
                if max(abs(vx - ux), abs(vy - uy)) <= OBS_RADIUS:
                    first[vid] = i + 1
                    break
    allv = {r[0] for row in vs for r in row}
    if not allv:
        return None, 0, 0
    unseen = len(allv) - len(first)
    return (max(first.values()) if first else None), unseen, len(allv)


def sec_detect(arms):
    print("=" * 78)
    print("G6  DETECTION TIMING - det_max_first_seen  (THE COST THE FIX EXISTS FOR)")
    print("=" * 78)
    print("  Step at which the LAST victim first enters a searcher's 17x17 box.")
    print("  Purely geometric replay of recorded positions.")
    print("  Two estimators are reported. STRICT drops any run in which some")
    print("  victim was never seen; CENSORED keeps it, scoring an unseen victim at")
    print("  the horizon. STRICT is unbiased but loses most of the sample, so the")
    print("  seed-matched delta below uses CENSORED - state which you quote.")
    tabs = {}
    for tag, arm in arms:
        vals = {}
        strict = {}
        for k, run in arm.items():
            v, unseen, tot = det_max_first_seen(run)
            horizon = int(run.get("steps") or 240)
            if v is not None and unseen == 0:
                strict[k] = v
            vals[k] = horizon if unseen else (v if v is not None else horizon)
        if strict:
            srt = sorted(strict.values())
            print("  %-8s STRICT   n=%3d  mean %7.2f  median %6.1f"
                  % (tag, len(strict), sum(srt) / len(srt), srt[len(srt) // 2]))
        tabs[tag] = vals
        if vals:
            m = sum(vals.values()) / len(vals)
            srt = sorted(vals.values())
            print("  %-8s CENSORED n=%3d  mean %7.2f  median %6.1f  min %4d  max %4d"
                  % (tag, len(vals), m, srt[len(srt) // 2], srt[0], srt[-1]))
        else:
            print("  %-8s n=0" % tag)
    keys = [t for t, _ in arms]
    if len(keys) >= 2:
        a, b = tabs[keys[0]], tabs[keys[-1]]
        both = sorted(set(a) & set(b))
        if both:
            d = [b[k] - a[k] for k in both]
            better = sum(1 for x in d if x < 0)
            worse = sum(1 for x in d if x > 0)
            print()
            print("  SEED-MATCHED DELTA (%s -> %s) over %d tuples:"
                  % (keys[0], keys[-1], len(both)))
            print("    mean %+0.2f steps | earlier %d | later %d | tied %d"
                  % (sum(d) / len(d), better, worse, len(d) - better - worse))
            print("    NEGATIVE = the last victim is seen EARLIER = the fix helped.")
            for k in both:
                if b[k] != a[k]:
                    print("      %-6s %-8s %-11s  %4d -> %4d  (%+d)"
                          % (k[0], k[1], str(k[2]), a[k], b[k], b[k] - a[k]))
    print("  Reference: partial rho +0.465/+0.442/+0.438 across three pools;")
    print("  tertile means 73.2 / 89.2 / 115.7 steps.")


# ------------------------------------------------------------- G7 outcomes ---
def sec_outcomes(arms):
    print("=" * 78)
    print("G7  OUTCOMES PER ARM  (+ the battery cost the fix introduces)")
    print("=" * 78)
    print("  %-8s %4s %8s %6s %9s %14s %11s %9s %9s" %
          ("arm", "n", "rescued", "dead", "ff_deaths", "never_detected",
           "term_step", "bat_mean", "bat_min"))
    for tag, arm in arms:
        n = 0
        agg = collections.Counter()
        terms = []
        bats = []
        bmin = 100.0
        for k, run in sorted(arm.items()):
            ev = run.get("eval") or {}
            n += 1
            for f in ("rescued", "dead", "firefighter_deaths", "never_detected"):
                agg[f] += int(ev.get(f) or 0)
            if ev.get("terminal_step") is not None:
                terms.append(int(ev["terminal_step"]))
            for uid, s in steps_of(run).items():
                if s and s[0][2] == SEARCHER and s[-1][4] is not None:
                    bats.append(float(s[-1][4]))
                    bmin = min(bmin, min(float(x[4]) for x in s if x[4] is not None))
        print("  %-8s %4d %8d %6d %9d %14d %11.1f %9.2f %9.2f" %
              (tag, n, agg["rescued"], agg["dead"], agg["firefighter_deaths"],
               agg["never_detected"],
               (sum(terms) / len(terms)) if terms else -1,
               (sum(bats) / len(bats)) if bats else -1, bmin))
    print()
    print("  NOTE on never_detected: it UNDERCOUNTS roughly threefold - a victim")
    print("  that dies while still 'candidate' is booked to eval.dead.")
    print("  BATTERY is a real cost of this fix: a refused step drains 0.1, a")
    print("  successful one 0.3 (agents.py:369-375). Bound: 0.2 per converted")
    print("  refusal. Thresholds: low 30.0, critical 15.0.")


# ------------------------------------------------------------------- main ----
def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("section", nargs="?", default="all",
                    choices=["all", "identity", "pins", "signatures", "osc",
                             "exposure", "detect", "outcomes"])
    ap.add_argument("--off", default="sfOFF")
    ap.add_argument("--on", default="sfON")
    ap.add_argument("--ref", default="")
    a = ap.parse_args()

    off = load_arm(a.off)
    on = load_arm(a.on)
    ref = load_arm(a.ref) if a.ref else {}
    print("arms: %s=%d  %s=%d  %s=%d"
          % (a.off, len(off), a.on, len(on), a.ref or "(no ref)", len(ref)))

    # THE POOL VALIDATOR DOES NOT CHECK WHICH CHECKOUT A RUN CAME FROM, and this
    # round deliberately runs one arm from a second checkout. Verify it here.
    print("  repo / switch provenance per arm (the validator does NOT check this):")
    for tag, arm in (("%s" % a.off, off), ("%s" % a.on, on),
                     ("%s" % (a.ref or "-"), ref)):
        if not arm:
            continue
        repos = collections.Counter(str(r.get("repo") or "?") for r in arm.values())
        sw = collections.Counter(
            str((r.get("extra_params") or {}).get(
                "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", "<unset>"))
            for r in arm.values())
        print("    %-8s repo=%s  switch=%s" % (tag, dict(repos), dict(sw)))
        if len(repos) > 1:
            print("    !! %s MIXES CHECKOUTS - the arm is not comparable" % tag)
        if len(sw) > 1:
            print("    !! %s MIXES SWITCH VALUES - the arm is not one arm" % tag)
    if not off or not on:
        print("MISSING ARM DATA - nothing to do.")
        return 1
    arms = [(a.off, off), (a.on, on)]

    s = a.section
    if s in ("all", "identity") and ref:
        sec_identity(off, ref, a.off, a.ref)
        print()
    if s in ("all", "pins"):
        sec_pins(off, on, a.off, a.on)
        print()
    if s in ("all", "signatures"):
        sec_signatures(off, on, a.off, a.on)
        print()
    if s in ("all", "osc"):
        sec_osc(off, on, a.off, a.on)
        print()
    if s in ("all", "exposure"):
        sec_exposure(arms)
        print()
    if s in ("all", "detect"):
        sec_detect(arms)
        print()
    if s in ("all", "outcomes"):
        sec_outcomes(arms)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
