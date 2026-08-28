"""What do the route_blocked CONSUMERS actually do when the signal is live?

Read-only w.r.t. production source. Builds a real WildFireModel, dispatches a
firefighter to a victim, fires route_blocked through the real
_mark_route_blocked path, and reports what every downstream consumer does -
replacement pathway, planner pool filter, alert_manager, adaptation_manager,
rescue_executor - plus whether the unit can ever return to service.
"""
from __future__ import annotations
import contextlib, io as _io, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel


def build(seed=7, n_ff=2):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, NUM_AGENTS=4, NUM_VICTIMS=4, NUM_FIREFIGHTERS=n_ff,
                          WIND_DIRECTION="east", BATCH_SIZE=300,
                          FIRE_SPREAD_MULTIPLIER=0.75, PROBABILITY_MAP=False,
                          NUM_FIRE_TRACKERS=2, NUM_VICTIM_SEARCHERS=2)
    with contextlib.redirect_stdout(_io.StringIO()):
        m = WildFireModel()
        m.debug_log = False
    return m


def snap(m, label):
    rows = []
    for fid, ff in (m.firefighter_marker_agents or {}).items():
        rows.append("      %-12s status=%-13s assigned=%-5s target=%-10s rv=%-8s "
                    "exiting=%-5s dispatchable=%s"
                    % (fid, getattr(ff, "status", None), getattr(ff, "assigned", None),
                       str(getattr(ff, "target_pos", None)),
                       "yes" if getattr(ff, "rescued_victim", None) is not None else "no",
                       getattr(ff, "exiting", None),
                       m._firefighter_available_for_dispatch(ff)))
    print("   %s" % label)
    for r in rows:
        print(r)


def victim_view(m):
    out = []
    for vid, st in (m.managed_victims or {}).items():
        mk = (m.victim_marker_agents or {}).get(vid)
        out.append("%s:state=%s/marker=%s" % (
            vid, str(getattr(st, "status", "")).lower(),
            str(getattr(mk, "status", "")).lower() if mk is not None else "-"))
    return " ".join(out)


def run_to_dispatch(m, max_steps=200):
    """Step until some firefighter is actually assigned to a victim."""
    for s in range(1, max_steps + 1):
        with contextlib.redirect_stdout(_io.StringIO()):
            m.step()
        for fid, ff in (m.firefighter_marker_agents or {}).items():
            if getattr(ff, "assigned", False) and getattr(ff, "rescued_victim", None) is not None:
                return s, fid, ff
    return None, None, None


def main():
    print("=" * 78)
    print("route_blocked CONSUMER BEHAVIOUR UNDER A LIVE SIGNAL")
    print("=" * 78)

    m = build()
    step, fid, ff = run_to_dispatch(m)
    if ff is None:
        print("no dispatch occurred within the step budget; aborting")
        return
    vid = m._victim_id_from_agent(ff.rescued_victim)
    print("\n1. DISPATCH ESTABLISHED at step %s: %s -> %s" % (step, fid, vid))
    snap(m, "before firing:")
    print("      victims: %s" % victim_view(m))

    n_alerts_before = 0
    try:
        alerts = m.get_dashboard_state().get("alert_list", []) or []
        n_alerts_before = len(alerts)
    except Exception:
        pass

    print("\n2. FIRING route_blocked through the real _mark_route_blocked path")
    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf):
        ff._mark_route_blocked()
    printed = buf.getvalue().strip().splitlines()
    print("   stdout emitted by the handler:")
    for line in printed[:8]:
        print("      | %s" % line)
    snap(m, "immediately after firing:")
    print("      victims: %s" % victim_view(m))

    print("\n3. REPLACEMENT PATHWAY")
    replaced = [f for f, x in (m.firefighter_marker_agents or {}).items()
                if f != fid and getattr(x, "assigned", False)
                and getattr(x, "rescued_victim", None) is not None]
    print("   other firefighters now assigned: %s" % (replaced or "NONE"))
    print("   _blocked_replacement_attempted: %s" % sorted(m._blocked_replacement_attempted))
    evs = [e for e in (getattr(m, "_rescue_event_log", []) or [])
           if e.get("event_type") == "route_blocked"]
    print("   route_blocked rescue events recorded: %d %s"
          % (len(evs), [(e.get("victim_id"), e.get("firefighter_id")) for e in evs]))

    print("\n4. ALERTS")
    try:
        alerts = m.get_dashboard_state().get("alert_list", []) or []
        rb = [a for a in alerts if str(a.get("alert_type", "")) == "route_blocked"]
        print("   total alerts %d (was %d); route_blocked alerts: %d"
              % (len(alerts), n_alerts_before, len(rb)))
        for a in rb[:4]:
            print("      | severity=%s target=%s src=%s msg=%s"
                  % (a.get("severity"), a.get("target_id"),
                     a.get("source_module"), a.get("message")))
    except Exception as exc:
        print("   dashboard state failed: %r" % (exc,))

    print("\n5. PLANNER POOL / SNAPSHOT VIEW")
    sn = m.get_rescue_operational_snapshot()
    for f, e in (sn.get("firefighters", {}) or {}).items():
        print("      %-12s available=%-5s assigned=%-5s route_blocked=%-5s dead=%s"
              % (f, e.get("available"), e.get("assigned"),
                 e.get("route_blocked"), e.get("dead")))

    print("\n6. adaptation_manager / rescue_executor status views")
    from src_extension.execution.rescue_executor import RescueExecutor
    print("      rescue_executor._firefighter_is_active_physical(%s) = %s"
          % (fid, RescueExecutor._firefighter_is_active_physical(ff)))
    inv_buf = _io.StringIO()
    with contextlib.redirect_stdout(_io.StringIO()):
        old_err, sys.stderr = sys.stderr, inv_buf
        try:
            m.adaptation_manager.run_cycle(m, phase="post_move")
        finally:
            sys.stderr = old_err
    inv = inv_buf.getvalue().strip()
    print("      RescueInvariant complaints during a post_move cycle: %s"
          % (inv.splitlines()[:4] if inv else "none"))

    print("\n7. CAN THE BLOCKED UNIT EVER RETURN TO SERVICE? (latch check)")
    print("   stepping 60 more steps and watching its status ...")
    seen = []
    with contextlib.redirect_stdout(_io.StringIO()):
        for _ in range(60):
            m.step()
            seen.append(str(getattr(ff, "status", "")).lower())
    uniq = []
    for s in seen:
        if not uniq or uniq[-1] != s:
            uniq.append(s)
    print("   status trajectory: %s" % " -> ".join(uniq))
    print("   dead=%s  assigned=%s  target=%s  dispatchable=%s"
          % (getattr(ff, "dead", None), getattr(ff, "assigned", None),
             getattr(ff, "target_pos", None),
             m._firefighter_available_for_dispatch(ff)))
    snap(m, "final fleet:")
    print("   victims: %s" % victim_view(m))


main()
