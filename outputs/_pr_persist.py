"""Defect #5: upper bound on consequence. Make every _finalize_rescued_victim
call raise, so the outer `except Exception: pass` fires on EVERY firefighter
exit and the self-heal (re-queue next step) can never complete.

Answers: if a drop were permanent rather than self-healing, what breaks, and
would anyone reading normal output notice?
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

STATE = {"always": False, "raises": 0, "step": 0, "proc_calls": 0,
         "queue_lens": [], "returns": []}

_orig_final = WildFireModel._finalize_rescued_victim


def _final_fault(self, victim_id, agent=None, firefighter_id=None):
    if STATE["always"]:
        STATE["raises"] += 1
        raise RuntimeError("PERSISTENT-INJECTED-FAULT")
    return _orig_final(self, victim_id, agent, firefighter_id)


WildFireModel._finalize_rescued_victim = _final_fault

_orig_proc = WildFireModel._process_pending_agent_removals


def _proc_obs(self):
    STATE["proc_calls"] += 1
    STATE["queue_lens"].append(len(getattr(self, "_agents_pending_removal", []) or []))
    r = _orig_proc(self)
    STATE["returns"].append(int(r or 0))
    return r


WildFireModel._process_pending_agent_removals = _proc_obs

_orig_step = WildFireModel.step


def _step_obs(self):
    STATE["step"] += 1
    return _orig_step(self)


WildFireModel.step = _step_obs

TOKENS = ("Traceback", "PERSISTENT-INJECTED-FAULT", "ERROR", "error", "WARN",
          "warn", "fail", "Fail", "drop", "Drop", "pending", "Pending",
          "leak", "Leak", "RescueInvariant", "RescueAuthority")


def run(seed, p, steps, always):
    STATE.update({"always": always, "raises": 0, "step": 0, "proc_calls": 0})
    STATE["queue_lens"] = []
    STATE["returns"] = []
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
    residue = {}
    for a in model.schedule.agents:
        tn = type(a).__name__
        residue[tn] = residue.get(tn, 0) + 1
    vic_on_grid = [
        {"vid": getattr(a, "victim_id", None), "pos": str(a.pos),
         "status": str(getattr(a, "status", ""))}
        for a in model.schedule.agents if type(a).__name__ == "Victim"]
    return {
        "eval": {k: ev.get(k) for k in (
            "rescued", "dead", "unreachable", "candidate", "rescue_rate",
            "firefighter_deaths", "burnt_cells", "terminal_step", "steps_run")},
        "raises": STATE["raises"],
        "residue": residue,
        "victims_on_grid": vic_on_grid,
        "leftover_pending": len(getattr(model, "_agents_pending_removal", []) or []),
        "queue_max": max(STATE["queue_lens"]) if STATE["queue_lens"] else 0,
        "returns_sum": sum(STATE["returns"]),
        "stdout_lines": text.count("\n"),
        "tokens": {t: text.count(t) for t in TOKENS},
        "_text": text,
    }


if __name__ == "__main__":
    STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 240
    P = {"NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2,
         "WIND_DIRECTION": "east", "BATCH_SIZE": 300,
         "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
         "NUM_FIRE_TRACKERS": 2, "NUM_VICTIM_SEARCHERS": 2}
    clean = run(101, P, STEPS, always=False)
    ctext = clean.pop("_text")
    print("CLEAN    ", json.dumps(clean["eval"]), "residue=", json.dumps(clean["residue"]),
          "returns_sum=%d" % clean["returns_sum"], flush=True)
    bad = run(101, P, STEPS, always=True)
    btext = bad.pop("_text")
    print("PERSIST  ", json.dumps(bad["eval"]), "residue=", json.dumps(bad["residue"]),
          "raises=%d" % bad["raises"], "returns_sum=%d" % bad["returns_sum"],
          "leftover=%d" % bad["leftover_pending"], flush=True)
    print("TOKENS   ", json.dumps(bad["tokens"]), flush=True)
    cl = set(ctext.splitlines())
    new = [l for l in btext.splitlines() if l not in cl]
    print("NEW LINES vs clean: %d" % len(new), flush=True)
    for l in new[:25]:
        print("   +", l)
    print("VICTIMS ON GRID AT END (persist):", json.dumps(bad["victims_on_grid"]))
    print("VICTIMS ON GRID AT END (clean)  :", json.dumps(clean["victims_on_grid"]))
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "_pr_persist.json"), "w", encoding="utf-8") as fh:
        json.dump({"clean": clean, "persist": bad,
                   "new_lines_vs_clean": new[:60]}, fh, indent=2, default=str)
    print("WROTE outputs/_pr_persist.json")
