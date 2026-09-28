"""mf1 round (fix1 session 1), Part 1 design probe - DIAGNOSIS ONLY, no source change.

Runs outputs/_sd_probe.py (the sysdebug invariant probe: evaluate_scenarios params,
per-step UAV battery / rtb rows, fail-safe mode + reasons, analyzer trigger counts)
with ONE in-process patch: every UAV is constructed with
battery_level = MF1_LAUNCH_FRAC * 100 (and its battery_status label recomputed from
the UAV's own thresholds), i.e. the "reduced launch battery" candidate for scenario B.
MF1_LAUNCH_FRAC unset or 1 -> no patch at all (the control arm is the stock probe).

usage: _mf1_bprobe.py <launch_frac> <_sd_probe args...>
"""
from __future__ import annotations

import os
import sys

REPO = r"E:\Projects\SAS"


def main() -> int:
    frac = float(sys.argv[1])
    rest = sys.argv[2:]
    sys.path.insert(0, REPO)
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am  # noqa: E402

    if frac != 1.0:
        orig_init = am.UAV.__init__

        def _init(self, unique_id, model):
            orig_init(self, unique_id, model)
            self.battery_level = max(0.0, min(100.0, 100.0 * frac))
            # 51c5165 had per-UAV thresholds (30 / 15); fix1 item 2 moved them to one source.
            if hasattr(am, "battery_status_for"):
                self.battery_status = am.battery_status_for(self.battery_level)
            elif self.battery_level <= self.battery_critical_threshold:
                self.battery_status = "critical"
            elif self.battery_level <= self.battery_low_threshold:
                self.battery_status = "low"
            else:
                self.battery_status = "normal"

        am.UAV.__init__ = _init
    import _sd_probe  # noqa: E402

    sys.argv = [os.path.join(here, "_sd_probe.py")] + rest
    return _sd_probe.main()


if __name__ == "__main__":
    raise SystemExit(main())
