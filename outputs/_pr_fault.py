"""Defect #5 Part-2/3 probe: fault-injection into the pending-removal loop.

Establishes (a) blast radius of the outer `except Exception: pass`,
(b) whether a swallowed failure surfaces anywhere in normal output,
(c) whether the un-removed agents have observable consequence.
"""
from __future__ import annotations
import contextlib, io as _io, json, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import _build_evaluation

STATE = {
    "inject_on_call": -1,      # 1-based index of _finalize_rescued_victim call to blow up
    "final_calls": 0,
    "injected": 0,
    "step": 0,
    "queue_len_at_inject": 0,
    "lost": [],                # agents silently lost by the injected fault
    "queue_lens": [],
    "post_move_return": [],
}

_orig_final = WildFireModel._finalize_rescued_victim


def _final_fault(self, victim_id, agent=None, firefighter_id=None):
    STATE["final_calls"] += 1
    if STATE["final_calls"] == STATE["inject_on_call"]:
        STATE["injected"] += 1
        raise RuntimeError("INJECTED-FAULT")
    return _orig_final(self, victim_id, agent, firefighter_id)


_orig_proc = WildFireModel._process_pending_agent_removals


def _proc_obs(self):
    pending = list(getattr(self, "_agents_pending_removal", []) or [])
    STATE["queue_lens"].append(len(pending))
    before_inject = STATE["injected"]
    ret = _orig_proc(self)
    if STATE["injected"] > before_inject:
        STATE["queue_len_at_inject"] = len(pending)
        for a in pending:
            STATE["lost"].append({
                "step": STATE["step"], "type": type(a).__name__,
                "uid": getattr(a, "unique_id", None),
                "pos_after": str(getattr(a, "pos", None)),
                "in_sched_after": getattr(self.schedule, "_agents", {}).get(
                    getattr(a, "unique_id", None)) is a,
                "status_after": str(getattr(a, "status", "")),
            })
    STATE["post_move_return"].append(int(ret or 0))
    return ret


WildFireModel._process_pending_agent_removals = _proc_obs
WildFireModel._finalize_rescued_victim = _final_fault

_orig_step = WildFireModel.step


def _step_obs(self):
    STATE["step"] += 1
    return _orig_step(self)


WildFireModel.step = _step_obs


def params(wind="east", ft=2, vs=2):
    return {"NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2,
            "WIND_DIRECTION": wind, "BATCH_SIZE": 300,
            "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
            "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}


def run(seed, p, steps, inject_on_call=-1, capture=True):
    for k in ("final_calls", "injected", "step", "queue_len_at_inject"):
        STATE[k] = 0
    STATE["inject_on_call"] = inject_on_call
    STATE["lost"] = []
    STATE["queue_lens"] = []
    STATE["post_move_return"] = []

    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **p)

    buf = _io.StringIO()
    terminal_step = None
    n = 0
    with contextlib.redirect_stdout(buf):
        model = WildFireModel()
        model.debug_log = False
        for _ in range(steps):
            model.step()
            n += 1
            if terminal_step is None:
                panel = model.get_dashboard_state()
                if (panel.get("mission_status", {}) or {}).get("all_victims_terminal"):
                    terminal_step = n
    ev = _build_evaluation(model, terminal_step, n, p)
    text = buf.getvalue()
    # residue after the run
    residue = {"PathMarker": 0, "Victim": 0, "Firefighter": 0, "Fire": 0, "UAV": 0}
    for a in model.schedule.agents:
        tn = type(a).__name__
        if tn in residue:
            residue[tn] += 1
    leftover = [
        {"type": type(a).__name__, "uid": getattr(a, "unique_id", None),
         "pos": str(getattr(a, "pos", None))}
        for a in (getattr(model, "_agents_pending_removal", []) or [])
    ]
    return {
        "seed": seed, "eval": {k: ev.get(k) for k in (
            "rescued", "dead", "unreachable", "geographically_isolated",
            "never_detected", "horizon_unresolved", "unreachable_other",
            "candidate", "rescue_rate", "firefighter_deaths", "burnt_cells",
            "terminal_step", "steps_run")},
        "stdout_len": len(text),
        "stdout_lines": text.count("\n"),
        "residue_in_schedule": residue,
        "leftover_pending": leftover,
        "queue_max": max(STATE["queue_lens"]) if STATE["queue_lens"] else 0,
        "queue_hist": {},
        "injected": STATE["injected"],
        "queue_len_at_inject": STATE["queue_len_at_inject"],
        "lost": STATE["lost"],
        "final_calls": STATE["final_calls"],
        "_text": text,
    }


SILENCE_TOKENS = ("Traceback", "INJECTED-FAULT", "ERROR", "error", "WARN", "warn",
                  "fail", "Fail", "drop", "Drop", "pending", "Pending",
                  "unremoved", "leak", "Leak", "RemovalFailure")

if __name__ == "__main__":
    STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 240
    out = {"steps": STEPS, "runs": []}
    SEED = 101
    P = params("east", 2, 2)

    clean = run(SEED, P, STEPS, inject_on_call=-1)
    hist = {}
    for v in STATE["queue_lens"]:
        hist[str(v)] = hist.get(str(v), 0) + 1
    clean["queue_hist"] = hist
    clean_text = clean.pop("_text")
    out["runs"].append({"label": "clean", **clean})
    print("CLEAN", json.dumps(clean["eval"]), "queue_max=%d" % clean["queue_max"],
          "final_calls=%d" % clean["final_calls"], flush=True)

    for k in (1, 2):
        f = run(SEED, P, STEPS, inject_on_call=k)
        ftext = f.pop("_text")
        f["silence_probe"] = {
            t: ftext.count(t) for t in SILENCE_TOKENS
        }
        f["new_lines_vs_clean"] = None
        out["runs"].append({"label": "inject_final_call_%d" % k, **f})
        print("INJECT#%d" % k, json.dumps(f["eval"]),
              "injected=%d" % f["injected"],
              "queue_at_inject=%d" % f["queue_len_at_inject"],
              "lost=%d" % len(f["lost"]),
              "leftover=%d" % len(f["leftover_pending"]),
              "residue=%s" % json.dumps(f["residue_in_schedule"]), flush=True)
        # explicit diff of the two stdout streams: does anything new appear?
        cl = set(l for l in clean_text.splitlines())
        nw = [l for l in ftext.splitlines() if l not in cl]
        out["runs"][-1]["stdout_lines_absent_from_clean"] = nw[:40]
        out["runs"][-1]["n_stdout_lines_absent_from_clean"] = len(nw)

    out["clean_eval"] = clean["eval"]
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "_pr_fault.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)
    print("WROTE outputs/_pr_fault.json")
