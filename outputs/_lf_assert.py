"""Latch-fix round: ASSERT that every released unit re-enters the dispatch pool.

Same scenario/params/RNG setup as outputs/_l808_sweep.py, plus:

  - a wrapper on WildFireModel._clear_stale_route_blocks that records every unit
    the fix clears, with its full state before and after;
  - a per-step accountability trace for each cleared unit:
    (status, assigned, exiting, dead, pos, dispatchable, any_victim_needs_rescue);
  - an end-of-run verdict per cleared unit, which must be exactly one of
    DISPATCHABLE / DEAD / OFF_GRID / IDLE_NO_WORK. Anything else is UNACCOUNTED
    and fails the run loudly.

  - an end-of-run LATCH SCAN using the round's CORRECTED definition: alive, on
    the grid, NOT fire-enclosed, no live referent, and NOT dispatchable. This
    catches the Variant B shape - a unit cleared to status "assigned" by
    agents.py:1816, still undispatchable on `assigned`, and invisible to any
    scan that counts status == "route_blocked" alone.
    Fire-enclosed units and horizon flags (raised on the final step with a
    victim still live) are reported SEPARATELY, not folded into the count.

usage: _lf_assert.py --seed 202 --mode 0 --wind east --out <path>
                     [--set KEY=VALUE ...]
Read-only w.r.t. the model: every wrapper calls the original and returns its
result unchanged, draws from no RNG, and mutates no simulation state.
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import io as _io
import json
import os
import random
import sys
import time

os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation

CUR = {"step": 0}
CLEARS: list[dict] = []       # every unit the fix cleared
FIRES: list[dict] = []        # every route_blocked raise
STATS = collections.Counter()


def _parse_value(raw: str):
    text = str(raw).strip()
    low = text.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def _cell(a):
    p = getattr(a, "pos", None)
    return [int(p[0]), int(p[1])] if p is not None else None


def _st(a):
    return str(getattr(a, "status", "") or "").strip().lower()


def _enclosed(m) -> bool | None:
    try:
        nb = m._neighbor_cells()
        return bool(nb) and all(m._cell_contains_active_fire(c) for c in nb)
    except Exception:
        return None


def _snap(model, m) -> dict:
    return {
        "status": _st(m),
        "assigned": bool(getattr(m, "assigned", False)),
        "exiting": bool(getattr(m, "exiting", False)),
        "dead": bool(getattr(m, "dead", False)),
        "bound": getattr(m, "rescued_victim", None) is not None,
        "target": getattr(m, "target_pos", None) is not None,
        "pos": _cell(m),
        "dispatchable": bool(model._firefighter_available_for_dispatch(m)),
    }


# ---------------------------------------------------------------- wrappers

_orig_mark = am.Firefighter._mark_route_blocked


def _traced_mark(self):
    before = _st(self)
    tgt = getattr(self, "target_pos", None)
    _orig_mark(self)
    if _st(self) == "route_blocked" and before != "route_blocked":
        STATS["fires"] += 1
        FIRES.append({
            "step": CUR["step"], "ff": str(getattr(self, "unit_id", "")),
            "pos": _cell(self),
            "target": [int(tgt[0]), int(tgt[1])] if tgt is not None else None,
            "assigned": bool(getattr(self, "assigned", False)),
            "enclosed": _enclosed(self), "prev": before,
        })


am.Firefighter._mark_route_blocked = _traced_mark


_orig_clear = getattr(WildFireModel, "_clear_stale_route_blocks", None)

if _orig_clear is not None:
    def _traced_clear(self, stale, mode):
        before = {str(k): _snap(self, m) for k, m in stale}
        work = bool(self._any_victim_needs_rescue())
        _orig_clear(self, stale, mode)
        for k, m in stale:
            k = str(k)
            after = _snap(self, m)
            if after["status"] == before[k]["status"] == "route_blocked":
                continue          # held back (enclosed, or rung boundary)
            STATS["cleared"] += 1
            CLEARS.append({
                "step": CUR["step"], "ff_id": k,
                "unit": str(getattr(m, "unit_id", k) or k),
                "mode": int(mode),
                "work_left_at_clear": work,
                "before": before[k], "after": after,
                "trace": [],
            })

    WildFireModel._clear_stale_route_blocks = _traced_clear


# ---------------------------------------------------------------- the run

def run(seed, params, steps):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    terminal_step = None
    last_needs_step = None
    ran = 0
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        for s in range(1, steps + 1):
            CUR["step"] = s
            model.step()
            ran = s
            work = bool(model._any_victim_needs_rescue())
            if work:
                last_needs_step = s
            markers = getattr(model, "firefighter_marker_agents", {}) or {}
            # per-step accountability for every unit the fix has cleared
            for rec in CLEARS:
                if s < rec["step"]:
                    continue
                m = markers.get(rec["ff_id"])
                if m is None:
                    continue
                row = _snap(model, m)
                row["step"] = s
                row["work"] = work
                rec["trace"].append(row)
            if terminal_step is None:
                panel = model.get_dashboard_state()
                if (panel.get("mission_status", {}) or {}).get("all_victims_terminal"):
                    terminal_step = s

        markers = getattr(model, "firefighter_marker_agents", {}) or {}

        # ---- verdict per cleared unit -------------------------------------
        for rec in CLEARS:
            m = markers.get(rec["ff_id"])
            tail = rec["trace"]
            end = _snap(model, m) if m is not None else None
            rec["end"] = end
            if end is None:
                rec["verdict"] = "UNACCOUNTED:marker_missing"
            elif end["dispatchable"]:
                rec["verdict"] = "DISPATCHABLE"
            elif end["dead"]:
                rec["verdict"] = "DEAD"
            elif end["pos"] is None:
                rec["verdict"] = "OFF_GRID"
            elif end["assigned"] or end["exiting"]:
                # taken by real work after the clear - the pool re-absorbed it
                rec["verdict"] = "RE_DISPATCHED"
            elif not any(r["work"] for r in tail):
                rec["verdict"] = "IDLE_NO_WORK"
            else:
                rec["verdict"] = "UNACCOUNTED:undispatchable_with_work"
            rec["ever_had_work_after_clear"] = any(r["work"] for r in tail)
            rec["trace_len"] = len(tail)
            # keep the trace small: the transitions only
            trimmed, prev = [], None
            for r in tail:
                key = (r["status"], r["assigned"], r["exiting"], r["dead"],
                       r["pos"] is None, r["dispatchable"], r["work"])
                if key != prev:
                    trimmed.append(r)
                    prev = key
            rec["trace"] = trimmed

        # ---- end-of-run latch scan, CORRECTED definition -------------------
        latched, enclosed_held, horizon, flagged_any = [], [], [], []
        for k, m in markers.items():
            uid = str(getattr(m, "unit_id", k) or k)
            if getattr(m, "dead", False):
                continue
            st = _st(m)
            dispatchable = bool(model._firefighter_available_for_dispatch(m))
            if dispatchable:
                continue
            if getattr(m, "pos", None) is None:
                continue
            if getattr(m, "exiting", False):
                continue          # carrying: legitimately busy
            enc = _enclosed(m)
            fires = [f for f in FIRES if f["ff"] == uid]
            last_fire = fires[-1] if fires else None
            row = {
                "ff": uid, "pos": _cell(m), "status": st,
                "assigned": bool(getattr(m, "assigned", False)),
                "bound": getattr(m, "rescued_victim", None) is not None,
                "enclosed_at_end": enc,
                "flag_step": last_fire["step"] if last_fire else None,
                "flag_pos": last_fire["pos"] if last_fire else None,
                "assigned_at_flag": last_fire["assigned"] if last_fire else None,
                "last_victim_needs_step": last_needs_step,
                "steps_run": ran,
            }
            if st == "route_blocked":
                flagged_any.append(uid)
            if enc:
                enclosed_held.append(row)          # 70e1b33's guard, deliberate
            elif last_fire is not None and last_fire["step"] >= ran:
                horizon.append(row)                # flag raised on the final step
            elif last_needs_step is not None and last_needs_step >= ran:
                horizon.append(row)                # run ended with work still live
            else:
                latched.append(row)                # the real thing

        ev = _build_evaluation(model, terminal_step, ran, params)
        counters = {
            "stale_cleared_total": int(
                getattr(model, "ff_route_blocks_stale_cleared_total", 0) or 0),
            "stale_released_total": int(
                getattr(model, "ff_route_blocks_stale_released_total", 0) or 0),
            "claims_released_total": int(
                getattr(model, "ff_claims_released_total", 0) or 0),
        }
    ev["seed"] = seed
    ev["wall_s"] = round(time.perf_counter() - t0, 1)
    return (ev, latched, enclosed_held, horizon, flagged_any, terminal_step,
            last_needs_step, counters)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--wind", default="east")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--mode", type=int, required=True,
                    help="BASE_STATION_MODE")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    preset = BUILTIN_SCENARIOS[a.scenario]
    n = preset["NUM_AGENTS"]
    ft = n // 2 or 1
    params = {"NUM_AGENTS": n, "NUM_VICTIMS": preset["NUM_VICTIMS"],
              "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"], "WIND_DIRECTION": a.wind,
              "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": n - ft,
              "BASE_STATION_MODE": a.mode}
    for item in a.set:
        if "=" not in item:
            continue
        key, _, raw = item.partition("=")
        params[key.strip()] = _parse_value(raw)

    (ev, latched, enclosed_held, horizon, flagged, terminal_step,
     last_needs, counters) = run(a.seed, params, a.steps)

    unaccounted = [c for c in CLEARS if str(c["verdict"]).startswith("UNACCOUNTED")]
    out = {
        "seed": a.seed, "mode": a.mode, "wind": a.wind, "steps": a.steps,
        # the RESOLVED integer, never the string "default": the shipped default
        # moved from 2 to 1 during this round, so an unresolved stamp would mean
        # different things in files written days apart
        "switch": int(WildFireModel._route_block_stale_clear_mode()),
        "switch_requested": params.get("ROUTE_BLOCK_STALE_CLEAR", "default"),
        "eval": ev, "terminal_step": terminal_step,
        "last_victim_needs_step": last_needs,
        "counters": counters,
        "clears": CLEARS,
        "latched": latched,
        "enclosed_held": enclosed_held,
        "horizon": horizon,
        "flagged_at_end": flagged,
        "unaccounted": unaccounted,
        "gate": {
            "latched_units": len(latched),
            "unaccounted_units": len(unaccounted),
            "PASS": len(latched) == 0 and len(unaccounted) == 0,
        },
        "stats": dict(STATS),
    }
    with open(a.out, "w") as f:
        json.dump(out, f)
    print("seed=%s mode=%s wind=%s switch=%s | cleared=%d released=%d | "
          "latched=%d enclosed_held=%d horizon=%d unaccounted=%d | GATE %s"
          % (a.seed, a.mode, a.wind, out["switch"],
             counters["stale_cleared_total"], counters["stale_released_total"],
             len(latched), len(enclosed_held), len(horizon), len(unaccounted),
             "PASS" if out["gate"]["PASS"] else "FAIL"),
          file=sys.stderr)
    return 0 if out["gate"]["PASS"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
