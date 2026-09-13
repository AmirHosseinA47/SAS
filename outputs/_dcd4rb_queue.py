"""dcd4rb round: emit the queues for outputs/_dcd4rb_pool.sh.

queue line: kind|tag|repo|wind|roles|seeds|steps|extra
  kind ff  one harness run  (outputs/_ffr_harness.py)
  kind rb  one route_blocked gate shard (outputs/_rblatch_campaign2.py)

THE CONFIGURATION UNDER TEST is dcD with the dock fix ON:
  MODE=3 MECHANISM=2 RESERVE=0 MARGIN=39.23 DEPOTS=9 SPLIT=2, DOCK_FIX not set
  (shipped 2). The --set string is character for character the depot round's
  dcrbD gate line (outputs/_dc_rbgate.sh arm D) and the dfD / d4D harness line
  (outputs/_df_queue.txt, outputs/_dcd4_queue.txt), so a shard is comparable with
  dcrbD at the file level and a harness run with dfD.

ARMS (all config-only on the live tree, no per-arm code):
  D  dcD, dock fix ON                       - the gate under test
  Z  --set BASE_STATION_MODE=0              - "the same seeds at the same commit
                                              WITHOUT dcD's settings" (the brief's
                                              NEW-vs-CARRIED control); explicit, not
                                              a bare default, so this queue cannot
                                              change meaning after a flip
  K  dcD, --set BASE_STATION_DOCK_FIX=0     - same commit, fix OFF: separates the
                                              dock fix from dcD, and reproduces the
                                              depot round's fix-absent dcrbD if the
                                              commits since 9f77178 are inert there
Gate shards drgD/drgZ/drgK{a,b,c,s}: the 18-seed split of outputs/_ffr_rbgate.sh
verbatim (east 101-505 / 606-909 / 111-444, south 101-505). Tags checked against
every _rblatch_camp2_* tag in outputs/: none is a prefix of another either way
(_ffr_rbcompare.py globs "<tag>*").
Harness runs drhD/drhZ/drhK on the same 18 tuples with --uav-actions: the gate
campaign records no per-step UAV state, so deadlock / livelock / standoff /
drone-steps-in-fire (brief items 4-6) are measured on these, and each one's eval
is checked against its shard's eval for the same seed (same simulation).

CONTROLS (queue `controls`, run and checked BEFORE the wave is launched):
  six committed dock-fix-round harness runs, none of them a tuple the dcd4
  controls used and none in the rbgate 18, so they widen the verified set:
    drxD vs dfD     south/half/707, east/half/1010
    drxZ vs dfzero  east/default/101, south/half/909
    drxK vs dfkill  south/half/606, east/default/303
  plus two single-seed gate-instrument controls. Seed 101 is the FIRST seed of
  shards s and a, so a one-seed process starts from the same process state and
  must reproduce that seed's eval and every per-seed hook record:
    drxrbB  south 101, the dfrb line (dcB config, fix on, 7f951cb) vs dfrbs
    drxrbZ  east 101, no --set                                       vs rbca / dcinerta

usage: .venv/Scripts/python.exe outputs/_dcd4rb_queue.py controls > outputs/_dcd4rb_controls.txt
       .venv/Scripts/python.exe outputs/_dcd4rb_queue.py wave     > outputs/_dcd4rb_queue.txt
"""
import sys

REPO = "E:/Projects/SAS"
ARMED = "--set BASE_STATION_MODE=3 --set BASE_STATION_RETURN_MECHANISM=2"
DIST = "--set UAV_RETURN_TO_BASE_RESERVE=0 --set BASE_STATION_RETURN_MARGIN=39.23"
TWO_DEPOT = "--set BASE_STATION_DEPOTS=9 --set BASE_STATION_SPAWN_SPLIT=2"

SETS = {
    "D": "%s %s %s" % (ARMED, DIST, TWO_DEPOT),
    "Z": "--set BASE_STATION_MODE=0",
    "K": "%s %s %s --set BASE_STATION_DOCK_FIX=0" % (ARMED, DIST, TWO_DEPOT),
    "dfB": "%s %s" % (ARMED, DIST),                                   # dfrb / dfB line
    "dfkill": "%s %s --set BASE_STATION_DOCK_FIX=0" % (ARMED, DIST),  # dfkill line
    "none": "",
}

RB_SHARDS = (("a", "east", "101,202,303,404,505"),
             ("b", "east", "606,707,808,909"),
             ("c", "east", "111,222,333,444"),
             ("s", "south", "101,202,303,404,505"))
RB18 = [(w, "half", int(s)) for _sh, w, seeds in RB_SHARDS for s in seeds.split(",")]


def ff(tag, w, r, s, sets):
    return "ff|%s|%s|%s|%s|%d|240|--uav-actions %s" % (tag, REPO, w, r, s, SETS[sets])


def rb(tag, w, seeds, sets):
    return ("rb|%s|%s|%s|half|%s|240|%s" % (tag, REPO, w, seeds, SETS[sets])).rstrip()


def controls():
    return [
        ff("drxD", "south", "half", 707, "D"),
        ff("drxD", "east", "half", 1010, "D"),
        ff("drxZ", "east", "default", 101, "Z"),
        ff("drxZ", "south", "half", 909, "Z"),
        ff("drxK", "south", "half", 606, "dfkill"),
        ff("drxK", "east", "default", 303, "dfkill"),
        rb("drxrbB", "south", "101", "dfB"),
        rb("drxrbZ", "east", "101", "none"),
    ]


def wave():
    out = []
    # the gate shards first: they are the long poles (4-5 seeds in one process)
    # and the gate is decided by them
    for arm in ("D", "Z", "K"):
        for sh, w, seeds in RB_SHARDS:
            out.append(rb("drg%s%s" % (arm, sh), w, seeds, arm))
    # per-step harness runs: D and Z interleaved per tuple, K last
    for w, r, s in RB18:
        out.append(ff("drhD", w, r, s, "D"))
        out.append(ff("drhZ", w, r, s, "Z"))
    for w, r, s in RB18:
        out.append(ff("drhK", w, r, s, "K"))
    return out


def extend():
    """prereg section 5: one 300-step harness run (tag drl<arm>) per (arm, tuple) that ends
    with a unit route_blocked and alive at step 240 in that arm's gate shards. Emitted only
    after every gate shard exists; a missing shard is an error, not an empty queue."""
    import json
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    out = []
    for arm in ("D", "Z", "K"):
        hit = []
        for sh, w, _seeds in RB_SHARDS:
            p = os.path.join(here, "_rblatch_camp2_drg%s%s_D_%s.json" % (arm, sh, w))
            if not os.path.exists(p):
                raise SystemExit("gate shard missing: %s" % p)
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            for r in d.get("latched") or []:
                if (w, int(r["seed"])) not in hit:
                    hit.append((w, int(r["seed"])))
        for w, s in hit:
            out.append("ff|drl%s|%s|%s|half|%d|300|--uav-actions %s" % (arm, REPO, w, s, SETS[arm]))
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    which = sys.argv[1] if len(sys.argv) > 1 else "wave"
    for ln in {"controls": controls, "wave": wave, "extend": extend}[which]():
        print(ln)
