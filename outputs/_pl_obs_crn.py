"""Planner round: the CRN instrument - outputs/_pl_obs.py around outputs/_fm2_probe_harness.py (requires exactly one --set FM2P_CRN=1)."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True   # no __pycache__ for the sidecar or the --repo checkout's modules

import _pl_obs  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(_pl_obs.main("crn"))
