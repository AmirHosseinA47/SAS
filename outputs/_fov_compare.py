"""FOV-frame round Part 3: pre vs post gate.

Deliberately NOT _sc_compare.py. That script requires cellcolor_sha256 to
DIFFER, because in the scorched round the change WAS a cell colour. Here the
change is an overlay drawn in JS from the uavs/victims payload, and
serve_dashboard's `cells` dict is built inside a Fire-only loop - no UAV,
victim or firefighter can contribute a byte to it. cellcolor therefore CANNOT
move, and requiring it to would fail a correct patch; leaving it as the positive
control would pass a patch that was never exercised. It is demoted to a NEGATIVE
control here, the mirror of the demotion _rh_control.py:26-28 records.

  SIMULATION  identical   stdout / positions / firemap / scorchmap / eval / residue
  cellcolor   identical   NEGATIVE control - this round touches no cell decider
  fovpayload  DIFFERS     POSITIVE control A - the overlay payload
  pixels      DIFFERS     POSITIVE control C - the rendered dashboard

STALENESS GUARD, learned the hard way in this round. The repo already ships
_sc_control_pre.json and _sc_control_post.json, committed by the scorched round
at 3b1ffbf, and _sc_control.py writes its JSON only once, at the very end. A
first run of this comparator read those committed files instead of the in-flight
ones and reported the gate as FAILED on the negative control - correctly, since
in THAT round cellcolor was the positive control and was required to differ.
The lesson is the repo's own recorded instrument-drift hazard, so this script
now reads distinctly TAGGED files this round produces (fovpre/fovpost) and
refuses to run on anything older than the patch, rather than trusting a path.

usage: _fov_compare.py <pre_outputs_dir> [max_age_seconds]
"""
from __future__ import annotations
import json, os, subprocess, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)
PRE = sys.argv[1] if len(sys.argv) > 1 else BASE
MAX_AGE = float(sys.argv[2]) if len(sys.argv) > 2 else 86400.0

PRE_JSON = os.path.join(PRE, "_sc_control_fovpre.json")
POST_JSON = os.path.join(BASE, "_sc_control_fovpost.json")


def _fresh(path: str) -> float:
    if not os.path.exists(path):
        raise SystemExit("MISSING %s - the control arm did not finish" % path)
    age = time.time() - os.path.getmtime(path)
    if age > MAX_AGE:
        raise SystemExit(
            "STALE %s (%.0f s old, limit %.0f). Refusing to compare: this is the "
            "trap that made the first run of this gate read as a failure."
            % (path, age, MAX_AGE))
    return age


print("provenance:")
for p in (PRE_JSON, POST_JSON):
    print("  %-58s %6.0f s old" % (os.path.relpath(p, REPO), _fresh(p)))
print("  post tree HEAD: %s" % subprocess.run(
    ["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
    capture_output=True, text=True).stdout.strip())

pre = json.load(open(PRE_JSON, encoding="utf-8"))
post = json.load(open(POST_JSON, encoding="utf-8"))

SIM = ["stdout_sha256", "stdout_lines", "stdout_len", "agent_positions_sha256",
       "firemap_sha256", "scorchmap_sha256", "leftover_pending"]
DICTS = ["eval", "residue", "ground_counts"]

ok = True
bar = "=" * 78
print(bar); print("1. SIMULATION DIGESTS - must be IDENTICAL"); print(bar)
for key in sorted(pre["runs"]):
    a, b = pre["runs"][key], post["runs"][key]
    print("\n%s" % key)
    for f in SIM + DICTS:
        same = a[f] == b[f]
        ok &= same
        shown = str(a[f])[:24] if f in SIM else "(dict)"
        print("  %-26s %-26s %s" % (f, shown, "IDENTICAL" if same
              else "*** DIFFERS *** post=%s" % str(b[f])[:40]))
    # full position list, not just its hash
    same = a["agent_positions"] == b["agent_positions"]
    ok &= same
    print("  %-26s %-26s %s" % ("agent_positions (full list)",
                                "%d entries" % len(a["agent_positions"]),
                                "IDENTICAL" if same else "*** DIFFERS ***"))

print("\n" + bar); print("2. RAW STDOUT BYTE DIFF"); print(bar)
for key in sorted(pre["runs"]):
    stem = key.replace("/", "-").replace("|", "_")
    fa = os.path.join(PRE, "_sc_control_fovpre_%s.stdout.txt" % stem)
    fb = os.path.join(BASE, "_sc_control_fovpost_%s.stdout.txt" % stem)
    ba, bb = open(fa, "rb").read(), open(fb, "rb").read()
    same = ba == bb
    ok &= same
    print("  %-22s pre %7d B / post %7d B   %s"
          % (key, len(ba), len(bb), "IDENTICAL" if same else "*** DIFFERS ***"))
    if not same:
        import difflib
        da = ba.decode("utf-8", "replace").splitlines()
        db = bb.decode("utf-8", "replace").splitlines()
        for ln in list(difflib.unified_diff(da, db, "pre", "post", n=1))[:20]:
            print("      " + ln.rstrip())

print("\n" + bar); print("3. NEGATIVE CONTROL - cellcolor must be IDENTICAL"); print(bar)
print("   (the scorched round's POSITIVE control, demoted: `cells` is built in a")
print("    Fire-only loop at serve_dashboard.py:117-126, so an overlay moves 0 bytes)")
for key in sorted(pre["runs"]):
    a, b = pre["runs"][key], post["runs"][key]
    same = a["cellcolor_sha256"] == b["cellcolor_sha256"]
    ok &= same
    print("  %-22s %s  %s" % (key, a["cellcolor_sha256"][:16],
                              "IDENTICAL" if same else "*** DIFFERS ***"))

print("\n" + bar); print("4. POSITIVE CONTROL A - overlay payload must DIFFER"); print(bar)
pa = json.load(open(os.path.join(PRE, "_fov_payload_pre.json"), encoding="utf-8"))
pb = json.load(open(os.path.join(BASE, "_fov_payload_post.json"), encoding="utf-8"))
moved = pa["fovpayload_sha256"] != pb["fovpayload_sha256"]
ok &= moved
print("  pre  %s  radius=%s flee=%s ffdist=%s" % (pa["fovpayload_sha256"][:16],
      pa["publishes_fov_radius"], pa["publishes_flee"], pa["publishes_ffdist"]))
print("  post %s  radius=%s flee=%s ffdist=%s" % (pb["fovpayload_sha256"][:16],
      pb["publishes_fov_radius"], pb["publishes_flee"], pb["publishes_ffdist"]))
print("  %s" % ("DIFFERS - control fires" if moved else "*** IDENTICAL - CONTROL DID NOT FIRE ***"))
for k in ("publishes_fov_radius", "publishes_flee", "publishes_ffdist"):
    good = (pa[k] is False) and (pb[k] is True)
    ok &= good
    print("  %-24s pre=%-5s post=%-5s %s" % (k, pa[k], pb[k], "OK" if good else "*** WRONG ***"))

print("\n" + bar); print("5. POSITIVE CONTROL C - rendered pixels must DIFFER"); print(bar)
for tag, fn in (("nominal", "_fov_pixelaudit_r30.json"), ("edge-clipped", "_fov_pixelaudit_clip.json")):
    p = os.path.join(BASE, fn)
    if not os.path.exists(p):
        print("  %-14s (missing %s)" % (tag, fn)); ok = False; continue
    d = json.load(open(p))
    good = d["changed"] > 0 and d["stray"] == 0 and d["silent_segments"] == 0
    ok &= good
    print("  %-14s changed %6d  on-geometry %6d  stray %d  silent %d  %s"
          % (tag, d["changed"], d["on_geometry"], d["stray"], d["silent_segments"],
             "PASS" if good else "*** FAIL ***"))

print("\n" + bar)
print("GATE: %s" % ("PASS" if ok else "FAIL"))
print(bar)
raise SystemExit(0 if ok else 1)
