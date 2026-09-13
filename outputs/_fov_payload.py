"""FOV-frame round, positive control layer A: digest the overlay payload.

The naive cell-colour digest CANNOT detect this change - serve_dashboard's
`cells` dict is built inside a Fire-only loop, so no UAV, victim or firefighter
can contribute a byte to it. It is therefore demoted to a NEGATIVE control (it
must be IDENTICAL), exactly the demotion _rh_control.py:26-28 records for the
mirror-image case, and this digest replaces it as the positive control.

What it covers is the data the overlay is drawn FROM, and nothing else:
  fov_radius / victim_flee_radius  the two constants /start publishes
  victims[].flee                   the per-victim eligibility flag
  firefighter_view[].nearest_fire_dist  the column that stands in for a frame

At the pre-patch commit all of these are absent, so the digest moves by
construction - which is the point: absence is what makes it a valid "before".

usage: _fov_payload.py <tag> <steps> <seed>
"""
from __future__ import annotations
import contextlib, hashlib, io as _io, json, os, random, sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
import serve_dashboard as sd

PARAMS = {"NUM_AGENTS": 3, "NUM_VICTIMS": 5, "NUM_FIREFIGHTERS": 3,
          "WIND_DIRECTION": "east", "BATCH_SIZE": 300,
          "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
          "NUM_FIRE_TRACKERS": 2, "NUM_VICTIM_SEARCHERS": 1}


def main() -> int:
    tag = sys.argv[1]
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 101
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng; wf.SYSTEM_RANDOM = rng; am.random = rng
    apply_scenario_config(cfv, wf, **PARAMS)

    per_step = []
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel(); model.debug_log = False
        for s in range(steps):
            model.step()
            fr = sd._capture_frame(model, s + 1)
            panel = fr.get("panel", {}) or {}
            per_step.append({
                "step": s + 1,
                "flee": [[v.get("id"), v.get("flee")] for v in fr.get("victims", [])],
                "ffdist": [[f.get("id"), f.get("nearest_fire_dist")]
                           for f in (panel.get("firefighter_view") or [])],
            })
    payload = {
        "fov_radius": int(getattr(cfv, "UAV_OBSERVATION_RADIUS", 8))
        if hasattr(sd, "_capture_frame") else None,
        # present only post-patch; absent pre-patch, which is the whole point
        "publishes_fov_radius": "fov_radius" in sd.HTML or "FOVR" in sd.HTML,
        "publishes_flee": any(v[1] is not None for st in per_step for v in st["flee"]),
        "publishes_ffdist": any(f[1] is not None for st in per_step for f in st["ffdist"]),
        "per_step": per_step,
    }
    blob = json.dumps(payload, sort_keys=True)
    out = {
        "tag": tag, "steps": steps, "seed": seed,
        "fovpayload_sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
        "publishes_fov_radius": payload["publishes_fov_radius"],
        "publishes_flee": payload["publishes_flee"],
        "publishes_ffdist": payload["publishes_ffdist"],
        "n_steps_captured": len(per_step),
        "sample_last": per_step[-1] if per_step else None,
    }
    path = os.path.join(BASE, "_fov_payload_%s.json" % tag)
    json.dump(out, open(path, "w"), indent=2, sort_keys=True)
    for k in ("fovpayload_sha256", "publishes_fov_radius", "publishes_flee",
              "publishes_ffdist"):
        print("%-24s %s" % (k, out[k]))
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
