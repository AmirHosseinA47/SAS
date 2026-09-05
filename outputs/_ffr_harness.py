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
                  subsystem, so a seed-matched feature run must reproduce these
                  digests step for step; the first differing step, if any,
                  localises an unintended perturbation.
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
Nothing is passed unless asked, so a bare invocation is the stock harness.
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
    }

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
    victim_steps: list[list] = []
    # feature 2: first step at which each cell was observed burning. Small
    # (<= one entry per grid cell) and it is what answers "did the victim step
    # into a cell that burned LATER".
    first_burn_step: dict = {}
    terminal_step = None
    step = 0
    t0 = time.perf_counter()
    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf):
        model = WildFireModel()
        model.debug_log = False
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
            for a in model.schedule.agents:
                if type(a).__name__ == "Fire":
                    parts.append("%s:%d%d%s" % (a.unique_id, int(bool(a.burning)), int(bool(a.burnt)), a.fuel))
                    if a.burning:
                        pos = getattr(a, "pos", None)
                        if pos is not None:
                            key = "%d,%d" % (int(pos[0]), int(pos[1]))
                            if key not in first_burn_step:
                                first_burn_step[key] = step
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
            vrow = []
            for vid, m in (getattr(model, "victim_marker_agents", {}) or {}).items():
                vrow.append([
                    str(vid),
                    _cell(getattr(m, "pos", None)),
                    str(getattr(m, "status", "") or ""),
                ])
            victim_steps.append(vrow)
        evaluation = _build_evaluation(model, terminal_step, step, params)
    wall = time.perf_counter() - t0
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
        "victim_steps": victim_steps,
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
        "stdout_sha256": hashlib.sha256(stdout_text.encode("utf-8", "replace")).hexdigest(),
        "stdout_lines": stdout_text.count("\n"),
    }
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
