"""Flip round: prove test_accessors_survive_junk_values binds all ten fallback sites.

For each of the ten literal sites the dcD flip moved in agents.py (getattr default,
except branch, out-of-range mapping), compile a MUTANT accessor with the pre-flip
literal put back, swap it into the agents module, and run the test function with a
real pytest MonkeyPatch. Every mutant must be KILLED by its own labelled assertion;
the unmutated control must pass. Nothing on disk is modified.

  .venv/Scripts/python.exe -B outputs/_flip_fallback_mutants.py
"""
import inspect
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("MPLBACKEND", "Agg")

import agents  # noqa: E402
from _pytest.monkeypatch import MonkeyPatch  # noqa: E402
import test_base_station as T  # noqa: E402

MUTANTS = [
    ("MODE getattr default", "base_station_mode",
     r'"BASE_STATION_MODE", 3\)', '"BASE_STATION_MODE", 0)'),
    ("MODE except branch", "base_station_mode", r'return 3\n', 'return 0\n'),
    ("DEPOTS getattr default", "base_station_depots",
     r'"BASE_STATION_DEPOTS", 9\)', '"BASE_STATION_DEPOTS", 0)'),
    ("SPLIT getattr default", "base_station_spawn_split",
     r'"BASE_STATION_SPAWN_SPLIT", 2\)', '"BASE_STATION_SPAWN_SPLIT", 0)'),
    ("SPLIT except branch", "base_station_spawn_split",
     r'return 2\n    return', 'return 0\n    return'),
    ("SPLIT out-of-range", "base_station_spawn_split", r'else 2', 'else 0'),
    ("RESERVE getattr default", "uav_return_to_base_reserve",
     r'RESERVE", 0\.0\)', 'RESERVE", 60.0)'),
    ("RESERVE except branch", "uav_return_to_base_reserve",
     r'return 0\.0\n', 'return 60.0\n'),
    ("MARGIN getattr default", "base_station_return_margin",
     r'MARGIN", 39\.23\)', 'MARGIN", 5.0)'),
    ("MARGIN except branch", "base_station_return_margin",
     r'return 39\.23\n', 'return 5.0\n'),
]


def mutate(fname, pattern, repl):
    src = inspect.getsource(getattr(agents, fname))
    new, n = re.subn(pattern, repl, src, count=1)
    if n != 1:
        raise SystemExit("PATTERN NOT FOUND %s %s" % (fname, pattern))
    ns = {}
    exec(compile(new, "mutant:" + fname, "exec"), agents.__dict__, ns)
    return ns[fname]


def main():
    mp = MonkeyPatch()
    try:
        T.test_accessors_survive_junk_values(mp)
    finally:
        mp.undo()
    print("CONTROL unmutated accessors: PASS")
    killed = 0
    for label, fname, pat, repl in MUTANTS:
        orig = getattr(agents, fname)
        setattr(agents, fname, mutate(fname, pat, repl))
        mp = MonkeyPatch()
        try:
            T.test_accessors_survive_junk_values(mp)
            print("SURVIVED  %s" % label)
        except AssertionError as exc:
            killed += 1
            msg = (str(exc).splitlines() or ["<no message>"])[0]
            print("KILLED    %-24s by: %s" % (label, msg))
        finally:
            mp.undo()
            setattr(agents, fname, orig)
    print("MUTANTS KILLED %d/%d" % (killed, len(MUTANTS)))
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
