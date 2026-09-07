"""Apply / check / revert the interior hazard retreat (interior-hazard round).

Same shape as outputs/_dim_patch.py: binary mode, each file's own line ending
preserved byte for byte (uav_executor.py is CRLF in the working tree, the other
two LF), every replacement asserted to occur exactly once, idempotent, reversible.

  --check   report whether the patch is present in each file
  --apply   apply it
  --revert  remove it

Files: src_extension/execution/uav_executor.py (the rule), common_fixed_variables.py
(the constant), README.md (its documentation). Design: outputs/interiorhazard_part1.txt 4.3.
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

EXEC = os.path.join(ROOT, "src_extension", "execution", "uav_executor.py")
CFV = os.path.join(ROOT, "common_fixed_variables.py")
README = os.path.join(ROOT, "README.md")

# ---------------------------------------------------------------------------
# uav_executor.py
# ---------------------------------------------------------------------------
E1_OLD = (
    "from common_fixed_variables import (\n"
    "    LAUNCH_GRACE_STEPS,\n"
    "    normalize_wind_direction,\n"
    "    wind_vector_from_direction,\n"
    ")\n"
)
E1_NEW = E1_OLD + (
    "import common_fixed_variables as _cfv  # module handle: constants read at call time\n"
)

E2_OLD = "    def _victim_edge_blocked_direction(self, agent: Any, direction: int) -> bool:\n"
E2_NEW = (
    "    def _hazard_retreat_range(self) -> int:\n"
    "        \"\"\"VICTIM_SEARCHER_HAZARD_RETREAT_RANGE, read at call time from the\n"
    "        common_fixed_variables MODULE (not the import-time names above) so a\n"
    "        per-run override through apply_scenario_config is visible.\n"
    "          0      the searcher hazard gate retreats only within 2 cells of a\n"
    "                 grid edge, and the retreat is scored toward the interior\n"
    "          1..98  it retreats when the nearest strict fire/smoke cell is\n"
    "                 within that many cells, scored by hazard distance only\n"
    "          >= 99  it retreats on every gated step, scored by hazard only\n"
    "        \"\"\"\n"
    "        try:\n"
    "            return max(0, int(getattr(_cfv, \"VICTIM_SEARCHER_HAZARD_RETREAT_RANGE\", 0)))\n"
    "        except (TypeError, ValueError):\n"
    "            return 0\n"
    "\n"
) + E2_OLD

E3_OLD = (
    "    def _apply_victim_searcher_hazard_gate(\n"
    "        self, agent: Any, chosen_dir: int, action: str,\n"
    "    ) -> tuple[int, str]:\n"
    "        pos = getattr(agent, \"pos\", None)\n"
)
E3_NEW = (
    "    def _apply_victim_searcher_hazard_gate(\n"
    "        self, agent: Any, chosen_dir: int, action: str,\n"
    "    ) -> tuple[int, str]:\n"
    "        \"\"\"Final safety pass on a victim searcher's chosen direction, in order:\n"
    "        strict hazard on the current cell -> retreat; edge-blocked direction ->\n"
    "        retreat; the hazard retreat rule (VICTIM_SEARCHER_HAZARD_RETREAT_RANGE,\n"
    "        see _hazard_retreat_range); the 3-cell strict lookahead, passing the\n"
    "        chosen direction through or re-ranking the safe ones. Returns\n"
    "        (direction, action label).\"\"\"\n"
    "        pos = getattr(agent, \"pos\", None)\n"
)

E4_OLD = (
    "        model = self._resolve_model(agent)\n"
    "        pos = getattr(agent, \"pos\", None)\n"
    "        if pos is not None and model is not None:\n"
    "            if self._distance_from_boundary(int(pos[0]), int(pos[1]), model) <= 2.0:\n"
    "                retreat = self._retreat_to_safe_interior_direction(agent)\n"
    "                if retreat is not None:\n"
    "                    if \"retarget_to_interior\" in action or \"retarget\" in action:\n"
    "                        return retreat, \"victim_search_wind_aware_retarget_to_interior\"\n"
    "                    return retreat, action\n"
    "\n"
    "        if self._strict_path_lookahead_safe(agent, chosen_dir):\n"
    "            return chosen_dir, action\n"
)
E4_NEW = (
    "        model = self._resolve_model(agent)\n"
    "        pos = getattr(agent, \"pos\", None)\n"
    "        retreat_range = self._hazard_retreat_range()\n"
    "        if pos is not None and model is not None:\n"
    "            cell = (int(pos[0]), int(pos[1]))\n"
    "            if retreat_range > 0:\n"
    "                # Interior hazard retreat: on every gated step (range >= 99), or\n"
    "                # when the nearest strict fire/smoke cell is within `retreat_range`\n"
    "                # cells, the chosen direction is replaced by the retreat - the\n"
    "                # strictly safe neighbour furthest from any hazard. Edge handling\n"
    "                # is the edge-blocked filter (margin 3) inside the retreat and the\n"
    "                # candidate filters; no edge test is needed here. Until the grid\n"
    "                # size became readable (2026-09-06) the edge test below read 0.0\n"
    "                # everywhere and this fired on every gated step by accident; the\n"
    "                # constant makes that behaviour deliberate and switchable.\n"
    "                retreat_now = (\n"
    "                    retreat_range >= 99\n"
    "                    or self._min_strict_hazard_distance(cell) <= float(retreat_range)\n"
    "                )\n"
    "            else:\n"
    "                # Range 0: the edge-only gate - a searcher within 2 cells of a grid\n"
    "                # edge steps back toward the interior.\n"
    "                retreat_now = self._distance_from_boundary(cell[0], cell[1], model) <= 2.0\n"
    "            if retreat_now:\n"
    "                retreat = self._retreat_to_safe_interior_direction(agent)\n"
    "                if retreat is not None:\n"
    "                    if \"retarget_to_interior\" in action or \"retarget\" in action:\n"
    "                        return retreat, \"victim_search_wind_aware_retarget_to_interior\"\n"
    "                    return retreat, action\n"
    "\n"
    "        if self._strict_path_lookahead_safe(agent, chosen_dir):\n"
    "            return chosen_dir, action\n"
)

E5_OLD = (
    "            score = self._distance_from_boundary(cell[0], cell[1], model) * 10.0\n"
    "            score += self._min_strict_hazard_distance(cell, fire_cells, smoke_cells) * 5.0\n"
)
E5_NEW = (
    "            score = (\n"
    "                self._distance_from_boundary(cell[0], cell[1], model) * 10.0\n"
    "                if retreat_range == 0\n"
    "                else 0.0\n"
    "            )\n"
    "            score += self._min_strict_hazard_distance(cell, fire_cells, smoke_cells) * 5.0\n"
)

E6_OLD = (
    "        smoke_cells = self._collect_strict_smoke_cells(model)\n"
    "        best_dir: int | None = None\n"
    "        best_score = -float(\"inf\")\n"
    "        pos = getattr(agent, \"pos\", None)\n"
)
E6_NEW = (
    "        smoke_cells = self._collect_strict_smoke_cells(model)\n"
    "        # Range 0 scores the retreat toward the grid interior (edge handling);\n"
    "        # any other range scores by hazard distance only and leaves the edge\n"
    "        # to the edge-blocked filter below. See _hazard_retreat_range.\n"
    "        edge_scored = self._hazard_retreat_range() == 0\n"
    "        best_dir: int | None = None\n"
    "        best_score = -float(\"inf\")\n"
    "        pos = getattr(agent, \"pos\", None)\n"
)

E7_OLD = (
    "            score = self._distance_from_boundary(cell[0], cell[1], model) * 14.0\n"
    "            hazard_dist = self._min_strict_hazard_distance(cell, fire_cells, smoke_cells)\n"
    "            score += hazard_dist * 8.0\n"
    "            if pos is not None:\n"
    "                curr_dist = self._distance_from_boundary(int(pos[0]), int(pos[1]), model)\n"
    "                next_dist = self._distance_from_boundary(cell[0], cell[1], model)\n"
    "                if next_dist > curr_dist:\n"
    "                    score += 18.0\n"
)
E7_NEW = (
    "            score = (\n"
    "                self._distance_from_boundary(cell[0], cell[1], model) * 14.0\n"
    "                if edge_scored\n"
    "                else 0.0\n"
    "            )\n"
    "            hazard_dist = self._min_strict_hazard_distance(cell, fire_cells, smoke_cells)\n"
    "            score += hazard_dist * 8.0\n"
    "            if edge_scored and pos is not None:\n"
    "                curr_dist = self._distance_from_boundary(int(pos[0]), int(pos[1]), model)\n"
    "                next_dist = self._distance_from_boundary(cell[0], cell[1], model)\n"
    "                if next_dist > curr_dist:\n"
    "                    score += 18.0\n"
)

E8_OLD = (
    "            score = self._distance_from_boundary(cell[0], cell[1], model) * 10.0\n"
    "            score += self._min_strict_hazard_distance(cell, fire_cells, smoke_cells) * 6.0\n"
)
E8_NEW = (
    "            score = (\n"
    "                self._distance_from_boundary(cell[0], cell[1], model) * 10.0\n"
    "                if edge_scored\n"
    "                else 0.0\n"
    "            )\n"
    "            score += self._min_strict_hazard_distance(cell, fire_cells, smoke_cells) * 6.0\n"
)

# ---------------------------------------------------------------------------
# common_fixed_variables.py
# ---------------------------------------------------------------------------
C1_OLD = (
    "VICTIM_FLEE_TRIGGER_DISTANCE = 3\n"
    "VICTIM_FLEE_MAX_DISPLACEMENT = 6\n"
)
C1_NEW = C1_OLD + (
    "\n"
    "# Victim-searcher interior hazard retreat. The searcher hazard gate in\n"
    "# src_extension/execution/uav_executor.py replaces the searcher's chosen\n"
    "# direction with a one-step RETREAT - the strictly safe neighbour furthest from\n"
    "# any burning or smoke cell - when this rule fires:\n"
    "#   0       off: the retreat fires only within 2 cells of a grid edge (the\n"
    "#           edge-only gate, with the retreat scored toward the interior)\n"
    "#   1..98   on when the nearest strict fire/smoke cell is within this many\n"
    "#           cells of the searcher (manhattan)\n"
    "#   >= 99   on at every gated step\n"
    "# When on, the retreat and the gate's fallback ranking score by hazard distance\n"
    "# only; keeping off the grid edge is left to the edge-blocked filter (margin 3)\n"
    "# and the planner's boundary margins, which are live regardless.\n"
    "# History: until the grid size became readable (dimension fix, 2026-09-06) the\n"
    "# gate's edge test read 0.0 everywhere and the retreat's boundary terms were 0,\n"
    "# so the model ran with this rule ALWAYS ON and hazard-only for its whole record\n"
    "# - by accident. 99 is that behaviour made intentional; 0 is what the edge-only\n"
    "# code did once the read worked, measured at +1.1 points of searcher steps on a\n"
    "# burning cell (2.1% -> 3.2%). Overridable per run through apply_scenario_config\n"
    "# like every other scenario parameter, and read at call time so an override\n"
    "# applies. Deterministic - it draws from no RNG.\n"
    "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE = 99\n"
)

# ---------------------------------------------------------------------------
# README.md
# ---------------------------------------------------------------------------
R1_OLD = (
    "`SECURITY_DISTANCE`: It establishes the minimum distance that UAVs should be "
    "separated from each other for avoiding collisions.\n"
    "\n"
    "### Firefighters\n"
)
R1_NEW = (
    "`SECURITY_DISTANCE`: It establishes the minimum distance that UAVs should be "
    "separated from each other for avoiding collisions.\n"
    "\n"
    "`VICTIM_SEARCHER_HAZARD_RETREAT_RANGE`: The victim searchers' interior hazard "
    "retreat. When it fires, the searcher's chosen step is replaced by a retreat to "
    "the strictly safe neighbouring cell furthest from any burning or smoke cell. "
    "`0` fires it only within 2 cells of a grid edge (edge handling only); a value "
    "from `1` to `98` fires it whenever the nearest fire or smoke cell is within that "
    "many cells; `99` (the default) fires it on every step the searcher's hazard gate "
    "evaluates. The searchers ran with the always-on form for the whole history of the "
    "model, because the grid size was unreadable and the edge test was always true; the "
    "constant makes that behaviour deliberate and switchable. Can be overridden per run "
    "through `apply_scenario_config`.\n"
    "\n"
    "### Firefighters\n"
)

PATCHES = {
    EXEC: [(E1_OLD, E1_NEW), (E2_OLD, E2_NEW), (E3_OLD, E3_NEW), (E4_OLD, E4_NEW),
           (E5_OLD, E5_NEW), (E6_OLD, E6_NEW), (E7_OLD, E7_NEW), (E8_OLD, E8_NEW)],
    CFV: [(C1_OLD, C1_NEW)],
    README: [(R1_OLD, R1_NEW)],
}


def _read(path):
    with open(path, "rb") as f:
        b = f.read()
    eol = b"\r\n" if b"\r\n" in b else b"\n"
    return b.replace(b"\r\n", b"\n").decode("utf-8"), eol


def _write(path, text, eol):
    data = text.encode("utf-8").replace(b"\n", eol)
    with open(path, "wb") as f:
        f.write(data)


def state(path):
    text, _ = _read(path)
    olds = [text.count(o) for o, n in PATCHES[path]]
    news = [text.count(n) for o, n in PATCHES[path]]
    # three of the new snippets CONTAIN their old snippet (an insertion next to
    # an anchor), so "applied" means each new text occurs once and the old text
    # occurs exactly as often as it does inside the new one
    inside = [n.count(o) for o, n in PATCHES[path]]
    if all(c == 1 for c in news) and all(c == i for c, i in zip(olds, inside)):
        return "applied"
    if all(c == 1 for c in olds) and all(c == 0 for c in news):
        return "absent"
    return "MIXED olds=%s news=%s" % (olds, news)


def apply(path, revert=False):
    text, eol = _read(path)
    before = len(text.encode("utf-8"))
    for old, new in PATCHES[path]:
        src, dst = (new, old) if revert else (old, new)
        n = text.count(src)
        if n != 1:
            raise SystemExit("%s: expected exactly one occurrence of a snippet, found %d:\n%s" % (path, n, src[:200]))
        text = text.replace(src, dst)
    _write(path, text, eol)
    after = len(text.encode("utf-8"))
    return before, after, eol


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    rc = 0
    for path in (EXEC, CFV, README):
        rel = os.path.relpath(path, ROOT)
        st = state(path)
        if a.check:
            print("%-45s %s" % (rel, st))
            rc |= int(st != "applied")
            continue
        want = "absent" if a.apply else "applied"
        if st != want:
            print("%-45s skipped (state: %s)" % (rel, st))
            rc |= int(st.startswith("MIXED"))
            continue
        before, after, eol = apply(path, revert=a.revert)
        print("%-45s %s  %d -> %d bytes  eol=%s  now: %s" % (
            rel, "reverted" if a.revert else "applied", before, after, "CRLF" if eol == b"\r\n" else "LF", state(path)))
    return rc


if __name__ == "__main__":
    sys.exit(main())
