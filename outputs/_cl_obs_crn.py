"""Carrying-leg round: the CRN instrument - outputs/_fm2_probe_harness.py through the sidecar.

Takes exactly _fm2_probe_harness.py's command line and requires exactly one
--set FM2P_CRN=1. Installs the pass-through observers of outputs/_cl_obs.py, runs the
fm2 probe harness unchanged in this process (it patches Fire.step's draw and runs
outputs/_ffr_harness.py, then adds its "fm2p" block to the JSON), then writes
<out-without-.json>.clobs.json. See outputs/_cl_obs.py and outputs/_cl_tooling_spec.txt F.
"""
from __future__ import annotations

import sys

# The pool runs `$PY <launcher>` WITHOUT -B: no __pycache__ for _cl_obs or for the
# --repo checkout's modules it imports (rule A3). Set before any further import.
sys.dont_write_bytecode = True

import _cl_obs  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(_cl_obs.main("crn"))
