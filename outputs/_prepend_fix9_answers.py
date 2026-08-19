# -*- coding: utf-8 -*-
import os
path = os.path.join(os.path.dirname(__file__), "fix9_part1.txt")
with open(path, "r", encoding="utf-8") as f:
    raw = f.read()
answers = r"""FIX9 PART 1 ANSWERS (structured). Raw probe log follows after RAW_LOG.
Python 3.10.11 | mesa 1.2.1 | UAV_OBSERVATION_RADIUS=8
Probe: outputs/_diag_y_coverage.py  (read-only; no production edits)

================================================================
Q1  Coverage extent
================================================================
D/north seed=101 (miss v3 at (25,3)):
  searcher_ids=['2503']
  trajectory x: min=2 median=11.0 max=26
  trajectory y: min=5 median=31.0 max=44
  fraction steps y<=12: 0.075   y>=38: 0.237  (n_pos=240)
  fraction steps x<=12: 0.688   x>=30: 0.000
  occupy reachable south y<=12: 18  north y>=37: 67
  occupy blocked south y<=2: 0  north y>=46: 0
  occupy interior-edge south y<=6: 6  north y>=43: 14
  coverage_y_commit steps: north=143 south=80 none=17
  target y: min=4.0 median=45.0 max=48.0
  observed cells: 1420 / 2500 = 0.568
  covered x-range: [0, 34]  covered y-range: [0, 49]
  fire in north blocked band: step60 27/200 on fire, step120 37/200

D/south seed=101 (miss v1 at (25,48)):
  trajectory x: min=1 median=8.0 max=26
  trajectory y: min=15 median=32.0 max=48
  fraction steps y<=12: 0.000   y>=38: 0.375
  fraction steps x<=12: 0.875   x>=30: 0.000
  occupy reachable south y<=12: 0  north y>=37: 93
  occupy blocked south y<=2: 0  north y>=46: 21
  coverage_y_commit steps: north=46 south=179 none=15
  target y: min=1.0 median=4.0 max=46.0
  observed cells: 1213 / 2500 = 0.485
  covered x-range: [0, 34]  covered y-range: [7, 49]
  fire in south blocked band: step60 42/150 on fire (do NOT delete _downwind_edge_blocked)

A/west seed=505 (west-fix success contrast):
  trajectory x: min=11 median=29.0 max=38
  trajectory y: min=5 median=26.0 max=43
  fraction steps y<=12: 0.133   y>=38: 0.129
  fraction steps x<=12: 0.025   x>=30: 0.467
  observed cells: 1603 / 2500 = 0.641
  covered x-range: [3, 46]  covered y-range: [0, 49]

Contrast: A/west has a completed east second-sweep (x median 29, max 38, 46.7% x>=30).
D/north and D/south camp west (x median 11 and 8, x>=30 never) because _allow_east_force
is west-only. Y occupancy is biased: D/north only 7.5% at y<=12; D/south 0% at y<=12
despite 179 south-commit steps.

================================================================
Q2  Y-axis analogue of the x-axis trap
================================================================
YES, with an important difference: a y-commit already exists, but it fights the
strip the way the old unoccupiable west release did.

Constraints that bound the searcher's y target:
1. Hybrid downwind in _score_hybrid_search_cell: score = capped_downwind * 3.0 * wind_w
   (lines 991-992). Under north wind this prefers high y; under south, low y.
2. _finalize_coverage_target (829-902): x-strip latch is WEST ONLY. Y is only via
   coverage_y_commit (ty forced to y_max-4=45 or y_min+4=4). No y-strip latch.
3. _allow_east_force (182-185): return w == "west". Measured:
   west=True north=False south=False east=False. No y analogue.
4. No north_strip_done / south_strip_done in _default_wind_search_state
   (only west_strip_done, east_strip_done at 414-415).
5. _downwind_edge_blocked (1243-1255): north cy>=y_max-3 => y=46..49 (200 cells);
   south cy<=y_min+2 => y=0..2 (150 cells). Live: D/north never occupies blocked
   bands. D/south never occupies y<=2; DOES occupy y>=46 (21 steps) which is NOT
   blocked under south wind.
6. _cell_on_edge margin=WIND_INTERIOR_MARGIN=6 (455-469, 1005): y<=6 or y>=43.
7. _coverage_y_commit_target_y (804-812): north=45, south=4.
8. Corridor/escape DROP cy < y_force_min or cy > y_force_max (3196-3199, 3366-3369)
   i.e. only y>=45 when north-committed, only y<=4 when south-committed.
9. _coverage_y_commit_penetrated (770-781): north ay>=43, south ay<=6.

Unoccupiable release (the rotated x trap):
  South commit wants cy<=4 AND south wind blocks cy<=2 AND interior treats cy<=6
  as edge. D/south 101: 179 south-commit steps, target y median=4, ZERO steps at
  y<=12. The south release never becomes occupiable.
  North commit wants cy>=45 AND north wind blocks cy>=46 AND interior cy>=43.
  D/north occupies y>=43 only 14 steps, never y>=46.

A second, live mechanism: _coverage_y_lower_camping treats max(recent y)<31 as
"stuck south" and commits NORTH. D/west 404 (x already fixed, median x=35) still
has north-commit 183 vs south 41 and only 7.5% at y<=12, so y-commit yanks north
before the south strip is finished. That is the y analogue of never releasing
the downwind pull.

================================================================
Q3  D/east 202 and D/west 404 miss v3 (25,3)
================================================================
D/east 202: y min=5, covered y-range [0,49], frac y<=12=0.150. NOT "y-min stays
above 11". Closest approach min_s=14.14 = hypot(14,2) from about (11,5) to (25,3).
x median=11, 81.2% x<=12, x>=30 never. Combined: south dip at west x.
in_blocked=False in_covered=False ever_r8=False.

D/west 404: x IS fixed (median=35 max=40, 70.4% x>=30, covered x [3,48]).
y min=5, only 7.5% y<=12, north-commit 183 vs south 41.
min_s=10.20 min_any=9.00 ever_r8=False in_covered=False nearby_cells=1.
This is a y-coverage gap independent of wind: the west x-fix succeeded, the
searcher still does not dwell at low y long enough (or at x near 25) to put
(25,3) inside r=8.

Verdict: general low-y blind spot that wind modulates, not a pure N/S phenomenon.
Apply y-strip / suppress north-yank on E/W as well as N/S. D/east may still miss
if west-x camping persists (that is the Q4-class x gap, not this bug).

================================================================
Q4  A/north 101 and B/north 101 v0 (40,25)
================================================================
OUTSIDE the y hypothesis. Mid-y, high-x.
A/north 101 and B/north 101 identical searcher traj (seed 101, 3 UAV, north):
  x min/median/max = 4 / 10.0 / 25
  fraction x<=12: 0.729   x>=30: 0.000
  y median=32
  victim_0 (40,25) min_s=15.30 min_any=8.94 ever_r8=False in_covered=False
This is the east second-sweep gap: _allow_east_force is west-only, so north wind
never gets the east pull that A/west 505 used (x max 38). Do NOT fold an east
second-sweep under north wind into this y fix. Exclude these 2 from the
success criterion (y-extreme 8, not all 10).

================================================================
Q5  All 10 never_detected vs observation / blocked
================================================================
combo       seed  victim    coord     blocked  in_covered  ever_s_r8  ever_any_r8  min_s   min_any
D/north     101   v3        (25,3)    False    False       False      False        14.14   14.14
D/north     404   v3        (25,3)    False    False       False      False         8.60    8.60
D/north     505   v3        (25,3)    False    False       False      True*        15.13    3.16
D/south     101   v1        (25,48)   False    False       False      False        12.37   10.00
A/south     303   v1        (32,46)   False    False       False      False        18.87   18.87
D/east      202   v3        (25,3)    False    False       False      False        14.14   12.37
D/west      404   v3        (25,3)    False    False       False      False        10.20    9.00
C/west      303   v1        (14,44)   False    False       False      False         9.85    9.22
A/north     101   v0        (40,25)   False    False       False      False        15.30    8.94
B/north     101   v0        (40,25)   False    False       False      False        15.30    8.94

* D/north 505 ever_any_r8=True min_any=3.16 is almost certainly a tracker AFTER
  the never_detected timeout (terminal_step=210 in fix8). Searcher min_s=15.13
  never entered r=8. Treat as coverage gap, not confirmation/lifecycle.

None of the 10 spawn cells sit in a _downwind_edge_blocked band.
None of the y-extreme 8 were inside a searcher observation radius.
Several are just outside r=8 (8.60, 9.85, 10.20): more y dwell would catch them.

================================================================
DECISION GATE
================================================================
- y-extreme victims were NEVER inside searcher r=8. Proceed with Part 2 y-mirror.
- Do NOT stop for confirmation/lifecycle (the one ever_any_r8 is post-timeout).
- A/north and B/north v0 are an x-gap. Exclude from this fix.
- Apply y-strip latch + camping recovery on N/S AND E/W (Q3: D/west is a clean
  y-gap after the x-fix). Suppress north y-commit while south strip is pending.
- Do NOT enable east force under north/south (would change x-axis behaviour).
- Do NOT delete _downwind_edge_blocked (D/south step60: 42/150 blocked cells on fire;
  D/north step60: 27/200). Target the reachable band (y=8 / y=41) instead of y=4 / y=45.
- Loosen the y_force_min/max 4-cell DROP (keep half-band filter). That drop is the
  unoccupiable south-commit trap (179 commit steps, 0 occupation of y<=12).

RAW_LOG
"""
# Keep answers + original raw log (answers already summarize; append original).
if raw.startswith("FIX9 PART 1 ANSWERS"):
    print("already prepended")
else:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(answers)
        f.write(raw if raw.endswith("\n") else raw + "\n")
    print("wrote", path, "bytes", os.path.getsize(path))
