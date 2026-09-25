outputs/_cl_replay/ - the exit-stall round's OFFLINE REPLAY of the candidate exit-leg
rules, preserved VERBATIM by the carrying-leg round (Part 1, 2026-09-25).

WHY IT IS HERE
  outputs/exitstall_part1.txt section 8 estimates FF_EXIT_LEG_MODE=2 ("F5 + F1") from this
  replay: 212 legs, steps 3507 -> 1643, stalled 56 -> 20, adjacent/smoky 123/36 -> 12/3.
  Until now the code existed only in an earlier session's Temp scratchpad
  (C:\Users\ahrar\AppData\Local\Temp\claude\E--Projects-SAS\e5e891da-...\scratchpad\
  xs_static\fixscope\), which can be cleaned up at any time. Copied with cp -p; every
  file's sha256 equals its source's (SHA256SUMS.txt). NOT modified.

WHAT IT IS (see outputs/carryleg_part1.txt sections 1 C6-C7 and 2.3)
  fs_env.py            fire from recorded burn_intervals; smoke re-simulated per cell
                       (guessed fuel F_GUESS, default 8, where a cell did not burn out)
  fs_rules.py          _move_toward transcribed (tiers 1-4) + variants F1..F6;
                       bfs_first_step = the F5 rule mode 2 implements
  fs_counterfactual.py replays each completed leg on its own recorded fire
  fs_validate.py       checks fs_env / fs_rules against the exit-stall xstrace windows
  fs_legs.py, fs_reads.py  helpers used by the exit-stall static workflow
  list_*.txt           the file lists replayed (CRLF; stripped on read)
  cf_*.txt             the replay's outputs, 2026-09-21

HOW TO RUN (read-only; absolute path E:/Projects/SAS/outputs is hard-coded)
  cd outputs/_cl_replay
  F_GUESS=8 ../../.venv/Scripts/python.exe -B fs_counterfactual.py list_census.txt
  ../../.venv/Scripts/python.exe -B fs_validate.py

KNOWN (verified 2026-09-25 by the carrying-leg Part 1 verification)
  - The "F5" row has no F1 completion test; it completes through a local target
    reassignment (fs_counterfactual.py:78-79). A real F1+F5 rule gives identical numbers
    in all 7 sets (cf_f1f5.txt).
  - It covers 212 legs in 59 files (2 vmon files have no burn_intervals).
  - "20 still stalled" is measured to the FIXED exit cell; measured to the cell actually
    reached it is 2 (cf_metrics.txt). 18 of the 20 have no fallback step and no reversal
    (cf_stalled20.txt).
  - Nothing recorded validates the BFS itself. The carrying-leg Part 2 pre-wave check
    must bind the IMPLEMENTED kernel IN THE CONSUMER MODULE (fs_counterfactual and drive
    import bfs_first_step by name, so rebinding fs_rules.bfs_first_step after import does
    NOTHING and the check would pass vacuously - check_binding.py demonstrates it), call
    both kernels on every search and require 0 mismatches over the pre-registered call
    counts, and only then reproduce these numbers. See outputs/carryleg_part1.txt 8.4.

BLOCK 2 - ADDED BY THE CARRYING-LEG PART 1 (2026-09-25), listed separately in SHA256SUMS.txt
  drive.py        base/F1/F5 + F1F5 (the implemented mode 2), fallback/search step counts
  metrics.py      stall to the reached cell, reversals, off-exit endings, per list
  stalled20.py    why the 20 F5 "stalls" (fixed exit) remain: 18 are clean farther walks
  holds.py        hold census of the base replay (0 holds)
  drive_ff.py     F5 vs a burning-only search (F5ns) and "clean first, else burning-only /
                  least exposure" (F5L/F5E), at fuel guess 7/8/10
  check_binding.py the binding trap above: rebinding fs_rules after import is a no-op
  cf_f1f5.txt, cf_metrics.txt, cf_stalled20.txt, cf_burnonly_gap.txt  their frozen outputs
  Run (read-only): cd outputs/_cl_replay
    F_GUESS=8 ../../.venv/Scripts/python.exe -B drive.py list_census.txt list_uhC.txt ...
    ../../.venv/Scripts/python.exe -B metrics.py list_census.txt list_uhC.txt ...
    ../../.venv/Scripts/python.exe -B stalled20.py
    for g in 7 8 10: F_GUESS=$g ../../.venv/Scripts/python.exe -B drive_ff.py list_<set>.txt

LINE ENDINGS: the sha256 values in SHA256SUMS.txt are of the bytes as written on 2026-09-25.
This repo has core.autocrlf=true: git stores these text files with LF in the index and may
check them out with CRLF, which changes their hash. To verify after a checkout, hash the
LF form (git show <commit>:<path> | sha256sum, for files that were LF when hashed), or
normalise CRLF->LF before hashing.
