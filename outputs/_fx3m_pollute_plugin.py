"""fix3a merge - test-isolation check for tests/test_wind_aware_trajectory_regression.py (the maintainer's (iv)).
A pytest plugin that POLLUTES the module globals at session start with exactly the state the full suite used to
leave behind (outputs/_fx3r_state_suite_*.json: variable wind west -> east p 0.8, 2 UAVs, 3 victims, BATCH_SIZE
99999), then records, at the start of every test body, what the test actually sees. The test file must pin its
own configuration, so what it sees must be the source defaults, whatever was left behind.

usage (repo root): PYTHONPATH=outputs pytest -p _fx3m_pollute_plugin tests/test_wind_aware_trajectory_regression.py
writes outputs/_fx3m_isolation_seen.json
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
POLLUTION = {"FIXED_WIND": False, "FIRST_DIR": "west", "FIRST_DIR_PROB": 0.8, "SECOND_DIR": "east",
             "NUM_AGENTS": 2, "NUM_VICTIMS": 3, "BATCH_SIZE": 99999}
SEEN: dict = {}


def pytest_configure(config):  # noqa: D401 - pytest hook
    import common_fixed_variables as cfv
    import wildfire_model as wf

    for mod in (cfv, wf):
        for key, value in POLLUTION.items():
            setattr(mod, key, value)


def pytest_runtest_call(item):  # noqa: D401 - pytest hook (after fixtures, before the test body)
    import common_fixed_variables as cfv
    import wildfire_model as wf

    SEEN[item.name] = {"%s.%s" % (m, k): getattr(mod, k, None)
                       for m, mod in (("cfv", cfv), ("wf", wf)) for k in POLLUTION}


def pytest_unconfigure(config):  # noqa: D401 - pytest hook
    with open(os.path.join(HERE, "_fx3m_isolation_seen.json"), "w", encoding="utf-8") as fh:
        json.dump(SEEN, fh, indent=1, sort_keys=True)
