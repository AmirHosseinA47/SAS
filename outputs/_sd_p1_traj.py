"""sysdebug Part 1: replay the two wind-trajectory regression tests with per-step detail.

Runs the test module's own _run_wind_simulation (same seeding, same setup, same
BASE_STATION_MODE 0 pin the tests apply through monkeypatch) and prints, per step, the
searcher's position, executed action, path-decision option id and its target, and the
wind_aware_victim_search option's target. Read-only; nothing in the model is changed
beyond what the test itself does.

usage: _sd_p1_traj.py north south [steps]
"""
import os
import sys

sys.path.insert(0, r"E:\Projects\SAS")
sys.path.insert(0, r"E:\Projects\SAS\tests")
os.environ.setdefault("MPLBACKEND", "Agg")

import common_fixed_variables as cfv  # noqa: E402
import test_wind_aware_trajectory_regression as T  # noqa: E402


def run(wind, steps):
    cfv.BASE_STATION_MODE = 0  # the tests' _pin_centre_spawn
    T._seed_deterministic_environment(wind, seed=T.DEFAULT_SEED)
    model = T.WildFireModel()
    T._apply_model_wind(model, wind)
    T._configure_no_live_victims(model)
    vs = T._victim_searcher_id(model)
    agent = T._uav_agent(model, vs)
    rows = []
    for s in range(steps):
        model.step()
        d = T._latest_path_decision(model, vs)
        ctx = getattr(d, "uncertainty_context", None) or {}
        rows.append((s + 1, tuple(agent.pos), T._last_exec_action(model, vs),
                     getattr(d, "selected_option_id", None),
                     ctx.get("target_position"), ctx.get("target_region"),
                     T._latest_wind_option_target(model),
                     str(getattr(model.wind, "wind_direction", "?"))))
    return rows


def main():
    a, b = sys.argv[1], sys.argv[2]
    steps = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    ra, rb = run(a, steps), run(b, steps)
    print("step | %s: pos action option target_pos target_region windopt wind || %s: same" % (a, b))
    for x, y in zip(ra, rb):
        print(x, "||", y[1:])
    print("SUMMARY %s windopt targets:" % a, sorted(set(r[6] for r in ra if r[6])))
    print("SUMMARY %s windopt targets:" % b, sorted(set(r[6] for r in rb if r[6])))
    print("SUMMARY final_target %s=%s %s=%s" % (a, ra[-1][4] or ra[-1][5], b, rb[-1][4] or rb[-1][5]))


if __name__ == "__main__":
    main()
