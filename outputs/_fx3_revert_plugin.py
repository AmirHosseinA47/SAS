"""fix3a revert check - a pytest plugin that forces the switches named in FX3_REVERT (comma list) to 0 in
common_fixed_variables for the whole session. A test that monkeypatches the same switch itself still wins.

usage (repo root): set PYTHONPATH=outputs; FX3_REVERT=SEARCHER_CORNER_ESCAPE pytest -p _fx3_revert_plugin ...
"""
from __future__ import annotations

import os


def pytest_configure(config):  # noqa: D401 - pytest hook
    import common_fixed_variables as cfv

    for name in [n.strip() for n in (os.environ.get("FX3_REVERT") or "").split(",") if n.strip()]:
        setattr(cfv, name, 0)
