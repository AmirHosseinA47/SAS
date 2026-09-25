"""Validate the radius-8 detection predictor against the never_detected escape (an exact label of
'never confirmed, never assigned for 210 steps'):
 A) every victim marked never_detected at 210: was any UAV within 8 of its cell before 210? (predict: no)
 B) every victim whose victim_steps status is 'candidate' at the last step, not marked never_detected,
    horizon >= 211: predictor must say a UAV came within 8 (it was confirmed, label re-synced).
Non-recursive listdir of outputs/ (names only); sample of files."""
import json, os, math

OUT = r"E:\Projects\SAS\outputs"
names = sorted(n for n in os.listdir(OUT) if n.startswith("_ffr_") and n.endswith(".json"))


def first_within(vs, us, vid, upto):
    for t in range(1, min(upto, len(vs)) + 1):
        vrow = [r for r in vs[t - 1] if r[0] == vid]
        if not vrow or vrow[0][1] is None:
            continue
        vx, vy = vrow[0][1]
        for u in us[t - 1]:
            if u[1] is not None and math.hypot(u[1][0] - vx, u[1][1] - vy) <= 8:
                return t
    return None


A = [0, 0]
B = [0, 0]
badA, badB = [], []
for n in names[::4]:
    try:
        d = json.load(open(os.path.join(OUT, n)))
    except Exception:
        continue
    vs, us = d.get("victim_steps"), d.get("uav_steps")
    if not vs or not us or len(vs) != len(us):
        continue
    esc = d.get("unreachable_escape_log") or []
    nd = {e["victim_id"] for e in esc if e.get("cause") == "never_detected"}
    anymark = {e["victim_id"] for e in esc}
    for v in nd:
        A[0] += 1
        p = first_within(vs, us, v, 209)
        if p is None:
            A[1] += 1
        else:
            badA.append((n, v, p))
    if len(vs) >= 211:
        for r in vs[-1]:
            v = r[0]
            if r[2] == "candidate" and v not in anymark:
                B[0] += 1
                p = first_within(vs, us, v, len(vs))
                if p is not None:
                    B[1] += 1
                else:
                    badB.append((n, v))
print("A never_detected victims with NO UAV within 8 before 210:", A[1], "of", A[0], "exceptions", badA[:5])
print("B end-'candidate' unmarked victims with a UAV within 8 at some step:", B[1], "of", B[0], "exceptions", badB[:5])
