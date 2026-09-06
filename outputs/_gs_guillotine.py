"""For every victim written off (never_detected) in arm A, what happened to it in arm C
(same seed, timeout off): first detection step, final status, rescue step.
usage: _gs_guillotine.py --held A100 --off C100"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics

OUT = os.path.dirname(os.path.abspath(__file__))
DETECTED = ("confirmed", "assigned", "rescued")


def _load(tag):
    out = {}
    for f in glob.glob(os.path.join(OUT, "_gs_%s_*.json" % tag)):
        d = json.load(open(f, encoding="utf-8"))
        out[(d["wind"], d["roles"], int(d["seed"]))] = d
    return out


def _first(d, vid, statuses):
    for s, v, st, pos in d["victim_transitions"]:
        if v == vid and st in statuses:
            return int(s)
    return None


def _final(d, vid):
    st = None
    for s, v, stt, pos in d["victim_transitions"]:
        if v == vid:
            st = stt
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--held", default="A100")
    ap.add_argument("--off", default="C100")
    a = ap.parse_args()
    held = _load(a.held)
    off = _load(a.off)
    print("=== victims written off in %s (never_detected) -> fate in %s (timeout off) ===" % (a.held, a.off))
    det_steps, resc_steps = [], []
    n_wo = n_det = n_resc = n_dead_after_det = n_never = n_dead_undet = 0
    for key in sorted(held):
        dh = held[key]
        dc = off.get(key)
        wo = [m["vid"] for m in dh.get("unreachable_marks", []) if "never" in str(m.get("reason", "")).lower()]
        for vid in wo:
            n_wo += 1
            if dc is None:
                print("  %s %s: no %s run" % (key, vid, a.off))
                continue
            fd = _first(dc, vid, DETECTED)
            fr = _first(dc, vid, ("rescued",))
            fin = _final(dc, vid)
            fate = "never detected" if fd is None else ("rescued@%d" % fr if fr else "detected@%d then %s" % (fd, fin))
            print("  %-22s %-9s -> %s" % ("%s/%s/%d" % key, vid, fate))
            if fd is None:
                n_never += 1
                if fin == "dead":
                    n_dead_undet += 1
            else:
                n_det += 1
                det_steps.append(fd)
                if fr:
                    n_resc += 1
                    resc_steps.append(fr)
                elif fin == "dead":
                    n_dead_after_det += 1
    print("  write-offs: %d | detected later when the timeout is off: %d (rescued %d, died after detection %d) | never detected in 960 steps: %d (of which died %d)" % (
        n_wo, n_det, n_resc, n_dead_after_det, n_never, n_dead_undet))
    if det_steps:
        ds = sorted(det_steps)
        print("  detection steps of the rescued-or-detected write-offs: %s | median %d, p90 %d, max %d" % (
            ds, statistics.median(ds), ds[int(0.9 * (len(ds) - 1))], ds[-1]))
    if resc_steps:
        rs = sorted(resc_steps)
        print("  rescue steps: %s | median %d, max %d" % (rs, statistics.median(rs), rs[-1]))
    # whole-arm detection distribution with the timeout off
    all_det = sorted(s for d in off.values() for vid in d["geometry"]["victim_spawns"] for s in [_first(d, vid, DETECTED)] if s is not None)
    n_all = sum(len(d["geometry"]["victim_spawns"]) for d in off.values())
    print("  %s: %d/%d victims ever detected; detection steps median %s p90 %s max %s; budget needed to see 90%% / 100%% of detections: %s / %s" % (
        a.off, len(all_det), n_all, statistics.median(all_det) if all_det else "-", all_det[int(0.9 * (len(all_det) - 1))] if all_det else "-", all_det[-1] if all_det else "-",
        all_det[int(0.9 * (len(all_det) - 1))] if all_det else "-", all_det[-1] if all_det else "-"))
    all_resc = sorted(s for d in off.values() for vid in d["geometry"]["victim_spawns"] for s in [_first(d, vid, ("rescued",))] if s is not None)
    print("  %s: %d rescues; rescue steps median %s p90 %s max %s" % (a.off, len(all_resc), statistics.median(all_resc) if all_resc else "-", all_resc[int(0.9 * (len(all_resc) - 1))] if all_resc else "-", all_resc[-1] if all_resc else "-"))
    for T in (240, 300, 400, 500, 600, 700, 800, 960):
        print("    rescues completed by step %d: %d ; detections by %d: %d" % (T, sum(1 for s in all_resc if s <= T), T, sum(1 for s in all_det if s <= T)))


if __name__ == "__main__":
    main()
