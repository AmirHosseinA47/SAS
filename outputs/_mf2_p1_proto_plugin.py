"""fix2 Part 1 (item 3): the wind-fix PROTOTYPE as a pytest plugin, to run existing test files
against the proposed rule without touching the source. NO SOURCE EDIT.

usage (from the repo root):
  set PYTHONPATH=outputs;  pytest -p _mf2_p1_proto_plugin <test files>
Env MF2_PROTO = "ycommit+near6" (default) | "ycommit" | "near6" | "none".
  ycommit  the wind-aware y-commit of outputs/_mf2_p1_proto3.py (install_ycommit)
  near6    the proposed SEARCHER gate switch: at the always-retreat setting (range >= 99) the
           searcher hazard gate uses range 6 - it retreats only when a strict fire/smoke cell
           is within 6 cells (the existing K semantics of the same gate) - AND the gate-bypassing
           pathfinding route (_attempt_pathfinding_toward_target) gets the same near-field rule:
           within 6 cells a routed move that approaches a strict hazard is replaced by the retreat
"""
from __future__ import annotations

import os

import src_extension.adaptation.local_adaptation_generator as lag
import src_extension.execution.uav_executor as ux

MODE = set((os.environ.get("MF2_PROTO") or "ycommit+near6").split("+"))


def _install_ycommit():
    orig_update = lag._update_coverage_y_commit

    def update(wind_state, y_min, y_max, agent_y=None):
        if lag._active_lane_axis(wind_state) == "y":
            return orig_update(wind_state, y_min, y_max, agent_y)
        if agent_y is not None:
            if float(agent_y) >= y_max - lag.COVERAGE_Y_COMMIT_PENETRATE_MARGIN:
                wind_state["north_strip_done"] = True
            if float(agent_y) <= y_min + lag.COVERAGE_Y_COMMIT_PENETRATE_MARGIN:
                wind_state["south_strip_done"] = True
        commit = wind_state.get("coverage_y_commit")
        if commit in ("north", "south"):
            if agent_y is not None and lag._coverage_y_commit_penetrated(str(commit), float(agent_y), y_min, y_max):
                wind_state["coverage_y_commit"] = None
            return
        if not (lag._coverage_y_lower_camping(wind_state, y_min, y_max)
                or lag._coverage_y_upper_camping(wind_state, y_min, y_max)):
            return
        wind = str(wind_state.get("last_wind_direction") or "").strip().lower()
        recent = [int(v) for v in (wind_state.get("recent_y_positions") or [])][-lag.COVERAGE_Y_SWEEP_MIN_STEPS:]
        lower_max, upper_min = lag._grid_y_half_split(y_min, y_max)
        if wind in ("north", "south"):
            down = wind
            up = "south" if down == "north" else "north"
            if not wind_state.get("%s_strip_done" % down):
                wind_state["coverage_y_commit"] = down
                return
            if not wind_state.get("%s_strip_done" % up):
                wind_state["coverage_y_commit"] = up
                return
        if len(recent) < lag.COVERAGE_Y_SWEEP_MIN_STEPS:
            return
        if max(recent) <= lower_max:
            wind_state["coverage_y_commit"] = "north"
        elif min(recent) >= upper_min:
            wind_state["coverage_y_commit"] = "south"

    lag._update_coverage_y_commit = update


def _install_near6():
    orig = ux.UAVExecutor._hazard_retreat_range

    def rng(self):
        r = orig(self)
        return 6 if r >= 99 else r

    ux.UAVExecutor._hazard_retreat_range = rng

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
            if nxt is not None and dh <= 6 and self._min_strict_hazard_distance(nxt) < dh:
                retreat = self._retreat_to_safe_interior_direction(agent)
                if retreat is not None:
                    return retreat, lab
        return d, lab

    ux.UAVExecutor._attempt_pathfinding_toward_target = route


if "ycommit" in MODE:
    _install_ycommit()
if "near6" in MODE:
    _install_near6()


def pytest_report_header(config):
    return "MF2 PROTOTYPE ACTIVE: %s" % sorted(MODE)
