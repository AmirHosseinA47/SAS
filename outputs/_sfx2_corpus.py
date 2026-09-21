"""sfx2 round, ITEM 2 - which paths deliver an OFF-GRID or UAV-BLOCKED direction
to agents.py move(), by role and by the executor dispatch arm that produced it.

READ-ONLY over the committed corpus. Runs NO simulation, imports NO simulation
code, writes nothing (stdout only). Every corpus file is reached through a
NON-RECURSIVE glob of the form _ffr_<TAG>_*.json with cwd = outputs/ (and, with
--broad, the non-recursive glob _ffr_*.json). No recursive traversal of outputs/.

Usage (from outputs/):
    E:\\Projects\\SAS\\.venv\\Scripts\\python.exe _sfx2_corpus.py [--broad] > _sfx2_corpus.txt

WHAT IS MEASURED, per arm and per role
  (a) evaluable UAV-steps and every REFUSED step (p[i] == p[i-1]) split into
        NO_ATTEMPT   move() returned before the legality test: base_state
                     charging/docked (agents.py:833-835 rtb_docked_hold), or an
                     EMPTY executor label on a non-returning step (inferred
                     agents.py:844-846 no_managed_direction_hold)
        OFF_GRID     refused target p[i] + MOVE[dir[i]] outside HEIGHT x WIDTH
        UAV_BLOCKED  in-bounds target holding another UAV. agents.py:393-399
                     not_UAV_adjacent tests ONLY the target cell (no adjacency,
                     despite its name). Two reconstructions are reported:
                       PRE   = other UAVs at p[i-1] (the brief's approximation)
                       SWEEP = schedule order: UAVs earlier in the uav_steps row
                               at p[i], later ones at p[i-1] (SimultaneousActivation
                               advances in _agents insertion order, the order the
                               harness iterates when it writes the row)
        UNEXPLAINED  none of the above
  (b) FULL action-label histograms on OFF_GRID and on UAV_BLOCKED refusals,
      split by base_state
  (c) every label classified into the dispatch arm of UAVExecutor.execute
      (uav_executor.py:416-434 at 629a321) - LABEL-ONLY (the brief's scheme) and
      BASE-STATE-AWARE (the move layer first: a docked UAV never attempts, and a
      returning UAV's direction is overwritten by agents.py:817 under return
      mechanism 2, so the executor label on that step did not steer it)
  (d) latch signatures - maximal runs >= 2 of consecutive refused steps, same
      UAV, same cell, same selected_dir, same cause
  (e) the hidden-path check - every off-grid refusal whose label does not carry
      victim_search_hazard_retreat
  (f) the searcherfire "wider population" (167 records / 57 tuples / 160,320
      UAV-steps / 657 off-grid refusals), reproduced
  (g) --broad: the off-grid census over every _ffr_*.json that has uav_steps

RESULT SHAPE TO EXPECT: PRE leaves a few in-bounds refusals UNEXPLAINED that SWEEP
explains; SWEEP leaves none. No post-filter in uav_executor.py rejects a UAV-
occupied cell (UAV positions enter only as soft score terms), so UAV_BLOCKED is
filter-agnostic, whereas OFF_GRID is not.

ALIGNMENT (established by searcherfire, re-used, not re-derived here): row i of
uav_steps / uav_actions is recorded after model.step() number i+1; selected_dir
at i is the direction APPLIED in that step (p[i-1] -> p[i]); the uav_actions
label is model.latest_execution_result['local']['uav_results'][uid]['action'] of
the SAME step's pre-move dispatch (_ffr_harness.py:591-605; the only
_run_execution call is in the pre_move cycle, adaptation_manager.py:120). It is
the executor's POST-FILTER label; agents.py move-layer labels live on
agent.execution_action, which the harness never records.
"""
import argparse
import collections
import glob
import os
import re
import sys

from _sf_cat import load
from _sfx_analyze import dims, in_grid

MX = [1, 0, -1, 0]
MY = [0, -1, 0, 1]
SEARCHER = "victim_searcher"
TRACKER = "fire_tracker"
GATE_LABEL = "victim_search_hazard_retreat"
MOVE_LAYER_LABELS = {"rtb_docked_hold", "no_managed_direction_hold", "rtb_return",
                     "rtb_docked", "rtb_relaunch"}
DOCKED = ("charging", "docked")

MAIN_ARMS = ("sfREF", "sfOFF", "sfON", "sfSCAN")
WIDER = ("dcD", "d4D", "dfD", "drhD", "flhD", "fmOFF", "f3OFF")

CAUSES = ("OFF_GRID", "UAV_BLOCKED", "NO_ATTEMPT", "UNEXPLAINED")

# dispatch arms, in print order
LABEL_ARMS = ("RTB", "HOLD", "TRACKER_HOLD_ESCAPE", "SEARCHER_EXEMPT_BFS",
              "SEARCHER_RETARGET", "SEARCHER_GATE", "SEARCHER_ROLE_PRESERVING_FS",
              "TRACKER_FINAL_SAFETY", "FAILSAFE_SEARCH_MODE", "MOVE_LAYER",
              "NO_EXEC_RESULT", "NO_LABEL_DATA", "OTHER")
STATE_ARMS = ("MOVE_LAYER_DOCKED", "MOVE_LAYER_RTB_RETURN") + LABEL_ARMS
UNFILTERED = {"RTB", "HOLD", "TRACKER_HOLD_ESCAPE", "SEARCHER_EXEMPT_BFS",
              "MOVE_LAYER_RTB_RETURN"}


def label_arm(label, role):
    """The brief's label-only dispatch arm (uav_executor.py:416-434)."""
    if label is None:
        return "NO_LABEL_DATA"
    if label == "":
        return "NO_EXEC_RESULT"
    if label in MOVE_LAYER_LABELS:
        return "MOVE_LAYER"
    if label == "rtb_waypoint":
        return "RTB"
    if label == "hold":
        return "HOLD"
    if label.startswith("search_mode"):
        return "FAILSAFE_SEARCH_MODE"
    if role == TRACKER:
        if label.startswith("hold_escape"):
            return "TRACKER_HOLD_ESCAPE"
        return "TRACKER_FINAL_SAFETY"
    if role == SEARCHER:
        if label == "victim_search_escape_bfs":
            return "SEARCHER_EXEMPT_BFS"
        if "retarget_to_interior" in label:
            return "SEARCHER_RETARGET"
        if label.endswith("_hazard_escape"):
            return "SEARCHER_ROLE_PRESERVING_FS"
        return "SEARCHER_GATE"
    return "OTHER"


def state_arm(label, role, bst, mech):
    """Base-state-aware: the move layer decides first (agents.py:822-853; the
    mechanism-2 steer that overwrites selected_dir is agents.py:796-819, run from
    advance() :861 before move())."""
    if bst in DOCKED:
        return "MOVE_LAYER_DOCKED"
    if bst == "returning" and mech != 1:
        return "MOVE_LAYER_RTB_RETURN"
    return label_arm(label, role)


def effective_mech(run):
    p = run.get("params") or {}
    v = p.get("BASE_STATION_RETURN_MECHANISM")
    if v is None:
        return 2, "unrecorded(code default 2)"
    try:
        return int(v), "params"
    except (TypeError, ValueError):
        return 2, "unparseable(%r)" % (v,)


def ua_status(run):
    if "uav_actions" not in run:
        return "missing"
    ua = run["uav_actions"]
    if ua is None:
        return "null"
    if len(ua) < len(run.get("uav_steps") or []):
        return "short"
    return "present"


def trip_berth(run, uid, t):
    """Target berth of the return trip active at 1-based step t, from rtb_log."""
    for trip in (run.get("rtb_log") or {}).get(uid, []) or []:
        ts = trip.get("trigger_step")
        arr = trip.get("arrival_step")
        if ts is None or t < ts:
            continue
        if arr is not None and t >= arr:
            continue
        b = trip.get("target_berth")
        return tuple(b) if b else None
    return None


def analyze_run(run):
    """-> list of per-step records (dicts) for every UAV-step, evaluable or not."""
    h, w = dims(run)
    mech, _ = effective_mech(run)
    us = run.get("uav_steps") or []
    ua = run.get("uav_actions")
    out = []
    for i in range(len(us)):
        rows = us[i]
        amap = None
        if ua and i < len(ua) and ua[i] is not None:
            amap = {a[0]: a for a in ua[i]}
        cur = {r[0]: (tuple(r[1]) if r[1] is not None else None) for r in rows}
        prv = ({r[0]: (tuple(r[1]) if r[1] is not None else None) for r in us[i - 1]}
               if i > 0 else {})
        order = [r[0] for r in rows]
        for k, r in enumerate(rows):
            uid, cell, role, d = r[0], cur[r[0]], r[2], r[3]
            bst = r[5] if len(r) > 5 else None
            label = None
            if amap is not None:
                a = amap.get(uid)
                label = a[1] if a is not None else None
            rec = {"i": i, "t": i + 1, "uid": uid, "role": role, "cell": cell,
                   "dir": d, "bst": bst, "label": label,
                   "larm": label_arm(label, role),
                   "sarm": state_arm(label, role, bst, mech)}
            p0 = prv.get(uid)
            if i == 0 or p0 is None or cell is None or d is None:
                rec["eval"] = False
                rec["why"] = ("first_step" if i == 0 else
                              "no_prev" if p0 is None else
                              "no_cell" if cell is None else "no_dir")
                out.append(rec)
                continue
            rec["eval"] = True
            rec["prev"] = p0
            tgt = (p0[0] + MX[d], p0[1] + MY[d])
            rec["tgt"] = tgt
            rec["tgt_in"] = in_grid(tgt[0], tgt[1], h, w)
            if cell == tgt:
                rec["out"] = "moved"
            elif cell != p0:
                rec["out"] = "moved_other"
            else:
                rec["out"] = "refused"
                pre = {prv[j] for j in prv if j != uid and prv[j] is not None}
                swp = set()
                swp_who = {}
                for j in order[:k]:
                    if j != uid and cur.get(j) is not None:
                        swp.add(cur[j])
                        swp_who.setdefault(cur[j], j)
                for j in order[k + 1:]:
                    if j != uid and prv.get(j) is not None:
                        swp.add(prv[j])
                        swp_who.setdefault(prv[j], j)
                rec["blocker"] = swp_who.get(tgt)
                blk_pre = rec["tgt_in"] and tgt in pre
                blk_swp = rec["tgt_in"] and tgt in swp
                if bst in DOCKED:
                    base = "NO_ATTEMPT"
                    rec["na"] = "rtb_docked_hold"
                elif label == "" and bst != "returning":
                    base = "NO_ATTEMPT"
                    rec["na"] = "no_managed_direction_hold(inferred)"
                elif not rec["tgt_in"]:
                    base = "OFF_GRID"
                else:
                    base = None
                if base is not None:
                    rec["cause"] = rec["cause_swp"] = base
                else:
                    rec["cause"] = "UAV_BLOCKED" if blk_pre else "UNEXPLAINED"
                    rec["cause_swp"] = "UAV_BLOCKED" if blk_swp else "UNEXPLAINED"
            if rec["sarm"] == "MOVE_LAYER_RTB_RETURN":
                berth = trip_berth(run, uid, i + 1)
                if berth is not None:
                    d0 = abs(p0[0] - berth[0]) + abs(p0[1] - berth[1])
                    d1 = abs(tgt[0] - berth[0]) + abs(tgt[1] - berth[1])
                    rec["rtb_toward"] = d1 < d0
                else:
                    rec["rtb_toward"] = None
            out.append(rec)
    # blocker kind for every UAV_BLOCKED (SWEEP) refusal, from the blocker's own
    # record in the same step: HEAD_ON = the blocker was itself refused while
    # aiming at this UAV's cell; BLOCKER_DOCKED = the blocker is parked
    # (charging/docked); BLOCKER_REFUSED = refused, aiming elsewhere;
    # SWEEP_TRANSIENT = it stood on the target when this UAV advanced and moved
    # away later in the same sweep; BLOCKER_MOVED_IN = it moved onto the target
    # earlier in the same sweep; BLOCKER_OTHER = none of these.
    idx = {(r["i"], r["uid"]): r for r in out}
    for r in out:
        if not r.get("eval") or r.get("cause_swp") != "UAV_BLOCKED":
            continue
        b = idx.get((r["i"], r.get("blocker")))
        if b is None or not b.get("eval"):
            r["blk_kind"] = "BLOCKER_UNKNOWN"
        elif b.get("bst") in DOCKED:
            r["blk_kind"] = "BLOCKER_DOCKED"
        elif b.get("out") == "refused" and b.get("tgt") == r["cell"]:
            r["blk_kind"] = "HEAD_ON"
        elif b.get("out") == "refused":
            r["blk_kind"] = "BLOCKER_REFUSED"
        elif b.get("prev") == r["tgt"]:
            r["blk_kind"] = "SWEEP_TRANSIENT"   # blocker LEFT the cell later in the sweep
        elif b.get("cell") == r["tgt"]:
            r["blk_kind"] = "BLOCKER_MOVED_IN"  # blocker ENTERED the cell earlier in the sweep
        else:
            r["blk_kind"] = "BLOCKER_OTHER"
    return out


def latches(recs):
    """Maximal runs >= 2 of consecutive refused steps, same uid/cell/dir/cause.
    The cause used is the SWEEP reconstruction (cause_swp), the one that explains
    every refusal in the corpus; PRE and SWEEP differ only on UAV_BLOCKED vs
    UNEXPLAINED, never on OFF_GRID or NO_ATTEMPT."""
    by = collections.defaultdict(list)
    for r in recs:
        if r["eval"]:
            by[r["uid"]].append(r)
    res = []
    for uid, s in by.items():
        s.sort(key=lambda r: r["i"])
        j = 0
        while j < len(s):
            r = s[j]
            if r["out"] != "refused":
                j += 1
                continue
            k = j
            while (k + 1 < len(s) and s[k + 1]["out"] == "refused"
                   and s[k + 1]["i"] == s[k]["i"] + 1
                   and s[k + 1]["cell"] == r["cell"] and s[k + 1]["dir"] == r["dir"]
                   and s[k + 1]["cause_swp"] == r["cause_swp"]):
                k += 1
            if k > j:
                seg = s[j:k + 1]
                res.append({"uid": uid, "role": r["role"], "cell": r["cell"],
                            "dir": r["dir"], "cause": r["cause_swp"], "start": r["t"],
                            "len": k - j + 1,
                            "labels": tuple(sorted({str(x["label"]) for x in seg})),
                            "sarms": tuple(sorted({x["sarm"] for x in seg})),
                            "blk": tuple(sorted({x.get("blk_kind", "-") for x in seg})),
                            "bst": tuple(sorted({str(x["bst"]) for x in seg}))})
            j = k + 1
    return res


# --------------------------------------------------------------- accumulate ---
class Acc:
    def __init__(self):
        self.runs = 0
        self.tuples = set()
        self.ua = collections.Counter()
        self.mech = collections.Counter()
        self.repo = collections.Counter()
        self.switch = collections.Counter()
        self.uavsteps = 0
        self.noneval = collections.Counter()
        self.a = collections.defaultdict(collections.Counter)   # role -> counter
        self.swp_matrix = collections.Counter()                  # (role, pre, swp)
        self.lab_off = collections.defaultdict(collections.Counter)
        self.lab_blk = collections.defaultdict(collections.Counter)
        self.lab_blk_swp = collections.defaultdict(collections.Counter)
        self.blk_kind = collections.Counter()
        self.lab_all = collections.defaultdict(collections.Counter)   # role -> label
        self.carm = collections.defaultdict(collections.Counter)  # (scheme, role, arm)
        self.offgrid = []                                         # detail rows
        self.latch = []
        self.rtb = collections.Counter()
        self.na_kind = collections.Counter()
        self.docked_moved = 0
        self.movelayer_labels = collections.Counter()

    def add(self, run, recs, tag):
        self.runs += 1
        key = (run.get("wind"), run.get("roles"), run.get("seed"))
        self.tuples.add(key)
        self.ua[ua_status(run)] += 1
        m, src = effective_mech(run)
        self.mech["%d:%s" % (m, src)] += 1
        self.repo[str(run.get("repo"))] += 1
        self.switch[str((run.get("extra_params") or {}).get(
            "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", "<unset>"))] += 1
        for r in recs:
            self.uavsteps += 1
            role = r["role"]
            self.lab_all[role][str(r["label"])] += 1
            if r["label"] in MOVE_LAYER_LABELS:
                self.movelayer_labels[r["label"]] += 1
            if not r["eval"]:
                self.noneval[(role, r["why"])] += 1
                continue
            c = self.a[role]
            c["eval"] += 1
            c[r["out"]] += 1
            for scheme, arm in (("label", r["larm"]), ("state", r["sarm"])):
                cc = self.carm[(scheme, role, arm)]
                cc["steps"] += 1
                if r["out"] == "refused":
                    cc["refused"] += 1
                    cc[r["cause"]] += 1
                    cc["swp_" + r["cause_swp"]] += 1
                elif r["out"] == "moved_other":
                    cc["moved_other"] += 1
            if r["sarm"] == "MOVE_LAYER_RTB_RETURN":
                self.rtb[(role, r.get("rtb_toward"))] += 1
            if r["bst"] in DOCKED and r["out"] != "refused":
                self.docked_moved += 1
            if r["out"] != "refused":
                continue
            c[r["cause"]] += 1
            c["swp_" + r["cause_swp"]] += 1
            if not r["tgt_in"]:
                c["raw_offgrid_target"] += 1
            if r["cause"] == "NO_ATTEMPT":
                self.na_kind[(role, r["na"])] += 1
            self.swp_matrix[(role, r["cause"], r["cause_swp"])] += 1
            bst = r["bst"] if r["bst"] else "free"
            if r["cause"] == "OFF_GRID":
                self.lab_off[role][(str(r["label"]), bst)] += 1
            if r["cause"] == "UAV_BLOCKED":
                self.lab_blk[role][(str(r["label"]), bst)] += 1
            if r["cause_swp"] == "UAV_BLOCKED":
                self.lab_blk_swp[role][(str(r["label"]), bst)] += 1
                self.blk_kind[(role, r["sarm"], r.get("blk_kind"))] += 1
            if not r["tgt_in"]:
                self.offgrid.append((tag, run.get("wind"), run.get("roles"),
                                     run.get("seed"), r["uid"], role, r["t"],
                                     r["cell"], r["dir"], r["label"], r["bst"],
                                     r["cause"]))
        for L in latches(recs):
            L["tag"] = tag
            L["key"] = key
            self.latch.append(L)


def load_tag(tag):
    files = sorted(glob.glob("_ffr_%s_*.json" % tag))
    runs, bad = [], []
    for p in files:
        try:
            run = load(p)
        except Exception as exc:
            bad.append((p, str(exc)))
            continue
        runs.append((p, run))
    return files, runs, bad


def build(tags):
    acc = Acc()
    info = {"files": 0, "unreadable": [], "no_uav_steps": []}
    for tag in tags:
        files, runs, bad = load_tag(tag)
        info["files"] += len(files)
        info["unreadable"] += bad
        for p, run in runs:
            if not run.get("uav_steps"):
                info["no_uav_steps"].append(p)
                continue
            acc.add(run, analyze_run(run), tag)
    return acc, info


# -------------------------------------------------------------------- print ---
def hdr(s):
    print()
    print("=" * 100)
    print(s)
    print("=" * 100)


def print_provenance(name, acc, info):
    print("  %-10s files=%d readable-with-uav_steps runs=%d distinct tuples=%d UAV-steps=%d"
          % (name, info["files"], acc.runs, len(acc.tuples), acc.uavsteps))
    print("  %-10s uav_actions: %s | return mechanism: %s" % ("", dict(acc.ua), dict(acc.mech)))
    print("  %-10s repo: %s | bounds-fix switch: %s" % ("", dict(acc.repo), dict(acc.switch)))
    if info["unreadable"]:
        print("  %-10s !! UNREADABLE: %s" % ("", info["unreadable"]))
    if info["no_uav_steps"]:
        print("  %-10s !! NO uav_steps (skipped, counted): %d %s"
              % ("", len(info["no_uav_steps"]), info["no_uav_steps"][:5]))
    if acc.movelayer_labels:
        print("  %-10s !! agents.py move-layer labels found in uav_actions: %s"
              % ("", dict(acc.movelayer_labels)))


def print_a(name, acc):
    print("  %-8s %-16s %7s %7s %6s %7s | %7s %8s %8s %8s | %8s %8s"
          % ("arm", "role", "eval", "moved", "movOth", "refused", "OFFGRID",
             "BLK_pre", "NO_ATT", "UNEX_pre", "BLK_swp", "UNEX_swp"))
    for role in sorted(acc.a):
        c = acc.a[role]
        print("  %-8s %-16s %7d %7d %6d %7d | %7d %8d %8d %8d | %8d %8d"
              % (name, role, c["eval"], c["moved"], c["moved_other"], c["refused"],
                 c["OFF_GRID"], c["UAV_BLOCKED"], c["NO_ATTEMPT"], c["UNEXPLAINED"],
                 c["swp_UAV_BLOCKED"], c["swp_UNEXPLAINED"]))
    ne = collections.Counter()
    for (role, why), v in acc.noneval.items():
        ne[role] += v
    print("  %-8s non-evaluable UAV-steps: %s" % (name, dict(sorted(acc.noneval.items()))))
    na = dict(sorted(acc.na_kind.items()))
    print("  %-8s NO_ATTEMPT by kind: %s" % (name, na if na else "{} (none)"))
    mx = {k: v for k, v in acc.swp_matrix.items() if k[1] != k[2]}
    print("  %-8s PRE vs SWEEP disagreements (role, pre, sweep): %s"
          % (name, mx if mx else "none"))
    if acc.docked_moved:
        print("  %-8s !! docked/charging steps that MOVED: %d" % (name, acc.docked_moved))


def print_b(name, acc):
    for title, src in (("OFF_GRID", acc.lab_off), ("UAV_BLOCKED (PRE rule)", acc.lab_blk),
                       ("UAV_BLOCKED (SWEEP rule)", acc.lab_blk_swp)):
        roles = sorted(set(acc.a) | set(src))
        for role in roles:
            h = src.get(role) or collections.Counter()
            tot = sum(h.values())
            print("  %-8s %-16s %-22s total %d" % (name, role, title, tot))
            if not tot:
                print("  %-8s %-16s     (none)" % ("", ""))
                continue
            bylab = collections.defaultdict(collections.Counter)
            for (lab, bst), v in h.items():
                bylab[lab][bst] += v
            for lab, bc in sorted(bylab.items(), key=lambda kv: -sum(kv[1].values())):
                print("  %-8s %-16s     %-52s %5d   [%s]"
                      % ("", "", lab, sum(bc.values()),
                         " ".join("%s=%d" % (b, bc[b]) for b in sorted(bc))))


def print_vocab(name, acc):
    for role in sorted(acc.lab_all):
        for lab, v in sorted(acc.lab_all[role].items(), key=lambda kv: -kv[1]):
            lab2 = None if lab == "None" else lab
            print("  %-8s %-16s %-52s %6d  -> %s"
                  % (name, role, lab, v, label_arm(lab2, role)))


def print_c(name, acc, scheme):
    arms = STATE_ARMS if scheme == "state" else LABEL_ARMS
    print("  %-8s %-16s %-28s %6s %7s | %7s %7s %7s %7s | %7s %7s %s"
          % ("arm", "role", "dispatch arm", "steps", "refused", "OFFGRID", "BLK_pre",
             "NO_ATT", "UNX_pre", "BLK_swp", "UNX_swp", "filter"))
    roles = sorted({k[1] for k in acc.carm if k[0] == scheme})
    for role in roles:
        for arm in arms:
            c = acc.carm.get((scheme, role, arm))
            if not c:
                continue
            print("  %-8s %-16s %-28s %6d %7d | %7d %7d %7d %7d | %7d %7d %s"
                  % (name, role, arm, c["steps"], c["refused"], c["OFF_GRID"],
                     c["UAV_BLOCKED"], c["NO_ATTEMPT"], c["UNEXPLAINED"],
                     c["swp_UAV_BLOCKED"], c["swp_UNEXPLAINED"],
                     "UNFILTERED" if arm in UNFILTERED else ""))


def print_rtb(name, acc):
    if not acc.rtb:
        print("  %-8s no MOVE_LAYER_RTB_RETURN steps" % name)
        return
    for role in sorted({k[0] for k in acc.rtb}):
        t = acc.rtb.get((role, True), 0)
        f = acc.rtb.get((role, False), 0)
        n = acc.rtb.get((role, None), 0)
        print("  %-8s %-16s returning steps: dir reduces distance to the trip's target "
              "berth %d / %d (not: %d, no trip found: %d)" % (name, role, t, t + f, f, n))


def print_d(name, acc):
    g = collections.defaultdict(list)
    for L in acc.latch:
        g[(L["role"], L["cause"])].append(L)
    if not g:
        print("  %-8s no latch runs" % name)
    for (role, cause), Ls in sorted(g.items()):
        longest = max(Ls, key=lambda L: L["len"])
        print("  %-8s %-16s %-12s runs %4d  steps %5d  longest %3d  (%s/%s/%s uid %s cell %s dir %d start %d)"
              % (name, role, cause, len(Ls), sum(L["len"] for L in Ls), longest["len"],
                 longest["key"][0], longest["key"][1], longest["key"][2], longest["uid"],
                 longest["cell"], longest["dir"], longest["start"]))
        sets = collections.Counter()
        steps = collections.Counter()
        for L in Ls:
            k = ("labels=" + "|".join(L["labels"]) + "  arms=" + "|".join(L["sarms"])
                 + "  base=" + "|".join(L["bst"])
                 + ("  blocker=" + "|".join(L["blk"]) if L["cause"] == "UAV_BLOCKED" else ""))
            sets[k] += 1
            steps[k] += L["len"]
        for k, v in sorted(sets.items(), key=lambda kv: -kv[1]):
            print("  %-8s %-16s %-12s     x%-4d steps %-5d %s" % ("", "", "", v, steps[k], k))


def print_e(name, acc, full_list):
    bad = [o for o in acc.offgrid if o[9] is None or GATE_LABEL not in str(o[9])]
    byrole = collections.Counter(o[5] for o in acc.offgrid)
    print("  %-8s off-grid-target refusals (ANY base_state, ANY cause) checked: %d  by role %s"
          % (name, len(acc.offgrid), dict(byrole) if byrole else "{}"))
    exact = collections.Counter(str(o[9]) for o in acc.offgrid)
    print("  %-8s   exact labels: %s" % ("", dict(exact) if exact else "{}"))
    bstc = collections.Counter(str(o[10]) for o in acc.offgrid)
    print("  %-8s   base_state: %s" % ("", dict(bstc) if bstc else "{}"))
    if not bad:
        print("  %-8s   NON-GATE-LABELLED: NONE (0 of %d)" % ("", len(acc.offgrid)))
    else:
        print("  %-8s   NON-GATE-LABELLED: %d" % ("", len(bad)))
        for o in bad:
            print("  %-8s     %s" % ("", o))
    if full_list and acc.offgrid:
        ev = collections.defaultdict(list)
        for o in acc.offgrid:
            ev[(o[0], o[1], o[2], o[3], o[4], o[7], o[8])].append(o)
        print("  %-8s   per (run, uid, cell, dir): steps, first..last, labels, base_state" % "")
        for k, v in sorted(ev.items(), key=lambda kv: (str(kv[0][1]), str(kv[0][3]), kv[0][4])):
            print("  %-8s     %-6s %-6s %-5s %-11s uid %s cell %-8s dir %d  n=%-3d steps %d..%d  %s  %s"
                  % ("", k[0], k[1], k[2], k[3], k[4], "(%d,%d)" % k[5], k[6], len(v),
                     min(o[6] for o in v), max(o[6] for o in v),
                     sorted({str(o[9]) for o in v}), sorted({str(o[10]) for o in v})))


def section_all(name, acc, info, full_offgrid):
    hdr("ARM %s" % name)
    print_provenance(name, acc, info)
    print("\n  (a) REFUSALS BY CAUSE")
    print_a(name, acc)
    print("\n  (b) FULL LABEL HISTOGRAMS ON REFUSALS, [base_state split]")
    print_b(name, acc)
    print("\n  (c0) LABEL VOCABULARY -> LABEL-ONLY DISPATCH ARM (all UAV-steps, evaluable or not)")
    print_vocab(name, acc)
    print("\n  (c1) KEY TABLE, LABEL-ONLY dispatch arm (the brief's scheme; evaluable steps)")
    print_c(name, acc, "label")
    print("\n  (c2) KEY TABLE, BASE-STATE-AWARE dispatch arm (who actually delivered the direction)")
    print_c(name, acc, "state")
    print_rtb(name, acc)
    print("\n  (c3) UAV_BLOCKED (SWEEP) refusals by role, base-state-aware arm and BLOCKER KIND")
    for (role, arm, kind), v in sorted(acc.blk_kind.items()):
        print("  %-8s %-16s %-28s %-16s %5d" % (name, role, arm, kind, v))
    print("\n  (d) LATCH SIGNATURES (>= 2 consecutive refused, same uid/cell/dir/cause; "
          "cause = SWEEP rule)")
    print_d(name, acc)
    print("\n  (e) HIDDEN-PATH CHECK")
    print_e(name, acc, full_offgrid)


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--broad", action="store_true",
                    help="(g) off-grid census over every _ffr_*.json (non-recursive glob)")
    a = ap.parse_args()

    print("sfx2 ITEM 2 - corpus measurement (read-only, no simulation)")
    print("python %s" % sys.version.split()[0])
    print("grid dims: params HEIGHT/WIDTH when recorded, else 50x50 (_sfx_analyze.dims); "
          "x is the HEIGHT axis")
    print("MOVE_X=%s MOVE_Y=%s  (0=E 1=S 2=W 3=N)" % (MX, MY))

    main_accs = {}
    for tag in MAIN_ARMS:
        acc, info = build([tag])
        main_accs[tag] = (acc, info)
        section_all(tag, acc, info, full_offgrid=True)

    hdr("CROSS-CHECK against _sf_analyze.refusals() (searcherfire's reader, 50x50, no docked test)")
    import _sf_analyze
    for tag in MAIN_ARMS + ("dcD",):
        C, _labels = _sf_analyze.refusals("_ffr_%s_*.json" % tag)
        acc = main_accs[tag][0] if tag in main_accs else build([tag])[0]
        for role in sorted(C):
            c = C[role]
            mine = acc.a[role]
            in_bounds_mine = (mine["refused"] - mine["raw_offgrid_target"])
            print("  %-7s %-16s _sf_analyze: steps %6d refused %5d offgrid %4d uavblock %5d | "
                  "this tool: eval %6d refused %5d raw-offgrid %4d in-bounds(BLK+NA+UNX) %5d  %s"
                  % (tag, role, c["steps"], c["refused"], c["refused_offgrid"],
                     c["refused_uavblock"], mine["eval"], mine["refused"],
                     mine["raw_offgrid_target"], in_bounds_mine,
                     "MATCH" if (c["steps"] == mine["eval"] and c["refused"] == mine["refused"]
                                 and c["refused_offgrid"] == mine["raw_offgrid_target"]
                                 and c["refused_uavblock"] == in_bounds_mine) else "DIFF"))
    print("  NOTE: _sf_analyze's 'uavblock' is every in-bounds refusal, so it INCLUDES the")
    print("  docked NO_ATTEMPT steps (searcherfire_part1.txt s.6 'dcD tracker 755 / searcher")
    print("  619' = UAV_BLOCKED + NO_ATTEMPT + UNEXPLAINED here).")

    hdr("(e) SUMMARY - off-grid refusals per arm and role, and non-gate-labelled ones")
    for tag in MAIN_ARMS:
        acc = main_accs[tag][0]
        byrole = collections.Counter(o[5] for o in acc.offgrid)
        bad = [o for o in acc.offgrid if o[9] is None or GATE_LABEL not in str(o[9])]
        roles = sorted(acc.a)
        print("  %-8s %s   non-gate-labelled %d"
              % (tag, "  ".join("%s=%d" % (r, byrole.get(r, 0)) for r in roles), len(bad)))

    hdr("(f) THE SEARCHERFIRE WIDER POPULATION: %s" % ", ".join(WIDER))
    print("  searcherfire_part1.txt s.3.4 (git show searcherfire:outputs/searcherfire_part1.txt):")
    print("  '167 run-records / 57 tuples / 160,320 UAV-steps ... ALL 657 out-of-bounds")
    print("  refusals ... are victim searchers'. The report names no arm list for it.")
    print("  Identification (this tool): the five shipped-default arms it names in s.0.5")
    print("  (113 records) plus the fire-mechanic OFF arms fmOFF and f3OFF, which s.2 lists")
    print("  in its 'broader shipped-default set'. Verified below by recount.")
    pooled = Acc()
    pinfo = {"files": 0, "unreadable": [], "no_uav_steps": []}
    per = {}
    for tag in WIDER:
        acc, info = build([tag])
        per[tag] = (acc, info)
        pinfo["files"] += info["files"]
        pinfo["unreadable"] += info["unreadable"]
        pinfo["no_uav_steps"] += info["no_uav_steps"]
    # pooled pass (re-uses the per-tag loads' logic; loads again to keep Acc simple)
    pooled, pinfo2 = build(list(WIDER))
    print()
    for tag in WIDER:
        acc = per[tag][0]
        byrole = collections.Counter(o[5] for o in acc.offgrid)
        print("  %-6s runs %3d tuples %2d UAV-steps %6d  off-grid-target refusals: %s"
              % (tag, acc.runs, len(acc.tuples), acc.uavsteps,
                 dict(byrole) if byrole else "{}"))
    byrole = collections.Counter(o[5] for o in pooled.offgrid)
    print("  POOLED runs %d  distinct tuples %d  UAV-steps %d  off-grid-target refusals %d %s"
          % (pooled.runs, len(pooled.tuples), pooled.uavsteps, len(pooled.offgrid), dict(byrole)))
    ok = (pooled.runs == 167 and len(pooled.tuples) == 57 and pooled.uavsteps == 160320
          and len(pooled.offgrid) == 657)
    print("  REPRODUCES 167 / 57 / 160,320 / 657: %s" % ("YES" if ok else "NO"))
    section_all("WIDER167", pooled, pinfo2, full_offgrid=True)
    hdr("(f) per-tag (a)/(c2) for the wider population")
    for tag in WIDER:
        acc = per[tag][0]
        print_a(tag, acc)
        print_c(tag, acc, "state")
        print()

    if a.broad:
        hdr("(g) BROAD CENSUS - every _ffr_*.json (non-recursive glob) with uav_steps")
        files = sorted(glob.glob("_ffr_*.json"))
        tags = collections.OrderedDict()
        for f in files:
            m = re.match(r"_ffr_(.+?)_(east|south|west|north)_", f)
            tags.setdefault(m.group(1) if m else f, []).append(f)
        grand = collections.Counter()
        nongate = []
        brole = collections.Counter()
        bstate = collections.Counter()
        barm = collections.Counter()
        bsteps = collections.Counter()
        bexact = collections.Counter()
        skipped = collections.Counter()
        for tag, fl in tags.items():
            c = collections.Counter()
            for p in fl:
                try:
                    run = load(p)
                except Exception:
                    c["unreadable"] += 1
                    continue
                if not run.get("uav_steps"):
                    c["no_uav_steps"] += 1
                    continue
                c["runs"] += 1
                c["ua_" + ua_status(run)] += 1
                c["mech_%d" % effective_mech(run)[0]] += 1
                recs = analyze_run(run)
                for r in recs:
                    if not r["eval"]:
                        continue
                    c["eval"] += 1
                    bsteps[(r["role"], r["sarm"])] += 1
                    if r["out"] == "moved_other":
                        c["moved_other"] += 1
                    if r["out"] != "refused":
                        continue
                    c["refused"] += 1
                    c[r["cause"]] += 1
                    c["swp_" + r["cause_swp"]] += 1
                    barm[(r["role"], r["sarm"], r["cause_swp"])] += 1
                    if not r["tgt_in"]:
                        c["off_" + r["role"]] += 1
                        brole[r["role"]] += 1
                        bstate[str(r["bst"])] += 1
                        bexact[str(r["label"])] += 1
                        if r["label"] is None:
                            c["off_nolabel"] += 1
                        elif GATE_LABEL in r["label"]:
                            c["off_gate"] += 1
                        else:
                            c["off_NONGATE"] += 1
                            nongate.append((tag, p, r["uid"], r["role"], r["t"],
                                            r["cell"], r["dir"], r["label"], r["bst"]))
            if not c["runs"]:
                skipped[tag] = len(fl)
                continue
            grand.update(c)
            print("  %-14s runs %3d ua[%s] mech[%s] eval %6d refused %5d OFF %4d BLKpre %4d "
                  "NA %5d UNXpre %3d UNXswp %d movOth %d | off-grid S=%d T=%d | gate %d "
                  "nonGATE %d nolabel %d"
                  % (tag, c["runs"],
                     ",".join("%s=%d" % (k[3:], v) for k, v in sorted(c.items())
                              if k.startswith("ua_")),
                     ",".join("%s=%d" % (k[5:], v) for k, v in sorted(c.items())
                              if k.startswith("mech_")),
                     c["eval"], c["refused"], c["OFF_GRID"], c["UAV_BLOCKED"],
                     c["NO_ATTEMPT"], c["UNEXPLAINED"], c["swp_UNEXPLAINED"],
                     c["moved_other"],
                     c["off_" + SEARCHER], c["off_" + TRACKER], c["off_gate"],
                     c["off_NONGATE"], c["off_nolabel"]))
        print()
        print("  tags with no uav_steps in any file (skipped): %d tags, %d files"
              % (len(skipped), sum(skipped.values())))
        print("  GRAND: runs %d eval %d refused %d OFF_GRID %d UAV_BLOCKED pre %d / sweep %d "
              "NO_ATTEMPT %d UNEXPLAINED pre %d / sweep %d moved_other %d"
              % (grand["runs"], grand["eval"], grand["refused"], grand["OFF_GRID"],
                 grand["UAV_BLOCKED"], grand["swp_UAV_BLOCKED"], grand["NO_ATTEMPT"],
                 grand["UNEXPLAINED"], grand["swp_UNEXPLAINED"], grand["moved_other"]))
        print("  GRAND off-grid-target refusals by role: %s | by base_state: %s"
              % (dict(brole), dict(bstate)))
        print("  GRAND off-grid label class: gate %d  NON-GATE %d  no-label-data %d"
              % (grand["off_gate"], grand["off_NONGATE"], grand["off_nolabel"]))
        print("  GRAND off-grid EXACT labels (None = run has no uav_actions): %s" % dict(bexact))
        print("  GRAND evaluable steps and refusals by (role, base-state-aware dispatch arm), "
              "cause [SWEEP rule]:")
        for (role, arm), n in sorted(bsteps.items()):
            parts = ["%s=%d" % (cz, barm.get((role, arm, cz), 0)) for cz in CAUSES]
            print("    %-16s %-28s steps %7d  refused: %s%s"
                  % (role, arm, n, "  ".join(parts),
                     "  UNFILTERED" if arm in UNFILTERED else ""))
        if nongate:
            print("  NON-GATE off-grid refusals:")
            for x in nongate:
                print("    %s" % (x,))
        else:
            print("  NON-GATE off-grid refusals: NONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
