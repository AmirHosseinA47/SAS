"""Recovery-hysteresis round Part-3 control: byte-identity harness.

Derived from outputs/_pr_control.py (defect #5) and outputs/_sc_control.py
(defect #9-A2), so the standard is continuous with those rounds. NO
instrumentation of any kind is installed - every digest is a plain read of
public model state after the run.

Differences from the #5 / #9-A2 harnesses, all additive:

  * ONE SEED PER PROCESS. This round proves identity over the canonical 13-run
    sample, not 3 combos. Combos inside one process must stay sequential
    (they share the module-level RNG), so instead each run gets its own
    process and the driver fans them out. Cross-process parallelism cannot
    perturb results: each process seeds its own random.Random(seed) into
    cfv / wf / agents.
  * rngstate  sha256 of the seeded generator's state AFTER the run. This is
               the most sensitive single digest available: if the deletion
               shifted ANY draw, this moves even when positions coincidentally
               agree. The #5/#9-A2 harnesses did not carry it.
  * modetraj  the fail-safe mode after every step, as a string. THIS ROUND
               DELETES CODE ON THE FAIL-SAFE PATH, so the mode trajectory is
               the digest most directly at risk and must be compared
               explicitly rather than folded into stdout.
  * scorchmap the #9-A2 4-state ground map (virgin/burning/burnt/scorched),
               kept for continuity with that round.
  * cellcolor kept from #9-A2, but here it is a NEGATIVE control: this round
               touches no renderer, so it must be IDENTICAL. In #9-A2 it was
               the positive control and was required to differ.

usage: _rh_control.py <tag> <run_index 1..13> [steps]
"""
from __future__ import annotations
import contextlib, hashlib, io as _io, json, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import _build_evaluation, _cell_color

BASE = os.path.dirname(os.path.abspath(__file__))


def params(wind, ft, vs):
    return {"NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2,
            "WIND_DIRECTION": wind, "BATCH_SIZE": 300,
            "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
            "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}


# The canonical 13-run sample, in the same order as outputs/failsafe_part1.txt
# section 2.1 and outputs/_rh_probe.json.
COMBOS = [
    ("east_half_101",    "D/east/half",    101, params("east",  2, 2)),
    ("east_half_202",    "D/east/half",    202, params("east",  2, 2)),
    ("east_half_303",    "D/east/half",    303, params("east",  2, 2)),
    ("east_half_404",    "D/east/half",    404, params("east",  2, 2)),
    ("east_half_505",    "D/east/half",    505, params("east",  2, 2)),
    ("south_half_101",   "D/south/half",   101, params("south", 2, 2)),
    ("south_half_202",   "D/south/half",   202, params("south", 2, 2)),
    ("south_half_303",   "D/south/half",   303, params("south", 2, 2)),
    ("south_half_404",   "D/south/half",   404, params("south", 2, 2)),
    ("south_half_505",   "D/south/half",   505, params("south", 2, 2)),
    ("east_def_101",     "D/east/default", 101, params("east",  None, None)),
    ("east_def_202",     "D/east/default", 202, params("east",  None, None)),
    ("east_def_303",     "D/east/default", 303, params("east",  None, None)),
]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run(seed, p, steps):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **p)
    buf = _io.StringIO()
    terminal_step = None
    modetraj = []
    n = 0
    with contextlib.redirect_stdout(buf):
        model = WildFireModel()
        model.debug_log = False
        for _ in range(steps):
            model.step()
            n += 1
            # pure reads, no instrumentation
            st = getattr(model, "latest_failsafe_state", None)
            mode = getattr(getattr(st, "mode", None), "value", None)
            modetraj.append(str(mode))
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
    poslist = sorted(
        "%s:%s:%s" % (type(a).__name__, getattr(a, "unique_id", ""), a.pos)
        for a in model.schedule.agents if type(a).__name__ != "Fire"
    )
    fires = sorted((x for x in model.schedule.agents
                    if type(x).__name__ == "Fire"), key=lambda x: x.unique_id)
    firemap = "".join(
        "1" if getattr(a, "burning", False) else ("2" if getattr(a, "burnt", False) else "0")
        for a in fires
    )

    def _ground(a):
        if getattr(a, "burning", False):
            return "1"
        if getattr(a, "burnt", False):
            return "2"
        if getattr(a, "has_burned", False):
            return "3"
        return "0"

    scorchmap = "".join(_ground(a) for a in fires)
    counts = {k: scorchmap.count(k) for k in "0123"}
    colors = [_cell_color(a) for a in fires]
    hist = {}
    for c in colors:
        hist[c] = hist.get(c, 0) + 1

    mode_hist = {}
    for m in modetraj:
        mode_hist[m] = mode_hist.get(m, 0) + 1

    return {
        "eval": dict(ev),
        "residue": residue,
        "terminal_step": terminal_step,
        "stdout_sha256": _sha(text),
        "stdout_lines": text.count("\n"),
        "stdout_len": len(text),
        "agent_positions_sha256": _sha("\n".join(poslist)),
        "agent_positions": poslist,
        "firemap_sha256": _sha(firemap),
        "scorchmap_sha256": _sha(scorchmap),
        "ground_counts": {"virgin": counts["0"], "burning": counts["1"],
                          "burnt": counts["2"], "scorched": counts["3"]},
        "cellcolor_sha256": _sha("".join(colors)),
        "cellcolor_hist": dict(sorted(hist.items(), key=lambda kv: -kv[1])),
        "leftover_pending": len(getattr(model, "_agents_pending_removal", []) or []),
        # the two additions that matter most for THIS round
        "rngstate_sha256": _sha(repr(rng.getstate())),
        "modetraj_sha256": _sha("|".join(modetraj)),
        "modetraj": modetraj,
        "mode_hist": mode_hist,
        "_text": text,
    }


if __name__ == "__main__":
    TAG = sys.argv[1]
    IDX = int(sys.argv[2])
    STEPS = int(sys.argv[3]) if len(sys.argv) > 3 else 240
    label, combo, seed, p = COMBOS[IDX - 1]
    r = run(seed, p, STEPS)
    text = r.pop("_text")
    with open(os.path.join(BASE, "_rh_ctl_%s_%s.stdout.txt" % (TAG, label)),
              "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    out = {"tag": TAG, "label": label, "combo": combo, "seed": seed,
           "steps": STEPS, "run": r}
    with open(os.path.join(BASE, "_rh_ctl_%s_%s.json" % (TAG, label)),
              "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)
    print(label,
          "stdout=%s" % r["stdout_sha256"][:16],
          "pos=%s" % r["agent_positions_sha256"][:16],
          "fire=%s" % r["firemap_sha256"][:16],
          "scorch=%s" % r["scorchmap_sha256"][:16],
          "color=%s" % r["cellcolor_sha256"][:16],
          "rng=%s" % r["rngstate_sha256"][:16],
          "mode=%s" % r["modetraj_sha256"][:16],
          flush=True)
