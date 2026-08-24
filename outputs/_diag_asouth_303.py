"""A/south regression diagnosis (read-only). Reuses the FIX14 target-following
probe verbatim; adds a NOHOLD mode that neutralizes _apply_target_hold at
module scope so the same tree can be run as "x-clamp alone" (fix13-equivalent).

Usage: python outputs/_diag_asouth_303.py worker <seed> <hold|nohold> <out.json>
       python outputs/_diag_asouth_303.py            # all 5 seeds x 2 modes
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

SEEDS = [101, 202, 303, 404, 505]
STEPS = 240


def _load_probe():
    spec = importlib.util.spec_from_file_location(
        "_tf_probe", os.path.join(_HERE, "_diag_target_following_FIX14.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_tf_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


def worker(seed: int, mode: str, out_json: str) -> int:
    probe = _load_probe()
    GEN = probe.GEN
    if mode == "nohold":
        # x-clamp alone: the finalized target passes through untouched, and no
        # commit_* state is ever written. Module-level, no production edit.
        GEN._apply_target_hold = lambda final, wind_state, **kw: final
    res = probe.run_one("A", "south", seed, STEPS)
    res["mode"] = mode
    c = res["counters"]
    print("mode=%s seed=%d" % (mode, seed), flush=True)
    for k in ("gen_calls_searcher", "advance_calls", "commit_calls", "bonus_calls_total"):
        print("  %-24s %d" % (k, c.get(k, 0)), flush=True)
        if not c.get(k, 0):
            print("PATCH VERIFICATION FAILED: %s == 0" % k, flush=True)
            return 3
    with open(out_json, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f)
    print("wrote %s (%.1fs)" % (out_json, res["elapsed_s"]), flush=True)
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "worker":
        return worker(int(argv[1]), argv[2], argv[3])
    rc_all = 0
    for mode in ("hold", "nohold"):
        for seed in SEEDS:
            out_json = os.path.join(_HERE, "_as_%s_%d.json" % (mode, seed))
            log = out_json.replace(".json", ".log")
            t0 = time.time()
            env = dict(os.environ, PYTHONUNBUFFERED="1")
            with open(log, "w", encoding="utf-8", newline="\n") as lf:
                p = subprocess.run(
                    [sys.executable, __file__, "worker", str(seed), mode, out_json],
                    env=env, cwd=_ROOT, stdout=lf, stderr=subprocess.STDOUT,
                )
            print("DONE %s seed=%d exit=%d %.1fs" % (mode, seed, p.returncode, time.time() - t0), flush=True)
            rc_all = rc_all or p.returncode
    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())
