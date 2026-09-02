"""Defect #7 Part-2 analysis: aggregate the 13-run fail-safe override sample."""
from __future__ import annotations
import glob, json, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(pat):
    out = []
    for p in sorted(glob.glob(os.path.join(HERE, pat))):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                out.append((os.path.basename(p), json.load(fh)))
        except Exception as exc:
            print("SKIP %s: %s" % (p, exc))
    return out


def hdr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


runs = load("_fs_east_half_*.json") + load("_fs_south_half_*.json") + load("_fs_east_def_*.json")
print("loaded %d lifecycle runs" % len(runs))

hdr("1. PER-RUN OVERRIDE LIFECYCLE")
print("%-22s %6s %6s %7s %8s %8s %8s %7s %7s" % (
    "run", "upd", "trans", "clrFire", "clrSurv", "sopW", "sopMMw", "srn", "ira"))
tot = {"clear": 0, "surv": 0, "resolve": 0, "sopmm": 0, "srn": 0, "ira": 0, "skip": 0}
stale_rows = []
for name, d in runs:
    r = d["rec"]
    sop_mm_writes = sum(1 for w in r["sop_writes"] if w[3] == "mission_mode")
    print("%-22s %6d %6d %7d %8d %8d %8d %7d %7d" % (
        name.replace("_fs_", "").replace(".json", ""),
        r["mm_update_calls"], len(r["mm_transitions"]),
        r["disp_clear_fires"], r["disp_survives"],
        len(r["sop_writes"]), sop_mm_writes,
        r["mm_should_return_calls"], r["mm_is_inforecovery_calls"]))
    tot["clear"] += r["disp_clear_fires"]
    tot["surv"] += r["disp_survives"]
    tot["resolve"] += r["disp_resolve_true"]
    tot["sopmm"] += sop_mm_writes
    tot["srn"] += r["mm_should_return_calls"]
    tot["ira"] += r["mm_is_inforecovery_calls"]
    tot["skip"] += r["disp_skip_global"]
    # STALENESS: steps where ModeManager mode is normal but sop.mission_mode is not
    stale = [s for s in r["step_mode"]
             if s[1] == "normal" and s[2] not in ("None", "normal", "")]
    stale_rows.append((name, len(stale), stale[:3], stale[-3:] if stale else []))
print("\nTOTALS: resolve_true=%d clear_fires=%d survives=%d skip_global=%d "
      "sop_mission_mode_writes=%d should_return_to_normal_calls=%d is_info_recovery_calls=%d"
      % (tot["resolve"], tot["clear"], tot["surv"], tot["skip"], tot["sopmm"],
         tot["srn"], tot["ira"]))

hdr("2. STALENESS: steps with mode==normal BUT sop.mission_mode still non-normal")
tot_stale = 0
for name, n, first, last in stale_rows:
    tot_stale += n
    print("%-22s stale_steps=%4d  first=%s  last=%s"
          % (name.replace("_fs_", "").replace(".json", ""), n, first, last))
print("\nTOTAL STALE STEPS ACROSS SAMPLE: %d" % tot_stale)

hdr("3. MODE OCCUPANCY (update() calls ending in each mode)")
agg = {}
for _n, d in runs:
    for k, v in d["rec"]["mm_mode_calls_by_mode"].items():
        agg[k] = agg.get(k, 0) + v
tot_upd = sum(agg.values())
for k, v in sorted(agg.items(), key=lambda x: -x[1]):
    print("  %-22s %8d  (%5.1f%%)" % (k, v, 100.0 * v / max(tot_upd, 1)))

hdr("4. MODE EPISODE DURATIONS (consecutive end-of-step runs in one mode)")
# Derived from the per-step end-of-step mode, so an episode closes on ANY mode
# change (including non-normal -> non-normal), not only on a return to normal.
by_mode = {}
open_at_end = []
for name, d in runs:
    seq = [(s[0], s[1]) for s in d["rec"]["step_mode"]]
    if not seq:
        continue
    cur_mode, start = seq[0][1], seq[0][0]
    for step, m in seq[1:] + [(None, "<END>")]:
        if m != cur_mode:
            dur = (d["steps"] if step is None else step - 1) - start + 1
            by_mode.setdefault(cur_mode, []).append(dur)
            if step is None:
                open_at_end.append((name, cur_mode, dur))
            cur_mode, start = m, step
for m, lst in sorted(by_mode.items(), key=lambda x: -len(x[1])):
    print("  %-22s episodes=%4d  min=%3d med=%6.1f max=%4d  total_steps=%5d"
          % (m, len(lst), min(lst), statistics.median(lst), max(lst), sum(lst)))
print("\n  episodes still open at run end (persisted to the last step):")
for name, m, dur in open_at_end:
    print("    %-22s mode=%-22s final_run_length=%d"
          % (name.replace("_fs_", "").replace(".json", ""), m, dur))
print("\n  full duration distributions:")
for m, lst in sorted(by_mode.items(), key=lambda x: -len(x[1])):
    print("    %-22s %s" % (m, sorted(lst)))

hdr("4b. INTRA-STEP TRANSITIONS (visible only via direct hooks, not sampling)")
intra = 0
for name, d in runs:
    per_step = {}
    for t in d["rec"]["mm_transitions"]:
        per_step[t[0]] = per_step.get(t[0], 0) + 1
    n = sum(1 for k, v in per_step.items() if v > 1)
    intra += n
    if n:
        print("  %-22s steps with >1 transition inside them: %d"
              % (name.replace("_fs_", "").replace(".json", ""), n))
print("  TOTAL steps containing more than one mode transition: %d" % intra)

hdr("5. DISPATCHER CLEAR EVENTS (override resolved True, but mode read == normal)")
for name, d in runs:
    det = d["rec"]["disp_clear_detail"]
    if det:
        print("  %s: %d events" % (name, len(det)))
        for row in det[:8]:
            print("     step=%s mission_mode=%r action=%r search=%s reason=%r mode_at_read=%r"
                  % tuple(row))

hdr("6. WHAT THE DECISION LOOKED LIKE (mission_mode histogram over dispatches)")
dm, rr = {}, {}
for _n, d in runs:
    for k, v in d["rec"]["disp_decision_modes"].items():
        dm[k] = dm.get(k, 0) + v
    for k, v in d["rec"]["disp_resolve_reasons"].items():
        rr[k] = rr.get(k, 0) + v
for k, v in sorted(dm.items(), key=lambda x: -x[1]):
    print("  decision.mission_mode %-24s %6d" % (k, v))
print()
for k, v in sorted(rr.items(), key=lambda x: -x[1]):
    print("  override_reason %-58s %6d" % (k[:58], v))

hdr("7. SOP WRITE SITES (all runs)")
ws = {}
for _n, d in runs:
    for k, v in d["rec"]["sop_write_sites"].items():
        ws[k] = ws.get(k, 0) + v
for k, v in sorted(ws.items(), key=lambda x: -x[1]):
    print("  %8d  %s" % (v, k))
print("\n  sop_same_object (model vs knowledge_manager):",
      set(d.get("sop_same_object") for _n, d in runs))
print("  final SOP per run:")
for name, d in runs:
    print("    %-22s %s" % (name.replace("_fs_", "").replace(".json", ""), d["final_sop"]))

hdr("8. REASON SETS ACTUALLY OBSERVED")
rs = {}
for _n, d in runs:
    for k, v in d["rec"]["sc_reason_sets"].items():
        rs[k] = rs.get(k, 0) + v
for k, v in sorted(rs.items(), key=lambda x: -x[1])[:20]:
    print("  %8d  %s" % (v, k))

hdr("9. OUTCOMES vs OVERRIDE ACTIVITY")
print("%-22s %8s %8s %6s %5s %5s %5s %6s %6s" % (
    "run", "clrFire", "survives", "stale", "resc", "dead", "ffd", "nvdet", "term"))
for (name, d), (_n2, ns, _f, _l) in zip(runs, stale_rows):
    e = d["eval"]
    r = d["rec"]
    print("%-22s %8d %8d %6d %5s %5s %5s %6s %6s" % (
        name.replace("_fs_", "").replace(".json", ""),
        r["disp_clear_fires"], r["disp_survives"], ns,
        e["rescued"], e["dead"], e["firefighter_deaths"],
        e["never_detected"], e["terminal_step"]))
