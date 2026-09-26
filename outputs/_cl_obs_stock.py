"""Carrying-leg round: the STOCK instrument - outputs/_ffr_harness.py through the sidecar.

Takes exactly _ffr_harness.py's command line. Installs the pass-through observers of
outputs/_cl_obs.py, runs the harness unchanged in this process, then writes
<out-without-.json>.clobs.json. Refuses any --set FM2P_* key (those belong to the CRN
instrument, _cl_obs_crn.py). See outputs/_cl_obs.py and outputs/_cl_tooling_spec.txt F.
"""
from __future__ import annotations

import sys

# The pool runs `$PY <launcher>` WITHOUT -B: no __pycache__ for _cl_obs or for the
# --repo checkout's modules it imports (rule A3). Set before any further import.
sys.dont_write_bytecode = True

import _cl_obs  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(_cl_obs.main("stock"))
