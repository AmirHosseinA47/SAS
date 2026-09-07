"""Interior-hazard round: the two scenario-matrix tests that bound searcher
hazard exposure (strict fire/smoke steps <= 2 in 50 steps), run against any
checkout with an optional per-consumer dead-read replay, in seconds.

  test_no_crash_zero_victims      EDGE_CASES[0] (1 UAV, 0 victims), north, 50 steps
  test_scenario_a_no_5x5_camping  SCENARIO_A (2 UAVs, 3 victims), east, 50 steps

usage: _ih_testprobe.py --repo <checkout> [--dead f1,f2] [--set K=V ...] [--repeat N]
Same seeding as the tests (run_scenario seeds SYSTEM_RANDOM from SEED=42), so a
result is deterministic per (checkout, dead set).
"""
from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--dead", default="")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--steps", type=int, default=50)
    args = ap.parse_args()
    repo = os.path.abspath(args.repo)
    sys.path.insert(0, os.path.join(repo, "tests"))
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import common_fixed_variables as cfv  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    from wildfire_model import WildFireModel  # noqa: E402
    from src_extension.execution.uav_executor import UAVExecutor  # noqa: E402
    import victim_searcher_scenario_validation as vs  # noqa: E402
    assert os.path.abspath(wf.__file__).lower().startswith(repo.lower()), wf.__file__
    dead = [d.strip() for d in args.dead.split(",") if d.strip()]
    if dead:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _dim_hooks  # noqa: E402
        _dim_hooks.install(WildFireModel, UAVExecutor, dead=dead)
    extra = {}
    for item in args.set:
        k, v = item.split("=", 1)
        try:
            extra[k] = int(v)
        except ValueError:
            try:
                extra[k] = float(v)
            except ValueError:
                extra[k] = {"true": True, "false": False}.get(v.lower(), v)
    if extra:
        # applied on top of the scenario's own apply_scenario_config (which does
        # not touch these keys), before every run
        _orig = vs._configure_scenario

        def _cfg(**kw):
            _orig(**kw)
            for k, v in extra.items():
                setattr(cfv, k, v)
                setattr(wf, k, v)
        vs._configure_scenario = _cfg
    print("repo=%s dead=%s set=%s" % (repo, dead, extra))
    for name, scen, wind in (("edge/zero_victims", vs.EDGE_CASES[0], "north"), ("A/east", vs.SCENARIO_A, "east")):
        for i in range(args.repeat):
            r = vs.run_scenario(scenario_name=name, scenario=scen, wind=wind, steps=args.steps)
            m = r.metrics
            print("  %-18s run %d: strict_fire_smoke_steps=%s (limit 2) camping_5x5=%s unique_positions=%s failures=%s searcher=%s"
                  % (name, i + 1, m.get("strict_fire_smoke_steps"), m.get("camping_5x5"), m.get("unique_positions"),
                     r.failures, r.victim_searcher_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
