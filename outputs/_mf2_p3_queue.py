"""fix2 Part 3: the pre-registered waves (outputs/fix2_part1.txt section 9 + outputs/fix2_part3_prereg.txt).

Writes four queues for outputs/_mf2_pool.py:
  _mf2_q_p3r.jsonl  the c08456b reference arms only (mf2hR, mf2gR) - independent of every fix2 edit
  _mf2_q_p3a.jsonl  identity and the shipped system first:
                    mf2Z  (probe, 16 configs, every fix2 switch 0)       P3-1(a), before-arm
                    mf2ALL(probe, 16 configs, shipped)                   the all-together arm
                    mf2hR / mf2hZ (harness, fix1's 16 canonical tuples)  P3-1(b)
                    mf2gR / mf2gZ / mf2gS (rbgate, 4 shards each)        P3-10, P3-1(c)
  _mf2_q_p3b.jsonl  single-fix arms, 8 configs each (A-D x S/E): mf2A1 mf2FS mf2A2 mf2A3a mf2A3b mf2A4
  _mf2_q_p3c.jsonl  the D-7 CRN arms (outputs/_fm2_probe_harness.py, FM2P_CRN=1, --uav-actions),
                    A-D x N/S/E/W at fresh seeds 9701-9716: mf2hcZ mf2hc3 mf2hcX mf2hcS
The c08456b reference checkout is REF (a detached worktree, no .venv junction - the pool runs the
parent .venv with --repo / cwd).
"""
import json
import os
import sys

REPO = r"E:\Projects\SAS"
REF = r"E:\Projects\SAS_wt\mf2_c08456b"
OUT = os.path.join(REPO, "outputs")
SW = ["GLOBAL_ANALYZER_FIRE_SOURCE_FIX", "FAILSAFE_REAL_ALARMS", "UAV_HOLD_STATIONARY",
      "SEARCHER_WIND_COVERAGE_FIX", "SEARCHER_GATE_NEAR_FIELD", "STAGGERED_LAUNCH_BATTERY"]
ALL_OFF = {s: 0 for s in SW}
WIND = {"E": "east", "N": "north", "S": "south", "W": "west"}


def sets(values):
    out = []
    for k, v in values.items():
        out += ["--set", "%s=%s" % (k, v)]
    return out


def probe_line(arm, cfg, switches):
    with open(os.path.join(OUT, "_sd_mf1P_%s.json.argv" % cfg), encoding="utf-8") as fh:
        a = list(json.load(fh)["argv"][1:])
    name = "%s_%s" % (arm, cfg)
    out = os.path.join(OUT, "_sd_%s.json" % name)
    a[a.index("--out") + 1] = out
    a[a.index("--tag") + 1] = name
    return {"name": name, "argv": [os.path.join(OUT, "_mf2_probe.py"), "--"] + a + sets(switches), "out": out}


def only(switch):
    d = dict(ALL_OFF)
    d[switch] = 1
    return d


def main():
    cfg16 = ["%s_%s" % (s, w) for s in "ABCD" for w in "ENSW"]
    cfg8 = ["%s_%s" % (s, w) for s in "ABCD" for w in "SE"]
    qr, qa, qb, qc = [], [], [], []
    for cfg in cfg16:
        qa.append(probe_line("mf2Z", cfg, ALL_OFF))
    for cfg in cfg16:
        qa.append(probe_line("mf2ALL", cfg, {}))
    # P3-1(b): fix1's canonical harness sample (C13 + A/B/C), fix2 all-off vs the c08456b checkout
    tuples = ([("D", "east", "half", s) for s in (101, 202, 303, 404, 505)]
              + [("D", "south", "half", s) for s in (101, 202, 303, 404, 505)]
              + [("D", "east", "default", s) for s in (101, 202, 303)]
              + [("A", "west", "default", 9501), ("B", "north", "default", 9502), ("C", "south", "default", 9503)])
    for arm, repo, extra in (("mf2hR", REF, {}), ("mf2hZ", REPO, ALL_OFF)):
        for sc, w, roles, seed in tuples:
            name = "%s_%s_%s_%s_%d" % (arm, sc, w, roles, seed)
            out = os.path.join(OUT, "_ffr_%s.json" % name)
            argv = [os.path.join(OUT, "_ffr_harness.py"), "--repo", repo, "--scenario", sc, "--wind", w,
                    "--roles", roles, "--seed", str(seed), "--steps", "360", "--out", out, "--tag", arm] + sets(extra)
            (qr if repo == REF else qa).append({"name": name, "argv": argv, "out": out})
    # P3-10 / P3-1(c): the route_blocked gate, fix1's four shards
    shards = [("a", "east", "101,202,303,404,505"), ("b", "east", "606,707,808,909"),
              ("c", "east", "111,222,333,444"), ("s", "south", "101,202,303,404,505")]
    for arm, root, extra in (("mf2gR", REF, {}), ("mf2gZ", REPO, ALL_OFF), ("mf2gS", REPO, {})):
        for sh, w, seeds in shards:
            tag = "%s%s" % (arm, sh)
            out = os.path.join(root, "outputs", "_rblatch_camp2_%s_D_%s.json" % (tag, w))
            argv = [os.path.join(root, "outputs", "_rblatch_campaign2.py"), "--scenario", "D", "--wind", w,
                    "--steps", "240", "--seeds", seeds, "--tag", tag] + sets(extra)
            (qr if root == REF else qa).append({"name": tag, "cwd": root, "argv": argv, "out": out})
    for arm, switch in (("mf2A1", "FAILSAFE_REAL_ALARMS"), ("mf2FS", "GLOBAL_ANALYZER_FIRE_SOURCE_FIX"),
                        ("mf2A2", "UAV_HOLD_STATIONARY"), ("mf2A3a", "SEARCHER_WIND_COVERAGE_FIX"),
                        ("mf2A3b", "SEARCHER_GATE_NEAR_FIELD"), ("mf2A4", "STAGGERED_LAUNCH_BATTERY")):
        for cfg in cfg8:
            qb.append(probe_line(arm, cfg, only(switch)))
    # P3-5(b): the B/west loop (B/west/9608) must be seen with 3b alone, not only in mf2ALL
    qb.append(probe_line("mf2A3b", "B_W", only("SEARCHER_GATE_NEAR_FIELD")))
    # P3-12: D-7 - 3b against the range-99 behaviour under CRN
    crn_arms = (("mf2hcZ", ALL_OFF), ("mf2hc3", only("SEARCHER_GATE_NEAR_FIELD")),
                ("mf2hcX", {"SEARCHER_GATE_NEAR_FIELD": 0}), ("mf2hcS", {}))
    for arm, extra in crn_arms:
        for i, cfg in enumerate(cfg16):
            sc, w = cfg.split("_")
            seed = 9701 + i
            name = "%s_%s_%s_%d" % (arm, sc, WIND[w], seed)
            out = os.path.join(OUT, "_ffr_%s.json" % name)
            argv = [os.path.join(OUT, "_fm2_probe_harness.py"), "--repo", REPO, "--scenario", sc,
                    "--wind", WIND[w], "--roles", "half", "--seed", str(seed), "--steps", "360",
                    "--uav-actions", "--out", out, "--tag", arm, "--set", "FM2P_CRN=1"] + sets(extra)
            qc.append({"name": name, "argv": argv, "out": out})
    # names-only lists for outputs/_sd_analyze.py (P3-9), one per probe arm
    for arm in ("mf2Z", "mf2ALL", "mf2A1", "mf2FS", "mf2A2", "mf2A3a", "mf2A3b", "mf2A4"):
        names = [ln["name"] for ln in qa + qb if ln["name"].startswith(arm + "_")]
        with open(os.path.join(OUT, "_mf2_an_%s.jsonl" % arm), "w", encoding="utf-8", newline="\n") as fh:
            for n in names:
                fh.write(json.dumps({"name": n}) + "\n")
    for fname, q in (("_mf2_q_p3r.jsonl", qr), ("_mf2_q_p3a.jsonl", qa), ("_mf2_q_p3b.jsonl", qb), ("_mf2_q_p3c.jsonl", qc)):
        with open(os.path.join(OUT, fname), "w", encoding="utf-8", newline="\n") as fh:
            for ln in q:
                fh.write(json.dumps(ln) + "\n")
        print("wrote %d lines to %s" % (len(q), fname))


if __name__ == "__main__":
    sys.exit(main())
