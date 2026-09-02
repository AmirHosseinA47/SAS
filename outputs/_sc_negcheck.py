"""Is the updated assertion actually load-bearing?

Runs the SCORCHED fixture through the PRE-PATCH renderer extracted with
`git show HEAD:main.py`, and checks that the new assertion would have FAILED
against it. If it passes against both old and new code, it locks nothing.
"""
from __future__ import annotations
import importlib.util, os, subprocess, sys, tempfile
os.environ.setdefault("MPLBACKEND", "Agg")

BASE_COMMIT = os.environ.get("SC_BASE_COMMIT", "a89a2ab")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import agents
from common_fixed_variables import BURNING_RATE
from test_executor_routing_and_burnt import _fire_model_stub

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m

def scorched_fixture(uid):
    model = _fire_model_stub()
    fire = agents.Fire(unique_id=uid, model=model, burning=False)
    fire.has_burned = True
    fire.fuel = BURNING_RATE * 3
    fire.burnt = False
    fire.smoke = agents.Smoke(fire_cell_fuel=fire.fuel)
    return fire

def burnt_fixture(uid):
    model = _fire_model_stub()
    fire = agents.Fire(unique_id=uid, model=model, burning=False)
    fire.burnt = True
    fire.fuel = 0
    fire.smoke = agents.Smoke(fire_cell_fuel=0)
    return fire

# Extract the pre-patch renderer straight from git rather than keeping a stale
# copy of main.py checked in beside this script.
_tmp = tempfile.mkdtemp(prefix="sc_old_")
_old_main = os.path.join(_tmp, "main.py")
with open(_old_main, "wb") as fh:
    fh.write(subprocess.check_output(["git", "show", "%s:main.py" % BASE_COMMIT], cwd=ROOT))
old = load(_old_main, "main_old")
new = load(os.path.join(ROOT, "main.py"), "main_new")

print("SCORCHED fixture (has_burned=True, burnt=False, fuel>0)")
co = old.agent_portrayal(scorched_fixture(101))["Color"]
cn = new.agent_portrayal(scorched_fixture(102))["Color"]
print("  pre-patch renderer (%s) -> %s" % (BASE_COMMIT, co))
print("  post-patch renderer               -> %s" % cn)
print("  new assertion == '#895e00' against OLD code: %s   <- must be False"
      % (co == "#895e00"))
print("  new assertion == '#895e00' against NEW code: %s   <- must be True"
      % (cn == "#895e00"))
print("  new assertion != '#2b2b2b' against OLD code: %s   <- must be False"
      % (co != "#2b2b2b"))

print("\nBURNT fixture (burnt=True, fuel=0) - unchanged test, must not move")
bo = old.agent_portrayal(burnt_fixture(103))["Color"]
bn = new.agent_portrayal(burnt_fixture(104))["Color"]
print("  pre-patch  -> %s" % bo)
print("  post-patch -> %s" % bn)
print("  unchanged: %s   <- must be True" % (bo == bn == "#2b2b2b"))

good = (co != "#895e00") and (cn == "#895e00") and (co == "#2b2b2b") and (bo == bn == "#2b2b2b")
print("\nVERDICT: the updated assertion is %s"
      % ("LOAD-BEARING - it fails against the old behaviour and passes against the new"
         if good else "*** VACUOUS OR WRONG ***"))
sys.exit(0 if good else 1)
