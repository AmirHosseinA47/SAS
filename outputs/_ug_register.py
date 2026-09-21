"""Ungated round: build outputs/ungated_runner_register.txt - every runner, queue arm and
probe whose meaning the FF_FIREFIGHT_* default flip changes.

Inputs, all read-only:
  - outputs/_ug_register_scan.py (the universe: git ls-files, no directory walk)
  - outputs/_flip_audit_coverage.json (the base-station flip's audit class of every
    runner/probe that existed at b853617 - none of which could set an FF switch)
  - the per-file rulings of the Part 1 audit of the 28 new model-touching probes and the
    8 pins this round's commit made (both below, verbatim from outputs/ungated_part1.txt)

  .venv/Scripts/python.exe -B outputs/_ug_register.py      (writes the register)
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _ug_register_scan as S  # noqa: E402

OUT = os.path.join(HERE, "ungated_runner_register.txt")

# Effective configuration model. E/F/K/G = extinguish, firebreak, engaged range, gate.
PRE_FLIP = {"E": 0, "F": 0, "K": 3, "G": 1}      # 11c3661 and every commit since d3640e3
POST_FLIP = {"E": 1, "F": 1, "K": 1, "G": 0}     # this round's shipped default
PRE_GATE = {"E": 0, "F": 0, "K": 3, "G": 0}      # 003ed91 / a3a24f1: no gate existed (== open)


def effective(sets, base):
    v = dict(base)
    for k in ("E", "F", "K", "G"):
        if k in sets:
            try:
                v[k] = int(float(sets[k]))
            except ValueError:
                v[k] = sets[k]
    ext = bool(v["E"]) and isinstance(v["K"], int) and 1 <= v["K"] < 2
    fb = bool(v["F"])
    if not (ext or fb):
        return "OFF"
    parts = []
    parts.append("E" if ext else "-")
    parts.append("F" if fb else "-")
    parts.append("K%s" % v["K"])
    parts.append("gate" if v["G"] else "ungated")
    return " ".join(parts)


def era(tag):
    if tag.startswith(("fm", "f2")):
        return "pre-gate (round 1/2 probes, before d3640e3)", PRE_GATE
    if tag.startswith("f3"):
        return "gate era (d3640e3)", PRE_FLIP
    return "no fire mechanic in use (switches off or absent)", PRE_FLIP


PINNED = {
    "outputs/_ir/rbgate.sh": "line 21",
    "outputs/_vm_runwaves.sh": "lines 16, 18",
    "outputs/_vm_runwaves2.sh": "lines 14, 16",
    "outputs/_ih_post.sh": "line 14 (its PYTEST stage still runs the shipped default)",
    "outputs/_dim_post.sh": "line 13 (its PYTEST stage still runs the shipped default)",
    "outputs/_vm_postwave.sh": "line 13 (its PYTEST stage still runs the shipped default)",
}

# Part 1 audit of the 28 model-touching probes added since b853617 (read-only agent,
# file:line evidence in its transcript; summarised in ungated_part1.txt 2.5).
NEW_PY = {
    "outputs/_bm_capture.py": ("SILENT-CHANGE", "live WildFireModel (:15, :37-40), no FF set; writes <prefix>_s<step>.json"),
    "outputs/_bm_capture2.py": ("SILENT-CHANGE", "live model (:19, :63-67); truth() hardcodes idle range 3 (:42), false for engaged units"),
    "outputs/_bm_trace.py": ("SILENT-CHANGE", "live model (:25, :63-73); records E/F/K effective values (:126-128) but not the gate"),
    "outputs/_dfp_frames.py": ("SILENT-CHANGE", "live model, FIREPROOF only (:49-54); OVERWRITES tracked _dfp_frame_{pre,post}.json (:84-85), no skip"),
    "outputs/_bm_payload.py": ("LOUD-DOWNSTREAM", "tag bmpost overwrites a tracked payload; _bm_compare.py:71-85 needs digests equal to _bm/p3/pre"),
    "outputs/_dfp_payload.py": ("LOUD", "FIREPROOF=0 control requires 0 cleared cells (:181); a firebreak clear counts (:116-118) -> FAIL, exit 1; overwrites tracked _dfp_payload.json/.txt"),
    "outputs/_firemech_cycle_search.py": ("FF-PARTIAL / RESTORED", "sets D/E/F/K, not G (:55-58): gated at HEAD, round-1 meaning again after the flip"),
    "outputs/_dfp_colour.py": ("FAILS-LOUDLY", "ROOT=E:/Projects/SAS_wt/dfp (:37) is gone; crashes at :54"),
    "outputs/_flip_behaviour_diff.py": ("LOUD", "cfv expectations (:21) lack the four flipped values: prints BAD after the flip"),
    "outputs/_firemech_band_probe.py": ("UNAFFECTED", "builds a model, never steps it"),
    "outputs/_fm2_fire_replay.py": ("UNAFFECTED", "fire-only replay: Fire agents only, no model.step() (:283-288)"),
    "outputs/_fm2_verify_replay.py": ("UNAFFECTED", "fire-only replay"),
    "outputs/_fm2_rng_offset.py": ("UNAFFECTED", "fire-only replay"),
    "outputs/_fm2_rng_pinned.py": ("UNAFFECTED", "fire-only replay"),
    "outputs/_fm2_diag_extvar.py": ("UNAFFECTED", "numpy only"),
    "outputs/_fm2_diag_south404.py": ("UNAFFECTED", "own pure-python fire replay"),
    "outputs/_fm2_probe_harness.py": ("PASSTHROUGH (harness)", "applies the in-tree gate ON TOP of FM2P_GATE (it wraps _firefight_prepare); unset FF switches take the new defaults"),
    "outputs/_bm_compare.py": ("UNAFFECTED", "comparator"), "outputs/_bm_page_e2e.py": ("UNAFFECTED", "headless page only"),
    "outputs/_bm_pixelaudit.py": ("UNAFFECTED", "reads images"), "outputs/_bm_proto.py": ("UNAFFECTED", "prototype page"),
    "outputs/_bm/p3/_verify_ast.py": ("UNAFFECTED", "AST reader"), "outputs/_bm/p3/_verify_payload2.py": ("UNAFFECTED", "reader"),
    "outputs/_dfp_page_gate.py": ("INHERITS _dfp_frames", "compares arms built from the frames _dfp_frames writes"),
    "outputs/_dfp_prereg.py": ("UNAFFECTED", "records source hashes of cfv/agents, which change"),
    "outputs/_sfx2_corpus.py": ("UNAFFECTED", "reader"), "outputs/_dfp_rbgate.py": ("UNAFFECTED", "reads shards"),
    "outputs/_fm3_rbgate.py": ("UNAFFECTED", "reads shards"), "outputs/_firemech_rbgate.py": ("UNAFFECTED", "reads shards"),
}
PASSTHROUGH_NOTE = {
    "outputs/_ffr_rbgate.sh": "callers _dim_post.sh:13 dimfix, _ih_post.sh:14 ihrest, _vm_postwave.sh:13 vmon "
                              "- FF-PINNED since the ungated commit; _dc_rbgate.sh dcrbA-D pass no FF switch "
                              "(FF-silent); every recorded shard exists, so a rerun SKIPs unless one is removed",
    "outputs/_ffr_runall.sh": "callers _vm_runwaves.sh vmoff/vmon and _vm_runwaves2.sh vmon3/vmoff2 - FF-PINNED "
                              "since the ungated commit; _lat_launch_base.sh latbase FAILS-LOUDLY; the recorded "
                              "ffabs/ffoff/phfix* invocations pass no FF switch (FF-silent)",
}
GENERATORS = ("outputs/_firemech_queue.py", "outputs/_fm2_queue.py", "outputs/_fm2_queue2.py",
              "outputs/_fm3_queue.py", "outputs/_dfp_queue.py")


def main():
    sys.stdout.reconfigure(newline="\n")
    tracked = S.git_list("--", "outputs")
    untracked = S.git_list("--others", "--exclude-standard", "--", "outputs")
    files = sorted(set(p for p in tracked + untracked if not p.startswith(S.QUAR)))
    audit = json.load(open(os.path.join(HERE, "_flip_audit_coverage.json")))
    flip = {}
    for key in ("shell", "python"):
        for path, cls, why in audit[key]:
            flip[path] = (cls, why)
    L = []
    say = L.append
    say("UNGATED RUNNER REGISTER - tooling whose meaning changes at the FF_FIREFIGHT_* default flip")
    say("Generated by outputs/_ug_register.py. Design: outputs/ungated_part1.txt 2.5.")
    say("")
    say("THE FLIP: FF_FIREFIGHT_EXTINGUISH 0->1, FIREBREAK 0->1, ENGAGED_RETREAT_RANGE 3->1,")
    say("MISSION_GATE 1->0 (DRY_RUN stays 0). Idle firefighters now fight fire from step 1 in")
    say("every run that does not set these switches.")
    say("")
    say("RULE (agents.Firefighter._firefight_prepare): a run is FF-SAFE iff it sets EXTINGUISH and")
    say("FIREBREAK explicitly and, when either is non-zero, ENGAGED_RETREAT_RANGE and MISSION_GATE")
    say("too. The minimal pin is --set FF_FIREFIGHT_EXTINGUISH=0 --set FF_FIREFIGHT_FIREBREAK=0.")
    say("")
    say("WHAT BETRAYS A POST-FLIP RUN: harness JSON gains firefight_log / firefight_counters /")
    say("firefight_shadow / fire_cleared_unburned_final once any unit engages. Gate shards")
    say("(_rblatch_camp2_*), evaluate_scenarios text and custom probe JSON DO NOT. The pool")
    say("validators compare only a queue line's own --set list, so they call such runs VALID.")
    say("")
    say("#" * 88)
    say("NOT COVERED BY THE 8 PINS - READ FIRST (Part 2 review finding; maintainer decision pending)")
    say("#" * 88)
    say("The 8 Q6 pins are the base-station flip's MODE=0 lines (_ir/rbgate.sh, _vm_runwaves.sh x2,")
    say("_vm_runwaves2.sh x2, _ih_post.sh, _dim_post.sh, _vm_postwave.sh). NONE of them is a fire-mechanic")
    say("line, so they do NOT protect a reproduction of round 2 (or round 1). REGISTERED ONLY, NOT PINNED:")
    say("  _fm3_queue.txt     f3OFF 27 lines, f3GATE 27, f3RES 13")
    say("  _fm3_rb_queue.txt  f3RBG{a,b,c,s}: 4 shard lines, 18 runs")
    say("Re-run AS-IS after the flip (accessors checked: E True, F True, K 1, gate False):")
    say("  f3GATE, f3RBG*  recorded 'E - K1 gate'      -> 'E F K1 ungated' (firebreak ON, gate OFF)")
    say("  f3OFF           recorded OFF                -> the full shipped feature")
    say("  f3RES           recorded 'E - K1 ungated'   -> gains the firebreak")
    say("The pool validators would call such reruns VALID, and the gate shards record no FF value.")
    say("Completed queue lines are NOT edited in place (the pools would quarantine the committed")
    say("runs and silently rerun them). REPRODUCTION RECIPE - always under NEW tags, all switches:")
    say("  f3GATE / f3RBG*  --set FF_FIREFIGHT_EXTINGUISH=1 --set FF_FIREFIGHT_FIREBREAK=0")
    say("                   --set FF_FIREFIGHT_ENGAGED_RETREAT_RANGE=1 --set FF_FIREFIGHT_MISSION_GATE=1")
    say("  f3RES            E=1 F=0 K=1 G=0")
    say("  f3OFF            E=0 F=0")
    say("  round 1 / f2 arms marked CHANGED in section A: set E and F to their recorded value (0 when the")
    say("  line did not set it), K to its recorded value (3 when unset) and G=0 (no gate existed then).")
    say("  Arms marked RESTORED need nothing beyond the recorded --set list.")
    say("")
    say("HOW TO REUSE ANY OF THIS: set all four FF switches (or E=0 F=0) explicitly; new tags;")
    say("never edit a completed queue line in place; the E:/Projects/SAS_wt/ worktrees are gone.")
    say("")
    say("EFFECTIVE CONFIGURATION NOTATION: 'E F K1 ungated' = extinguish, firebreak, engaged")
    say("range 1, no gate; '-' = that action impossible (extinguish needs K < 2); OFF = no action.")
    say("")

    # ---------------------------------------------------------------- queues
    say("=" * 88)
    say("A. QUEUE FILES - per arm: recorded / at 11c3661 (pre-flip) / after the flip")
    say("=" * 88)
    queues = [p for p in files if p.endswith(".txt") and "queue" in os.path.basename(p).lower()
              and not os.path.basename(p).startswith("_ug")]
    say("(this round's own queues, outputs/_ug_*queue*.txt, are excluded: every line in them sets its")
    say(" arm explicitly or deliberately runs the shipped default - outputs/ungated_part1.txt 6.3)")
    tot = collections.Counter()
    for q in queues:
        arms = collections.OrderedDict()
        for line in S.read_text(q).splitlines():
            parsed = S.parse_queue_line(line)
            if parsed is None:
                continue
            tag, repo, sets, n, fm2p = parsed
            cls = S.classify_sets(sets, repo)
            key = (tag, cls, tuple(sorted(sets.items())), tuple(fm2p))
            a = arms.setdefault(key, [0, 0])
            a[0] += 1
            a[1] += n
        if not arms:
            if q.endswith(("_l808_queue.txt", "_l808_queue2.txt")):
                say("%s  (seed|mode|wind format, not parsed)" % q)
                say("    %s" % ("FAILS-LOUDLY under its own _l808_pool.sh: CRLF death at the final write (28 lines)"
                               if q.endswith("_l808_queue.txt") else
                               "SILENT via _l808_pool2.sh (hardcoded sim command, no FF channel): 34 lines, now ungated"))
                tot["FAILS-LOUDLY" if q.endswith("_l808_queue.txt") else "CHANGED"] += 28 if q.endswith("_l808_queue.txt") else 34
            continue
        say(q)
        for (tag, cls, sets, fm2p), (nl, nr) in arms.items():
            sets = dict(sets)
            desc, base = era(tag)
            rec = effective(sets, base)
            head = effective(sets, PRE_FLIP)
            post = effective(sets, POST_FLIP)
            if cls in ("FAILS-LOUDLY", "OTHER-CHECKOUT"):
                verdict = cls + (" (checkout gone)" if cls == "FAILS-LOUDLY" else " (pre-feature checkout: unaffected)")
            elif post == rec:
                verdict = "RESTORED by the flip" if head != rec else "UNCHANGED"
            else:
                verdict = "CHANGED" + (" SILENTLY" if cls == "SILENT" else " (partial --set)")
            if cls == "PARTIAL":
                cls_out = "PARTIAL"
            else:
                cls_out = cls
            tot[(verdict.split(" ")[0])] += nl
            say("    %-12s %3d lines %3d runs  %-8s set=%s%s" % (
                tag, nl, nr, cls_out, ",".join("%s=%s" % kv for kv in sorted(sets.items())) or "-",
                (" +" + ",".join(fm2p)) if fm2p else ""))
            say("        recorded [%s]: %s | at 11c3661: %s | after flip: %s  => %s" % (
                desc.split(" (")[0], rec, head, post, verdict))
    say("")
    say("QUEUE LINE TOTALS BY VERDICT: %s" % dict(tot))
    say("")

    # ---------------------------------------------------------------- shell
    say("=" * 88)
    say("B. SHELL / POWERSHELL RUNNERS - only the PINNED group (6 files, 8 lines) sets an FF switch;")
    say("   every other entry sets none. Quoted reasons are the base-station audit's (b853617) unless")
    say("   marked FF.")
    say("=" * 88)
    shells = [p for p in files if p.endswith((".sh", ".ps1"))]
    groups = collections.defaultdict(list)
    for p in shells:
        if p in PINNED:
            groups["PINNED (FF-SAFE on the pinned lines since the ungated commit)"].append(
                (p, PINNED[p] + "; flip audit: " + flip.get(p, ("?", ""))[0]))
            continue
        cls, why = flip.get(p, (None, None))
        if p in PASSTHROUGH_NOTE:
            why = "FF: " + PASSTHROUGH_NOTE[p]
        if cls is None:
            if p.endswith("_ug_pytest.sh") or p.endswith("_flip_pytest.sh"):
                groups["PYTEST (runs the suite on the live tree: tests the shipped ungated default)"].append((p, "this round's / the flip round's suite runner"))
            elif p.endswith("_dfp_pool.sh") or "_pool" in p:
                groups["QUEUE-DRIVEN POOL (meaning = its queue, section A)"].append((p, "copy of _dcd4rb_pool.sh"))
            else:
                groups["UNCLASSIFIED"].append((p, ""))
            continue
        head = cls.split(" ")[0]
        if head in ("SILENT-CHANGE", "FLIP-SAFE", "SILENT-BY-CONSTRUCTION"):
            groups["FF-SILENT (runs the live tree at the default FF values -> now ungated)"].append((p, "flip audit %s: %s" % (cls, why)))
        elif head == "PASSTHROUGH":
            groups["PASSTHROUGH (meaning set by caller arguments; a caller without FF --set is now ungated)"].append((p, why))
        elif head == "PYTEST":
            groups["PYTEST (runs the suite on the live tree: tests the shipped ungated default)"].append((p, why))
        elif head == "FAILS-LOUDLY":
            groups["FAILS-LOUDLY (unchanged)"].append((p, why))
        else:
            groups["NOT-A-SIM (unaffected)"].append((p, why))
    for g in sorted(groups):
        say("-- %s (%d)" % (g, len(groups[g])))
        for p, why in groups[g]:
            say("  %s" % p)
            if why:
                say("      %s" % why[:400])
    say("")

    # ---------------------------------------------------------------- python
    say("=" * 88)
    say("C. PYTHON FILES IN outputs/")
    say("=" * 88)
    pys = [p for p in files if p.endswith(".py")]
    groups = collections.defaultdict(list)
    for p in pys:
        if p in NEW_PY:
            cls, why = NEW_PY[p]
            groups[cls].append((p, why))
            continue
        if p in GENERATORS:
            groups["QUEUE GENERATOR (its committed queue .txt is what pools read; section A)"].append((p, ""))
            continue
        if os.path.basename(p).startswith("_ug"):
            groups["THIS ROUND'S TOOLING"].append((p, ""))
            continue
        cls, why = flip.get(p, (None, None))
        if cls is None:
            groups["NOT-A-SIM (new since b853617: reader / analyzer / plugin, no model build)"].append((p, ""))
            continue
        head = cls.split(" ")[0]
        if head in ("SILENT-CHANGE", "SIM-EXPLICIT", "OTHER-CHECKOUT", "FAILS-LOUDLY") and cls != "FAILS-LOUDLY":
            groups["FF-SILENT (flip audit: %s)" % cls].append((p, why))
        elif cls == "FAILS-LOUDLY":
            groups["FAILS-LOUDLY (unchanged)"].append((p, why))
        elif head.startswith("HARNESS"):
            groups["PASSTHROUGH (harness / library)"].append((p, why))
        else:
            groups["NOT-A-SIM (flip audit)"].append((p, why))
    for g in sorted(groups):
        say("-- %s (%d)" % (g, len(groups[g])))
        for p, why in groups[g]:
            say("  %s%s" % (p, ("\n      " + why[:220]) if why else ""))
    say("")
    say("=" * 88)
    say("D. ENTRY POINTS")
    say("=" * 88)
    say("  evaluate_scenarios.py, serve_dashboard.py, main.py set no FF switch: from the flip on")
    say("  they run, score and show the ungated feature. A bare `python main.py` shows firefighters")
    say("  fighting fire from step 1. The dashboard's 'fire d/r' column shows r=3 for an engaged")
    say("  idle unit whose real retreat range is 1 (serve_dashboard.py:1025) - recorded, to be fixed")
    say("  in its own display round (maintainer ruling Q4).")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print("wrote %s (%d lines); queue totals %s" % (OUT, len(L), dict(tot)))


if __name__ == "__main__":
    main()
