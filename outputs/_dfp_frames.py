# -*- coding: utf-8 -*-
"""Non-burnable-depot round: capture the two dashboard frames the page gate renders.

Both come from ONE model state, so the before/after pair differs only by the
rendering change and not by a different fire:

  _dfp_frame_post.json   serve_dashboard._capture_frame as it is now
  _dfp_frame_pre.json    the same state with _cell_color monkey-patched back to
                         the 6281542 body (compiled from git, not retyped) and
                         the new `nofuel` key removed - i.e. what 6281542's
                         server would have sent for this exact state

Blob shape is outputs/_bm_page_e2e.py's, so the existing driver conventions work.
The model is stepped with _capture_frame called on EVERY step, like
outputs/_bm_capture2.py, so fr.trails is the real walked history.

usage: _dfp_frames.py [seed] [wind] [step]
"""
from __future__ import annotations

import contextlib
import io as _io
import json
import os
import random
import sys

os.environ.setdefault("MPLBACKEND", "Agg")
BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)
sys.path.insert(0, REPO)
sys.path.insert(0, BASE)

import agents as am  # noqa: E402
import common_fixed_variables as cfv  # noqa: E402
import wildfire_model as wf  # noqa: E402
import serve_dashboard as sd  # noqa: E402
from _dfp_payload import old_cell_color  # noqa: E402
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config  # noqa: E402
from wildfire_model import WildFireModel  # noqa: E402


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 101
    wind = sys.argv[2] if len(sys.argv) > 2 else "east"
    step = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    old_fn, _body = old_cell_color()

    cfv.BASE_STATION_FIREPROOF = 1
    P = {"NUM_AGENTS": 3, "NUM_VICTIMS": 5, "NUM_FIREFIGHTERS": 3,
         "WIND_DIRECTION": wind, "BATCH_SIZE": 300,
         "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
         "NUM_FIRE_TRACKERS": 2, "NUM_VICTIM_SEARCHERS": 1,
         "BASE_STATION_FIREPROOF": 1}
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **P)
    sd.SESSION["trails"] = {}
    W, H = int(getattr(cfv, "WIDTH", 50)), int(getattr(cfv, "HEIGHT", 50))
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        for i in range(step + 1):
            if i:
                model.step()
            post = sd._capture_frame(model, i)
        real = sd._cell_color
        sd._cell_color = old_fn
        try:
            pre = sd._capture_frame(model, step)
        finally:
            sd._cell_color = real
    pre.pop("nofuel", None)

    common = {"width": W, "height": H, "cs": 560.0 / W,
              "fov_radius": int(getattr(cfv, "UAV_OBSERVATION_RADIUS", 8)),
              "victim_flee_radius": int(am.victim_flee_trigger_distance()),
              "seed": seed, "wind": wind, "steps": step, "params": P}
    n_cleared = len(post.get("nofuel") or [])
    for name, fr in (("pre", pre), ("post", post)):
        blob = dict(common, frame=fr)
        p = os.path.join(BASE, "_dfp_frame_%s.json" % name)
        json.dump(blob, open(p, "w"), sort_keys=True)
        print("wrote %s  cells=%d nofuel=%d" % (p, len(fr["cells"]), len(fr.get("nofuel") or [])))
    changed = sum(1 for k in post["cells"] if post["cells"][k] != pre["cells"][k])
    print("cleared cells in this state: %d ; cells whose colour differs pre/post: %d"
          % (n_cleared, changed))
    if n_cleared == 0:
        raise SystemExit("no cleared cells in this state - the capture proves nothing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
