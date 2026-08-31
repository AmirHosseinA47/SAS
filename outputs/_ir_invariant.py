"""Empirical test of the leash invariant the re-anchor design rests on.

FIRST (WRONG) FORM OF THE CLAIM:
  "_survival_move on its own can never leave a firefighter more than
   IDLE_RETREAT_MAX_CELLS from _idle_retreat_origin."
  REFUTED by this script on the recorded traces: 10 landings at d = 7..10.

WHY IT FAILED: _survival_move has TWO movers, not one.
  (i)  the leashed candidate move (agents.py:877-879), which can only pick a
       cell that passed `from_origin > IDLE_RETREAT_MAX_CELLS -> continue`;
  (ii) `_assigned_one_step_retreat` (agents.py:888-916), called at :773, :808,
       :865 and :872, which moves the unit with NO leash test and never
       touches the origin.
  Every one of the 10 violations is mover (ii).

CORRECTED CLAIM (what the design actually needs):
  All four call sites of (ii) are guarded by `self.target_pos`, so (ii) can
  only ever run for an ASSIGNED unit. For an IDLE unit the leashed move is
  the only mover inside _survival_move. Therefore an idle unit observed at
  d > IDLE_RETREAT_MAX_CELLS proves its position or origin changed during an
  earlier assigned/exiting spell - the origin belongs to a manoeuvre that is
  over.

This script tests the corrected claim: split every observed move by whether
the unit was idle, and check that no IDLE move lands beyond the leash.
"""
import json, sys, collections

MAX = 6


def md(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


viol_idle, viol_assigned = [], []
land_hist = {True: collections.Counter(), False: collections.Counter()}
n_moves = collections.Counter()

for path in sys.argv[1:]:
    d = json.load(open(path))
    tag = path.split("_sb_")[-1].replace(".json", "")
    for s in d["surv"]:
        if not s.get("moved"):
            continue
        n_moves["all"] += 1
        org, post, pre = s.get("origin"), s.get("post_pos"), s.get("pos")
        if org is None or post is None:
            n_moves["origin_None"] += 1
            continue
        idle = bool(s.get("idle"))
        n_moves["idle" if idle else "assigned"] += 1
        dd = md(tuple(post), tuple(org))
        land_hist[idle][dd] += 1
        if dd > MAX:
            row = (tag, s["seed"], s["ff"], s["step"], pre, org, post, dd,
                   s.get("stalled_pre"))
            (viol_idle if idle else viol_assigned).append(row)

print("moves observed                    :", n_moves["all"])
print("  origin was None (no leash yet)  :", n_moves["origin_None"])
print("  idle moves with an origin       :", n_moves["idle"])
print("  assigned moves with an origin   :", n_moves["assigned"])
print()
print("landing |post - origin| histogram, IDLE     :",
      dict(sorted(land_hist[True].items())))
print("landing |post - origin| histogram, ASSIGNED :",
      dict(sorted(land_hist[False].items())))
print()
print("IDLE landings beyond the leash     :", len(viol_idle))
for v in viol_idle:
    print("   ", v)
print("ASSIGNED landings beyond the leash :", len(viol_assigned),
      "  (expected: _assigned_one_step_retreat is unleashed)")
for v in viol_assigned:
    print("   ", v)
print()
if not viol_idle:
    print("RESULT: the CORRECTED (idle-scoped) invariant HOLDS.")
    print("        For an idle unit, d > %d is sound evidence of a stale origin," % MAX)
    print("        so the re-anchor must be scoped to idle units only.")
else:
    print("RESULT: corrected invariant ALSO violated - rework needed.")
