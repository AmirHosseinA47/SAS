"""fix3a round 2 - read-only pytest plugin: when a test whose name contains FX3R_DUMP_MATCH (default "diverge")
starts, dump every UPPERCASE module attribute of common_fixed_variables and wildfire_model (JSON-safe values) to
outputs/_fx3r_state_<FX3R_DUMP_TAG>_<test name>.json. Used to find the global state earlier tests leave behind
(the two wind-trajectory tests fail only in the full-suite order). Changes nothing.

usage (repo root): PYTHONPATH=outputs FX3R_DUMP_TAG=suite pytest -p _fx3r_state_plugin ...
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _safe(value):
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value][:50]
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in list(value.items())[:50]}
    return repr(value)[:80]


def pytest_runtest_setup(item):  # noqa: D401 - pytest hook
    match = os.environ.get("FX3R_DUMP_MATCH", "diverge")
    if match not in item.name:
        return
    import common_fixed_variables as cfv
    import wildfire_model as wf

    state = {}
    for mod_name, mod in (("cfv", cfv), ("wf", wf)):
        for name in dir(mod):
            if name.isupper():
                state["%s.%s" % (mod_name, name)] = _safe(getattr(mod, name))
    tag = os.environ.get("FX3R_DUMP_TAG", "run")
    path = os.path.join(HERE, "_fx3r_state_%s_%s.json" % (tag, item.name))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True, indent=0)
