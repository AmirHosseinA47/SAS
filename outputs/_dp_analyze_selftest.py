"""Dispatch round, amendment A2 22.5(4): SYNTHETIC-RECORD SELF-TEST of the analyzer's R-B and R-C code.

Hand-built dp records (no run) through the pure functions of outputs/_dp_analyze.py: rb_cut_refusals, rb_ledgers,
rb_figures, rb_checks_fail (R-B, 22.2) and m8_classify, m8_trigger (R-C, 22.3). Each case states what 22.2 / 22.3
require; the script prints one line per case and exits 1 if any fails.

    .venv/Scripts/python.exe outputs/_dp_analyze_selftest.py [--out outputs/_dp_analyze_selftest_result.txt]
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_argv = sys.argv
sys.argv = _argv[:1]
import _dp_analyze as DA  # noqa: E402
sys.argv = _argv

U0, U1, U2 = "ff_unit_0", "ff_unit_1", "ff_unit_2"
V0, V1 = "victim_0", "victim_1"
LINES: list[str] = []
FAILS: list[str] = []


def cmd(step, phase, vid, uid, ok=True, action="assign", reason="initial"):
    """One dp.commands row: [step, phase, action, victim, unit, reason, success, route_open, d_route, manhattan]."""
    return [step, phase, action, vid, uid, reason, ok, True, 5, 5]


def case(name, cond, detail=""):
    LINES.append("%-4s %s%s" % ("PASS" if cond else "FAIL", name, ("  | " + detail) if detail else ""))
    if not cond:
        FAILS.append(name)


def latched_scene(b0_u0):
    """dp0: victim_1 latched-held at step 10 (its only binder ff_unit_2 route_blocked); ff_unit_0 free with a finite
    route (d 7) and b0(ff_unit_0, victim_1) = b0_u0 from its own earlier assigns."""
    cmds = [cmd(2, "post", V1, U2)]
    cmds += [cmd(3 + k, "post", V1, U0) for k in range(b0_u0)]
    binders = [[10, [[V1, [[U2, "route_blocked"]]]]]]
    waiting = [[10, 1, [[V1, [[U0, 7, 0]]]]]]          # dp0 records b = 0 (no live ledger)
    m3a = [[10, 1, 1, [U0]]]
    return cmds, binders, waiting, m3a


def main() -> int:
    # (1) a latched-held victim whose only finite-d free unit has b0 = 2 (blocked) and b0 = 1 (allowed)
    for b0, want in ((2, "blocked"), (1, "allowed")):
        cmds, binders, waiting, m3a = latched_scene(b0)
        num, lists, chk = DA.rb_figures(waiting, binders, m3a, cmds, False)
        got = "blocked" if num["gb_f_blocked"] == 1 and num["gb_f_allowed"] == 0 else (
            "allowed" if num["gb_f_allowed"] == 1 and num["gb_f_allowed_WL"] == 1 else "?")
        m3 = (num["m3b_allowed"], num["m3b_blocked"], num["m3a_allowed"], num["m3a_blocked"])
        m3_want = (0, 1, 0, 1) if want == "blocked" else (1, 0, 1, 0)
        case("(1) latched-held, b0 = %d -> %s (G-B(f), M3(b), M3(a))" % (b0, want),
             got == want and m3 == m3_want and not DA.rb_checks_fail(chk),
             "G-B(f) %s, M3 b-ok/b-blk/a-ok/a-blk %s, checks %s" % (got, m3, {k: v for k, v in chk.items() if v}))
    # (1') the same victim and pair with the cap NOT applied would be allowed: the cap is the arm-independent rule,
    # so a dp1 record (live ledger) with recorded b = 2 is blocked exactly like dp0's b0 = 2
    cmds, binders, waiting, m3a = latched_scene(2)
    waiting1 = [[10, 1, [[V1, [[U0, 7, 2]]]]]]
    m3a1 = [[10, 1, 0, [U0]]]
    num, lists, chk = DA.rb_figures(waiting1, binders, m3a1, cmds, True)
    case("(1') dp1 recorded b = 2 on a latched-held victim -> blocked, checks clean",
         num["gb_f_blocked"] == 1 and num["m3a_blocked"] == 1 and not DA.rb_checks_fail(chk),
         "num %s checks %s" % (dict(num), {k: v for k, v in chk.items() if v}))
    # (2) a W victim (no living binder) with b0 = 5 -> allowed (a FILL is uncapped)
    cmds = [cmd(1 + k, "post", V0, U0) for k in range(5)]
    waiting = [[10, 1, [[V0, [[U0, 4, 0]]]]]]
    num, lists, chk = DA.rb_figures(waiting, [[10, []]], [[10, 1, 1, [U0]]], cmds, False)
    led = DA.rb_ledgers(cmds, [10])[10][(U0, V0)]
    case("(2) W victim with b0 = 5 -> allowed", led == 5 and num["gb_f_allowed_W"] == 1 and num["gb_f_blocked"] == 0
         and num["m3a_allowed"] == 1, "b0 %d num %s" % (led, dict(num)))
    # (2') the cut: a post-phase assign AT the sample step counts, a later step's does not
    cmds = [cmd(10, "pre", V0, U0), cmd(10, "post", V0, U0), cmd(11, "pre", V0, U0)]
    led = DA.rb_ledgers(cmds, [9, 10, 11])
    case("(2') cut: b0 at steps 9 / 10 / 11 = 0 / 2 / 3",
         (led[9][(U0, V0)], led[10][(U0, V0)], led[11][(U0, V0)]) == (0, 2, 3),
         "%s" % [led[s][(U0, V0)] for s in (9, 10, 11)])
    # (3) a sweep-phase assign at the sample step -> REFUSED (tooling defect); so is one stamped init
    cmds = [cmd(2, "post", V1, U2), cmd(10, "sweep", V0, U0)]
    num, lists, chk = DA.rb_figures([[10, 1, [[V0, []]]]], [[10, [[V1, [[U2, "route_blocked"]]]]]], [], cmds, False)
    ref_init = DA.rb_cut_refusals([cmd(0, "init", V0, U0)])
    unsuccessful = DA.rb_cut_refusals([cmd(10, "sweep", V0, U0, ok=False), cmd(10, "sweep", V0, U0, action="unassign")])
    case("(3) a successful sweep-phase assign at the sample step is refused (also init; not a failed or an unassign)",
         chk["refused"] == [[10, "sweep", V0, U0, "initial"]] and DA.rb_checks_fail(chk) and len(ref_init) == 1
         and unsuccessful == [], "refused %s, init %s" % (chk["refused"], ref_init))
    # (4) a free unit with no finite route to any waiting victim: M3(a) reads it from the ids, with b0 from the
    # rebuild (its pair is in no waiting row); ff_unit_1 has b0 = 2 with the only waiting victim (latched-held) ->
    # blocked; ff_unit_0 (finite route, b0 = 1) -> allowed
    cmds = [cmd(2, "post", V1, U2), cmd(3, "post", V1, U0), cmd(4, "post", V1, U1), cmd(5, "post", V1, U1)]
    binders = [[10, [[V1, [[U2, "route_blocked"]]]]]]
    waiting = [[10, 2, [[V1, [[U0, 7, 0]]]]]]
    num, lists, chk = DA.rb_figures(waiting, binders, [[10, 2, 2, [U0, U1]]], cmds, False)
    case("(4) free unit with no finite route: M3(a) uses the ids (1 allowed, 1 blocked); M3(b) sees only the routed one",
         (num["m3a"], num["m3a_allowed"], num["m3a_blocked"], num["m3b_allowed"], num["m3b_blocked"]) == (2, 1, 1, 1, 0)
         and not DA.rb_checks_fail(chk), "num %s" % dict(num))
    num, lists, chk = DA.rb_figures(waiting, binders, [[10, 2, 2]], cmds, False)
    case("(4') an m3a row without ids (dp_probe v1) is refused for M3(a)",
         chk["m3a_noids"] == 1 and num["m3a_allowed"] == 0 and DA.rb_checks_fail(chk), "noids %d" % chk["m3a_noids"])
    # (5) a dp1 record whose recorded b disagrees with its commands -> TOOLING STOP (check (i)); also (ii) and (iii)
    cmds = [cmd(2, "post", V1, U2), cmd(3, "post", V1, U0), cmd(4, "post", V1, U0)]
    binders = [[10, [[V1, [[U2, "route_blocked"]]]]]]
    num, lists, chk = DA.rb_figures([[10, 1, [[V1, [[U0, 7, 1]]]]]], binders, [[10, 1, 1, [U0]]], cmds, True)
    case("(5) dp1 recorded b 1 vs rebuild 2 -> check (i) fails, R-B figures stop",
         chk["i"] == [[10, U0, V1, 1, 2]] and DA.rb_checks_fail(chk), "i %s" % chk["i"])
    num, lists, chk = DA.rb_figures([[10, 1, [[V1, [[U0, 7, 2]]]]]], binders, [[10, 1, 1, [U0]]], cmds, True)
    case("(5') dp1 recorded m3a n_ok 1 vs recomputed 0 -> check (ii) fails",
         chk["i"] == [] and len(chk["ii"]) == 1 and DA.rb_checks_fail(chk), "ii %s" % chk["ii"])
    num, lists, chk = DA.rb_figures([], [[10, [[V1, [[U2, "route_blocked"]]]]]], [], [cmd(11, "pre", V1, U2)], False)
    case("(5'') a binder whose assign is not before the cut -> check (iii) fails",
         chk["iii"] == [[10, U2, V1]] and DA.rb_checks_fail(chk), "iii %s" % chk["iii"])
    case("(5) ... and dp1's G-B(f) reads its RECORDED b (1: allowed), not the rebuild (2)",
         DA.rb_figures([[10, 1, [[V1, [[U0, 7, 1]]]]]], binders, [[10, 1, 1, [U0]]], cmds, True)[0]["gb_f_allowed"] == 1)
    # (4b) review 2: M3(a) counts a unit allowed through a W victim it has NO finite route to (22.2: "including those
    # with no finite route") - a W victim with no candidates and a latched-held victim whose only candidate is capped
    cmds = [cmd(2, "post", V1, U2), cmd(3, "post", V1, U0), cmd(4, "post", V1, U0)]
    binders = [[10, [[V1, [[U2, "route_blocked"]]]]]]
    num, lists, chk = DA.rb_figures([[10, 1, [[V0, []], [V1, [[U0, 7, 0]]]]]], binders, [[10, 1, 1, [U0]]], cmds,
                                    False)
    case("(4b) M3(a) allowed through an unreachable W victim; M3(b) blocked (the only routed pair is capped)",
         (num["m3a_allowed"], num["m3a_blocked"], num["m3b_allowed"], num["m3b_blocked"], num["gb_f_blocked"]) ==
         (1, 0, 0, 1, 1) and not DA.rb_checks_fail(chk), "num %s" % dict(num))
    # (2'') review 2: the cut keeps an ADVANCE-phase assign at the sample step and places a sweep one after it
    led = DA.rb_ledgers([cmd(10, "advance", V0, U0), cmd(10, "sweep", V0, U0)], [10, 11])
    case("(2'') cut: advance at step 10 counted at 10, sweep at step 10 only from 11 (b0 1 / 2)",
         (led[10][(U0, V0)], led[11][(U0, V0)]) == (1, 2), "%s" % [led[s][(U0, V0)] for s in (10, 11)])
    # (7) review 2: duplicate sample steps, and an m3a row with no waiting sample at its step, are tooling failures
    num, lists, chk = DA.rb_figures([[10, 0, [[V0, []]]]], [[10, []], [10, []]], [[11, 1, 1, [U0]]], [], False)
    case("(7) a duplicate binders step and an m3a row without its waiting sample -> checks fail",
         chk["dup"] == [["binders", 10]] and len(chk["ii"]) == 1 and DA.rb_checks_fail(chk),
         "dup %s ii %s" % (chk["dup"], chk["ii"]))
    # (8) review 2: a STOPPED G-B(f) makes the outcome undetermined - never "would be PASS"; another gate's FAIL stands
    import contextlib
    import io
    import types
    with open(os.path.join(HERE, "dispatch_part1.txt"), encoding="utf-8") as fh:
        sec15 = DA.section15(fh.read())
    ident = {"probe": True, "probe_same": 64, "probe_compared": 64, "shards": True, "mismatch": 0}
    st = {"missing": [], "invalid": [], "crash_dp1": []}
    M = {"S3": {"verdict": "PASS", "pass": True}, "S4": {"verdict": "PASS", "pass": True},
         "S5": {"pass": True, "items": {}}, "S6": {"pass": True, "median_R": 0.001, "p99": 5.0}}
    opts = types.SimpleNamespace(smoke=None, allow_incomplete=False)
    stop = "STOPPED (R-B tooling check failed - A2 22.2)"
    verdicts = []
    for g_n in (True, False):
        G = {"G-N": g_n, "G-B(f) allowed": stop, "G-B(f) blocked": stop, "_v": {"gb_f_allowed": 3}}
        with contextlib.redirect_stdout(io.StringIO()):
            verdicts.append(DA.sec_decision(sec15, ident, st, G, M, "PASS", "PASS", {"status": "PASS", "latched": 0},
                                            opts))
    case("(8) STOPPED G-B(f): verdict INCOMPLETE, outcome undetermined (no 'would be'); with another gate failing: FAIL",
         verdicts[0].startswith("INCOMPLETE (G-B(f) allowed, G-B(f) blocked STOPPED") and "would be" not in verdicts[0]
         and verdicts[1] == "FAIL", "%s" % verdicts)
    # (6) M8 (R-C): 0 deaths in a set -> not met; exactly 25% in both -> met; 24% -> not met
    entries = [{"victim": V0, "detection_step": 10, "death_step": 30, "min_d": 19},   # 19 + 1 <= 20: critical
               {"victim": V1, "detection_step": 10, "death_step": 30, "min_d": 20},   # 21 > 20: futile
               {"victim": "victim_2", "detection_step": 10, "death_step": None, "min_d": 3}]
    fc, fu, rows = DA.m8_classify(entries)
    case("(6a) M8 classification boundary: min_d + 1 == death - detection is FEASIBLE-CRITICAL; a survivor is not "
         "counted", (fc, fu) == (1, 1), "rows %s" % rows)
    case("(6b) a set with 0 detected-victim deaths -> not met", DA.m8_trigger({"set1": (0, 0), "set2": (1, 3)}) is False)
    case("(6c) exactly 25% in both sets -> MET", DA.m8_trigger({"set1": (1, 3), "set2": (2, 6)}) is True)
    case("(6d) 24% in one set -> not met", DA.m8_trigger({"set1": (6, 19), "set2": (1, 3)}) is False)
    LINES.append("")
    LINES.append("SELF-TEST %s (%d cases, %d failed)" % ("PASS" if not FAILS else "FAIL", sum(
        1 for ln in LINES if ln.startswith(("PASS", "FAIL"))), len(FAILS)))
    text = "\n".join(LINES)
    print(text)
    if "--out" in _argv:
        with open(_argv[_argv.index("--out") + 1], "w", encoding="utf-8", newline="\n") as fh:
            fh.write("dispatch amendment A2 22.5(4) - synthetic-record self-test of _dp_analyze.py R-B / R-C\n\n" +
                     text + "\n")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
