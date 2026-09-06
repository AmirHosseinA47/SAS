"""Apply / check / revert the grid-dimension plumbing fix (dimension round).

Same shape as outputs/_lc_patch.py and outputs/_ir_patch.py: binary mode, CRLF
preserved byte for byte, idempotent, reversible.

  --check   report whether the patch is present
  --apply   insert it
  --revert  remove it

The change is two instance attributes in WildFireModel.reset(), assigned on the
line after the mesa grid is built, plus the comment that explains them. Nothing
else in the file is touched. Design: outputs/dimension_part1.txt section 5.
"""
from __future__ import annotations
import argparse, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(os.path.dirname(HERE), "wildfire_model.py")

# Written with LF; converted to the file's own line ending at run time
# (wildfire_model.py is LF in the working tree and in the index; agents.py
# and uav_executor.py happen to be CRLF in the working tree - core.autocrlf
# is true, so the committed blob is LF either way). Whatever the file uses
# is preserved byte for byte.
ANCHOR_LF = (
    b"        self.grid = mesa.space.MultiGrid(HEIGHT, WIDTH, False)\n"
    b"        self.schedule = mesa.time.SimultaneousActivation(self)\n"
)

PATCHED_LF = (
    b"        self.grid = mesa.space.MultiGrid(HEIGHT, WIDTH, False)\n"
    b"        # Expose the grid extent on the instance. Every dimension read in\n"
    b"        # agents.py and src_extension/ asks the MODEL for HEIGHT/WIDTH and\n"
    b"        # silently falls back to a literal 50 (or to None, which disables the\n"
    b"        # executor's boundary helpers) when the attribute is missing - and it\n"
    b"        # always was. Same globals the grid was just built from, assigned in\n"
    b"        # the same call, so the two cannot disagree. mesa's MultiGrid takes\n"
    b"        # (width, height): grid.width is HEIGHT (the x extent), grid.height is\n"
    b"        # WIDTH (the y extent), which is why these are not derived from it.\n"
    b"        self.HEIGHT = HEIGHT\n"
    b"        self.WIDTH = WIDTH\n"
    b"        self.schedule = mesa.time.SimultaneousActivation(self)\n"
)


def _eol(b: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in b else b"\n"


def anchors(b: bytes):
    eol = _eol(b)
    return ANCHOR_LF.replace(b"\n", eol), PATCHED_LF.replace(b"\n", eol)


def read():
    with open(TARGET, "rb") as f:
        return f.read()


def write(b):
    with open(TARGET, "wb") as f:
        f.write(b)


def state(b):
    anchor, patched = anchors(b)
    if patched in b:
        return "patched"
    if anchor in b:
        return "clean"
    return "unrecognised"


def stats(b):
    crlf = b.count(b"\r\n")
    return "%d bytes, %d CRLF, %d bare-LF" % (len(b), crlf, b.count(b"\n") - crlf)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    b = read()
    st = state(b)
    print("target : %s" % TARGET)
    print("before : %s  (%s)" % (st, stats(b)))
    if st == "unrecognised":
        print("ERROR: neither the clean nor the patched anchor was found. "
              "Refusing to touch the file.")
        return 2
    if a.check:
        return 0
    anchor, patched = anchors(b)
    if a.apply:
        if st == "patched":
            print("after  : already patched, nothing to do (idempotent)")
            return 0
        if b.count(anchor) != 1:
            print("ERROR: anchor is not unique; refusing.")
            return 2
        write(b.replace(anchor, patched))
    else:
        if st == "clean":
            print("after  : already clean, nothing to do (idempotent)")
            return 0
        write(b.replace(patched, anchor))
    nb = read()
    print("after  : %s  (%s)" % (state(nb), stats(nb)))
    return 0


sys.exit(main())
