# -*- coding: utf-8 -*-
"""Non-burnable-depot round: the PAYLOAD proof of the display change.

The base-mark round's pixel audit varies `drawMap` (JavaScript) across two
revisions with the frame payload held FIXED. That instrument is structurally
blind to this change: the new colour is produced by serve_dashboard._cell_color
in PYTHON and reaches the page inside `fr.cells`, so it never passes through
drawMap at all. Replaying the frozen base-mark payloads would show 12 identical
gate images and prove nothing.

So the payload itself is the object under test. For ONE model state this builds
two frames:

  POST  serve_dashboard._capture_frame as it is now
  PRE   the same call with _cell_color monkey-patched back to the 6281542 body,
        lifted from `git show 6281542:serve_dashboard.py` and compiled - not
        retyped - and with the new `nofuel` key removed

and asserts, cell by cell over all 2500:

  * every cell whose colour changed is a cell that is CLEARED (fuel 0, never
    burned, not burning, not burnt) - and every cleared cell changed;
  * the PRE colour of each of those is exactly VEGETATION_COLORS[0] = #414141,
    which is also FIRE_COLORS[0]: the collision the round is removing;
  * the POST colour is exactly the measured #193cff;
  * NOTHING else in the payload moved - every other key is equal, and for
    `cells` the symmetric difference outside the cleared set is empty.

A negative control runs the same comparison with BASE_STATION_FIREPROOF = 0: no
cell may change, and `nofuel` must be empty. Without it, "every changed cell is
a depot cell" would also be satisfied by a renderer that painted the depot block
unconditionally.

usage: _dfp_payload.py [seed] [wind] [step]
  -> outputs/_dfp_payload.json, outputs/_dfp_payload.txt
"""
from __future__ import annotations

import ast
import contextlib
import io as _io
import json
import os
import random
import subprocess
import sys

os.environ.setdefault("MPLBACKEND", "Agg")
BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)
sys.path.insert(0, REPO)

import agents as am  # noqa: E402
import common_fixed_variables as cfv  # noqa: E402
import wildfire_model as wf  # noqa: E402
import serve_dashboard as sd  # noqa: E402
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config  # noqa: E402
from wildfire_model import WildFireModel  # noqa: E402

PRE_REV = "6281542"
NEW = "#193cff"
OUT = []


def P(s=""):
    OUT.append(str(s))
    print(s)
    sys.stdout.flush()


def old_cell_color():
    """_cell_color exactly as 6281542 defines it, compiled from git, not retyped."""
    src = subprocess.run(["git", "-C", REPO, "show", "%s:serve_dashboard.py" % PRE_REV],
                         capture_output=True, check=True).stdout.decode("utf-8")
    tree = ast.parse(src)
    want = {"_cell_color", "_veg_color", "_fire_color"}
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in want]
    if len(fns) != 3:
        raise SystemExit("expected 3 colour helpers at %s, found %d" % (PRE_REV, len(fns)))
    mod = ast.Module(body=fns, type_ignores=[])
    ast.fix_missing_locations(mod)
    ns = {"cfv": cfv}
    exec(compile(mod, "%s:serve_dashboard.py" % PRE_REV, "exec"), ns)
    body = ast.unparse(fns[[f.name for f in fns].index("_cell_color")])
    return ns["_cell_color"], body


def build(seed, wind, step, fireproof):
    cfv.BASE_STATION_FIREPROOF = fireproof
    params = {"NUM_AGENTS": 3, "NUM_VICTIMS": 5, "NUM_FIREFIGHTERS": 3,
              "WIND_DIRECTION": wind, "BATCH_SIZE": 300,
              "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": 2, "NUM_VICTIM_SEARCHERS": 1,
              "BASE_STATION_FIREPROOF": fireproof}
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    sd.SESSION["trails"] = {}
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        for i in range(step + 1):
            if i:
                model.step()
            frame = sd._capture_frame(model, i)
    return model, frame


def cleared_cells(model):
    out = set()
    for a in model.schedule.agents:
        if type(a).__name__ != "Fire" or getattr(a, "pos", None) is None:
            continue
        if (a.get_fuel() <= 0 and not a.is_burnt()
                and not getattr(a, "has_burned", False) and not a.is_burning()):
            out.add("%d,%d" % (int(a.pos[0]), int(a.pos[1])))
    return out


def arm(seed, wind, step, fireproof, old_fn):
    model, post = build(seed, wind, step, fireproof)
    real = sd._cell_color
    sd._cell_color = old_fn
    try:
        with contextlib.redirect_stdout(_io.StringIO()):
            pre = sd._capture_frame(model, step)
    finally:
        sd._cell_color = real
    pre.pop("nofuel", None)                     # the key 6281542 does not publish
    return model, pre, post


def compare(label, model, pre, post, expect_changes):
    P("")
    P("-" * 92)
    P("%s" % label)
    P("-" * 92)
    depot = set()
    st = getattr(model, "base_station", None)
    if st:
        depot = {"%d,%d" % (int(x), int(y)) for x, y in st["cells"]}
    cleared = cleared_cells(model)
    pc, oc = post["cells"], pre["cells"]
    assert set(pc) == set(oc), "the cell KEY set moved, which nothing here should do"
    changed = {k for k in pc if pc[k] != oc[k]}
    res = {
        "cells_total": len(pc),
        "depot_cells": len(depot),
        "cleared_cells": len(cleared),
        "changed_cells": len(changed),
        "changed_equals_cleared": changed == cleared,
        "changed_outside_depot": sorted(changed - depot),
        "pre_colours_of_changed": sorted({oc[k] for k in changed}),
        "post_colours_of_changed": sorted({pc[k] for k in changed}),
        "nofuel_len": len(post.get("nofuel") or []),
        "nofuel_equals_cleared": set(post.get("nofuel") or []) == cleared,
        "other_keys_equal": sorted(k for k in set(pre) | set(post)
                                   if k not in ("cells", "nofuel") and pre.get(k) != post.get(k)),
    }
    P("  cells in the payload            %d" % res["cells_total"])
    P("  depot cells (from the model)    %d" % res["depot_cells"])
    P("  CLEARED cells (fuel 0, never burned, not burning, not burnt)  %d" % res["cleared_cells"])
    P("  cells whose colour CHANGED      %d" % res["changed_cells"])
    P("  changed set == cleared set      %s" % res["changed_equals_cleared"])
    P("  changed cells outside a depot   %s" % (res["changed_outside_depot"] or "NONE"))
    P("  their colour BEFORE             %s" % res["pre_colours_of_changed"])
    P("  their colour AFTER              %s" % res["post_colours_of_changed"])
    P("  fr.nofuel length                %d   == cleared set: %s"
      % (res["nofuel_len"], res["nofuel_equals_cleared"]))
    P("  every OTHER payload key equal   %s"
      % ("yes" if not res["other_keys_equal"] else "NO: %s" % res["other_keys_equal"]))
    ok = True
    if expect_changes:
        ok &= res["changed_equals_cleared"] and res["cleared_cells"] > 0
        ok &= res["pre_colours_of_changed"] == [cfv.VEGETATION_COLORS[0]]
        ok &= res["post_colours_of_changed"] == [NEW]
        ok &= res["nofuel_equals_cleared"]
    else:
        ok &= res["changed_cells"] == 0 and res["cleared_cells"] == 0 and res["nofuel_len"] == 0
    ok &= not res["other_keys_equal"]
    res["pass"] = bool(ok)
    P("  %s" % ("PASS" if ok else "FAIL"))
    return res


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 101
    wind = sys.argv[2] if len(sys.argv) > 2 else "east"
    step = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    old_fn, body = old_cell_color()
    P("=" * 92)
    P("PAYLOAD PROOF OF THE DISPLAY CHANGE  -  outputs/_dfp_payload.py")
    P("=" * 92)
    P("  seed %d  wind %s  step %d   PRE = %s, its _cell_color compiled from git:"
      % (seed, wind, step, PRE_REV))
    for ln in body.splitlines():
        P("    | %s" % ln)
    P("  VEGETATION_COLORS[0] = %s  and  FIRE_COLORS[0] = %s  (the collision being removed)"
      % (cfv.VEGETATION_COLORS[0], cfv.FIRE_COLORS[0]))
    P("  new colour = %s" % NEW)

    m1, pre1, post1 = arm(seed, wind, step, 1, old_fn)
    r1 = compare("ARM ON  (BASE_STATION_FIREPROOF = 1)", m1, pre1, post1, True)
    m0, pre0, post0 = arm(seed, wind, step, 0, old_fn)
    r0 = compare("NEGATIVE CONTROL (BASE_STATION_FIREPROOF = 0) - nothing may change",
                 m0, pre0, post0, False)

    P("")
    P("  OVERALL %s" % ("PASS" if r1["pass"] and r0["pass"] else "FAIL"))
    out = {"pre_rev": PRE_REV, "seed": seed, "wind": wind, "step": step,
           "new_colour": NEW, "on": r1, "off": r0,
           "pass": bool(r1["pass"] and r0["pass"])}
    json.dump(out, open(os.path.join(BASE, "_dfp_payload.json"), "w"), indent=1, sort_keys=True)
    with open(os.path.join(BASE, "_dfp_payload.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(OUT) + "\n")
    return 0 if out["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
