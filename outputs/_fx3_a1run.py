"""fix3a Part 1 - a full run of the A1 / A2 PROTOTYPES (outputs/_fx3_proto_a1.py, _fx3_proto_a2.py:
monkeypatches only) through outputs/_fx3_probe.py - or, with --b2/--b3, through outputs/_fx3_bproto.py
(the B2 / B3 prototype). NO SOURCE EDIT.

usage: _fx3_a1run.py --a1 R+S+D|none --a2 0|1 [--k K] [--b2 0|1 --b3 none|low|crit] [--hazard] -- <_sd_probe args>
"""
from __future__ import annotations

import os
import runpy
import sys


def main() -> int:
    argv = sys.argv[1:]
    cut = argv.index("--")
    opts = argv[:cut]
    os.environ["FX3_A1"] = opts[opts.index("--a1") + 1]
    os.environ["FX3_A2"] = opts[opts.index("--a2") + 1] if "--a2" in opts else "0"
    if "--k" in opts:
        os.environ["FX3_K"] = opts[opts.index("--k") + 1]
    here = os.path.dirname(os.path.abspath(__file__))
    repo = r"E:\Projects\SAS"
    sys.path.insert(0, repo)
    sys.path.insert(0, here)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import _fx3_proto_a1  # noqa: F401,E402  (installs the A1 patches named in FX3_A1)
    import _fx3_proto_a2  # noqa: F401,E402  (installs the A2 patches when FX3_A2 == "1")
    if "--b2" in opts:
        runner = os.path.join(here, "_fx3_bproto.py")
        b = ["--b2", opts[opts.index("--b2") + 1], "--b3", opts[opts.index("--b3") + 1]]
        mod = runpy.run_path(runner, run_name="fx3_bproto_module")
        sys.argv = [sys.argv[0]] + b + argv[cut:]
    else:
        mod = runpy.run_path(os.path.join(here, "_fx3_probe.py"), run_name="fx3_probe_module")
        sys.argv = [sys.argv[0]] + [a for a in opts if a == "--hazard"] + argv[cut:]
    return mod["main"]()


if __name__ == "__main__":
    sys.exit(main())
