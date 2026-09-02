"""Defect #9-A2 Part-3 control: byte-identity harness.

Derived verbatim from outputs/_pr_control.py (defect #5), same COMBOS, same
steps, so the standard is identical to the #12 and #5 rounds. Two additions,
both purely observational:

  * scorchmap  - a 4-state ground map (0 virgin / 1 burning / 2 burnt /
                 3 scorched). The #5 firemap could not tell burnt from
                 scorched; this round is precisely about that distinction, so
                 the control must be able to see it. It is a SIMULATION
                 digest and must be identical pre/post.
  * cellcolor  - sha256 of serve_dashboard._cell_color over every Fire cell in
                 unique_id order. This is the POSITIVE control: it is the one
                 digest that is EXPECTED to differ after the patch, proving the
                 rendering change actually took effect rather than the run
                 simply not exercising it. Also reports the colour histogram.

usage: _sc_control.py <tag> [steps]
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


COMBOS = [
    ("D/east/half", 101, params("east", 2, 2)),
    ("D/south/half", 101, params("south", 2, 2)),
    ("D/east/default", 101, params("east", None, None)),
]


def run(seed, p, steps):
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
    # positions of every non-Fire agent: catches any movement divergence
    poslist = sorted(
        "%s:%s:%s" % (type(a).__name__, getattr(a, "unique_id", ""), a.pos)
        for a in model.schedule.agents if type(a).__name__ != "Fire"
    )
    fires = sorted((x for x in model.schedule.agents
                    if type(x).__name__ == "Fire"), key=lambda x: x.unique_id)
    # burning/burnt fire map: catches any environment divergence (identical
    # encoding to defect #5's _pr_control.py, kept for comparability)
    firemap = "".join(
        "1" if getattr(a, "burning", False) else ("2" if getattr(a, "burnt", False) else "0")
        for a in fires
    )
    # 4-state ground map: adds the scorched state the #5 firemap folded away
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
    # POSITIVE CONTROL: the rendered colour of every cell. Expected to DIFFER.
    colors = [_cell_color(a) for a in fires]
    hist = {}
    for c in colors:
        hist[c] = hist.get(c, 0) + 1
    return {
        "eval": dict(ev),
        "residue": residue,
        "stdout_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "stdout_lines": text.count("\n"),
        "stdout_len": len(text),
        "agent_positions_sha256": hashlib.sha256(
            "\n".join(poslist).encode("utf-8")).hexdigest(),
        "agent_positions": poslist,
        "firemap_sha256": hashlib.sha256(firemap.encode("utf-8")).hexdigest(),
        "scorchmap_sha256": hashlib.sha256(scorchmap.encode("utf-8")).hexdigest(),
        "ground_counts": {"virgin": counts["0"], "burning": counts["1"],
                          "burnt": counts["2"], "scorched": counts["3"]},
        "cellcolor_sha256": hashlib.sha256("".join(colors).encode("utf-8")).hexdigest(),
        "cellcolor_hist": dict(sorted(hist.items(), key=lambda kv: -kv[1])),
        "leftover_pending": len(getattr(model, "_agents_pending_removal", []) or []),
        "_text": text,
    }


if __name__ == "__main__":
    TAG = sys.argv[1] if len(sys.argv) > 1 else "pre"
    STEPS = int(sys.argv[2]) if len(sys.argv) > 2 else 240
    digest = {"tag": TAG, "steps": STEPS, "runs": {}}
    for label, seed, p in COMBOS:
        r = run(seed, p, STEPS)
        text = r.pop("_text")
        key = "%s|%d" % (label, seed)
        digest["runs"][key] = r
        with open(os.path.join(BASE, "_sc_control_%s_%s.stdout.txt"
                               % (TAG, key.replace("/", "-").replace("|", "_"))),
                  "w", encoding="utf-8") as fh:
            fh.write(text)
        print(key, "stdout_sha=%s" % r["stdout_sha256"][:16],
              "pos_sha=%s" % r["agent_positions_sha256"][:16],
              "fire_sha=%s" % r["firemap_sha256"][:16],
              "scorch_sha=%s" % r["scorchmap_sha256"][:16],
              "color_sha=%s" % r["cellcolor_sha256"][:16],
              json.dumps(r["ground_counts"]), flush=True)
    with open(os.path.join(BASE, "_sc_control_%s.json" % TAG), "w",
              encoding="utf-8") as fh:
        json.dump(digest, fh, indent=2, default=str)
    print("WROTE outputs/_sc_control_%s.json" % TAG)
