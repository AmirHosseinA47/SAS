"""dcd4 round: every return-leg FREEZE (>= 3 frames on one cell) and what blocked it,
plus every long STATIONARY episode of a non-returning UAV.

Read-only. Found while reading the deadlock readout: in d4D south/half/423146201
UAV 2501 froze 18 frames at (7,45) on a pure-axis approach to berth (3,45), held by
UAV 2502 - a victim SEARCHER that was not returning, sitting at (6,45) with its
selected direction pointing back into 2501. The redefined stranding gate cannot
see an episode that resolves before the horizon, and no check at all looks at the
blocking UAV, so this script covers both sides.

SECTION 1 - return-leg freezes. A freeze is frames k..j with one position while
base_state == "returning". Each REFUSED move is a frame m in k+1..j. All UAV work
runs inside one advance() sweep that mutates the grid as it goes, so the agent
that refused the move may have been on the cell BEFORE the step (frame m-1) and
gone AFTER it (frame m); both frames are checked. The steer may be on either
axis: the primary (larger residual) axis toward the berth, or - once stalled, or
under the dock-fix recovery latch - the other one. Both candidate cells are
checked. A freeze's blocker set is every UAV found on a candidate cell on any
refused frame. HEAD-ON means that UAV's selected_dir at that frame points back at
the frozen cell.
(An earlier version looked only at post-step positions on the primary axis and
called three short freezes "nothing on the cell"; the report's verification pass
showed all three were brief blocks by other UAVs. Corrected here.)

SECTION 2 - stationary episodes of NON-returning UAVs: maximal runs of >= 10
frames on one cell with base_state "" on every frame. Split by whether the
episode starts before or after the run's terminal_step (after it, no victim is
left and nothing the UAV does can change an outcome).

usage: .venv/Scripts/python.exe outputs/_dcd4_freezes.py [--arms d4D,d4A,d4off,dfD,dfA,dcB]
"""
import argparse
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _dcd4_analyze as AN  # noqa: E402

MOVE_X = [1, 0, -1, 0]      # agents.py move(): index = selected_dir
MOVE_Y = [0, -1, 0, 1]


def axis_cells(pos, target):
    dx, dy = target[0] - pos[0], target[1] - pos[1]
    out = []
    if dx:
        out.append((pos[0] + (1 if dx > 0 else -1), pos[1]))
    if dy:
        out.append((pos[0], pos[1] + (1 if dy > 0 else -1)))
    return out


def points_at(c, cell, into):
    sd = c[3]
    try:
        sd = int(sd)
    except (TypeError, ValueError):
        return False
    return 0 <= sd < 4 and (cell[0] + MOVE_X[sd], cell[1] + MOVE_Y[sd]) == into


def run_freezes(tag, t, d, min_len=3):
    rows, log = d["uav_steps"], d.get("rtb_log") or {}
    uids = [c[0] for c in rows[0]]
    out = []
    for a, uid in enumerate(uids):
        trips = {tr["trigger_step"]: tr for tr in log.get(uid, [])}
        f = 0
        while f < len(rows):
            if rows[f][a][5] != "returning":
                f += 1
                continue
            g = f
            while g < len(rows) and rows[g][a][5] == "returning":
                g += 1
            trip = trips.get(f + 1)
            target = tuple(trip["target_berth"]) if trip else None
            k = f
            while k < g:
                pos = tuple(rows[k][a][1])
                j = k
                while j + 1 < g and tuple(rows[j + 1][a][1]) == pos:
                    j += 1
                n = j - k + 1
                if n >= min_len and target is not None:
                    blockers = {}
                    for m in range(k + 1, j + 1):
                        for cell in axis_cells(pos, target):
                            for fr in (m - 1, m):
                                for b, c in enumerate(rows[fr]):
                                    if b != a and c[1] is not None and tuple(c[1]) == cell:
                                        key = c[0]
                                        info = blockers.setdefault(key, {"state": set(), "head_on": False,
                                                                         "frames": set(), "role": c[2]})
                                        info["state"].add(c[5] or "flying")
                                        info["frames"].add(m)
                                        info["head_on"] |= points_at(c, cell, pos)
                    kind = "none found"
                    if blockers:
                        states = set().union(*(v["state"] for v in blockers.values()))
                        kind = ("flying UAV" if "flying" in states else
                                "returning UAV" if "returning" in states else "charging UAV")
                    inside = bool(d.get("base_station")) and any(
                        o[0] <= pos[0] < o[0] + d["base_station"]["size"] and
                        o[1] <= pos[1] < o[1] + d["base_station"]["size"]
                        for o in (d["base_station"].get("depots") or [d["base_station"]["origin"]]))
                    out.append({"run": "%s %s" % (tag, AN.tlabel(t)), "uid": uid, "cell": pos,
                                "start_step": k + 1, "frames": n, "dist": AN.manh(pos, target),
                                "kind": kind, "inside": inside, "terminal": d.get("terminal_step"),
                                "blockers": blockers,
                                "arrived": bool(trip and trip.get("arrival_step") is not None)})
                k = j + 1
            f = g
    return out


def run_stationary(tag, t, d, min_len=10):
    rows = d["uav_steps"]
    term = d.get("terminal_step")
    out = []
    for a, uid in enumerate(c[0] for c in rows[0]):
        f = 0
        while f < len(rows):
            c = rows[f][a]
            if c[1] is None or (c[5] if len(c) > 5 else "") != "":
                f += 1
                continue
            pos = tuple(c[1])
            g = f
            while g + 1 < len(rows) and rows[g + 1][a][1] is not None and \
                    tuple(rows[g + 1][a][1]) == pos and (rows[g + 1][a][5] if len(rows[g + 1][a]) > 5 else "") == "":
                g += 1
            n = g - f + 1
            if n >= min_len:
                out.append({"run": "%s %s" % (tag, AN.tlabel(t)), "uid": uid, "role": c[2], "cell": pos,
                            "start_step": f + 1, "frames": n,
                            "after_terminal": term is not None and f + 1 > term})
            f = g + 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="d4D,d4A,d4off,dfD,dfA,dcB")
    a = ap.parse_args()
    sys.stdout.reconfigure(newline="\n")
    samples = {"d4D": "fourth", "d4A": "fourth", "d4off": "fourth"}
    stat_all = {}
    print("SECTION 1  RETURN-LEG FREEZES (>= 3 frames), blocker from pre- AND post-step occupancy, both axes")
    for tag in a.arms.split(","):
        tuples = AN.sample(samples.get(tag, "both"))
        fz, st, present = [], [], 0
        for t in tuples:
            d = AN.load_json(AN.ffr_path(tag, *t))
            if d is None:
                continue
            present += 1
            fz.extend(run_freezes(tag, t, d))
            st.extend(run_stationary(tag, t, d))
            del d
        stat_all[tag] = (present, st)
        kinds = collections.Counter(x["kind"] for x in fz)
        hist = collections.Counter(x["frames"] for x in fz)
        print("%-5s runs %d  freezes: %d  by blocker %s  lengths %s"
              % (tag, present, len(fz), dict(kinds), dict(sorted(hist.items()))))
        for x in sorted(fz, key=lambda x: (-x["frames"], x["run"])):
            bl = "; ".join("%s %s %s%s refused-frames %d" % (
                u, v["role"], "/".join(sorted(v["state"])), " HEAD-ON" if v["head_on"] else "",
                len(v["frames"])) for u, v in sorted(x["blocker"].items())) if False else \
                "; ".join("%s %s %s%s on %d of %d refused frames" % (
                    u, v["role"], "/".join(sorted(v["state"])), " HEAD-ON" if v["head_on"] else "",
                    len(v["frames"]), x["frames"] - 1) for u, v in sorted(x["blockers"].items()))
            print("    %-32s uid %s %2d frames from step %3d at %-8s d=%-2d %s terminal=%s  blockers: %s%s"
                  % (x["run"], x["uid"], x["frames"], x["start_step"], "(%d,%d)" % x["cell"], x["dist"],
                     "INSIDE depot " if x["inside"] else "outside depot", x["terminal"], bl or "none found",
                     "" if x["arrived"] else "  NOT ARRIVED"))
    print()
    print("SECTION 2  STATIONARY NON-RETURNING UAVs (>= 10 frames on one cell, base_state '' throughout)")
    for tag, (present, st) in stat_all.items():
        pre = [x for x in st if not x["after_terminal"]]
        post = [x for x in st if x["after_terminal"]]
        by_role = collections.Counter(x["role"] for x in pre)
        print("%-5s runs %d  before terminal: %d episodes / %d frames %s   after terminal: %d / %d"
              % (tag, present, len(pre), sum(x["frames"] for x in pre), dict(by_role),
                 len(post), sum(x["frames"] for x in post)))
        for x in sorted(pre, key=lambda x: -x["frames"])[:12]:
            print("    %-32s uid %s %-16s %-8s from step %3d for %3d frames"
                  % (x["run"], x["uid"], x["role"], "(%d,%d)" % x["cell"], x["start_step"], x["frames"]))
    print("FREEZES_COMPLETE")


if __name__ == "__main__":
    main()
