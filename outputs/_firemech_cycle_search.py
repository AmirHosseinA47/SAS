"""Fire mechanic round 1: search static fire geometries for zero-work movement cycles. Read-only.

Adapted from the Part 2 adversarial review's reproduction (which found the
approach<->retreat 2-cycle). Grows a real fire for TICKS fire steps from SEED,
freezes it, then places one idle firefighter on every STRIDE-th cell whose
manhattan distance to fire is 4..7 and calls the real Firefighter.advance() 40
times with the fire held static. The last 20 steps of each trial are classified:
  working  - at least one extinguish/clear action
  cycle p  - no work and positions repeat with period p in 2..4
  still    - no work and the unit holds one cell
  other    - no work, no short period (a walk)
Static fire is the worst case for a livelock: nothing external breaks it.

usage: _firemech_cycle_search.py ARM SEED TICKS STRIDE     ARM in F FS ES EFS DRY
"""
from __future__ import annotations

import collections
import contextlib
import io
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("MPLBACKEND", "Agg")

import agents  # noqa: E402
import common_fixed_variables as cfv  # noqa: E402
import wildfire_model as wf  # noqa: E402
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config  # noqa: E402
from wildfire_model import WildFireModel  # noqa: E402

CONFIGS = {
    "F": dict(firebreak=1),
    "FS": dict(firebreak=1, retreat_range=1),
    "ES": dict(extinguish=1, retreat_range=1),
    "EFS": dict(firebreak=1, extinguish=1, retreat_range=1),
    "DRY": dict(firebreak=1, extinguish=1, retreat_range=1, dry=1),
}


def cellof(a):
    return (int(a.pos[0]), int(a.pos[1]))


def main():
    arm, seed, ticks, stride = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    cfg = CONFIGS[arm]
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    agents.random = rng
    apply_scenario_config(
        cfv, wf,
        FF_FIREFIGHT_EXTINGUISH=cfg.get("extinguish", 0), FF_FIREFIGHT_FIREBREAK=cfg.get("firebreak", 0),
        FF_FIREFIGHT_ENGAGED_RETREAT_RANGE=cfg.get("retreat_range", 3), FF_FIREFIGHT_DRY_RUN=cfg.get("dry", 0))
    with contextlib.redirect_stdout(io.StringIO()):
        m = WildFireModel()
    m.debug_log = False
    fires = [a for a in m.schedule.agents if type(a) is agents.Fire]
    for _ in range(ticks):
        for a in fires:
            a.step()
        for a in fires:
            a.advance()
    snap = [(a, a.fuel, a.burning, a.burnt, a.has_burned, a.smoke.smoke) for a in fires]
    burning = {cellof(a) for a in fires if a.is_burning()}

    def restore():
        for a, fu, bu, bt, hb, sm in snap:
            a.fuel, a.burning, a.burnt, a.has_burned, a.smoke.smoke = fu, bu, bt, hb, sm
        if hasattr(m, "_firefight_shadow"):
            m._firefight_shadow = set()
        if hasattr(m, "_firefight_log"):
            m._firefight_log = []

    cands = []
    for x in range(50):
        for y in range(50):
            if (x * 50 + y) % stride or (x, y) in burning:
                continue
            if 4 <= min(abs(x - bx) + abs(y - by) for bx, by in burning) <= 7:
                cands.append((x, y))
    stats = collections.Counter()
    examples = {}
    t0 = time.time()
    for c in cands:
        restore()
        park = (0, 49) if c != (0, 49) else (49, 49)
        for oid, o in m.firefighter_marker_agents.items():
            if oid != "ff_unit_0":
                m.grid.move_agent(o, park)
        ff = m.firefighter_marker_agents["ff_unit_0"]
        m.grid.move_agent(ff, c)
        ff.dead = False
        ff.assigned = False
        ff.target_pos = None
        ff.rescued_victim = None
        ff.exiting = False
        ff.exit_target = None
        ff.rescue_completed = False
        ff.status = "available"
        ff._reset_idle_retreat_state()
        ff._firefight_suspended = False
        hist = []
        for _ in range(40):
            n0 = len(getattr(m, "_firefight_log", []) or [])
            ff.advance()
            lg = getattr(m, "_firefight_log", []) or []
            row = lg[-1] if len(lg) > n0 else {}
            hist.append((cellof(ff), row.get("action")))
        tail = hist[-20:]
        work = any(h[1] in ("extinguish", "clear") for h in tail)
        pos = [h[0] for h in tail]
        period = next((p for p in (1, 2, 3, 4) if all(pos[k] == pos[k + p] for k in range(len(pos) - p))), None)
        if work:
            key = "working"
        elif period is None:
            key = "other"
        elif period == 1:
            key = "still"
        else:
            key = "cycle%d" % period
            examples.setdefault(key, (c, tail[-6:]))
        stats[key] += 1
    n = len(cands)
    print("%s seed %d ticks %d trials %d secs %.0f | %s" % (
        arm, seed, ticks, n, time.time() - t0,
        "  ".join("%s %d" % (k, stats[k]) for k in ("working", "cycle2", "cycle3", "cycle4", "still", "other"))))
    for k, (c, t) in sorted(examples.items()):
        print("  EX %s start %s tail %s" % (k, c, t))


if __name__ == "__main__":
    main()
