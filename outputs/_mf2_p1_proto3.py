"""fix2 Part 1 (item 3): in-process PROTOTYPES of the wind fix, evaluated with the T7/T8 tests'
own helpers and assertions. NO SOURCE EDIT - every variant is a monkeypatch in this process.
A prototype validates the RULE, not a later transcription (see the memory note); Part 3 re-runs
the real tests on the real code.

usage: _mf2_p1_proto3.py <variant> [steps]
variants:
  stock        HEAD as is (+ a gate trace)
  ycommit      wind-aware y-commit only (N/S: commit toward the DOWNWIND half until the downwind
               strip is reached, then upwind; E/W: disjoint camping bands, no preference)
  range6       VICTIM_SEARCHER_HAZARD_RETREAT_RANGE = 6 only (retreat when fire/smoke <= 6 cells)
  ycommit+range6
  ycommit+approach  y-commit + the gate retreats only when the chosen move brings the searcher
               closer to a strict hazard that is within 6 cells (else the chosen direction stands)
Prints, per wind pair, the four checks of _assert_trajectory_or_region_diverged and whether each
test would PASS, plus the gate's replacement count for the searcher.
"""
from __future__ import annotations

import collections
import importlib.util
import os
import sys

REPO = r"E:\Projects\SAS"
sys.path.insert(0, REPO)
os.environ.setdefault("MPLBACKEND", "Agg")

import common_fixed_variables as cfv  # noqa: E402
import src_extension.adaptation.local_adaptation_generator as lag  # noqa: E402
import src_extension.execution.uav_executor as ux  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "twtr", os.path.join(REPO, "tests", "test_wind_aware_trajectory_regression.py"))
T = importlib.util.module_from_spec(spec)
sys.modules["twtr"] = T
spec.loader.exec_module(T)

GATE = collections.Counter()


def install_ycommit():
    orig_update = lag._update_coverage_y_commit

    def strip_marks(ws, agent_y, y_min, y_max):
        if agent_y is None:
            return
        if float(agent_y) >= y_max - lag.COVERAGE_Y_COMMIT_PENETRATE_MARGIN:
            ws["north_strip_done"] = True
        if float(agent_y) <= y_min + lag.COVERAGE_Y_COMMIT_PENETRATE_MARGIN:
            ws["south_strip_done"] = True

    def update(wind_state, y_min, y_max, agent_y=None):
        if lag._active_lane_axis(wind_state) == "y":
            return orig_update(wind_state, y_min, y_max, agent_y)
        strip_marks(wind_state, agent_y, y_min, y_max)
        commit = wind_state.get("coverage_y_commit")
        if commit in ("north", "south"):
            if agent_y is not None and lag._coverage_y_commit_penetrated(str(commit), float(agent_y), y_min, y_max):
                wind_state["coverage_y_commit"] = None
            return
        lower = lag._coverage_y_lower_camping(wind_state, y_min, y_max)
        upper = lag._coverage_y_upper_camping(wind_state, y_min, y_max)
        if not (lower or upper):
            return
        wind = str(wind_state.get("last_wind_direction") or "").strip().lower()
        if wind in ("north", "south"):
            down = wind  # north wind spreads fire toward +y (north); south toward -y
            up = "south" if down == "north" else "north"
            if not wind_state.get("%s_strip_done" % down):
                wind_state["coverage_y_commit"] = down
            elif not wind_state.get("%s_strip_done" % up):
                wind_state["coverage_y_commit"] = up
            else:
                recent = [int(v) for v in (wind_state.get("recent_y_positions") or [])][-lag.COVERAGE_Y_SWEEP_MIN_STEPS:]
                lower_max, upper_min = lag._grid_y_half_split(y_min, y_max)
                if recent and max(recent) <= lower_max:
                    wind_state["coverage_y_commit"] = "north"
                elif recent and min(recent) >= upper_min:
                    wind_state["coverage_y_commit"] = "south"
            return
        # E/W (or unknown) wind: disjoint halves - a searcher straddling the midline is not camping
        recent = [int(v) for v in (wind_state.get("recent_y_positions") or [])][-lag.COVERAGE_Y_SWEEP_MIN_STEPS:]
        if len(recent) < lag.COVERAGE_Y_SWEEP_MIN_STEPS:
            return
        lower_max, upper_min = lag._grid_y_half_split(y_min, y_max)
        if max(recent) <= lower_max:
            wind_state["coverage_y_commit"] = "north"
        elif min(recent) >= upper_min:
            wind_state["coverage_y_commit"] = "south"

    lag._update_coverage_y_commit = update


def install_gate_trace():
    ogate = ux.UAVExecutor._apply_victim_searcher_hazard_gate

    def gate(self, agent, chosen_dir, action):
        r = ogate(self, agent, chosen_dir, action)
        GATE["calls"] += 1
        if r[0] != chosen_dir:
            GATE["replaced"] += 1
        return r

    ux.UAVExecutor._apply_victim_searcher_hazard_gate = gate


def install_approach_gate(k=6):
    ogate = ux.UAVExecutor._apply_victim_searcher_hazard_gate

    def gate(self, agent, chosen_dir, action):
        pos = getattr(agent, "pos", None)
        if pos is not None:
            here = (int(pos[0]), int(pos[1]))
            nxt = self._next_cell_for_direction(agent, chosen_dir)
            if (self._strict_victim_hazard_level(here) <= 0 and nxt is not None
                    and self._strict_victim_hazard_level(nxt) <= 0
                    and not self._victim_wind_blocked_direction(agent, chosen_dir)
                    and self._strict_path_lookahead_safe(agent, chosen_dir)):
                d_here = self._min_strict_hazard_distance(here)
                d_next = self._min_strict_hazard_distance(nxt)
                if d_here > k or d_next >= d_here:
                    return chosen_dir, action  # not approaching a near hazard: keep the target
        return ogate(self, agent, chosen_dir, action)

    ux.UAVExecutor._apply_victim_searcher_hazard_gate = gate


def install_pathnear(k=6):
    """3b's second half: the near-field rule also covers the gate-bypassing pathfinding route
    (_attempt_pathfinding_toward_target - the pocket escape toward the grid midpoint and the
    retarget fallback): within k of a strict hazard, a routed move that brings the searcher
    closer to it is replaced by the gate's retreat."""
    oroute = ux.UAVExecutor._attempt_pathfinding_toward_target

    def route(self, agent, target, **kw):
        routed = oroute(self, agent, target, **kw)
        if routed is None:
            return None
        d, lab = routed
        pos = getattr(agent, "pos", None)
        if pos is not None:
            here = (int(pos[0]), int(pos[1]))
            nxt = self._next_cell_for_direction(agent, d)
            dh = self._min_strict_hazard_distance(here)
            if nxt is not None and dh <= k and self._min_strict_hazard_distance(nxt) < dh:
                retreat = self._retreat_to_safe_interior_direction(agent)
                if retreat is not None:
                    return retreat, lab
        return d, lab

    ux.UAVExecutor._attempt_pathfinding_toward_target = route


def main():
    variant = sys.argv[1] if len(sys.argv) > 1 else "stock"
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    cfv.BASE_STATION_MODE = 0  # the tests' _pin_centre_spawn
    parts = set(variant.split("+"))
    if "ycommit" in parts:
        install_ycommit()
    for part in parts:
        if part.startswith("range"):  # rangeK: the existing K semantics of the gate
            cfv.VICTIM_SEARCHER_HAZARD_RETREAT_RANGE = int(part[len("range"):])
    if "approach" in parts:
        install_approach_gate(6)
    if "pathnear" in parts:
        install_pathnear(6)
    install_gate_trace()
    tr = {}
    for wind in ("north", "south", "east", "west"):
        GATE.clear()
        tr[wind] = T._run_wind_simulation(wind, steps=steps, seed=T.DEFAULT_SEED)
        t = tr[wind]
        print("%-6s pos@mid %s final %s final_target %s wind_aware_actions %d gate %d/%d replaced targets[:6] %s" % (
            wind, t.positions[max(1, len(t.positions) // 2) - 1], t.final_position, t.final_target,
            t.wind_aware_actions, GATE["replaced"], GATE["calls"], list(dict.fromkeys(t.wind_planning_targets))[:6]))
    for a, b, name in (("north", "south", "T7 N/S"), ("east", "west", "T8 E/W")):
        A, B = tr[a], tr[b]
        ok = True
        why = []
        try:
            T._assert_wind_aware_behavior(A)
            T._assert_wind_aware_behavior(B)
        except AssertionError as exc:
            ok = False
            why.append("wind-aware: %s" % exc)
        sa, sb = set(A.wind_planning_targets), set(B.wind_planning_targets)
        c1 = bool(sa or sb)
        c2 = (not (sa and sb)) or sa != sb
        c3 = A.final_target is None or B.final_target is None or A.final_target != B.final_target
        mid = max(1, len(A.positions) // 2) - 1
        c4 = (A.final_position != B.final_position or A.positions[mid] != B.positions[mid]
              or A.final_quadrant != B.final_quadrant)
        ok = ok and c1 and c2 and c3 and c4
        print("%s [%s]: targets exist %s, target sets differ %s, final targets differ %s (%s vs %s), "
              "trajectory/region diverged %s -> %s %s" % (
                  name, variant, c1, c2, c3, A.final_target, B.final_target, c4,
                  "PASS" if ok else "FAIL", "; ".join(why)))


if __name__ == "__main__":
    main()
