"""Base-mark round Part 3: are the images the legibility-gate readers saw what the
FINAL source renders?  The gate images were produced before a late layout fix to
the firefighter TABLE (which does not touch the canvas). This re-renders every
gate image from the current working tree (or from the pre rev, for the status
quo) and compares sha256 of the RGB pixels. Writes the result next to the images.

usage: _bm_gate_images_check.py <pre_rev>
"""
from __future__ import annotations
import hashlib, os, subprocess, sys

BASE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(BASE, "_bm", "p3", "gate")
F = {"q": "f_east_101_s0.json", "b": "f_west_101_s105.json", "s": "f_south_202_s99.json"}


def sha(p):
    from PIL import Image
    return hashlib.sha256(Image.open(p).convert("RGB").tobytes()).hexdigest()


def main() -> int:
    pre = sys.argv[1]; lines = []; bad = 0
    for line in open(os.path.join(G, "_mapping_gate.txt")):
        neutral, name = line.split()
        kind, frame, scale = name.split("_")
        rev = "WORKTREE" if kind == "shipped" else pre
        tmp = os.path.join(G, "_recheck.png")
        subprocess.run([sys.executable, os.path.join(BASE, "_bm_scaled_shots.py"), rev, scale[1:], tmp,
                        os.path.join(BASE, "_bm", "p3", F[frame])], capture_output=True, check=True)
        same = sha(tmp) == sha(os.path.join(G, neutral)) == sha(os.path.join(G, name + ".png"))
        bad += (not same)
        lines.append("%s  %-18s rendered from %-8s == image the reader saw: %s  %s"
                     % (neutral, name, rev, same, sha(os.path.join(G, neutral))[:16]))
        os.remove(tmp)
    lines.append("ALL %d GATE IMAGES MATCH THE FINAL SOURCE" % len(lines) if not bad else "%d MISMATCH" % bad)
    open(os.path.join(G, "_images_vs_final_source.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
