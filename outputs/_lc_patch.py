"""Apply / check / revert the last_cell emergency re-admission (option b).

Same shape as outputs/_ir_patch.py from the idle-retreat round: binary mode,
CRLF preserved byte for byte, idempotent, and reversible.

  --check   report whether the patch is present
  --apply   insert it
  --revert  remove it

The change is a four-line terminal fallback inside `_retreat_candidates`.
Nothing above `return candidates` is touched, the signature is unchanged, and
the re-admitted cell still goes through the fire and leash filters because the
fallback re-runs the same chain with `last_cell=None`.
"""
from __future__ import annotations
import argparse, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(os.path.dirname(HERE), "agents.py")

ANCHOR = (
    b"                }\r\n"
    b"            )\r\n"
    b"        return candidates\r\n"
    b"\r\n"
    b"    def _pick_improving_retreat(\r\n"
)

PATCHED = (
    b"                }\r\n"
    b"            )\r\n"
    b"        if not candidates and last_cell is not None and current_dist == 0:\r\n"
    b"            # The unit is standing on a burning cell and every neighbour it\r\n"
    b"            # could still step to was ruled out by the anti-oscillation\r\n"
    b"            # memory. That memory exists to stop a unit ping-ponging between\r\n"
    b"            # two free cells, and it cannot serve that purpose here: the cell\r\n"
    b"            # being vacated is on fire, so the fire test above - which comes\r\n"
    b"            # first and so outranks it - refuses the step back anyway until\r\n"
    b"            # that cell burns out. Re-run the same chain without it, so\r\n"
    b"            # `last_cell` is considered only when nothing else survived and\r\n"
    b"            # every other filter, the leash included, still applies to it.\r\n"
    b"            return self._retreat_candidates(\r\n"
    b"                cell, origin, None, fire_cells, current_dist\r\n"
    b"            )\r\n"
    b"        return candidates\r\n"
    b"\r\n"
    b"    def _pick_improving_retreat(\r\n"
)


def read():
    with open(TARGET, "rb") as f:
        return f.read()


def write(b):
    with open(TARGET, "wb") as f:
        f.write(b)


def state(b):
    if PATCHED in b:
        return "patched"
    if ANCHOR in b:
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
    if a.apply:
        if st == "patched":
            print("after  : already patched, nothing to do (idempotent)")
            return 0
        nb = b.replace(ANCHOR, PATCHED)
        if nb.count(PATCHED) != 1:
            print("ERROR: anchor is not unique; refusing.")
            return 2
        write(nb)
    else:
        if st == "clean":
            print("after  : already clean, nothing to do (idempotent)")
            return 0
        nb = b.replace(PATCHED, ANCHOR)
        write(nb)
    nb = read()
    print("after  : %s  (%s)" % (state(nb), stats(nb)))
    return 0


sys.exit(main())
