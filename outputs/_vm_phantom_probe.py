"""Is the "rescue started without contact" defect pre-existing at 9c3eac6?

Observed in the guard-2 arm, D/east/half 303: ff_unit_1 and ff_unit_0 were BOTH
assigned to victim_0; ff_unit_0 rescued it at step 101; ff_unit_1 was never
unassigned, kept walking to the cell victim_0 had occupied, "arrived" at step
148 against empty ground and completed a second, phantom exit.

The question this probe settles is whether victim movement caused that, or
merely changed which unit survived long enough to expose it. It drives the
model directly - no victim ever moves - and asks two things of whichever
checkout is passed with --repo:

  Q1  Does the executor permit assigning ONE victim to TWO firefighters?
  Q2  When the first firefighter completes the rescue, is the second one
      unassigned - or does it walk to the stale target and start exiting
      against a victim that is no longer there?

usage: _vm_phantom_probe.py --repo <checkout>
Read-only with respect to the repo; it mutates only its own model instance.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
import random
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--seed", type=int, default=303)
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")

    import agents as am
    import common_fixed_variables as cfv
    import wildfire_model as wf
    from wildfire_model import PhysicalRescueCommand, WildFireModel

    for mod in (am, cfv, wf):
        path = os.path.abspath(getattr(mod, "__file__", ""))
        if not path.lower().startswith(repo.lower()):
            print("IMPORT MISMATCH: %s from %s" % (mod.__name__, path))
            return 3

    has_flee = hasattr(am.Victim, "_flee_approaching_fire")
    print("checkout          : %s" % repo)
    print("victim flee rule  : %s" % ("PRESENT" if has_flee else "ABSENT (pre-feature)"))

    rng = random.Random(args.seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
    model.debug_log = False

    vid = "victim_0"
    victim = model.victim_marker_agents[vid]
    ff_a = model.firefighter_marker_agents["ff_unit_0"]
    ff_b = model.firefighter_marker_agents["ff_unit_1"]

    # put the victim somewhere clear and stand both units two cells away
    cell = (25, 25)
    model.grid.move_agent(victim, cell)
    if hasattr(victim, "spawn_cell"):
        victim.spawn_cell = cell
    if hasattr(victim, "leash_anchor"):
        victim.leash_anchor = cell
    state = model.managed_victims[vid]
    state.confirmed = True
    state.status = "confirmed"
    state.rescue_assigned = False
    victim.status = "confirmed"
    model.grid.move_agent(ff_a, (23, 25))
    model.grid.move_agent(ff_b, (27, 25))
    for ff in (ff_a, ff_b):
        ff.dead = False
        ff.assigned = False
        ff.exiting = False
        ff.target_pos = None
        ff.rescued_victim = None
        ff.status = "available"

    def assign(ff_id):
        with contextlib.redirect_stdout(io.StringIO()):
            return model.apply_physical_rescue_command(
                PhysicalRescueCommand(
                    action="assign", victim_id=vid, firefighter_id=ff_id,
                    reason="test_initial", metadata={"victim_marker": victim},
                )
            )

    ok_a = assign("ff_unit_0")
    ok_b = assign("ff_unit_1")
    both = bool(
        ok_a and ok_b
        and ff_a.rescued_victim is victim
        and ff_b.rescued_victim is victim
    )
    print()
    print("Q1  one victim assigned to two firefighters : %s" % ("YES" if both else "no"))
    print("      ff_unit_0 assign ok=%s target=%s" % (ok_a, ff_a.target_pos))
    print("      ff_unit_1 assign ok=%s target=%s" % (ok_b, ff_b.target_pos))
    if not both:
        print("      -> executor refuses the double assignment on this checkout")
        return 0

    # ff_unit_0 finishes the rescue; the victim leaves the grid exactly as it
    # does in a real run.
    with contextlib.redirect_stdout(io.StringIO()):
        model._finalize_rescued_victim(vid, victim, firefighter_id="ff_unit_0")
        try:
            model.grid.remove_agent(victim)
        except Exception:
            pass
        model.schedule.remove(victim)

    print()
    print("after ff_unit_0 completes the rescue:")
    print("      victim status=%s pos=%s" % (victim.status, victim.pos))
    print("      ff_unit_1 assigned=%s target=%s rescued_victim=%s"
          % (ff_b.assigned, ff_b.target_pos,
             getattr(ff_b.rescued_victim, "victim_id", None)))

    still_bound = bool(ff_b.assigned and ff_b.rescued_victim is victim)
    print()
    print("Q2  second unit still bound to the rescued victim : %s"
          % ("YES" if still_bound else "no - it was unassigned"))
    if not still_bound:
        return 0

    # walk it in and see whether it starts exiting against empty ground
    steps = 0
    for steps in range(1, 40):
        ff_b.advance()
        if ff_b.exiting:
            break
    v_pos = getattr(ff_b.rescued_victim, "pos", None)
    contact = v_pos is not None and tuple(v_pos) == tuple(ff_b.pos or ())
    print("      ff_unit_1 walked %d steps, now at %s, exiting=%s"
          % (steps, ff_b.pos, ff_b.exiting))
    print("      victim position at that moment: %s" % (v_pos,))
    print()
    print("Q2 RESULT: rescue started WITHOUT contact = %s"
          % ("YES - phantom exit reproduced" if (ff_b.exiting and not contact) else "no"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
