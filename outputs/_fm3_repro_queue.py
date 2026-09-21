"""Reproduce firemech round 2's Part 3 arms (f3OFF / f3GATE / f3RES and the f3RBG* gate
shards) at ANY later tree, under NEW tags. Maintainer ruling, ungated round (2026-09-21).

WHY THIS EXISTS. The recorded queues (outputs/_fm3_queue.txt, _fm3_rb_queue.txt) set only
the FF switches that differed from the defaults of their day (d3640e3: E0 F0 K3 G1). Since
the ungated flip (ba58491: E1 F1 K1 G0) the same lines silently mean something else:
f3GATE and f3RBG* run ungated WITH firebreak, f3OFF runs the full shipped feature, f3RES
gains firebreak. Completed queue files are never edited in place (the pools would
quarantine the committed runs and rerun them under the edited line), so this generator
writes NEW files under NEW tags (f3 -> r3) and never touches the old ones.

EVERY LINE CARRIES
  - all four FF switches explicitly, at the recorded arm's EFFECTIVE values:
      r3OFF   E0 F0 (K and G unreachable)
      r3GATE  E1 F0 K1 G1        (f3GATE: extinguish + suppression, gate at its then-default 1)
      r3RES   E1 F0 K1 G0        (f3RES: the same, gate off)
      r3RBG*  E1 F0 K1 G1        (the gate shards were built from f3GATE's --set list)
  - the two world changes made after round 2 switched off:
      BASE_STATION_FIREPROOF=0              (non-burnable depots, 6668368)
      VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX=0  (searcher off-grid guard, 629a321)
    Without these a run reproduces the CONFIGURATION but not the RUN: the ungated round's
    ugA arm (with them) is value-identical to round 1's fmEFS on 23/23, ugX (without)
    on 0/23.
  Validated by outputs/_fm3_repro_check_queue.txt (one run per arm + one gate shard),
  compared value for value with the recorded f3* files by outputs/_fm3_repro_check.py.

  .venv/Scripts/python.exe -B outputs/_fm3_repro_queue.py
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
WORLD = "--set BASE_STATION_FIREPROOF=0 --set VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX=0"
FF = {
    "f3OFF": "--set FF_FIREFIGHT_EXTINGUISH=0 --set FF_FIREFIGHT_FIREBREAK=0",
    "f3GATE": ("--set FF_FIREFIGHT_EXTINGUISH=1 --set FF_FIREFIGHT_FIREBREAK=0 "
               "--set FF_FIREFIGHT_ENGAGED_RETREAT_RANGE=1 --set FF_FIREFIGHT_MISSION_GATE=1"),
    "f3RES": ("--set FF_FIREFIGHT_EXTINGUISH=1 --set FF_FIREFIGHT_FIREBREAK=0 "
              "--set FF_FIREFIGHT_ENGAGED_RETREAT_RANGE=1 --set FF_FIREFIGHT_MISSION_GATE=0"),
}
FF["f3RBG"] = FF["f3GATE"]


def new_tag(tag):
    assert tag.startswith("f3"), tag
    return "r3" + tag[2:]


def main():
    ff_lines, rb_lines = [], []
    for raw in open(os.path.join(HERE, "_fm3_queue.txt"), encoding="utf-8"):
        s = raw.strip()
        if not s:
            continue
        tag, repo, wind, roles, seed, _extra = s.split("|", 5)
        ff_lines.append("ff|%s|%s|%s|%s|%s|240|--uav-actions %s %s" % (
            new_tag(tag), repo, wind, roles, seed, FF[tag], WORLD))
    for raw in open(os.path.join(HERE, "_fm3_rb_queue.txt"), encoding="utf-8"):
        s = raw.strip()
        if not s:
            continue
        kind, tag, repo, wind, roles, seeds, steps, _extra = s.split("|", 7)
        rb_lines.append("rb|%s|%s|%s|%s|%s|%s|%s %s" % (
            new_tag(tag), repo, wind, roles, seeds, steps, FF["f3RBG"], WORLD))
    for name, lines in (("_fm3_repro_queue.txt", ff_lines), ("_fm3_repro_rb_queue.txt", rb_lines)):
        with open(os.path.join(HERE, name), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        print("%s %d lines" % (name, len(lines)))
    check = [l for l in ff_lines if "|east|half|101|" in l and l.split("|")[1] in ("r3OFF", "r3GATE", "r3RES")]
    check += [l for l in rb_lines if l.split("|")[1] == "r3RBGc"]
    with open(os.path.join(HERE, "_fm3_repro_check_queue.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(check) + "\n")
    print("_fm3_repro_check_queue.txt %d lines" % len(check))


if __name__ == "__main__":
    main()
