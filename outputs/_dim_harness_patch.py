"""Apply / check / revert the dimension-round additions to outputs/_ffr_harness.py.

Binary mode, line ending of the file preserved, idempotent, reversible, all-or-
nothing (every anchor must be present and unique or nothing is written).

Additions (all behind new CLI options; a bare invocation is unchanged):
  --dim-hook {none,deny,record}   class-level HEIGHT/WIDTH property hook
  --dim-observe                   helper + consumer observers (counterfactual)
  --dim-pin a,b,c                 _grid_dimension -> None for the named callers
plus an unconditional read-only per-step UAV row (uav_steps) and a "dim" key
in the output JSON. Implementation: outputs/_dim_hooks.py.
"""
from __future__ import annotations
import argparse, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "_ffr_harness.py")

EDITS = [
    # A1: CLI options
    (
        b'    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")\n'
        b'    args = ap.parse_args()\n',
        b'    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")\n'
        b'    ap.add_argument("--dim-hook", default="none", choices=["none", "deny", "record"],\n'
        b'                    help="dimension round: deny = HEIGHT/WIDTH reads raise (control arm); "\n'
        b'                         "record = every read attributed to its caller")\n'
        b'    ap.add_argument("--dim-observe", action="store_true",\n'
        b'                    help="dimension round: wrap the boundary helpers and their consumers "\n'
        b'                         "with a per-call counterfactual (needs --dim-hook record)")\n'
        b'    ap.add_argument("--dim-pin", default="",\n'
        b'                    help="dimension round: comma-separated callers of _grid_dimension "\n'
        b'                         "forced back to None (one-site-live ablation arms)")\n'
        b'    args = ap.parse_args()\n',
    ),
    # A2: install after _step_of
    (
        b'    def _step_of(model) -> int:\n'
        b'        return int(getattr(model, "evaluation_timesteps_counter", 0) or 0)\n',
        b'    def _step_of(model) -> int:\n'
        b'        return int(getattr(model, "evaluation_timesteps_counter", 0) or 0)\n'
        b'\n'
        b'    # ---- dimension round: attribute hook / pins / observers, all read-only ----\n'
        b'    # Installed on the classes before the model is built. A bare invocation\n'
        b'    # (no --dim-* option) imports nothing and changes nothing.\n'
        b'    dim = None\n'
        b'    dim_pins = [p.strip() for p in str(args.dim_pin or "").split(",") if p.strip()]\n'
        b'    if args.dim_hook != "none" or args.dim_observe or dim_pins:\n'
        b'        import _dim_hooks  # noqa: E402  (outputs/ is the script directory, on sys.path)\n'
        b'        from src_extension.execution.uav_executor import UAVExecutor  # noqa: E402\n'
        b'        dim = _dim_hooks.install(WildFireModel, UAVExecutor, hook=args.dim_hook,\n'
        b'                                 observe=args.dim_observe, pins=dim_pins, step_of=_step_of)\n',
    ),
    # A3: bind the model for step attribution
    (
        b'        model = WildFireModel()\n'
        b'        model.debug_log = False\n'
        b'        for _ in range(args.steps):\n',
        b'        model = WildFireModel()\n'
        b'        model.debug_log = False\n'
        b'        if dim is not None:\n'
        b'            _dim_hooks.bind_model(model)\n'
        b'        for _ in range(args.steps):\n',
    ),
    # A4: uav_steps declaration
    (
        b'    victim_steps: list[list] = []\n',
        b'    victim_steps: list[list] = []\n'
        b'    # dimension round: per-step UAV rows (id, cell, role, selected_dir) so the\n'
        b'    # first diverging UAV step of a seed-matched pair can be located exactly.\n'
        b'    uav_steps: list[list] = []\n',
    ),
    # A5: per-step UAV row
    (
        b'            victim_steps.append(vrow)\n',
        b'            victim_steps.append(vrow)\n'
        b'            urow = []\n'
        b'            for a in model.schedule.agents:\n'
        b'                if type(a).__name__ != "UAV":\n'
        b'                    continue\n'
        b'                sd = getattr(a, "selected_dir", None)\n'
        b'                urow.append([\n'
        b'                    str(a.unique_id),\n'
        b'                    _cell(getattr(a, "pos", None)),\n'
        b'                    str(getattr(a, "current_role", "") or ""),\n'
        b'                    (int(sd) if sd is not None else None),\n'
        b'                ])\n'
        b'            uav_steps.append(urow)\n',
    ),
    # A6: output keys
    (
        b'        "victim_steps": victim_steps,\n',
        b'        "victim_steps": victim_steps,\n'
        b'        "uav_steps": uav_steps,\n'
        b'        "dim": (_dim_hooks.export() if dim is not None else None),\n',
    ),
]


def _eol(b: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in b else b"\n"


def read():
    with open(TARGET, "rb") as f:
        return f.read()


def write(b):
    with open(TARGET, "wb") as f:
        f.write(b)


def stats(b):
    crlf = b.count(b"\r\n")
    return "%d bytes, %d CRLF, %d bare-LF" % (len(b), crlf, b.count(b"\n") - crlf)


def state(b):
    eol = _eol(b)
    n_clean = n_patched = 0
    for anchor, patched in EDITS:
        a, p = anchor.replace(b"\n", eol), patched.replace(b"\n", eol)
        if b.count(p) == 1:
            n_patched += 1
        elif b.count(a) == 1:
            n_clean += 1
    if n_patched == len(EDITS):
        return "patched"
    if n_clean == len(EDITS):
        return "clean"
    return "unrecognised (%d clean, %d patched of %d)" % (n_clean, n_patched, len(EDITS))


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
    if st.startswith("unrecognised"):
        print("ERROR: anchors not in a consistent state; refusing to touch the file.")
        return 2
    if a.check:
        return 0
    eol = _eol(b)
    if a.apply:
        if st == "patched":
            print("after  : already patched, nothing to do (idempotent)")
            return 0
        for anchor, patched in EDITS:
            b = b.replace(anchor.replace(b"\n", eol), patched.replace(b"\n", eol))
    else:
        if st == "clean":
            print("after  : already clean, nothing to do (idempotent)")
            return 0
        for anchor, patched in EDITS:
            b = b.replace(patched.replace(b"\n", eol), anchor.replace(b"\n", eol))
    write(b)
    nb = read()
    print("after  : %s  (%s)" % (state(nb), stats(nb)))
    return 0


sys.exit(main())
