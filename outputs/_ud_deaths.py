"""Urgency round, the 22.9 per-death review (maintainer ruling on report section 9, D-4): the DEATH TABLE.

READ-ONLY over the committed screen records. For every FRESH cell (sets 3-4) and every arm (0, U, M, MU) it lists
each detected-victim death (victim, detection, death, the frozen 22.9 class and flags, M8) and each firefighter death
(unit, step), with what the records say about the dying unit:
  - its last recorded state (status, bound victim, route_blocked, exiting) and the last state change before death;
  - the leg it died on (approach / carry / unbound) and the last bind, unbind and route_blocked raise before death;
  - every LIVE fix event of that unit (mv_events: kind, step, cell, today's cell), and the gap from the last one;
  - whether the death is VALUE-IDENTICAL to the same unit's or victim's death in the paired arm (same step).
It reuses _ud_analyze.py's loader and digest (the frozen 22.9 classes) unchanged; it computes nothing new about the
outcome. No movement outcome on seed sets 1-2 is read: only sets 3 and 4 are loaded.

usage: _ud_deaths.py --out <json> [--txt <summary>]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:]]
import _ud_analyze as A  # noqa: E402

FF_COLS = ("unit", "x", "y", "status", "bound", "exiting", "dead", "carrying", "victim", "target", "rb", "extra")


def ff_series(rows_ff, unit):
    """[(step, row)] for one unit; row is the rows_ff entry (step = index + 1)."""
    out = []
    for t, row in enumerate(rows_ff):
        for r in row:
            if r[0] == unit:
                out.append((t + 1, r))
    return out


def unit_story(d, unit, death):
    rows_ff = d["rows_ff"]
    ser = ff_series(rows_ff, unit)
    before = [(t, r) for t, r in ser if t < death]
    last = before[-1][1] if before else None
    changes = []
    prev = None
    for t, r in before:
        key = (r[3], r[8], r[10])
        if key != prev:
            changes.append([t, r[3], r[8], [r[1], r[2]], r[10]])
            prev = key
    cmds = (d.get("dp") or {}).get("commands") or []
    mine = [c for c in cmds if c[4] == unit and c[0] <= death]
    mv_ev = [e for e in d.get("mv_events") or [] if e.get("unit") == unit and e.get("live") and e["step"] <= death]
    last_fix = mv_ev[-1]["step"] if mv_ev else None
    rows = [r for r in (d.get("mv") or {}).get("rows") or [] if r[1] == unit and r[0] <= death]
    mv_tail = [[r[0], r[3], r[4], r[5], r[6], r[7], r[9], r[10], r[22], r[23], r[25], r[28], r[29], r[30], r[37]]
               for r in rows[-12:]]
    return {
        "last_row": last,
        "state_changes": changes[-10:],
        "commands": mine[-8:],
        "fix_events": [[e["kind"], e["step"], e.get("cell"), (e.get("today") or [None, None])[1], e.get("victim")]
                       for e in mv_ev],
        "n_fix_events": len(mv_ev),
        "last_fix_step": last_fix,
        "gap_last_fix_to_death": None if last_fix is None else death - last_fix,
        "mv_tail_cols": ["step", "leg", "branch", "pre", "post", "target", "st_pre", "st_post", "acted", "dc",
                         "df", "gesc", "cls_pre", "cls_post", "dcb"],
        "mv_tail": mv_tail,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--txt")
    o = ap.parse_args()
    frozen = A.load_seeds()

    class Opts:
        smoke = None
        smoke_files = {}
    cells = [c for c in A.screen_cells(frozen, Opts) if c["fresh"]]
    table = []
    for c in cells:
        entry = {"cell": c["id"], "seed": c["seed"], "scen": c["scen"], "wind": c["wind"], "arms": {}}
        raw = {}
        for arm in A.ARMS:
            p = A.run_path(arm, c, Opts)
            d = A.load_run(p)
            g = A.digest(d, arm, "%s_%s" % (A.ARM_TAG[arm], c["id"]), p, c["set"])
            raw[arm] = d
            ff = []
            for u, t in sorted(g["ff_dead"].items(), key=lambda kv: kv[1]):
                ff.append(dict({"unit": u, "death": t}, **unit_story(d, u, t)))
            entry["arms"][arm] = {
                "path": os.path.basename(p),
                "rescued": g["eval"].get("rescued"),
                "DD": [{k: x[k] for k in ("victim", "det", "death", "cls", "flags", "m8", "m8d")} for x in g["deaths"]],
                "ff": ff,
                "acted_live": g.get("acted_live"),
            }
        # first divergence of each arm from arm 0 (rows only; the analyzer's value identity is the gate's)
        for arm in ("U", "M", "MU"):
            fd = None
            for t in range(len(raw["0"]["rows_ff"])):
                if any(raw["0"][k][t] != raw[arm][k][t] for k in ("rows_ff", "rows_vic", "rows_uav")):
                    fd = t + 1
                    break
            entry["arms"][arm]["first_row_diff_vs_0"] = fd
        # paired identity of each death with arm 0's
        for arm in ("U", "M", "MU"):
            for x in entry["arms"][arm]["DD"]:
                x["same_in_0"] = any(y["victim"] == x["victim"] and y["death"] == x["death"]
                                     for y in entry["arms"]["0"]["DD"])
            for x in entry["arms"][arm]["ff"]:
                x["same_in_0"] = any(y["unit"] == x["unit"] and y["death"] == x["death"]
                                     for y in entry["arms"]["0"]["ff"])
        for x in entry["arms"]["0"]["DD"]:
            x["same_in_M"] = any(y["victim"] == x["victim"] and y["death"] == x["death"] for y in entry["arms"]["M"]["DD"])
        for x in entry["arms"]["0"]["ff"]:
            x["same_in_M"] = any(y["unit"] == x["unit"] and y["death"] == x["death"] for y in entry["arms"]["M"]["ff"])
        raw = None
        table.append(entry)
    with open(o.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(table, fh, indent=1, default=str)
    if o.txt:
        lines = []
        tot = collections.Counter()
        for e in table:
            for arm in A.ARMS:
                a = e["arms"][arm]
                tot[(arm, "DD")] += len(a["DD"])
                tot[(arm, "ff")] += len(a["ff"])
                for x in a["DD"]:
                    lines.append("%-22s %-2s DD  %-9s det %-4s death %-4s %-11s %s" % (
                        e["cell"], arm, x["victim"], x["det"], x["death"], x["cls"],
                        "" if arm == "0" else ("same-as-0" if x.get("same_in_0") else "NEW/CHANGED")))
                for x in a["ff"]:
                    lines.append("%-22s %-2s FF  %-9s death %-4s fixes %-3s last_fix %-4s gap %-4s %s" % (
                        e["cell"], arm, x["unit"], x["death"], x["n_fix_events"], x["last_fix_step"],
                        x["gap_last_fix_to_death"],
                        "" if arm == "0" else ("same-as-0" if x.get("same_in_0") else "NEW/CHANGED")))
        lines.append("TOTALS " + " ".join("%s:%s=%d" % (k[0], k[1], v) for k, v in sorted(tot.items())))
        with open(o.txt, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
