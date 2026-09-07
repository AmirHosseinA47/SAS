"""Dimension-round instrumentation for outputs/_ffr_harness.py.

Three independent pieces, all installed on CLASSES before the model is built and
all READ-ONLY with respect to the simulation (they call the original, return its
result unchanged, draw from no RNG, and mutate no simulation state):

  hook="deny"    WildFireModel.HEIGHT / .WIDTH become class-level properties whose
                 setter stores the value (so reset()'s assignment succeeds) and whose
                 getter RAISES AttributeError. Every `getattr(model, "HEIGHT", 50)`
                 then returns 50 and UAVExecutor._grid_dimension returns None -
                 exactly the read path of 8520706. This is the control arm.
  hook="record"  Same properties, but the getter returns the stored value and
                 records the reader (file, function, line) per read. When the
                 module-level DENY flag is set the getter raises instead - used by
                 the consumer observers' counterfactual evaluation below.
  observe=True   Wraps the two boundary helpers (call counts and non-dead results
                 per caller) and the consumer decisions that depend on them. Each
                 consumer call is evaluated twice: the real call, whose result is
                 returned, and a counterfactual call with DENY set, whose result is
                 compared and discarded. Nested wrapped calls made while DENY is
                 set pass straight through, so nothing is double-counted.
  pins=[names]   UAVExecutor._grid_dimension returns None when called from any of
                 the named functions, reproducing the dead path for exactly those
                 sites. Used by the one-site-live ablation arms.

Validated pattern: outputs/_bat_probe.py (class-level property hooks with caller
attribution) from the battery round.
"""
from __future__ import annotations

import collections
import os
import sys
from typing import Any

DENY = [False]
STATE: dict = {"mode": "none", "step_of": None}

REC: dict = {
    "reads": collections.Counter(),        # (name, file, reader) -> count
    "first_read_step": {},                 # (name, file, reader) -> step
    "writes": 0,
    "deny_raises": 0,
    "pin_hits": collections.Counter(),     # caller -> count
    "helper_calls": collections.Counter(), # (helper, caller) -> calls
    "helper_live": collections.Counter(),  # (helper, caller) -> calls whose result != dead value
    "helper_live_by_step": collections.Counter(),  # (helper, step) -> live results
    "helper_live_first": {},               # (helper, caller) -> [step, uav, x, y, result]
    "c3_execute_near": 0,                  # reads from `execute` where P True or D < 2
    "clamp_targets": [],                   # [step, uav, tx, ty] for _safe_search_target called from _execute_search_mode
    "consumers": [],                       # per call: [step, uav, role, x, y, consumer, real, cf, changed]
    "consumer_summary": collections.Counter(),  # (consumer, "calls"|"changed") -> n
    "first_changed": None,                 # [step, uav, role, consumer, real, cf]
}


def _step() -> int:
    fn = STATE.get("step_of")
    model = STATE.get("model")
    if fn is None or model is None:
        return -1
    try:
        return int(fn(model))
    except Exception:
        return -1


def _cell(pos) -> tuple:
    try:
        return (int(pos[0]), int(pos[1]))
    except Exception:
        return (None, None)


def _norm(v):
    if isinstance(v, tuple):
        return tuple(_norm(x) for x in v)
    if isinstance(v, float):
        return round(v, 6)
    return v


# ---------------------------------------------------------------------------
# 1. attribute hook
# ---------------------------------------------------------------------------
def _install_attr_hook(WildFireModel, mode: str) -> None:
    for name in ("HEIGHT", "WIDTH"):
        slot = "_dimhook_" + name

        def make(name=name, slot=slot):
            def getter(self):
                if mode == "deny" or DENY[0]:
                    REC["deny_raises"] += 1
                    raise AttributeError(name)
                f = sys._getframe(1)
                reader = f.f_code.co_name
                line = f.f_lineno
                fname = os.path.basename(f.f_code.co_filename)
                if reader == "_grid_dimension" and f.f_back is not None:
                    reader = "%s/%s" % (f.f_back.f_code.co_name, reader)
                    line = f.f_back.f_lineno
                    fname = os.path.basename(f.f_back.f_code.co_filename)
                key = (name, fname, "%s:%d" % (reader, line))
                REC["reads"][key] += 1
                if key not in REC["first_read_step"]:
                    REC["first_read_step"][key] = _step()
                return self.__dict__[slot]

            def setter(self, value):
                self.__dict__[slot] = value
                REC["writes"] += 1

            return property(getter, setter)

        setattr(WildFireModel, name, make())


# ---------------------------------------------------------------------------
# 2. pins (ablation arms)
# ---------------------------------------------------------------------------
def _install_pins(UAVExecutor, pins: set) -> None:
    orig = UAVExecutor._grid_dimension  # plain function (staticmethod unwrapped on class access)

    def wrapped(model, attribute_names):
        caller = sys._getframe(1).f_code.co_name
        if caller in pins:
            REC["pin_hits"][caller] += 1
            return None
        return orig(model, attribute_names)

    UAVExecutor._grid_dimension = staticmethod(wrapped)


# ---------------------------------------------------------------------------
# 2b. dead reads per CONSUMER (interior-hazard round)
# ---------------------------------------------------------------------------
def _install_dead(UAVExecutor, consumers: set) -> None:
    """Force the two boundary helpers back to their 8520706 dead values (D = 0.0,
    P = False) when called DIRECTLY from any of the named consumer functions,
    and leave every other caller live. Replays one component of the accidental
    always-on behaviour at a time on top of the fixed tree:
      _apply_victim_searcher_hazard_gate     C7 gate always on + C8 scoring dead
      _retreat_to_safe_interior_direction    C6 retreat scored by hazard only
      _victim_near_edge_escape_required      C5 force_interior_retarget always
      execute                                C3 near_boundary always (holds -> retarget)
    Not combined with observe=True (both wrap the helpers)."""
    orig_P = UAVExecutor._position_at_boundary
    orig_D = UAVExecutor._distance_from_boundary

    def dead_P(self, agent):
        if sys._getframe(1).f_code.co_name in consumers:
            REC["pin_hits"]["P<-" + sys._getframe(1).f_code.co_name] += 1
            return False
        return orig_P(self, agent)

    def dead_D(self, x, y, model):
        if sys._getframe(1).f_code.co_name in consumers:
            REC["pin_hits"]["D<-" + sys._getframe(1).f_code.co_name] += 1
            return 0.0
        return orig_D(self, x, y, model)

    UAVExecutor._position_at_boundary = dead_P
    UAVExecutor._distance_from_boundary = dead_D


# ---------------------------------------------------------------------------
# 3. observers
# ---------------------------------------------------------------------------
def _install_observers(UAVExecutor) -> None:
    # --- the two helpers: counts per caller, live (non-dead) results -------
    orig_P = UAVExecutor._position_at_boundary
    orig_D = UAVExecutor._distance_from_boundary
    orig_T = UAVExecutor._safe_search_target

    def obs_P(self, agent):
        if DENY[0]:
            return orig_P(self, agent)
        result = orig_P(self, agent)
        caller = sys._getframe(1).f_code.co_name
        key = ("P", caller)
        REC["helper_calls"][key] += 1
        if result:
            step = _step()
            REC["helper_live"][key] += 1
            REC["helper_live_by_step"][("P", step)] += 1
            if key not in REC["helper_live_first"]:
                x, y = _cell(getattr(agent, "pos", None))
                REC["helper_live_first"][key] = [step, str(self.uav_id), x, y, True]
            if caller == "execute":
                REC["c3_execute_near"] += 1
        return result

    def obs_D(self, x, y, model):
        if DENY[0]:
            return orig_D(self, x, y, model)
        result = orig_D(self, x, y, model)
        caller = sys._getframe(1).f_code.co_name
        key = ("D", caller)
        REC["helper_calls"][key] += 1
        if result != 0.0:
            step = _step()
            REC["helper_live"][key] += 1
            REC["helper_live_by_step"][("D", step)] += 1
            if key not in REC["helper_live_first"]:
                REC["helper_live_first"][key] = [step, str(self.uav_id), int(x), int(y), float(result)]
            if caller == "execute" and result < 2.0:
                REC["c3_execute_near"] += 1
        return result

    def obs_T(self, agent, target):
        result = orig_T(self, agent, target)
        if not DENY[0] and sys._getframe(1).f_code.co_name == "_execute_search_mode" and target is not None:
            REC["clamp_targets"].append([_step(), str(self.uav_id), float(target[0]), float(target[1])])
        return result

    UAVExecutor._position_at_boundary = obs_P
    UAVExecutor._distance_from_boundary = obs_D
    UAVExecutor._safe_search_target = obs_T

    # --- consumers: real result returned, counterfactual (reads denied) compared
    def wrap_consumer(name: str, agent_index: int):
        orig = getattr(UAVExecutor, name)

        def w(self, *a, **k):
            if DENY[0]:
                return orig(self, *a, **k)
            real = orig(self, *a, **k)
            DENY[0] = True
            try:
                cf = orig(self, *a, **k)
            finally:
                DENY[0] = False
            changed = _norm(real) != _norm(cf)
            step = _step()
            agent = a[agent_index] if len(a) > agent_index else k.get("agent")
            x, y = _cell(getattr(agent, "pos", None))
            try:
                role = str(self._read_uav_role() or "")
            except Exception:
                role = ""
            uid = str(self.uav_id)
            REC["consumer_summary"][(name, "calls")] += 1
            if changed:
                REC["consumer_summary"][(name, "changed")] += 1
                # the non-agent positional args (e.g. chosen_dir/action for the
                # hazard gate, proposed_dir for the final safety check) so a
                # changed decision can be read as "override removed" vs "added"
                extra = [(_norm(v) if isinstance(v, (int, float, str, tuple)) else str(type(v).__name__)) for v in a[agent_index + 1:]]
                REC["consumers"].append([step, uid, role, x, y, name, _norm(real), _norm(cf), True, extra])
                if REC["first_changed"] is None:
                    REC["first_changed"] = [step, uid, role, name, _norm(real), _norm(cf)]
            return real

        setattr(UAVExecutor, name, w)

    for name in (
        "_hold_needs_escape",                 # C1  (agent, current_dir) -> bool
        "_hold_escape_direction",             # C2  (agent) -> int | None
        "_safe_direction_or_escape",          # C4  (agent, proposed_dir) -> (dir, changed)
        "_victim_near_edge_escape_required",  # C5  (agent, model) -> bool
        "_retreat_to_safe_interior_direction",  # C6 (agent) -> int | None
        "_apply_victim_searcher_hazard_gate",  # C7/C8 (agent, chosen_dir, action) -> (dir, action)
    ):
        wrap_consumer(name, 0)


# ---------------------------------------------------------------------------
def install(WildFireModel, UAVExecutor, *, hook: str = "none", observe: bool = False,
            pins=(), step_of=None, dead=()) -> dict:
    STATE["mode"] = hook
    STATE["step_of"] = step_of
    if hook in ("deny", "record"):
        _install_attr_hook(WildFireModel, hook)
    pins = set(p for p in pins if p)
    if pins:
        _install_pins(UAVExecutor, pins)
    dead = set(d for d in dead if d)
    if dead:
        if observe:
            raise SystemExit("--dim-dead cannot be combined with --dim-observe (both wrap the helpers)")
        _install_dead(UAVExecutor, dead)
    if observe:
        if hook != "record":
            raise SystemExit("--dim-observe requires --dim-hook record (the counterfactual needs the deny toggle)")
        _install_observers(UAVExecutor)
    STATE["pins"] = sorted(pins)
    STATE["dead"] = sorted(dead)
    STATE["observe"] = bool(observe)
    return STATE


def bind_model(model) -> None:
    STATE["model"] = model


def export() -> dict:
    def kv(counter, keyfmt):
        return [[*keyfmt(k), int(v)] for k, v in sorted(counter.items(), key=lambda kv: (str(kv[0]), ))]
    return {
        "mode": STATE.get("mode"),
        "observe": STATE.get("observe", False),
        "pins": STATE.get("pins", []),
        "dead": STATE.get("dead", []),
        "writes": REC["writes"],
        "deny_raises": REC["deny_raises"],
        "reads": kv(REC["reads"], lambda k: list(k)),
        "first_read_step": [[*k, v] for k, v in sorted(REC["first_read_step"].items(), key=lambda kv: str(kv[0]))],
        "pin_hits": dict(REC["pin_hits"]),
        "helper_calls": kv(REC["helper_calls"], lambda k: list(k)),
        "helper_live": kv(REC["helper_live"], lambda k: list(k)),
        "helper_live_by_step": [[k[0], int(k[1]), int(v)] for k, v in sorted(REC["helper_live_by_step"].items())],
        "helper_live_first": {"%s|%s" % k: v for k, v in REC["helper_live_first"].items()},
        "c3_execute_near": REC["c3_execute_near"],
        "clamp_targets": REC["clamp_targets"],
        "consumer_summary": {"%s|%s" % k: int(v) for k, v in REC["consumer_summary"].items()},
        "consumers_changed": REC["consumers"],
        "first_changed": REC["first_changed"],
    }
