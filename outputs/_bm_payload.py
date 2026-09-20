"""Base-mark round Part 3: WHOLE-FRAME payload digest, per step.

The FOV round's payload digest (outputs/_fov_payload.py) hashes only a few keys
and does not cover fr.depots - the one key Item A reads - so as a negative
control for this round it would be close to vacuous. This hashes the ENTIRE
frame the dashboard publishes, json.dumps(_capture_frame(model, s),
sort_keys=True), at every step of the same three control combos _sc_control.py
uses, twice:

  full      the frame exactly as published
  stripped  the same frame with the round's ADDED keys removed (ADDED below)

Expected pre vs post:  `stripped` IDENTICAL at every step (negative control: the
patch changed nothing else in the payload, depots included); `full` DIFFERS at
every step where a firefighter row exists (positive control for exactly the
added key). It also records the union of firefighter_view row keys, so the
comparator can assert the key set grew by exactly ADDED.

_capture_frame is called on EVERY step, as the dashboard does, so fr.trails is
the real 60-point history. SESSION trails are reset per combo.

usage: _bm_payload.py <tag> [steps]      -> outputs/_bm_payload_<tag>.json
"""
from __future__ import annotations
import contextlib, copy, hashlib, io as _io, json, os, random, sys, time
os.environ.setdefault("MPLBACKEND", "Agg")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
import serve_dashboard as sd

ADDED = {"firefighter_view": ["exiting"]}      # panel keys this round adds


def params(wind, ft, vs):
    return {"NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2,
            "WIND_DIRECTION": wind, "BATCH_SIZE": 300,
            "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
            "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}


COMBOS = [("D/east/half", 101, params("east", 2, 2)),
          ("D/south/half", 101, params("south", 2, 2)),
          ("D/east/default", 101, params("east", None, None))]


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


def strip(frame: dict) -> dict:
    f = copy.deepcopy(frame)
    for view, keys in ADDED.items():
        for row in (f.get("panel") or {}).get(view) or []:
            for k in keys:
                row.pop(k, None)
    return f


def run(seed, p, steps):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng; wf.SYSTEM_RANDOM = rng; am.random = rng
    apply_scenario_config(cfv, wf, **p)
    sd.SESSION["trails"] = {}
    full, stripped, ffkeys, depots = [], [], set(), None
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel(); model.debug_log = False
        for s in range(steps + 1):
            if s:
                model.step()
            fr = sd._capture_frame(model, s)
            full.append(sha(fr)); stripped.append(sha(strip(fr)))
            for row in (fr.get("panel") or {}).get("firefighter_view") or []:
                ffkeys |= set(row.keys())
            if depots is None:
                depots = fr.get("depots")
    return {"full": full, "stripped": stripped, "ff_keys": sorted(ffkeys), "depots": depots,
            "full_all": sha(full), "stripped_all": sha(stripped)}


def main() -> int:
    tag = sys.argv[1]; steps = int(sys.argv[2]) if len(sys.argv) > 2 else 240
    out = {"tag": tag, "steps": steps, "python": sys.version, "written": time.time(), "combos": {}}
    for name, seed, p in COMBOS:
        t0 = time.time()
        out["combos"][name] = run(seed, p, steps)
        c = out["combos"][name]
        print("%-16s full %s stripped %s ff_keys %s (%.0f s)"
              % (name, c["full_all"][:12], c["stripped_all"][:12], c["ff_keys"], time.time() - t0), flush=True)
    json.dump(out, open(os.path.join(BASE, "_bm_payload_%s.json" % tag), "w"), indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
