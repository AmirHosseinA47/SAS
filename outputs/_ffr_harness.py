"""Feature 1 (firefighter rescue absence) measurement harness.

Mirrors evaluate_scenarios._run_seed EXACTLY - seeding order, apply_scenario_config,
model.debug_log = False, stdout redirected, per-step get_dashboard_state() polling
until the terminal step is found - so every metric it reports is comparable
seed-for-seed with the stock harness. On top of that it layers READ-ONLY
observers: each wrapper calls the original and returns its result unchanged,
draws nothing from any RNG, and mutates no simulation state.

It runs against ANY checkout via --repo (inserted at sys.path[0] before the
first simulation import), so the same file measures 1511ada and the feature
source with identical code.

Recorded per run:
  - eval        : serve_dashboard._build_evaluation, exactly as evaluate_scenarios
  - fire_digests: sha256 of (burning, burnt, fuel) of every Fire agent after
                  every step. The fire RNG stream is independent of the rescue
                  subsystem ONLY WHILE NO FIREFIGHTER WRITES FUEL: then a
                  seed-matched feature run must reproduce these digests step for
                  step, and the first differing step localises an unintended
                  perturbation. Since the ungated round (FF_FIREFIGHT_* shipped
                  E1 F1 K1 G0) idle firefighters write from step 1 and rescue
                  dispatch decides where they stand, and a write re-rolls the
                  fire's single random stream (firemech2_report.txt section 3) -
                  so at the shipped default a rescue-side change is EXPECTED to
                  change the digests. Digest identity localises a perturbation
                  again with --set FF_FIREFIGHT_EXTINGUISH=0 --set
                  FF_FIREFIGHT_FIREBREAK=0, or under FM2P_CRN=1 with
                  _fm2_probe_harness.py.
  - ff_steps    : per-step (pos, status, assigned, exiting, dead) of every
                  firefighter -> idle-on-edge share, absence windows, gaps
  - completions : rescue completions (Firefighter.advance flips rescue_completed)
  - recycles    : _recycle_firefighter_after_exit calls (landing cell, boundary?)
  - assigns / unassigns / unreachable marks (apply_physical_rescue_command)
  - planner     : every select_rescue_assignment decision with the pool sizes
  - absence_log : the feature's own removal/return log when present (getattr)

usage:
  _ffr_harness.py --repo <checkout> --wind east --roles half --seed 101
                  --steps 240 --out outputs/_ffr_<tag>_east_half_101.json
                  [--tag base] [--set KEY=VALUE ...]

--set KEY=VALUE adds an extra apply_scenario_config parameter (int/float/bool
parsed), e.g. --set FF_RESCUE_ABSENCE_MAX_STEPS=0 for a feature-off control.
Nothing is passed unless asked, so a bare invocation runs the tree's SHIPPED
defaults. Since the dcD flip (2026-09-14) that means BASE_STATION_MODE 3 with two
depots, and with the default --roles half and --scenario D a bare run is exactly the
drhD / d4D configuration; a mode-0 run needs --set BASE_STATION_MODE=0. Of the
base-station configuration the JSON records only what was passed with --set (in
params and extra_params), not the effective defaults or the commit. After the fact,
base_station (None vs a depot dict) separates mode 0 from mode >= 1; rtb_log shows
mode >= 2 only once a return has triggered (not before step ~151 on 50x50), and a
released_step shows mode 3. Since the ungated round a bare run ALSO has ungated
firefighting (FF_FIREFIGHT_* E1 F1 K1 G0), and fireproof depots since 6668368, so it
is no longer the drhD / d4D configuration; the firefighting-off pin is --set
FF_FIREFIGHT_EXTINGUISH=0 --set FF_FIREFIGHT_FIREBREAK=0. The firefight_log /
firefight_counters block in the JSON is what shows, after the fact, that a unit
engaged (outputs/ungated_runner_register.txt).
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io as _io
import json
import os
import random
import sys
import time


def _parse_value(raw: str):
    text = str(raw).strip()
    low = text.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("none", "null"):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="checkout to import the simulation from")
    ap.add_argument("--wind", default="east", choices=["north", "south", "east", "west"])
    ap.add_argument("--roles", default="half", choices=["half", "default"])
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--dim-hook", default="none", choices=["none", "deny", "record"],
                    help="dimension round: deny = HEIGHT/WIDTH reads raise (control arm); "
                         "record = every read attributed to its caller")
    ap.add_argument("--dim-observe", action="store_true",
                    help="dimension round: wrap the boundary helpers and their consumers "
                         "with a per-call counterfactual (needs --dim-hook record)")
    ap.add_argument("--dim-pin", default="",
                    help="dimension round: comma-separated callers of _grid_dimension "
                         "forced back to None (one-site-live ablation arms)")
    ap.add_argument("--dim-dead", default="",
                    help="interior-hazard round: comma-separated CONSUMER functions inside "
                         "which _distance_from_boundary returns 0.0 and _position_at_boundary "
                         "False (one accidental component replayed at a time)")
    ap.add_argument("--uav-actions", action="store_true",
                    help="interior-hazard round: record per step, per UAV, the executed action "
                         "label and the strict hazard state of its cell (read-only)")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")

    import agents as am  # noqa: E402
    import common_fixed_variables as cfv  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    from src_extension.adaptation.local_adaptation_generator import apply_scenario_config  # noqa: E402
    from wildfire_model import WildFireModel  # noqa: E402
    from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation, _resolve_role_count_params  # noqa: E402

    # sanity: the imported modules must come from --repo
    for mod in (am, cfv, wf):
        path = os.path.abspath(getattr(mod, "__file__", ""))
        if not path.lower().startswith(repo.lower()):
            print("IMPORT MISMATCH: %s from %s, expected under %s" % (mod.__name__, path, repo), file=sys.stderr)
            return 3

    # ---- params: identical to evaluate_scenarios._scenario_params at CLI defaults
    preset = BUILTIN_SCENARIOS.get(args.scenario, {})
    num_agents = int(preset.get("NUM_AGENTS", 3))
    if args.roles == "half":
        ft, vs = _resolve_role_count_params(num_agents, 2, 2)
    else:
        ft, vs = _resolve_role_count_params(num_agents, None, None)
    params = {
        "NUM_AGENTS": num_agents,
        "NUM_VICTIMS": int(preset.get("NUM_VICTIMS", 5)),
        "NUM_FIREFIGHTERS": int(preset.get("NUM_FIREFIGHTERS", 3)),
        "WIND_DIRECTION": str(args.wind),
        "BATCH_SIZE": 300,
        "FIRE_SPREAD_MULTIPLIER": 0.75,
        "PROBABILITY_MAP": False,
        "NUM_FIRE_TRACKERS": ft,
        "NUM_VICTIM_SEARCHERS": vs,
    }
    extra: dict = {}
    for item in args.set:
        if "=" not in item:
            print("bad --set %r" % item, file=sys.stderr)
            return 2
        k, v = item.split("=", 1)
        extra[k.strip()] = _parse_value(v)
    params.update(extra)

    H = int(getattr(cfv, "HEIGHT", 50))
    W = int(getattr(cfv, "WIDTH", 50))

    def _cell(pos):
        return None if pos is None else [int(pos[0]), int(pos[1])]

    def _on_boundary(pos) -> bool:
        if pos is None:
            return False
        x, y = int(pos[0]), int(pos[1])
        return x == 0 or x == H - 1 or y == 0 or y == W - 1

    def _step_of(model) -> int:
        return int(getattr(model, "evaluation_timesteps_counter", 0) or 0)

    # ---- dimension round: attribute hook / pins / observers, all read-only ----
    # Installed on the classes before the model is built. A bare invocation
    # (no --dim-* option) imports nothing and changes nothing.
    dim = None
    dim_pins = [p.strip() for p in str(args.dim_pin or "").split(",") if p.strip()]
    dim_dead = [p.strip() for p in str(args.dim_dead or "").split(",") if p.strip()]
    if args.dim_hook != "none" or args.dim_observe or dim_pins or dim_dead:
        import _dim_hooks  # noqa: E402  (outputs/ is the script directory, on sys.path)
        from src_extension.execution.uav_executor import UAVExecutor  # noqa: E402
        dim = _dim_hooks.install(WildFireModel, UAVExecutor, hook=args.dim_hook,
                                 observe=args.dim_observe, pins=dim_pins, step_of=_step_of,
                                 dead=dim_dead)

    def _vid(model, agent) -> str:
        if agent is None:
            return ""
        try:
            return str(model._victim_id_from_agent(agent) or "")
        except Exception:
            return str(getattr(agent, "victim_id", "") or "")

    REC = {
        "completions": [],
        "recycles": [],
        "assigns": [],
        "unassigns": [],
        "unreachable_marks": [],
        "planner": [],
        # feature 2 observers
        "exit_starts": [],
        "retargets": [],
        # lateral round: every hold decision, recorded at the decision itself
        "victim_holds": [],
        "victim_hold_flag_mismatch": 0,
    }

    # ---- lateral round: DIRECT hook on the victim's hold decision -------------
    # `Victim._note_flee_hold` is called by `_flee_approaching_fire` at the exact
    # point it decides to hold, with the reason and the source's own flags. The
    # wrap records each call together with the geometry the decision was made on,
    # recomputed from the same grid and fire state through the victim's own pure
    # helpers (no RNG, no mutation), and cross-checks the recomputed lateral
    # verdict against the flag the source passed. `best_lateral` is the cell the
    # source's own R5 tie-break would pick if R6 admitted equal-distance moves.
    # Absent on checkouts before feature 2, in which case nothing is wrapped.
    if hasattr(am.Victim, "_note_flee_hold"):
        _orig_hold = am.Victim._note_flee_hold
        _offsets = tuple(getattr(am, "ORTHOGONAL_OFFSETS", ((1, 0), (-1, 0), (0, 1), (0, -1))))

        def _obs_hold(self, reason, **flags):
            result = _orig_hold(self, reason, **flags)
            try:
                rec = {
                    "step": _step_of(self.model),
                    "victim": _vid(self.model, self),
                    "reason": str(reason),
                    "flags": {str(k): bool(v) for k, v in flags.items()},
                }
                pos = getattr(self, "pos", None)
                if pos is not None:
                    cell = (int(pos[0]), int(pos[1]))
                    fire_cells = self._burning_cells()
                    d0 = int(self._min_fire_distance(cell, fire_cells))
                    anchor = (
                        getattr(self, "leash_anchor", None)
                        or getattr(self, "spawn_cell", None)
                        or cell
                    )
                    leash = int(am.victim_flee_max_displacement())
                    grid = self.model.grid
                    cands = []
                    n_oob = n_burning = n_leash_blocked = 0
                    for order, (ox, oy) in enumerate(_offsets):
                        n = (cell[0] + ox, cell[1] + oy)
                        if grid.out_of_bounds(n):
                            n_oob += 1
                            continue
                        if n in fire_cells:
                            n_burning += 1
                            continue
                        fa = abs(n[0] - anchor[0]) + abs(n[1] - anchor[1])
                        if fa > leash:
                            n_leash_blocked += 1
                            continue
                        cands.append({
                            "cell": [n[0], n[1]],
                            "dist": int(self._min_fire_distance(n, fire_cells)),
                            "from_anchor": int(fa),
                            "order": order,
                            "has_exit": bool(self._cell_has_onward_exit(n, cell, fire_cells)),
                        })
                    with_exit = [c for c in cands if c["has_exit"]]
                    pool = with_exit if with_exit else cands
                    lateral = [c for c in pool if c["dist"] == d0]
                    best_lat = min(lateral, key=lambda c: (c["from_anchor"], c["order"])) if lateral else None
                    rec.update({
                        "cell": [cell[0], cell[1]],
                        "dist_before": d0,
                        "anchor": [int(anchor[0]), int(anchor[1])],
                        "leash": leash,
                        "spawn": _cell(getattr(self, "spawn_cell", None)),
                        "last_lateral_from": _cell(getattr(self, "_lateral_last_cell", None)),
                        "n_fire_cells": len(fire_cells),
                        "n_oob": n_oob,
                        "n_burning_nb": n_burning,
                        "n_leash_blocked": n_leash_blocked,
                        "candidates": cands,
                        "n_lateral": len(lateral),
                        "best_lateral": None if best_lat is None else best_lat["cell"],
                        "recomputed_lateral_available": bool(lateral),
                    })
                    if str(reason) == "no_improvement" and bool(lateral) != bool(flags.get("lateral_available", False)):
                        REC["victim_hold_flag_mismatch"] += 1
                REC["victim_holds"].append(rec)
            except Exception as exc:  # an observer must never take the run down
                REC["victim_holds"].append({"step": _step_of(self.model), "reason": str(reason), "error": repr(exc)})
            return result

        am.Victim._note_flee_hold = _obs_hold

    # ---- observers (call original, return unchanged) --------------------------
    _orig_recycle = WildFireModel._recycle_firefighter_after_exit

    def _obs_recycle(self, ff_marker):
        before = _cell(getattr(ff_marker, "pos", None))
        result = _orig_recycle(self, ff_marker)
        after = _cell(getattr(ff_marker, "pos", None))
        REC["recycles"].append({
            "step": _step_of(self),
            "ff": str(getattr(ff_marker, "unit_id", "") or ""),
            "pos_before": before,
            "pos_after": after,
            "on_boundary": _on_boundary(after),
        })
        return result

    WildFireModel._recycle_firefighter_after_exit = _obs_recycle

    _orig_advance = am.Firefighter.advance

    def _obs_advance(self):
        before = bool(getattr(self, "rescue_completed", False))
        before_exiting = bool(getattr(self, "exiting", False))
        before_target = _cell(getattr(self, "target_pos", None))
        result = _orig_advance(self)
        after = bool(getattr(self, "rescue_completed", False))
        # feature 2: the exiting False->True transition is the moment a rescue
        # is declared. Record whether the unit was actually STANDING ON the
        # victim then. A False here is a rescue completed with no contact -
        # exactly the failure mode the live re-target exists to prevent.
        if bool(getattr(self, "exiting", False)) and not before_exiting:
            rv = getattr(self, "rescued_victim", None)
            ff_cell = _cell(getattr(self, "pos", None))
            v_cell = _cell(getattr(rv, "pos", None)) if rv is not None else None
            REC["exit_starts"].append({
                "step": _step_of(self.model),
                "ff": str(getattr(self, "unit_id", "") or ""),
                "victim": _vid(self.model, rv),
                "ff_pos": ff_cell,
                "victim_pos": v_cell,
                "contact": bool(ff_cell is not None and v_cell is not None and ff_cell == v_cell),
            })
        after_target = _cell(getattr(self, "target_pos", None))
        if before_target is not None and after_target is not None and before_target != after_target:
            REC["retargets"].append({
                "step": _step_of(self.model),
                "ff": str(getattr(self, "unit_id", "") or ""),
                "victim": _vid(self.model, getattr(self, "rescued_victim", None)),
                "from": before_target,
                "to": after_target,
            })
        if after and not before:
            REC["completions"].append({
                "step": _step_of(self.model),
                "ff": str(getattr(self, "unit_id", "") or ""),
                "pos": _cell(getattr(self, "pos", None)),
                "victim": _vid(self.model, getattr(self, "rescued_victim", None)),
                "exit_target": _cell(getattr(self, "exit_target", None)),
            })
        return result

    am.Firefighter.advance = _obs_advance

    _orig_apply = WildFireModel.apply_physical_rescue_command

    def _obs_apply(self, cmd):
        ok = _orig_apply(self, cmd)
        action = str(getattr(cmd, "action", "") or "").strip().lower()
        rec = {
            "step": _step_of(self),
            "ff": str(getattr(cmd, "firefighter_id", "") or ""),
            "vid": str(getattr(cmd, "victim_id", "") or ""),
            "reason": str(getattr(cmd, "reason", "") or ""),
            "ok": bool(ok),
        }
        if action == "assign":
            REC["assigns"].append(rec)
        elif action == "unassign":
            REC["unassigns"].append(rec)
        elif action == "mark_unreachable":
            REC["unreachable_marks"].append(rec)
        return ok

    WildFireModel.apply_physical_rescue_command = _obs_apply

    _orig_select = wf.select_rescue_assignment

    def _obs_select(snapshot, reason, *a, **k):
        decision = _orig_select(snapshot, reason, *a, **k)
        ffs = snapshot.get("firefighters", {}) if isinstance(snapshot, dict) else {}
        n_avail = n_absent = n_dead = 0
        for entry in ffs.values():
            if not isinstance(entry, dict):
                continue
            if entry.get("dead"):
                n_dead += 1
                continue
            if entry.get("available"):
                n_avail += 1
            if entry.get("position") is None:
                n_absent += 1
        if isinstance(decision, dict):
            action = str(decision.get("action", "") or "")
            vid = str(decision.get("victim_id", "") or "")
            ff = str(decision.get("firefighter_id", "") or "")
        else:
            action = str(getattr(decision, "rescue_action", "") or "")
            vid = str(getattr(decision, "victim_id", "") or "")
            ff = str(getattr(decision, "firefighter_id", "") or "")
        REC["planner"].append({
            "step": int(snapshot.get("step", 0) or 0) if isinstance(snapshot, dict) else -1,
            "reason": str(reason or ""),
            "action": action,
            "vid": vid,
            "ff": ff,
            "n_available": n_avail,
            "n_offgrid_alive": n_absent,
            "n_dead": n_dead,
        })
        return decision

    wf.select_rescue_assignment = _obs_select

    # ---- run: byte-for-byte the evaluate_scenarios._run_seed sequence ----------
    rng = random.Random(args.seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)

    fire_digests: list[str] = []
    ff_steps: list[list] = []
    ff_bind_steps: list[list] = []
    victim_steps: list[list] = []
    # dimension round: per-step UAV rows (id, cell, role, selected_dir) so the
    # first diverging UAV step of a seed-matched pair can be located exactly.
    uav_steps: list[list] = []
    uav_actions: list[list] = []
    # base-station round: per-step partition snapshot - the ordered searcher
    # roster with each searcher's lane, and the ordered tracker roster with each
    # tracker's sector bounds. A reshuffle is any step at which a UAV's tuple
    # differs from the previous step; "mid-traverse" is a reshuffle on a step
    # where that UAV still had an unreached target. Pure reads.
    partition_steps: list[dict] = []

    def _base_state(uav) -> str:
        """"" / returning / docked / charging.

        Every read is defensive because this harness runs against ANY checkout
        via --repo, including 16b2da8, where none of these attributes and no
        base_station_mode() exist. "docked" and "charging" are distinct: at
        BASE_STATION_MODE 2 a UAV parks with nothing recharging it, and calling
        that "charging" would hide the cost the return-only arm exists to show.
        """
        if not getattr(uav, "rtb_docked", False):
            return "returning" if getattr(uav, "rtb_active", False) else ""
        mode_fn = getattr(am, "base_station_mode", None)
        try:
            recharging = callable(mode_fn) and int(mode_fn()) >= 3
        except (TypeError, ValueError):
            recharging = False
        return "charging" if recharging else "docked"
    # feature 2: first step at which each cell was observed burning. Small
    # (<= one entry per grid cell) and it is what answers "did the victim step
    # into a cell that burned LATER".
    first_burn_step: dict = {}
    # lateral round: full burning history per cell as half-open step intervals
    # [start, end) - burning in the post-step observation of every step in the
    # range, `end` None if still burning at the horizon. A cell can hold several
    # intervals (scorched ground re-ignites). This is what a time-expanded
    # survivability computation needs; first_burn_step alone cannot say when a
    # cell became safe again.
    burn_intervals: dict = {}
    burn_open: dict = {}
    prev_burning: set = set()
    terminal_step = None
    step = 0
    t0 = time.perf_counter()
    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf):
        model = WildFireModel()
        model.debug_log = False
        if dim is not None:
            _dim_hooks.bind_model(model)
        for _ in range(args.steps):
            model.step()
            step += 1
            if terminal_step is None:
                panel = model.get_dashboard_state()
                mission = panel.get("mission_status", {}) or {}
                if mission.get("all_victims_terminal"):
                    terminal_step = step
            # --- observers only below this line
            parts = []
            burning_now: set = set()
            for a in model.schedule.agents:
                if type(a).__name__ == "Fire":
                    parts.append("%s:%d%d%s" % (a.unique_id, int(bool(a.burning)), int(bool(a.burnt)), a.fuel))
                    if a.burning:
                        pos = getattr(a, "pos", None)
                        if pos is not None:
                            key = "%d,%d" % (int(pos[0]), int(pos[1]))
                            burning_now.add(key)
                            if key not in first_burn_step:
                                first_burn_step[key] = step
            for key in burning_now - prev_burning:
                burn_open[key] = step
            for key in prev_burning - burning_now:
                burn_intervals.setdefault(key, []).append([burn_open.pop(key), step])
            prev_burning = burning_now
            fire_digests.append(hashlib.sha256("|".join(parts).encode()).hexdigest())
            row = []
            for ff_id, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
                row.append([
                    str(ff_id),
                    _cell(getattr(m, "pos", None)),
                    str(getattr(m, "status", "") or ""),
                    bool(getattr(m, "assigned", False)),
                    bool(getattr(m, "exiting", False)),
                    bool(getattr(m, "dead", False)),
                ])
            ff_steps.append(row)
            # phantom-rescue round: which victim each unit is bound to, plus the
            # dispatch predicate, per step. A separate key so the 6-field
            # ff_steps rows that the earlier analyzers unpack keep their shape.
            # _firefighter_available_for_dispatch is a pure predicate on marker
            # state - no RNG, no mutation.
            brow = []
            for ff_id, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
                brow.append([
                    str(ff_id),
                    _vid(model, getattr(m, "rescued_victim", None)),
                    bool(model._firefighter_available_for_dispatch(m)),
                    bool(getattr(m, "rescue_completed", False)),
                    bool(getattr(m, "off_grid", False)),
                ])
            ff_bind_steps.append(brow)
            vrow = []
            for vid, m in (getattr(model, "victim_marker_agents", {}) or {}).items():
                vrow.append([
                    str(vid),
                    _cell(getattr(m, "pos", None)),
                    str(getattr(m, "status", "") or ""),
                ])
            victim_steps.append(vrow)
            urow = []
            for a in model.schedule.agents:
                if type(a).__name__ != "UAV":
                    continue
                sd = getattr(a, "selected_dir", None)
                # base-station round: battery and docked state. The harness
                # recorded NO battery at all before this, so a recharge arm had no
                # observable. base_state is "" / "returning" / "charging". Adding
                # these changes the recorded JSON shape, so every arm of the round
                # - the baseline checkout arm included - must be produced by this
                # same frozen harness or the arms are not comparable.
                urow.append([
                    str(a.unique_id),
                    _cell(getattr(a, "pos", None)),
                    str(getattr(a, "current_role", "") or ""),
                    (int(sd) if sd is not None else None),
                    round(float(getattr(a, "battery_level", 0.0) or 0.0), 4),
                    _base_state(a),
                ])
            uav_steps.append(urow)
            try:
                from src_extension.adaptation.local_adaptation_generator import (
                    resolve_victim_searcher_uav_ids as _rs_ids,
                    _searcher_crosswind_lane as _rs_lane,
                )
                _sids = list(_rs_ids(model) or [])
                _wind = str(getattr(cfv, "WIND_DIRECTION", "east"))
                _lanes = {}
                for _sid in _sids:
                    try:
                        _lanes[_sid] = _rs_lane(model, _sid, _wind, 0, int(model.HEIGHT) - 1,
                                                0, int(model.WIDTH) - 1)
                    except Exception:
                        _lanes[_sid] = None
                _sectors = {
                    str(k): (dict(v) if isinstance(v, dict) else None)
                    for k, v in (getattr(model, "_uav_sector_assignments", {}) or {}).items()
                }
                _targets = {}
                for a in model.schedule.agents:
                    if type(a).__name__ != "UAV":
                        continue
                    uid = str(a.unique_id)
                    try:
                        _targets[uid] = _cell(model._resolve_uav_path_context_target(uid))
                    except Exception:
                        _targets[uid] = None
                partition_steps.append({
                    "searchers": _sids,
                    "lanes": {k: (list(v) if v is not None else None) for k, v in _lanes.items()},
                    "sectors": _sectors,
                    "targets": _targets,
                })
            except Exception:
                partition_steps.append({})
            # interior-hazard round: the executed action label per UAV (from the
            # dispatcher's result of this step) and the strict hazard state of the
            # cell the UAV now stands on - burning (the executor's level 2), smoke
            # (visibility smoke_obscured_cells, the scenario helper's definition,
            # and the Fire agent's own active smoke, the executor's level 1) and
            # the manhattan distance to the nearest burning cell. Pure reads.
            if args.uav_actions:
                exec_r = getattr(model, "latest_execution_result", None) or {}
                local = exec_r.get("local", {}) if isinstance(exec_r, dict) else {}
                ures = (local.get("uav_results") or {}) if isinstance(local, dict) else {}
                vis = getattr(model, "visibility_model", None)
                vis_smoke = getattr(vis, "smoke_obscured_cells", None) if vis is not None else None
                vis_smoke = set(tuple(int(v) for v in c[:2]) for c in vis_smoke) if isinstance(vis_smoke, (set, list, tuple)) else set()
                burning_cells = set(tuple(int(v) for v in k.split(",")) for k in burning_now)
                arow = []
                for a in model.schedule.agents:
                    if type(a).__name__ != "UAV":
                        continue
                    uid = str(a.unique_id)
                    r = ures.get(uid) if isinstance(ures, dict) else None
                    act = str(r.get("action") or "") if isinstance(r, dict) else ""
                    pos = getattr(a, "pos", None)
                    cell = (int(pos[0]), int(pos[1])) if pos is not None else None
                    burning = int(cell in burning_cells) if cell else 0
                    vsm = int(cell in vis_smoke) if cell else 0
                    asm = 0
                    if cell is not None:
                        for occ in model.grid.get_cell_list_contents([cell]):
                            if type(occ).__name__ != "Fire":
                                continue
                            smoke = getattr(occ, "smoke", None)
                            is_active = getattr(smoke, "is_smoke_active", None) if smoke is not None else None
                            if (callable(is_active) and is_active()) or bool(getattr(smoke, "smoke", False)):
                                asm = 1
                                break
                    fdist = 99
                    if cell is not None and burning_cells:
                        fdist = min(abs(cell[0] - fx) + abs(cell[1] - fy) for fx, fy in burning_cells)
                    arow.append([uid, act, burning, vsm, asm, int(fdist)])
                uav_actions.append(arow)
        evaluation = _build_evaluation(model, terminal_step, step, params)
    wall = time.perf_counter() - t0
    for key, start in sorted(burn_open.items()):
        burn_intervals.setdefault(key, []).append([start, None])
    stdout_text = buf.getvalue()

    # ---- derived: idle-on-edge, absence windows from ff_steps ------------------
    idle_steps = idle_edge_steps = absent_steps = 0
    for row in ff_steps:
        for _ff, pos, status, assigned, exiting, dead in row:
            if dead:
                continue
            if pos is None:
                absent_steps += 1
                continue
            if status == "available" and not assigned and not exiting:
                idle_steps += 1
                if _on_boundary(pos):
                    idle_edge_steps += 1

    # gap from each recycle to that unit's next successful assign (baseline: how
    # soon a recycled unit is actually needed again)
    gaps = []
    for r in REC["recycles"]:
        nxt = [a["step"] for a in REC["assigns"] if a["ok"] and a["ff"] == r["ff"] and a["step"] >= r["step"]]
        gaps.append({"ff": r["ff"], "recycle_step": r["step"], "next_assign_step": (min(nxt) if nxt else None),
                     "gap": (min(nxt) - r["step"]) if nxt else None})

    event_counts: dict[str, int] = {}
    failed_reasons: list = []
    for e in list(getattr(model, "_rescue_event_log", []) or []):
        et = str(e.get("event_type", "") or "")
        event_counts[et] = event_counts.get(et, 0) + 1
        if et == "rescue_failed":
            failed_reasons.append({"step": e.get("step"), "vid": e.get("victim_id"), "reason": e.get("reason"),
                                   "meta": {k: str(v) for k, v in (e.get("metadata") or {}).items()}})

    out = {
        "tag": args.tag,
        "repo": repo,
        "scenario": args.scenario,
        "wind": args.wind,
        "roles": args.roles,
        "seed": args.seed,
        "steps": args.steps,
        "params": {k: v for k, v in params.items()},
        "extra_params": extra,
        "eval": evaluation,
        "terminal_step": terminal_step,
        "wall_s": round(wall, 1),
        "fire_final_digest": fire_digests[-1] if fire_digests else None,
        "fire_digests": fire_digests,
        "ff_steps": ff_steps,
        "ff_bind_steps": ff_bind_steps,
        "victim_steps": victim_steps,
        "uav_steps": uav_steps,
        "uav_actions": (uav_actions if args.uav_actions else None),
        "dim": (_dim_hooks.export() if dim is not None else None),
        "victim_spawns": {
            str(vid): _cell(getattr(m, "spawn_cell", None))
            for vid, m in (getattr(model, "victim_marker_agents", {}) or {}).items()
        },
        "victim_flee_log": list(getattr(model, "_victim_flee_log", []) or []),
        "first_burn_step": first_burn_step,
        # end state of the ground: `burnt` is fuel-exhausted and permanently
        # safe; `has_burned and not burnt` is the "scorched" state the burnt-cell
        # investigation found re-ignites. A fleeing victim can now stand on
        # either, which a static victim never could.
        "fire_ground_final": {
            "%d,%d" % (int(a.pos[0]), int(a.pos[1])): [
                int(bool(getattr(a, "has_burned", False))),
                int(bool(getattr(a, "burnt", False))),
                int(bool(getattr(a, "burning", False))),
            ]
            for a in model.schedule.agents
            if type(a).__name__ == "Fire" and getattr(a, "pos", None) is not None
        },
        "victim_flee_moves_total": int(getattr(model, "victim_flee_moves_total", 0) or 0),
        "victim_flee_hold_counts": dict(getattr(model, "victim_flee_hold_counts", {}) or {}),
        # lateral round
        "victim_holds": REC["victim_holds"],
        "victim_hold_flag_mismatch": int(REC["victim_hold_flag_mismatch"]),
        "burn_intervals": burn_intervals,
        "victim_lateral_log": list(getattr(model, "_victim_lateral_log", []) or []),
        "victim_lateral_counts": dict(getattr(model, "victim_lateral_counts", {}) or {}),
        "victim_leash_anchors": {
            str(vid): _cell(getattr(m, "leash_anchor", None))
            for vid, m in (getattr(model, "victim_marker_agents", {}) or {}).items()
        },
        "victim_leash_reanchors": {
            str(vid): int(getattr(m, "leash_reanchors", 0) or 0)
            for vid, m in (getattr(model, "victim_marker_agents", {}) or {}).items()
        },
        "exit_starts": REC["exit_starts"],
        "retargets": REC["retargets"],
        "completions": REC["completions"],
        "recycles": REC["recycles"],
        "assigns": REC["assigns"],
        "unassigns": REC["unassigns"],
        "unreachable_marks": REC["unreachable_marks"],
        "planner": REC["planner"],
        "recycle_to_next_assign": gaps,
        "idle": {"idle_steps": idle_steps, "idle_edge_steps": idle_edge_steps,
                 "idle_edge_share": (round(idle_edge_steps / idle_steps, 4) if idle_steps else None),
                 "absent_steps": absent_steps},
        "absence_log": list(getattr(model, "_ff_absence_log", []) or []),
        "absence_counters": {
            "removals_total": getattr(model, "ff_absence_removals_total", None),
            "returns_total": getattr(model, "ff_absence_returns_total", None),
            "absent_now": sorted(list(getattr(model, "_absent_firefighters", {}) or {})) if isinstance(getattr(model, "_absent_firefighters", None), dict) else None,
        },
        "unreachable_escape_log": list(getattr(model, "_unreachable_escape_log", []) or []),
        "rescue_event_counts": event_counts,
        "rescue_failed": failed_reasons,
        "pending_removal_failures_total": int(getattr(model, "pending_removal_failures_total", 0) or 0),
        "leftover_pending": len(list(getattr(model, "_agents_pending_removal", []) or [])),
        # --- base-station round -------------------------------------------------
        # The depot geometry actually used, so an arm's spawn cells are recoverable
        # from its own output rather than re-derived.
        # Depot-cost round: the DEPOT SET, recorded inside this field rather than
        # as a new top-level one. base_station is None whenever BASE_STATION_MODE
        # is 0, so reshaping it cannot drift the kill-switch identity - a mode-0
        # arm records None either way. The scalar origin/size are kept as depot-0
        # aliases so the earlier analyzers still read what they expect.
        "base_station": (
            None if getattr(model, "base_station", None) is None else {
                "origin": list(model.base_station["origin"]),
                "size": int(model.base_station["size"]),
                "uav_berths": [list(c) for c in model.base_station["uav_berths"]],
                "firefighter_berths": [list(c) for c in model.base_station["firefighter_berths"]],
                "depots": [list(d["origin"])
                           for d in (model.base_station.get("depots") or ())],
                "uav_berths_by_depot": [
                    [list(c) for c in row]
                    for row in (model.base_station.get("uav_berths_by_depot") or ())
                ],
                "uav_home": list(model.base_station.get("uav_home") or ()),
                "firefighter_home": list(model.base_station.get("firefighter_home") or ()),
            }
        ),
        # ONE RECORD PER RETURN TRIP, per UAV: trigger step and level, how far the
        # UAV was, when it arrived (None = never arrived, i.e. stranded), which
        # cell it docked on, and when it was released. This is what "every return
        # must complete or be accounted for" is checked against.
        "rtb_log": {
            str(a.unique_id): list(getattr(a, "rtb_log", []) or [])
            for a in model.schedule.agents if type(a).__name__ == "UAV"
        },
        "rtb_counters": {
            str(a.unique_id): {
                "trips": int(getattr(a, "rtb_trips", 0) or 0),
                "cycles": int(getattr(a, "rtb_cycles", 0) or 0),
                "return_steps": int(getattr(a, "rtb_return_steps", 0) or 0),
                "charge_steps": int(getattr(a, "rtb_charge_steps", 0) or 0),
                "final_battery": round(float(getattr(a, "battery_level", 0.0) or 0.0), 4),
                "final_docked": bool(getattr(a, "rtb_docked", False)),
                "final_active": bool(getattr(a, "rtb_active", False)),
                "berth": _cell(getattr(a, "rtb_berth", None)),
            }
            for a in model.schedule.agents if type(a).__name__ == "UAV"
        },
        # Per-step searcher lane and tracker sector, so "did any partition change
        # because a UAV went charging" is a measurement rather than an assertion.
        "partition_steps": partition_steps,
        "stdout_sha256": hashlib.sha256(stdout_text.encode("utf-8", "replace")).hexdigest(),
        "stdout_lines": stdout_text.count("\n"),
    }
    # --- fire mechanic round 1 --------------------------------------------------
    # Added ONLY when the model carries the feature's own log, which it creates
    # lazily on the first firefighting step. A feature-off run, and any checkout
    # without the feature, therefore produces exactly the JSON shape it produced
    # before this block existed, so fmOFF / fmREF stay comparable field for field
    # with the dfD arm recorded by the previous harness. Pure reads.
    ff_log = getattr(model, "_firefight_log", None)
    if ff_log is not None:
        shadow = getattr(model, "_firefight_shadow", None)
        out["firefight_log"] = list(ff_log)
        out["firefight_counters"] = {
            "extinguished": int(getattr(model, "firefight_extinguished_total", 0) or 0),
            "cleared": int(getattr(model, "firefight_cleared_total", 0) or 0),
            "cleared_unburned": int(getattr(model, "firefight_cleared_unburned_total", 0) or 0),
        }
        out["firefight_shadow"] = (
            sorted([int(c[0]), int(c[1])] for c in shadow) if isinstance(shadow, set) else None
        )
        # fuel exhausted on a cell that never burned. NOT only a firebreak: since
        # BASE_STATION_FIREPROOF (6668368) every fuel-less depot cell counts here too,
        # up to 50 cells, and this block is emitted only in runs that created a
        # firefight log. Subtract the run's own depot cells before using it as a
        # firebreak count (outputs/ungated_part1.txt P8; _ug_analyze.py does).
        # Comment only - the recorded value is unchanged, so the instrument is too.
        out["fire_cleared_unburned_final"] = sum(
            1 for a in model.schedule.agents
            if type(a).__name__ == "Fire" and getattr(a, "pos", None) is not None
            and getattr(a, "fuel", 1) <= 0 and not getattr(a, "has_burned", False)
        )
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f)
    os.replace(tmp, args.out)
    with open(args.out[:-5] + ".stdout.txt" if args.out.endswith(".json") else args.out + ".stdout.txt",
              "w", encoding="utf-8") as f:
        f.write(stdout_text)
    ev = evaluation
    print("%s %s/%s seed=%d rescued=%d dead=%d unreachable=%d never_detected=%d ff_deaths=%d terminal=%s "
          "completions=%d recycles=%d removals=%s returns=%s wall=%.0fs"
          % (args.tag, args.wind, args.roles, args.seed, ev["rescued"], ev["dead"], ev["unreachable"],
             ev.get("never_detected", 0), ev["firefighter_deaths"], ev["terminal_step"],
             len(REC["completions"]), len(REC["recycles"]),
             out["absence_counters"]["removals_total"], out["absence_counters"]["returns_total"], wall))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
