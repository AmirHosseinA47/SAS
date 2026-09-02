"""Defect #5 Part-3 control: byte-identity harness.

Runs the canonical combos with NO instrumentation of any kind, captures the
complete stdout of each run plus every evaluate_scenarios metric, and writes a
digest. Run once before the patch and once after; the two digests must match
exactly (same standard as defect #12).

usage: _pr_control.py <tag> [steps]
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
from serve_dashboard import _build_evaluation

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
    # burning/burnt fire map: catches any environment divergence
    firemap = "".join(
        "1" if getattr(a, "burning", False) else ("2" if getattr(a, "burnt", False) else "0")
        for a in sorted((x for x in model.schedule.agents
                         if type(x).__name__ == "Fire"),
                        key=lambda x: x.unique_id)
    )
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
        with open(os.path.join(BASE, "_pr_control_%s_%s.stdout.txt"
                               % (TAG, key.replace("/", "-").replace("|", "_"))),
                  "w", encoding="utf-8") as fh:
            fh.write(text)
        print(key, "stdout_sha=%s" % r["stdout_sha256"][:16],
              "pos_sha=%s" % r["agent_positions_sha256"][:16],
              "fire_sha=%s" % r["firemap_sha256"][:16],
              json.dumps(r["eval"]), flush=True)
    with open(os.path.join(BASE, "_pr_control_%s.json" % TAG), "w",
              encoding="utf-8") as fh:
        json.dump(digest, fh, indent=2, default=str)
    print("WROTE outputs/_pr_control_%s.json" % TAG)
