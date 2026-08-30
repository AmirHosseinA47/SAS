"""Is the `if status != "route_blocked":` guard at wildfire_model.py:3455
load-bearing?  Run unassign() on a route_blocked marker and read the managed
state AFTER the call, then compare against the same call with the guard
neutralised in-memory.  Read-only w.r.t. source."""
import os, sys, contextlib, io as _io
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wildfire_model import WildFireModel, PhysicalRescueCommand

with contextlib.redirect_stdout(_io.StringIO()):
    m = WildFireModel()
    m.debug_log = False

ff_id, ff = next(iter(m.firefighter_marker_agents.items()))
st = m.managed_firefighters.get(ff_id)
print("firefighter:", ff_id)

def show(tag):
    print("  %-26s marker.status=%-14s state.availability=%-12s state.route_state=%s"
          % (tag, getattr(ff, "status", None),
             getattr(st, "availability", None), getattr(st, "route_state", None)))

# --- case A: a NON-blocked unit goes through unassign (the general behaviour)
ff.status = "en_route"; ff.assigned = True; ff.target_pos = (10, 10)
st.availability = "assigned"; st.route_state = "en_route"
show("A before unassign")
m.apply_physical_rescue_command(PhysicalRescueCommand(
    action="unassign", victim_id="", firefighter_id=ff_id, reason="probe", metadata={}))
show("A after  unassign")

# --- case B: a route_blocked unit goes through unassign (the exception)
ff.status = "route_blocked"; ff.assigned = True; ff.target_pos = (10, 10)
st.availability = "assigned"; st.route_state = "en_route"
show("B before unassign")
m.apply_physical_rescue_command(PhysicalRescueCommand(
    action="unassign", victim_id="", firefighter_id=ff_id, reason="probe", metadata={}))
show("B after  unassign  (guard ON)")

# --- case C: same, but with the guard's effect forced (simulate guard removed)
ff.status = "route_blocked"; ff.assigned = True; ff.target_pos = (10, 10)
st.availability = "assigned"; st.route_state = "en_route"
st.route_state = "idle"; st.availability = "available"   # what the guard suppresses
print("  C forced idle/available, now calling the same sync unassign ends with:")
m._sync_firefighter_operational_knowledge([ff_id])
show("C after  sync")

print()
print("=> If B and C agree, the guard changes nothing durable: the sync at the")
print("   end of the unassign branch recomputes both fields from marker.status.")
