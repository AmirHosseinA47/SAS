"""Defect #9-A2 Part 3: pre vs post digest comparison.

Simulation digests (stdout, agent positions, firemap, scorchmap, eval metrics,
residue, leftover pending) MUST be identical.
The cellcolor digest MUST DIFFER - it is the positive control proving the
rendering change actually took effect on these runs.
"""
import hashlib, json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
pre = json.load(open(os.path.join(BASE, "_sc_control_pre.json"), encoding="utf-8"))
post = json.load(open(os.path.join(BASE, "_sc_control_post.json"), encoding="utf-8"))

SIM = ["stdout_sha256", "stdout_lines", "stdout_len", "agent_positions_sha256",
       "firemap_sha256", "scorchmap_sha256", "leftover_pending"]
ok = True
print("=" * 78)
print("SIMULATION DIGESTS - must be IDENTICAL")
print("=" * 78)
for key in sorted(pre["runs"]):
    a, b = pre["runs"][key], post["runs"][key]
    print("\n%s" % key)
    for f in SIM:
        same = a[f] == b[f]
        ok &= same
        v = str(a[f])
        print("  %-24s %-20s %s" % (f, v[:20], "IDENTICAL" if same else
                                    "*** DIFFERS *** post=%s" % str(b[f])[:20]))
    for f in ("eval", "residue", "ground_counts"):
        same = a[f] == b[f]
        ok &= same
        print("  %-24s %-20s %s" % (f, "(dict)", "IDENTICAL" if same else
                                    "*** DIFFERS ***\n    pre =%s\n    post=%s" % (a[f], b[f])))

print("\n" + "=" * 78)
print("RAW STDOUT DIFF - byte comparison of the captured files")
print("=" * 78)
for key in sorted(pre["runs"]):
    stem = key.replace("/", "-").replace("|", "_")
    fa = os.path.join(BASE, "_sc_control_pre_%s.stdout.txt" % stem)
    fb = os.path.join(BASE, "_sc_control_post_%s.stdout.txt" % stem)
    ba, bb = open(fa, "rb").read(), open(fb, "rb").read()
    same = ba == bb
    ok &= same
    print("  %-20s pre %6d bytes / post %6d bytes  sha %s  %s"
          % (key, len(ba), len(bb), hashlib.sha256(ba).hexdigest()[:16],
             "BYTE-IDENTICAL" if same else "*** DIFFERS ***"))

print("\n" + "=" * 78)
print("AGENT POSITIONS - full list comparison, not just the hash")
print("=" * 78)
for key in sorted(pre["runs"]):
    a, b = pre["runs"][key]["agent_positions"], post["runs"][key]["agent_positions"]
    same = a == b
    ok &= same
    print("  %-20s %d entries  %s" % (key, len(a),
          "IDENTICAL" if same else "*** DIFFERS *** %s"
          % [x for x in zip(a, b) if x[0] != x[1]][:3]))

print("\n" + "=" * 78)
print("POSITIVE CONTROL: cellcolor digest - must DIFFER (change took effect)")
print("=" * 78)
changed = True
for key in sorted(pre["runs"]):
    a, b = pre["runs"][key], post["runs"][key]
    diff = a["cellcolor_sha256"] != b["cellcolor_sha256"]
    changed &= diff
    print("\n%s  %s" % (key, "DIFFERS (as required)" if diff else "*** UNCHANGED - BAD ***"))
    print("    pre  %s  %s" % (a["cellcolor_sha256"][:16], a["cellcolor_hist"]))
    print("    post %s  %s" % (b["cellcolor_sha256"][:16], b["cellcolor_hist"]))
    pre_h, post_h = a["cellcolor_hist"], b["cellcolor_hist"]
    moved = pre_h.get("#2b2b2b", 0) - post_h.get("#2b2b2b", 0)
    print("    cells moved off #2b2b2b: %d   -> #895e00: %d   scorched count: %d"
          % (moved, post_h.get("#895e00", 0), a["ground_counts"]["scorched"]))
    consistent = (post_h.get("#895e00", 0) == moved)
    changed &= consistent
    print("    accounting: %s" % ("EXACT - every cell that left #2b2b2b became #895e00"
                                  if consistent else "*** MISMATCH ***"))

print("\n" + "=" * 78)
print("VERDICT")
print("=" * 78)
print("  simulation unchanged : %s" % ("PASS" if ok else "FAIL"))
print("  render change took effect : %s" % ("PASS" if changed else "FAIL"))
sys.exit(0 if (ok and changed) else 1)
