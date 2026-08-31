"""Apply the idle-retreat latch + leash fix to agents.py.

Idempotent, CRLF-preserving (agents.py is 100% CRLF and core.autocrlf=true;
the route_blocked round recorded a line-ending churn incident from a patch
script, so this one reads and writes bytes with newline='' semantics).

  --check   report whether the patch is applied, without writing
  --apply   write the change
  --revert  restore the pre-patch text
"""
from __future__ import annotations
import argparse, io, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(BASE, "agents.py")

# --------------------------------------------------------------------------
# 1. origin anchoring: also re-anchor a provably stale origin (idle only)
# --------------------------------------------------------------------------
OLD_ORIGIN = '''        origin = getattr(self, "_idle_retreat_origin", None)
        if origin is None:
            self._idle_retreat_origin = cell
            self._idle_retreat_steps = 0
            self._idle_retreat_stalled = False
            self._idle_retreat_last_cell = None
            origin = cell

        if bool(getattr(self, "_idle_retreat_stalled", False)):
            if self.target_pos and self._assigned_one_step_retreat(fire_cells):
                return
            return
'''

NEW_ORIGIN = '''        origin = getattr(self, "_idle_retreat_origin", None)
        if origin is None or (
            not self.target_pos
            and abs(cell[0] - origin[0]) + abs(cell[1] - origin[1])
            > IDLE_RETREAT_MAX_CELLS
        ):
            # The leash below is measured from where the retreat began, and the
            # scan only ever steps to cells within IDLE_RETREAT_MAX_CELLS of it.
            # For an idle unit that scan is the only thing that moves it here,
            # so standing further out than the leash allows proves something
            # else did: a walk to a victim, an assigned one-step retreat, or an
            # unassign that left it wherever it happened to be. The recorded
            # origin then belongs to a manoeuvre that is over, and leashing to
            # it tethers a stranded unit to a cell it left long ago. Anchor a
            # fresh manoeuvre here instead. The stall flag goes with it: that
            # verdict was reached through the old leash, so correcting the
            # leash invalidates it. Assigned units are excluded because
            # `_assigned_one_step_retreat` moves them without any leash test,
            # so for them the same distance proves nothing.
            self._idle_retreat_origin = cell
            self._idle_retreat_steps = 0
            self._idle_retreat_stalled = False
            self._idle_retreat_last_cell = None
            origin = cell

        if bool(getattr(self, "_idle_retreat_stalled", False)):
            if self.target_pos:
                self._assigned_one_step_retreat(fire_cells)
                return
            self._revalidate_idle_retreat_stall(cell, origin, fire_cells)
            return
'''

# --------------------------------------------------------------------------
# 2. candidate scan -> shared helper
# --------------------------------------------------------------------------
OLD_SCAN = '''        candidates: list[dict[str, object]] = []
        for ncell in self._neighbor_cells():
            if self._cell_contains_active_fire(ncell):
                continue
            if ncell == last_cell:
                continue
            from_origin = abs(ncell[0] - origin[0]) + abs(ncell[1] - origin[1])
            if from_origin > IDLE_RETREAT_MAX_CELLS:
                continue
            risk = self._firefighter_cell_risk(ncell)
            new_dist = self._min_fire_distance(ncell, fire_cells)
            candidates.append(
                {
                    "cell": ncell,
                    "risk": risk,
                    "dist": new_dist,
                    "improvement": new_dist - current_dist,
                    "ideal": self._cell_is_ideal_idle_standoff(ncell, fire_cells),
                    "required": self._cell_meets_required_idle_safety(
                        ncell, fire_cells
                    ),
                }
            )
'''

NEW_SCAN = '''        candidates = self._retreat_candidates(
            cell, origin, last_cell, fire_cells, current_dist
        )
'''

# --------------------------------------------------------------------------
# 3. tier 1 / tier 2 selection -> shared helper (tier 3 stays inline)
# --------------------------------------------------------------------------
OLD_PICK = '''        if not at_cap:
            ideal_reachable = [c for c in candidates if c["ideal"]]
            if ideal_reachable:
                chosen = max(
                    ideal_reachable,
                    key=lambda c: (c["dist"], -int(c["risk"])),
                )
            else:
                improving = [
                    c
                    for c in candidates
                    if int(c["improvement"]) > 0
                    or (
                        int(c["risk"]) < current_risk
                        and int(c["dist"]) >= current_dist
                    )
                ]
                if improving:
                    chosen = max(
                        improving,
                        key=lambda c: (
                            int(c["improvement"]),
                            int(c["dist"]),
                            -int(c["risk"]),
                        ),
                    )
                else:
                    chosen = max(
                        candidates,
                        key=lambda c: (int(c["dist"]), -int(c["risk"])),
                    )
                    if not self.target_pos:
                        self._idle_retreat_stalled = True
'''

NEW_PICK = '''        if not at_cap:
            chosen = self._pick_improving_retreat(
                candidates, current_dist, current_risk
            )
            if chosen is None:
                chosen = max(
                    candidates,
                    key=lambda c: (int(c["dist"]), -int(c["risk"])),
                )
                if not self.target_pos:
                    self._idle_retreat_stalled = True
'''

# --------------------------------------------------------------------------
# 4. the three new methods, inserted before _assigned_one_step_retreat
# --------------------------------------------------------------------------
ANCHOR = '''    def _assigned_one_step_retreat(
'''

NEW_METHODS = '''    def _retreat_candidates(
        self,
        cell: tuple[int, int],
        origin: tuple[int, int],
        last_cell: tuple[int, int] | None,
        fire_cells: set[tuple[int, int]],
        current_dist: int,
    ) -> list[dict[str, object]]:
        """Neighbour cells that survive the retreat filter chain.

        One definition, shared by the normal scan and by
        `_revalidate_idle_retreat_stall`, so the two can never drift apart
        about what "nowhere to go" means.
        """
        candidates: list[dict[str, object]] = []
        for ncell in self._neighbor_cells():
            if self._cell_contains_active_fire(ncell):
                continue
            if ncell == last_cell:
                continue
            from_origin = abs(ncell[0] - origin[0]) + abs(ncell[1] - origin[1])
            if from_origin > IDLE_RETREAT_MAX_CELLS:
                continue
            risk = self._firefighter_cell_risk(ncell)
            new_dist = self._min_fire_distance(ncell, fire_cells)
            candidates.append(
                {
                    "cell": ncell,
                    "risk": risk,
                    "dist": new_dist,
                    "improvement": new_dist - current_dist,
                    "ideal": self._cell_is_ideal_idle_standoff(ncell, fire_cells),
                    "required": self._cell_meets_required_idle_safety(
                        ncell, fire_cells
                    ),
                }
            )
        return candidates

    def _pick_improving_retreat(
        self,
        candidates: list[dict[str, object]],
        current_dist: int,
        current_risk: int,
    ) -> dict[str, object] | None:
        """Best candidate that genuinely beats standing still, else None.

        An ideal standoff ends the retreat outright, so it wins even when it
        is no further from the fire; otherwise a step must gain fire distance,
        or lower risk without giving distance up. The "take the least-bad
        neighbour anyway" fallback is deliberately not here: repeating that
        step is what the stall latch legitimately exists to stop, so the
        normal scan keeps it and the revalidation pass does not.
        """
        ideal_reachable = [c for c in candidates if c["ideal"]]
        if ideal_reachable:
            return max(
                ideal_reachable,
                key=lambda c: (c["dist"], -int(c["risk"])),
            )
        improving = [
            c
            for c in candidates
            if int(c["improvement"]) > 0
            or (
                int(c["risk"]) < current_risk
                and int(c["dist"]) >= current_dist
            )
        ]
        if improving:
            return max(
                improving,
                key=lambda c: (
                    int(c["improvement"]),
                    int(c["dist"]),
                    -int(c["risk"]),
                ),
            )
        return None

    def _revalidate_idle_retreat_stall(
        self,
        cell: tuple[int, int],
        origin: tuple[int, int],
        fire_cells: set[tuple[int, int]],
    ) -> None:
        """Re-test a stalled idle unit's retreat instead of trusting the flag.

        `_idle_retreat_stalled` only records that on one earlier step nothing
        nearby was worth stepping to. Read as permanent it is fatal: for an
        idle unit the check in `_survival_move` used to return before the
        candidate scan, and the only resets that could clear the flag - the
        ideal-standoff test at the top of `_survival_move`, and the standby
        branch of `advance` - both require the unit to already be safe, which
        is the exact complement of the condition that calls this. So while
        fire stayed near, a stalled idle unit never looked again even as the
        fire moved and its neighbourhood changed.

        Re-run the same filter chain and move only on a genuine improvement.
        A neighbour that is merely reachable is still refused, so when nothing
        has actually changed the unit holds its cell and stays latched exactly
        as before.
        """
        last_cell = getattr(self, "_idle_retreat_last_cell", None)
        current_dist = self._min_fire_distance(cell, fire_cells)
        current_risk = self._firefighter_cell_risk(cell)
        chosen = self._pick_improving_retreat(
            self._retreat_candidates(
                cell, origin, last_cell, fire_cells, current_dist
            ),
            current_dist,
            current_risk,
        )
        if chosen is None:
            return
        steps = int(getattr(self, "_idle_retreat_steps", 0) or 0)
        self._idle_retreat_last_cell = cell
        self.model.grid.move_agent(self, chosen["cell"])
        self._idle_retreat_steps = steps + 1
        # Only the stall flag is cleared. `_reset_idle_retreat_state` would
        # also drop `_idle_retreat_last_cell`, the anti-oscillation memory, on
        # the one path being added here. The existing reset sites still fire
        # normally once the unit is genuinely safe.
        self._idle_retreat_stalled = False

'''

EDITS = [
    ("origin anchoring + latch recheck", OLD_ORIGIN, NEW_ORIGIN),
    ("candidate scan -> _retreat_candidates", OLD_SCAN, NEW_SCAN),
    ("tier1/tier2 -> _pick_improving_retreat", OLD_PICK, NEW_PICK),
]


def read():
    with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
        return f.read()


def write(text):
    with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def crlf(s):
    """Our patch literals are LF; the file is CRLF. Convert on the way in."""
    return s.replace("\n", "\r\n")


def status(src):
    applied = "_revalidate_idle_retreat_stall" in src
    pending = [n for (n, old, new) in EDITS if crlf(old) in src]
    done = [n for (n, old, new) in EDITS if crlf(new) in src]
    return applied, pending, done


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--revert", action="store_true")
    ap.add_argument("--target", default="",
                    help="patch this file instead of agents.py (dry-run check)")
    a = ap.parse_args()

    global TARGET
    if a.target:
        TARGET = a.target
    src = read()
    n_crlf = src.count("\r\n")
    n_lf = src.count("\n") - n_crlf
    applied, pending, done = status(src)
    print("agents.py: %d CRLF lines, %d bare-LF lines" % (n_crlf, n_lf))
    print("new methods present : %s" % applied)
    print("edits still to make : %s" % (pending or "-"))
    print("edits already made  : %s" % (done or "-"))

    if a.check:
        return 0

    if a.apply:
        if applied:
            print("ALREADY APPLIED - nothing to do")
            return 0
        out = src
        for name, old, new in EDITS:
            o, n = crlf(old), crlf(new)
            if out.count(o) != 1:
                print("ABORT: anchor for %r matched %d times" % (name, out.count(o)))
                return 1
            out = out.replace(o, n)
        anc = crlf(ANCHOR)
        if out.count(anc) != 1:
            print("ABORT: insertion anchor matched %d times" % out.count(anc))
            return 1
        out = out.replace(anc, crlf(NEW_METHODS) + anc)
        if out.count("\n") - out.count("\r\n") != 0:
            print("ABORT: would introduce bare-LF lines")
            return 1
        write(out)
        print("APPLIED")
        return 0

    if a.revert:
        if not applied:
            print("NOT APPLIED - nothing to revert")
            return 0
        out = src
        out = out.replace(crlf(NEW_METHODS) + crlf(ANCHOR), crlf(ANCHOR))
        for name, old, new in EDITS:
            out = out.replace(crlf(new), crlf(old))
        write(out)
        print("REVERTED")
        return 0


sys.exit(main())
