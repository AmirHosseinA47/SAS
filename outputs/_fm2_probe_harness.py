"""firemech round 2, Part 1 DIAGNOSIS PROBES - out of tree, no source file is modified.

Runs outputs/_ffr_harness.py UNCHANGED, in this same process, after wrapping a few
attributes of the --repo checkout's modules. Every wrap reads its FM2P_* key from
common_fixed_variables at CALL time. The harness puts every --set KEY=VALUE there
through apply_scenario_config (setattr(cfv, key, value)) before the model is built,
so the keys are recorded in the run JSON's params/extra_params like any other --set
and the pool validator (outputs/_dcd4_validate.py) checks them against the queue.

WITH NO FM2P_* KEY SET EVERY WRAP IS A PASS-THROUGH: it calls the original with the
same arguments and returns its result, draws the same random numbers in the same
order, and creates no model or agent attribute. The identity arm (the round-1 fmDRY
configuration through this file) proves that against fmDRY, value for value.

KEYS
  FM2P_ENGAGE_ONLY=<unit_id>  only that firefighter may engage. Any other unit's
                              _firefight_prepare returns None before any feature
                              code runs - exactly the feature-off path for it.
  FM2P_LEASH=N                commitment limit. An idle unit's anchor is its cell on
                              the first step of its current idle streak (idle = the
                              eligibility prepare itself tests). A "move" plan whose
                              destination is more than N (manhattan) from the anchor
                              is dropped: plan None and retreat distance back to the
                              full buffer - what prepare returns when no plan exists.
                              Work in reach from where the unit already stands is kept.
  FM2P_GATE=resolved          engage only while NO victim is unresolved, by the
                              production helper local_adaptation_generator.
                              _count_unresolved_victims (rescued / dead / unreachable
                              / cancelled count as resolved).
  FM2P_WRITE_BEFORE=s         fire writes land only on steps < s; from step s on the
                              run continues in DRY mode (same decisions, the write goes
                              to the shadow set). A prefix intervention: bisecting s
                              finds the write a closed-loop outcome depends on.
  FM2P_CRN=1                  common random numbers for the fire. Fire.step's single
                              draw becomes a pure function of (seed, the cell's
                              unique_id, the cell's own steps_counter) instead of the
                              next number of the shared stream. A fire write can then
                              change the fire only through its physical consequences;
                              it can no longer shift the draw of every later cell. CRN
                              arms compare only with CRN arms - the fire itself is a
                              different (equally distributed) realisation from stock.

RECORD: when any FM2P_* key is set, the JSON gains one key "fm2p" (config, counters,
events), added after the harness finished writing, by atomic replace. The harness's
own fields, the .stdout.txt and its sha256 are untouched.
"""
from __future__ import annotations

import inspect
import json
import os
import runpy
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.join(HERE, "_ffr_harness.py")
M64 = (1 << 64) - 1

KEYS = ("FM2P_ENGAGE_ONLY", "FM2P_LEASH", "FM2P_GATE", "FM2P_WRITE_BEFORE", "FM2P_CRN")


def _argv_value(flag: str) -> str | None:
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return None


def _splitmix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & M64
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M64
    return z ^ (z >> 31)


def crn_uniform(seed: int, uid: int, tick: int) -> float:
    """[0, 1) from (seed, cell, tick) only - 53 bits, like random.random()."""
    h = _splitmix64(_splitmix64(_splitmix64(int(seed) & M64) ^ (int(uid) & M64)) ^ (int(tick) & M64))
    return (h >> 11) / float(1 << 53)


def install(repo: str, seed: int) -> dict:
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am  # noqa: E402
    import common_fixed_variables as cfv  # noqa: E402

    rec = {"counters": {"leash_dropped": 0, "gate_closed_calls": 0, "engage_only_blocked_calls": 0,
                        "dry_forced_calls": 0, "crn_draws": 0},
           "events": []}
    cur_step = [None]

    def key(name):
        v = getattr(cfv, name, None)
        return None if v in (None, "", "none", "None") else v

    # ---- Fire.step: the draw line only ------------------------------------------
    src = textwrap.dedent(inspect.getsource(am.Fire.step))
    needle = "generated = random.random()"
    if src.count(needle) != 1:
        raise SystemExit("FM2P: Fire.step draw line not found exactly once - refusing to run")
    body = src.replace(needle, "generated = _fm2p_draw(self)")
    factory = "def _fm2p_make(_fm2p_draw):\n" + textwrap.indent(body, "    ") + "    return step\n"
    ns: dict = {}
    # globals = the agents module dict, exactly the original's globals; the factory
    # itself lands in `ns`, so nothing is added to the agents module.
    exec(compile(factory, "<fm2p Fire.step>", "exec"), am.__dict__, ns)

    def _draw(fire):
        if key("FM2P_CRN"):
            rec["counters"]["crn_draws"] += 1
            return crn_uniform(seed, fire.unique_id, fire.steps_counter)
        return am.random.random()

    patched_step = ns["_fm2p_make"](_draw)
    patched_step.__qualname__ = am.Fire.step.__qualname__
    am.Fire.step = patched_step

    # ---- dry-run switch (WRITE_BEFORE) ----------------------------------------------
    orig_dry = am.ff_firefight_dry_run

    def dry_run():
        wb = key("FM2P_WRITE_BEFORE")
        if wb is not None and cur_step[0] is not None and cur_step[0] >= int(wb):
            rec["counters"]["dry_forced_calls"] += 1
            return True
        return orig_dry()

    am.ff_firefight_dry_run = dry_run

    # ---- Firefighter._firefight_prepare ----------------------------------------------
    orig_prepare = am.Firefighter._firefight_prepare

    def prepare(self):
        only = key("FM2P_ENGAGE_ONLY")
        leash = key("FM2P_LEASH")
        gate = key("FM2P_GATE")
        if only is None and leash is None and gate is None and key("FM2P_WRITE_BEFORE") is None:
            return orig_prepare(self)
        step = int(getattr(self.model, "evaluation_timesteps_counter", 0) or 0)
        cur_step[0] = step
        if leash is not None:
            idle = False
            if self.pos is not None and not self.target_pos and not self.exiting:
                available = getattr(self.model, "_firefighter_available_for_dispatch", None)
                idle = bool(callable(available) and available(self))
            if not idle:
                self._fm2p_anchor = None
            elif getattr(self, "_fm2p_anchor", None) is None:
                self._fm2p_anchor = (int(self.pos[0]), int(self.pos[1]))
        if only is not None and str(getattr(self, "unit_id", "")) != str(only):
            rec["counters"]["engage_only_blocked_calls"] += 1
            return None
        if gate is not None:
            if str(gate) != "resolved":
                raise SystemExit("FM2P_GATE must be 'resolved'")
            from src_extension.adaptation.local_adaptation_generator import _count_unresolved_victims
            if int(_count_unresolved_victims(self.model)) > 0:
                rec["counters"]["gate_closed_calls"] += 1
                return None
        ctx = orig_prepare(self)
        if ctx is not None and leash is not None and ctx.get("plan") is not None:
            kind, dest, _target = ctx["plan"]
            anchor = getattr(self, "_fm2p_anchor", None)
            if kind == "move" and anchor is not None:
                if abs(dest[0] - anchor[0]) + abs(dest[1] - anchor[1]) > int(leash):
                    ctx["plan"] = None
                    ctx["T"] = am.IDLE_RETREAT_SAFETY_BUFFER
                    rec["counters"]["leash_dropped"] += 1
                    if len(rec["events"]) < 5000:
                        rec["events"].append(["leash", step, str(self.unit_id), list(ctx["cell"]),
                                              [int(dest[0]), int(dest[1])], list(anchor)])
        return ctx

    prepare.__qualname__ = orig_prepare.__qualname__
    am.Firefighter._firefight_prepare = prepare
    return {"cfv": cfv, "rec": rec, "key": key}


def main() -> int:
    repo = _argv_value("--repo")
    seed = _argv_value("--seed")
    out = _argv_value("--out")
    if repo is None or seed is None or out is None:
        print("FM2P: --repo, --seed and --out are required", file=sys.stderr)
        return 2
    state = install(os.path.abspath(repo), int(seed))
    sys.argv = [HARNESS] + sys.argv[1:]
    code = 0
    try:
        runpy.run_path(HARNESS, run_name="__main__")
    except SystemExit as exc:
        code = int(exc.code or 0) if not isinstance(exc.code, str) else 1
        if isinstance(exc.code, str):
            print(exc.code, file=sys.stderr)
    if code != 0:
        return code
    cfv = state["cfv"]
    config = {k: getattr(cfv, k) for k in KEYS if getattr(cfv, k, None) not in (None, "", "none", "None")}
    if config:
        with open(out, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["fm2p"] = {"config": config, "counters": state["rec"]["counters"], "events": state["rec"]["events"]}
        tmp = out + ".fm2p.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
