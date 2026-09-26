"""Carrying-leg round, Part 2: THE SIDECAR - out of tree, pass-through, no source file is modified.

Spec: outputs/_cl_tooling_spec.txt section F (design outputs/carryleg_part1.txt 5.3).
Pattern: outputs/_fm2_probe_harness.py.

The harness records nothing that shows a carrying-leg branch ran (no tier, no movement
reason, no transition log; SERVED changes only internal streak state). This module wraps a
few attributes of the --repo checkout's modules with PASS-THROUGH observers, runs the
queue line's harness UNCHANGED in this same process via runpy, and afterwards writes ONE
extra file, <out-without-.json>.clobs.json. The harness JSON and its .stdout.txt are never
opened for writing.

Launchers (one per instrument):
    _cl_obs_stock.py -> outputs/_ffr_harness.py
    _cl_obs_crn.py   -> outputs/_fm2_probe_harness.py (which itself runs _ffr_harness.py)
Both take exactly the inner harness's command line, e.g.
    _cl_obs_stock.py --repo E:/Projects/SAS --wind east --roles half --seed 101
                     --steps 360 --out outputs/_ffr_clC_east_half_101.json --tag clC
                     --uav-actions --set BATCH_SIZE=360

EVERY WRAP IS A PASS-THROUGH: it calls the original with the same arguments and returns
its result unchanged (exceptions from the original propagate untouched), draws no random
number, prints nothing (the model's stdout is hashed into the harness JSON), and creates
no attribute on any model or agent object. Its bookkeeping lives in this module (STATE and
_MODELS). A bookkeeping failure never reaches the run: it is recorded, and at the end the
launcher exits 5 WITHOUT writing the sidecar (loud, never a silent partial record).

WHAT G1 PROVES, AND WHAT IT DOES NOT. G1 runs only arms with every switch off (clB, clC,
clKC; clC through this file == uhD recorded without it, every key but tag and wall_s). It
therefore proves pass-through ONLY for the wrappers that run with the switches off, and
only where a G1 run reaches them: WildFireModel.__init__ / step, Firefighter._mark_route_blocked / _exit_leg_enclosed,
WildFireModel.apply_physical_rescue_command (its casualty branch included: recorded uhD
has one casualty unassign, U30 east/half/1532569567 step 108) and
_is_productively_served's plain path. The switch-on wrappers - Firefighter._exit_leg_step
(MODE 2), Firefighter._exit_leg_hold and WildFireModel._exit_leg_held_cell (HOLD 1),
WildFireModel._exit_leg_custody (SERVED 1) and the served wrapper's second, key-less call
of the original - NEVER run in a G1 arm. For them the evidence is the code (each calls
the original once with the same arguments and returns its result; every extra read is a
pure attribute read, the served wrapper's second call is on a shallow copy of a pure
function's input) plus short self-tests, NOT G1. Extending the proof to them needs a
real-run identity pair: a C13 tuple whose clA / clKA sidecar shows holds > 0 and
hold_starts > 0, rerun through the PLAIN harness under a fresh tag and compared on every
key but tag and wall_s (a queue / analyzer step, not this file's).

A name the checkout does not have (the 6160438 worktree has no ff_exit_leg_* accessor and
no _exit_leg_* method) is NOT wrapped and is listed in "absent"; its counters stay 0 and
its event list stays empty, so every sidecar has the same shape.

STEP STAMPS: every event is stamped with the model's evaluation_timesteps_counter read at
the moment of the event. WildFireModel.step increments that counter at its top, so an
event stamped s happened during model step s - the harness's own convention (_step_of),
and the value the counter holds AFTER step s returns. Events are therefore aligned with
the harness rows: ff_steps[s-1] is the state after step s.

SIDECAR JSON (version 1)
  version, harness ("stock"|"crn"), repo (os.path.abspath, as the harness records it),
  argv (the launcher's command line after the script name),
  switches {"mode","hold","served"}: what agents.ff_exit_leg_mode()/hold()/served()
      return, read ONCE at the first WildFireModel.step call (after apply_scenario_config);
      "ABSENT" per name when the accessor does not exist,
  counters, events (each list capped at EVENT_CAP; overflow counted in events_dropped),
  transition_log_sha256  sha256(json.dumps(model._movement_transition_log or [],
                                            sort_keys=True, default=repr))
  movement_reason_sha256 sha256(json.dumps({unit_id: movement_reason} over
                                            model.firefighter_marker_agents,
                                            sort_keys=True, default=repr))
  absent [qualified names not found in the checkout]
  json_sha256            sha256 of the harness JSON's bytes (--out) as the inner harness
                         left it: the one link between this sidecar and ITS JSON (argv is
                         the same on every rerun of a line). A reader compares it with the
                         JSON on disk.
  source_sha256          {"agents.py", "wildfire_model.py", "common_fixed_variables.py",
                          "src_extension/planning/rescue_planner.py": sha256 of the file
                          that was IMPORTED (module __file__), read right after the import}
  src12                  the pool's src= digest (outputs/_cl_pool.sh src_digest) of those
                         four files: sha256 over the lines "<sha256> *<relative path>\n"
                         in that order, first 12 hex. For clB it names the 6160438
                         worktree's source, which the pool's src= (carryleg cwd) does not.
  tool_sha256            {basename: sha256} of _cl_obs.py, the launcher (sys.argv[0]) and
                         the inner harness file(s) run (crn: _fm2_probe_harness.py AND
                         _ffr_harness.py), read before the harness runs

COUNTERS / EVENTS (event name: row layout)
  model_steps               WildFireModel.step calls (must equal --steps)
  models_built              WildFireModel.__init__ calls (must be exactly 1)
  carrier_route_blocked     Firefighter._mark_route_blocked called on a unit that was
                            exiting before the call (every such call, works at 6160438)
      event carrier_route_blocked: [step, unit_id, pos]
  carrier_route_blocked_noop  the subset whose status was ALREADY route_blocked before
                            the call (the original then raises nothing)
  enclosed_calls            Firefighter._exit_leg_enclosed calls (every arm, HOLD 0 too)
  enclosure_triggers        ... that returned True (an enclosed carrier)
      event enclosure_triggers: [step, unit_id, pos]
  holds                     Firefighter._exit_leg_hold calls
      event holds: [step, unit_id, pos, victim_id]
  path_steps / fallback_steps  Firefighter._exit_leg_step returned "path" / "fallback"
  exit_leg_step_other       ... returned anything else (must stay 0)
      event exit_leg_steps: [step, unit_id, from_pos, to_pos, outcome]
  hold_starts               WildFireModel._exit_leg_held_cell returned a cell (a held
                            carrier's cell used as a reachability start; once per
                            held carrier per _update_unreachable_victims call)
      event hold_starts: [step, unit_id, cell]
  custody_calls             WildFireModel._exit_leg_custody calls
  custody_victim_steps      sum over those calls of the returned set's size
      event custody: [step, sorted victim ids]   (non-empty sets only)
  in_custody_calls          rescue_planner._is_productively_served calls whose flags
                            carry a truthy "in_custody" (the planner's own bool() test)
  served_by_custody_only    ... where the original returned True and the original on a
                            shallow copy WITHOUT the in_custody key returns False
                            (custody alone made it served)
  served_by_custody_only_not_geo  ... and additionally geo_reachable is False, read
                            exactly as the planner reads it:
                            flags.get("geo_reachable", flags.get("reachable", False))
                            (a prevented geographic-isolation streak increment)
      event served_by_custody_only: [step, geo_reachable]
  casualty_unassigns        WildFireModel.apply_physical_rescue_command with action
                            "unassign" and reason "firefighter_fire_casualty"
      event casualty_unassigns: [step, ff_id, victim_id, sorted(metadata keys)]
                            (metadata keys read BEFORE the call)
  events_dropped            events not stored because their list was at EVENT_CAP
  observer_errors           bookkeeping exceptions (any > 0 -> exit 5, no sidecar)
  hash_repr_fallbacks / hash_repr_addresses  default=repr uses while hashing, and how
                            many of those reprs carry a memory address (" at 0x"), which
                            would make a hash run-dependent. Both 0 in a sound run.

Off-exit completions (design 5.3 b) need no wrap: the harness's completions[] carry pos
and exit_target.

EXIT CODES: the inner harness's code when non-zero (no sidecar); 2 bad command line, or
a path this run would write already exists (rule A4: --out, <out>.tmp, <out>.fm2p.tmp
(crn), the .stdout.txt, the sidecar or its .tmp - checked before anything is imported or
run, so a rerun can never leave an old sidecar beside a new JSON); 4 provenance (module
imported from outside --repo, an imported source file unreadable, model/step count
mismatch, --out missing after the harness returned 0); 5 observer error. 0 only with the
sidecar written (tmp + os.replace).

BYTECODE: the launchers set sys.dont_write_bytecode before importing this module, so the
pool's plain `$PY <launcher>` (no -B) writes no __pycache__ for this file or for the
--repo checkout's modules (rule A3).

Extension hook for an out-of-tree probe (spec section L): main(harness, extra_install=f)
calls f(mods) after the wraps are installed and before the harness runs; mods holds
am/cfv/wf/rp and the helpers note(), stamp(), cell(); a probe may add counters/events
through note().
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
INNER = {
    "stock": os.path.join(HERE, "_ffr_harness.py"),
    "crn": os.path.join(HERE, "_fm2_probe_harness.py"),
}
VERSION = 1
EVENT_CAP = 5000

COUNTERS = (
    "model_steps",
    "models_built",
    "carrier_route_blocked",
    "carrier_route_blocked_noop",
    "enclosed_calls",
    "enclosure_triggers",
    "holds",
    "path_steps",
    "fallback_steps",
    "exit_leg_step_other",
    "hold_starts",
    "custody_calls",
    "custody_victim_steps",
    "in_custody_calls",
    "served_by_custody_only",
    "served_by_custody_only_not_geo",
    "casualty_unassigns",
    "events_dropped",
    "observer_errors",
    "hash_repr_fallbacks",
    "hash_repr_addresses",
)
EVENTS = (
    "carrier_route_blocked",
    "enclosure_triggers",
    "holds",
    "exit_leg_steps",
    "hold_starts",
    "custody",
    "served_by_custody_only",
    "casualty_unassigns",
)
SWITCHES = (("mode", "ff_exit_leg_mode"), ("hold", "ff_exit_leg_hold"), ("served", "ff_exit_leg_served"))
# the pool's src_digest files, in its order, as paths relative to the checkout
SOURCE_FILES = ("agents.py", "wildfire_model.py", "common_fixed_variables.py",
                "src_extension/planning/rescue_planner.py")

# The captured WildFireModel instances. A list in THIS module, never an attribute on
# the model.
_MODELS: list = []
STATE: dict = {
    "counters": {k: 0 for k in COUNTERS},
    "events": {k: [] for k in EVENTS},
    "switches": None,
    "absent": [],
    "errors": [],
    "am": None,
    "source_sha256": None,
    "src12": None,
}


# ---- helpers (pure; never raise into the run) ----------------------------------------
def _argv_value(argv: list, flag: str):
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return None


def _set_items(argv: list) -> list:
    """The --set KEY=VALUE items, as (key, raw value) in order."""
    out = []
    for i, a in enumerate(argv):
        item = None
        if a == "--set" and i + 1 < len(argv):
            item = argv[i + 1]
        elif a.startswith("--set="):
            item = a.split("=", 1)[1]
        if item is not None and "=" in item:
            k, v = item.split("=", 1)
            out.append((k.strip(), v))
    return out


def cell(pos):
    if pos is None:
        return None
    try:
        return [int(pos[0]), int(pos[1])]
    except Exception:
        return repr(pos)


def stamp(model) -> int:
    """The step an event belongs to: the live counter (s during model step s)."""
    if model is None:
        model = _MODELS[-1] if _MODELS else None
    if model is None:
        return 0
    return int(getattr(model, "evaluation_timesteps_counter", 0) or 0)


def note(counter: str | None = None, event_name: str | None = None, event=None, add: int = 1) -> None:
    counters = STATE["counters"]
    if counter is not None:
        counters[counter] = int(counters.get(counter, 0)) + int(add)
    if event_name is not None:
        lst = STATE["events"].setdefault(event_name, [])
        if len(lst) < EVENT_CAP:
            lst.append(event)
        else:
            counters["events_dropped"] += 1


def _error(where: str, exc: BaseException) -> None:
    STATE["counters"]["observer_errors"] += 1
    if len(STATE["errors"]) < 50:
        STATE["errors"].append("%s: %r" % (where, exc))


def _unit(agent) -> str:
    return str(getattr(agent, "unit_id", "") or "")


def _vid(model, agent) -> str:
    """The harness's own victim-id read (_ffr_harness._vid)."""
    if agent is None:
        return ""
    try:
        return str(model._victim_id_from_agent(agent) or "")
    except Exception:
        return str(getattr(agent, "victim_id", "") or "")


def _under(path: str, root: str) -> bool:
    p = os.path.normcase(os.path.abspath(path))
    r = os.path.normcase(os.path.abspath(root)).rstrip("\\/")
    return p.startswith(r + os.sep)


def _provenance_exit(msg: str):
    """Exit code 4 (provenance), with the reason on stderr. SystemExit(<str>) would exit 1."""
    print("CLOBS PROVENANCE: " + msg, file=sys.stderr)
    raise SystemExit(4)


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def src12(shas: dict) -> str:
    """outputs/_cl_pool.sh src_digest: `sha256sum <the four files> | sha256sum | cut -c1-12`
    run in the checkout (Git Bash's sha256sum prints "<hex> *<path>")."""
    text = "".join("%s *%s\n" % (shas[rel], rel) for rel in SOURCE_FILES)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _wrap(owner, name: str, qual: str, make) -> bool:
    """Replace owner.<name> by make(original); record `qual` as absent if missing."""
    orig = getattr(owner, name, None)
    if orig is None or not callable(orig):
        STATE["absent"].append(qual)
        return False
    wrapper = make(orig)
    functools.update_wrapper(wrapper, orig)
    setattr(owner, name, wrapper)
    return True


def read_switches(am) -> dict:
    out = {}
    for key, fname in SWITCHES:
        fn = getattr(am, fname, None)
        out[key] = fn() if callable(fn) else "ABSENT"
    return out


# ---- install -------------------------------------------------------------------------
def install(repo: str) -> dict:
    repo = os.path.abspath(repo)
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am  # noqa: E402
    import common_fixed_variables as cfv  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    import src_extension.planning.rescue_planner as rp  # noqa: E402

    shas = {}
    for mod, rel in zip((am, wf, cfv, rp), SOURCE_FILES):
        path = getattr(mod, "__file__", "") or ""
        if not _under(path, repo):
            _provenance_exit("%s imported from %s, expected under %s" % (mod.__name__, path, repo))
        if os.path.normcase(os.path.abspath(path)) != os.path.normcase(os.path.join(repo, *rel.split("/"))):
            _provenance_exit("%s imported from %s, expected %s" % (mod.__name__, path, rel))
        try:
            shas[rel] = file_sha256(path)
        except OSError as exc:
            _provenance_exit("cannot read the imported source %s: %r" % (path, exc))
    STATE["source_sha256"] = shas
    STATE["src12"] = src12(shas)
    STATE["am"] = am
    for _key, fname in SWITCHES:
        if not callable(getattr(am, fname, None)):
            STATE["absent"].append("agents." + fname)

    Model = wf.WildFireModel
    FF = am.Firefighter

    # -- WildFireModel.__init__: capture the instance ------------------------------------
    def make_init(orig):
        def __init__(self, *a, **k):
            result = orig(self, *a, **k)
            try:
                _MODELS.append(self)
                note("models_built")
            except Exception as exc:
                _error("WildFireModel.__init__", exc)
            return result
        return __init__

    _wrap(Model, "__init__", "WildFireModel.__init__", make_init)

    # -- WildFireModel.step: switches at the first call; step count ----------------------
    def make_step(orig):
        def step(self, *a, **k):
            if STATE["switches"] is None:
                try:
                    STATE["switches"] = read_switches(am)
                except Exception as exc:
                    _error("switches", exc)
            result = orig(self, *a, **k)
            try:
                note("model_steps")
            except Exception as exc:
                _error("WildFireModel.step", exc)
            return result
        return step

    _wrap(Model, "step", "WildFireModel.step", make_step)

    # -- Firefighter._mark_route_blocked: a carrier raising route_blocked -----------------
    def make_route_blocked(orig):
        def _mark_route_blocked(self, *a, **k):
            pre = None
            try:
                if bool(getattr(self, "exiting", False)):
                    pre = (
                        stamp(getattr(self, "model", None)),
                        _unit(self),
                        cell(getattr(self, "pos", None)),
                        str(getattr(self, "status", "") or "").strip().lower() == "route_blocked",
                    )
            except Exception as exc:
                _error("_mark_route_blocked pre", exc)
            result = orig(self, *a, **k)
            if pre is not None:
                try:
                    note("carrier_route_blocked", "carrier_route_blocked", [pre[0], pre[1], pre[2]])
                    if pre[3]:
                        note("carrier_route_blocked_noop")
                except Exception as exc:
                    _error("_mark_route_blocked", exc)
            return result
        return _mark_route_blocked

    _wrap(FF, "_mark_route_blocked", "Firefighter._mark_route_blocked", make_route_blocked)

    # -- Firefighter._exit_leg_enclosed ---------------------------------------------------
    def make_enclosed(orig):
        def _exit_leg_enclosed(self, *a, **k):
            result = orig(self, *a, **k)
            try:
                note("enclosed_calls")
                if result:
                    note("enclosure_triggers", "enclosure_triggers",
                         [stamp(getattr(self, "model", None)), _unit(self), cell(getattr(self, "pos", None))])
            except Exception as exc:
                _error("_exit_leg_enclosed", exc)
            return result
        return _exit_leg_enclosed

    _wrap(FF, "_exit_leg_enclosed", "Firefighter._exit_leg_enclosed", make_enclosed)

    # -- Firefighter._exit_leg_hold -------------------------------------------------------
    def make_hold(orig):
        def _exit_leg_hold(self, *a, **k):
            result = orig(self, *a, **k)
            try:
                model = getattr(self, "model", None)
                note("holds", "holds", [stamp(model), _unit(self), cell(getattr(self, "pos", None)),
                                        _vid(model, getattr(self, "rescued_victim", None))])
            except Exception as exc:
                _error("_exit_leg_hold", exc)
            return result
        return _exit_leg_hold

    _wrap(FF, "_exit_leg_hold", "Firefighter._exit_leg_hold", make_hold)

    # -- Firefighter._exit_leg_step: path / fallback --------------------------------------
    def make_leg_step(orig):
        def _exit_leg_step(self, *a, **k):
            frm = None
            try:
                frm = cell(getattr(self, "pos", None))
            except Exception as exc:
                _error("_exit_leg_step pre", exc)
            result = orig(self, *a, **k)
            try:
                if result == "path":
                    counter = "path_steps"
                elif result == "fallback":
                    counter = "fallback_steps"
                else:
                    counter = "exit_leg_step_other"
                note(counter, "exit_leg_steps",
                     [stamp(getattr(self, "model", None)), _unit(self), frm,
                      cell(getattr(self, "pos", None)), str(result)])
            except Exception as exc:
                _error("_exit_leg_step", exc)
            return result
        return _exit_leg_step

    _wrap(FF, "_exit_leg_step", "Firefighter._exit_leg_step", make_leg_step)

    # -- WildFireModel._exit_leg_held_cell ------------------------------------------------
    def make_held_cell(orig):
        def _exit_leg_held_cell(self, *a, **k):
            result = orig(self, *a, **k)
            try:
                if result is not None:
                    marker = a[0] if a else k.get("ff_marker")
                    note("hold_starts", "hold_starts", [stamp(self), _unit(marker), cell(result)])
            except Exception as exc:
                _error("_exit_leg_held_cell", exc)
            return result
        return _exit_leg_held_cell

    _wrap(Model, "_exit_leg_held_cell", "WildFireModel._exit_leg_held_cell", make_held_cell)

    # -- WildFireModel._exit_leg_custody --------------------------------------------------
    def make_custody(orig):
        def _exit_leg_custody(self, *a, **k):
            result = orig(self, *a, **k)
            try:
                size = len(result) if result is not None else 0
                note("custody_calls")
                note("custody_victim_steps", add=size)
                if size:
                    note(None, "custody", [stamp(self), sorted(str(v) for v in result)])
            except Exception as exc:
                _error("_exit_leg_custody", exc)
            return result
        return _exit_leg_custody

    _wrap(Model, "_exit_leg_custody", "WildFireModel._exit_leg_custody", make_custody)

    # -- rescue_planner._is_productively_served (module attribute, a global at call time) --
    def make_served(orig):
        def _is_productively_served(*a, **k):
            result = orig(*a, **k)
            try:
                flags = a[0] if a else k.get("flags")
                if isinstance(flags, dict) and bool(flags.get("in_custody", False)):
                    note("in_custody_calls")
                    bare = dict(flags)
                    bare.pop("in_custody", None)
                    # custody ALONE made it served: served with the key, not without
                    # (at 6160438 the key means nothing and the first test fails)
                    if result and not orig(bare):
                        geo = bool(flags.get("geo_reachable", flags.get("reachable", False)))
                        note("served_by_custody_only", "served_by_custody_only", [stamp(None), geo])
                        if not geo:
                            note("served_by_custody_only_not_geo")
            except Exception as exc:
                _error("_is_productively_served", exc)
            return result
        return _is_productively_served

    _wrap(rp, "_is_productively_served", "rescue_planner._is_productively_served", make_served)

    # -- WildFireModel.apply_physical_rescue_command: casualty unassigns ------------------
    def make_apply(orig):
        def apply_physical_rescue_command(self, *a, **k):
            pre = None
            try:
                cmd = a[0] if a else k.get("cmd")
                action = str(getattr(cmd, "action", "") or "").strip().lower()
                reason = str(getattr(cmd, "reason", "") or "").strip()
                if action == "unassign" and reason == "firefighter_fire_casualty":
                    md = getattr(cmd, "metadata", None)
                    keys = sorted(str(x) for x in md.keys()) if isinstance(md, dict) else []
                    pre = [stamp(self), str(getattr(cmd, "firefighter_id", "") or ""),
                           str(getattr(cmd, "victim_id", "") or ""), keys]
            except Exception as exc:
                _error("apply_physical_rescue_command pre", exc)
            result = orig(self, *a, **k)
            if pre is not None:
                try:
                    note("casualty_unassigns", "casualty_unassigns", pre)
                except Exception as exc:
                    _error("apply_physical_rescue_command", exc)
            return result
        return apply_physical_rescue_command

    _wrap(Model, "apply_physical_rescue_command", "WildFireModel.apply_physical_rescue_command", make_apply)

    return {"am": am, "cfv": cfv, "wf": wf, "rp": rp, "repo": repo,
            "note": note, "stamp": stamp, "cell": cell, "state": STATE}


# ---- the end-of-run hashes -----------------------------------------------------------
def _hash(obj) -> str:
    def default(o):
        r = repr(o)
        STATE["counters"]["hash_repr_fallbacks"] += 1
        if " at 0x" in r:
            STATE["counters"]["hash_repr_addresses"] += 1
        return r
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=default).encode("utf-8")).hexdigest()


def sidecar_path(out: str) -> str:
    return (out[:-5] if out.endswith(".json") else out) + ".clobs.json"


def main(harness: str, extra_install=None) -> int:
    if harness not in INNER:
        print("CLOBS: unknown harness %r" % (harness,), file=sys.stderr)
        return 2
    argv = list(sys.argv[1:])
    repo = _argv_value(argv, "--repo")
    out = _argv_value(argv, "--out")
    if repo is None or out is None:
        print("CLOBS: --repo and --out are required", file=sys.stderr)
        return 2
    sets = _set_items(argv)
    fm2p = [(k, v) for k, v in sets if k.startswith("FM2P_")]
    if harness == "stock" and fm2p:
        print("CLOBS: FM2P_* keys on the stock instrument: %r" % (fm2p,), file=sys.stderr)
        return 2
    if harness == "crn":
        if _argv_value(argv, "--seed") is None:
            print("CLOBS: --seed is required by the CRN instrument", file=sys.stderr)
            return 2
        crn = [v for k, v in fm2p if k == "FM2P_CRN"]
        if len(crn) != 1 or crn[0].strip() != "1":
            print("CLOBS: the CRN instrument requires exactly one --set FM2P_CRN=1 (got %r)" % (crn,),
                  file=sys.stderr)
            return 2
    steps_raw = _argv_value(argv, "--steps")
    try:
        want_steps = int(steps_raw) if steps_raw is not None else 240  # the harness default
    except ValueError:
        print("CLOBS: bad --steps %r" % (steps_raw,), file=sys.stderr)
        return 2

    # Rule A4: every path this run writes must be new. An old sidecar (or JSON) left by an
    # earlier run of the same line would otherwise sit beside this run's output and still
    # match it on argv.
    stdout_txt = (out[:-5] if out.endswith(".json") else out) + ".stdout.txt"
    writes = [out, out + ".tmp", stdout_txt, sidecar_path(out), sidecar_path(out) + ".tmp"]
    if harness == "crn":
        writes.append(out + ".fm2p.tmp")
    present = [p for p in writes if os.path.lexists(p)]
    if present:
        print("CLOBS: refusing to run - path(s) this run would write already exist: %s"
              % ", ".join(present), file=sys.stderr)
        return 2

    launcher = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else None
    tool_files = [os.path.abspath(__file__)]
    if launcher:
        tool_files.append(launcher)
    tool_files.append(INNER[harness])
    if harness == "crn":
        tool_files.append(INNER["stock"])  # _fm2_probe_harness.py runs _ffr_harness.py
    tool_sha = {}
    for p in tool_files:
        try:
            tool_sha[os.path.basename(p)] = file_sha256(p)
        except OSError as exc:
            print("CLOBS PROVENANCE: cannot read %s: %r" % (p, exc), file=sys.stderr)
            return 4

    mods = install(repo)
    if extra_install is not None:
        extra_install(mods)

    inner = INNER[harness]
    sys.argv = [inner] + argv
    code = 0
    try:
        runpy.run_path(inner, run_name="__main__")
    except SystemExit as exc:
        if isinstance(exc.code, str):
            print(exc.code, file=sys.stderr)
            code = 1
        else:
            code = int(exc.code or 0)
    if code != 0:
        return code

    counters = STATE["counters"]
    if len(_MODELS) != 1 or counters["models_built"] != 1:
        print("CLOBS PROVENANCE: %d model(s) built, expected exactly 1 - no sidecar" % len(_MODELS),
              file=sys.stderr)
        return 4
    if counters["model_steps"] != want_steps:
        print("CLOBS PROVENANCE: observed %d model steps, --steps says %d - no sidecar"
              % (counters["model_steps"], want_steps), file=sys.stderr)
        return 4
    try:
        json_sha = file_sha256(out)
    except OSError as exc:
        print("CLOBS PROVENANCE: the harness returned 0 but --out %s cannot be read (%r) - no sidecar"
              % (out, exc), file=sys.stderr)
        return 4
    model = _MODELS[0]
    if STATE["switches"] is None:
        STATE["switches"] = read_switches(STATE["am"])
    try:
        transition_sha = _hash(list(getattr(model, "_movement_transition_log", None) or []))
        reasons = {
            str(getattr(m, "unit_id", ff_id) or ff_id): getattr(m, "movement_reason", None)
            for ff_id, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items()
        }
        reason_sha = _hash(reasons)
    except Exception as exc:
        _error("hashes", exc)
        transition_sha = reason_sha = None
    if counters["observer_errors"]:
        print("CLOBS: %d observer error(s) - no sidecar:" % counters["observer_errors"], file=sys.stderr)
        for e in STATE["errors"]:
            print("  " + e, file=sys.stderr)
        return 5

    record = {
        "version": VERSION,
        "harness": harness,
        "repo": mods["repo"],
        "argv": argv,
        "switches": STATE["switches"],
        "counters": counters,
        "events": STATE["events"],
        "transition_log_sha256": transition_sha,
        "movement_reason_sha256": reason_sha,
        "absent": list(STATE["absent"]),
        "json_sha256": json_sha,
        "source_sha256": STATE["source_sha256"],
        "src12": STATE["src12"],
        "tool_sha256": tool_sha,
    }
    path = sidecar_path(out)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(record, f)
    os.replace(tmp, path)
    return 0
