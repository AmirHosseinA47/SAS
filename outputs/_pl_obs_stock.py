"""Planner round: the STOCK instrument - outputs/_pl_obs.py around outputs/_ffr_harness.py."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True   # no __pycache__ for the sidecar or the --repo checkout's modules

import _pl_obs  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(_pl_obs.main("stock"))
