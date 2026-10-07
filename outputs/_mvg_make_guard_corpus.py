"""MVG round Part 2d (outputs/urgency_part1d.txt 1d.8 (4) T-G7): the GUARD CORPUS - every live fix (a) / (b) decision
of the urgency screen's replayed arm-M runs, with its decision board and the FROZEN guard's verdict on it, written as
test data for tests/test_stranding_guard.py::test_tg7_* (the built movement_paths.stranding_guard must equal it on
every decision; value identity, no outcome read).

WHAT IT RECORDS, per decision (one row; columns in the file's "cols"): the replay run, step, unit and fix kind; u (the
unit's cell before the advance: the mv row's "pre"), n (the cell the fix took: the event's "taken"), v (the bound
victim's cell: the mv row's "target"); the decision board (the true burning and active-smoke sets, sorted cell
lists); the wind vector; the grid extents (x_size, y_size); and the frozen verdict (admit, c_n, T(v)) of
outputs/_mvg_guard_diag.guard - G-T, with the wind - called exactly as that file's own diagnostic calls it (1d.2.6):
guard(u, n, v, burning set, smoky set, tuple(wind vector) or None, W, H).

WHY THIS WAY. The frozen guard (sha256 70eeba78..., LF form) imports U1's helpers from
src_extension/planning/urgency_dispatch.py, which branch mvg does not carry (ruling: U1 not merged). It is therefore
run HERE, in the urgency checkout's context (that checkout's root first on sys.path, the frozen file loaded BY PATH
from its outputs/), never against this branch's code; the corpus is the bridge. The decisions are those of the 43
arm-M R0 replays (outputs/_ud_replay/_bd_udrp_ud2*_R0.json with _sd_udrp_ud2*_R0.json: each reproduced its committed
record exactly, Part 1d 1d.2.6) - 1 019 decisions, 626 of them vetoed (1d.2.6's footprint).

CHECKS (the tool refuses - exits non-zero with a message - rather than guess):
  - the frozen file's sha256 (CRLF folded to LF) is 70eeba78... in the urgency checkout; this branch's byte copy
    outputs/_mvg_guard_diag.py hashes the same;
  - after the import, urgency_dispatch and fire_arrival_estimate resolve INSIDE the urgency checkout;
  - every board file has its record file, holds no knockout (ko_rules and ko_applied empty: an R0), and every live
    (a) / (b) event has its mv row and its decision board;
  - every frozen verdict equals the one the diagnostic itself wrote in Part 1d
    (outputs/_ud_replay/_mvg_guard_diag.json, the "GT" entries, same events in the same order);
  - the counts equal 1d.2.6: 43 runs, 1 019 decisions, 626 vetoes; (a) 953 with 610 vetoes, (b) 66 with 16; 20 runs
    with a veto.
Nothing in the urgency checkout is written. The output is byte-reproducible (sorted cell lists, gzip mtime 0, no
time stamp): a re-run must give the same sha256.

usage: python -B outputs/_mvg_make_guard_corpus.py [--urgency E:/Projects/SAS_wt/urgency]
           [--out <mvg root>/tests/data/mvg_guard_corpus.json.gz]
"""
from __future__ import annotations

import argparse
import glob
import gzip
import hashlib
import importlib.util
import io
import json
import math
import os
import platform
import subprocess
import sys

VERSION = "mvg_guard_corpus v1"
FROZEN_SHA = "70eeba7877dae6174999ae2a00774bdeeb36ced08d35df407f27318cd3a313b2"
FROZEN_REL = "outputs/_mvg_guard_diag.py"
REPLAY_REL = "outputs/_ud_replay"
DIAG_JSON = "_mvg_guard_diag.json"
COLS = ["run", "step", "unit", "kind", "u", "n", "v", "burning", "smoky", "wind", "grid", "admit", "c", "T_v"]
# Part 1d 1d.2.6, THE FOOTPRINT (arm M, 43 cells).
EXPECTED = {"runs": 43, "decisions": 1019, "vetoes": 626, "a": (953, 610), "b": (66, 16), "runs_with_veto": 20}

HERE = os.path.dirname(os.path.abspath(__file__))
MVG_ROOT = os.path.dirname(HERE)


def refuse(msg: str) -> None:
    print("REFUSED: " + msg, file=sys.stderr)
    raise SystemExit(2)


def sha_lf(path: str) -> tuple[str, str]:
    """(sha256 of the bytes with CRLF folded to LF, sha256 of the raw bytes)."""
    with open(path, "rb") as fh:
        raw = fh.read()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(), hashlib.sha256(raw).hexdigest()


def norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def inside(path: str, root: str) -> bool:
    return norm(path).startswith(norm(root) + os.sep)


def encode_float(x: float):
    """A float as JSON: finite values as numbers (repr round-trips exactly), the rest as "inf" / "-inf" / "nan"."""
    x = float(x)
    if math.isfinite(x):
        return x
    return "nan" if math.isnan(x) else ("inf" if x > 0 else "-inf")


def load_frozen(urgency: str):
    """The frozen guard module, loaded BY PATH from the urgency checkout with that checkout's root first on
    sys.path (the file itself inserts its own parent's parent there too)."""
    path = os.path.join(urgency, *FROZEN_REL.split("/"))
    if not os.path.isfile(path):
        refuse("frozen guard not found: %s" % path)
    lf, raw = sha_lf(path)
    if lf != FROZEN_SHA:
        refuse("frozen guard sha256 (LF) %s != %s (%s)" % (lf, FROZEN_SHA, path))
    copy = os.path.join(MVG_ROOT, *FROZEN_REL.split("/"))
    if not os.path.isfile(copy) or sha_lf(copy)[0] != FROZEN_SHA:
        refuse("this branch's copy %s does not hash to the frozen sha256" % copy)
    if "src_extension" in sys.modules:
        refuse("src_extension was imported before the frozen guard: it would not resolve in the urgency checkout")
    sys.path[:] = [p for p in sys.path if norm(p or os.getcwd()) not in (norm(MVG_ROOT), norm(HERE))]
    sys.path.insert(0, urgency)
    spec = importlib.util.spec_from_file_location("_mvg_frozen_guard_diag", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ud = sys.modules.get("src_extension.planning.urgency_dispatch")
    fae = sys.modules.get("src_extension.planning.fire_arrival_estimate")
    if ud is None or fae is None or not inside(ud.__file__, urgency) or not inside(fae.__file__, urgency):
        refuse("the frozen guard's imports did not resolve inside %s" % urgency)
    return module, {"path": FROZEN_REL, "sha256_lf": lf, "sha256_raw": raw, "copy_sha256_lf": sha_lf(copy)[0],
                    "urgency_dispatch_sha256_lf": sha_lf(ud.__file__)[0],
                    "fire_arrival_estimate_sha256_lf": sha_lf(fae.__file__)[0]}


def git_head(root: str) -> str:
    try:
        proc = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--urgency", default="E:/Projects/SAS_wt/urgency")
    ap.add_argument("--out", default=os.path.join(MVG_ROOT, "tests", "data", "mvg_guard_corpus.json.gz"))
    args = ap.parse_args()
    urgency = os.path.abspath(args.urgency)
    if norm(urgency) == norm(MVG_ROOT):
        refuse("--urgency must be the urgency checkout, not this one")
    guard_mod, frozen = load_frozen(urgency)
    guard = guard_mod.guard

    rdir = os.path.join(urgency, *REPLAY_REL.split("/"))
    with open(os.path.join(rdir, DIAG_JSON), encoding="utf-8") as fh:
        diag = json.load(fh)
    bpaths = sorted(glob.glob(os.path.join(rdir, "_bd_udrp_ud2*_R0.json")))
    if len(bpaths) != EXPECTED["runs"]:
        refuse("%d R0 board files, expected %d" % (len(bpaths), EXPECTED["runs"]))

    rows, sources = [], []
    for bpath in bpaths:
        name = os.path.basename(bpath)[len("_bd_"):-len(".json")]
        run = name[len("udrp_"):-len("_R0")]
        spath = os.path.join(rdir, "_sd_%s.json" % name)
        if not os.path.isfile(spath):
            refuse("no record for %s" % bpath)
        with open(bpath, encoding="utf-8") as fh:
            bd = json.load(fh)
        with open(spath, encoding="utf-8") as fh:
            d = json.load(fh)
        if bd.get("ko_rules") or bd.get("ko_applied"):
            refuse("%s is not an R0 (knockout rules present)" % bpath)
        sources.append({"run": run, "boards": os.path.basename(bpath), "record": os.path.basename(spath),
                        "boards_sha256": sha_lf(bpath)[1], "record_sha256": sha_lf(spath)[1]})
        w, h = (int(x) for x in bd["grid"])
        wind_vec = bd["wind"]["vector"]
        wind = tuple(float(x) for x in wind_vec) if wind_vec else None
        dec = {(s, uid): dig for s, uid, _p, _t, _st, _ex, dig in bd["decisions"]}
        cols = d["mv"]["cols"]
        mv = {}
        for r in d["mv"]["rows"]:
            row = dict(zip(cols, r))
            mv[(row["step"], row["unit"])] = row
        ref = [e for e in diag.get(run, [])]
        k = 0
        for e in d.get("mv_events") or []:
            if not e.get("live") or e.get("kind") not in ("a", "b"):
                continue
            row = mv.get((e["step"], e["unit"]))
            dig = dec.get((e["step"], e["unit"]))
            if row is None or dig is None or dig not in bd["boards"]:
                refuse("%s step %s %s: no mv row or decision board" % (run, e["step"], e["unit"]))
            board = bd["boards"][dig]
            burning = {tuple(int(v) for v in c) for c in board["burning"]}
            smoky = {tuple(int(v) for v in c) for c in board["smoky"]}
            u, n, v = (tuple(int(x) for x in row["pre"]), tuple(int(x) for x in e["taken"]),
                       tuple(int(x) for x in row["target"]))
            admit, c_n, t_v = guard(u, n, v, burning, smoky, wind, w, h)
            if k >= len(ref):
                refuse("%s: more events than the Part 1d diagnostic recorded" % run)
            gt = ref[k]
            k += 1
            if (gt.get("step"), gt.get("unit"), gt.get("kind")) != (e["step"], e["unit"], e["kind"]) or \
                    tuple(gt["u"]) != u or tuple(gt["n"]) != n or tuple(gt["v"]) != v or \
                    (gt["GT"]["admit"], gt["GT"]["c"], gt["GT"]["T_v"]) != (bool(admit), c_n, float(t_v)):
                refuse("%s step %s %s: the frozen verdict differs from the Part 1d diagnostic's" % (
                    run, e["step"], e["unit"]))
            rows.append([run, int(e["step"]), str(e["unit"]), str(e["kind"]), list(u), list(n), list(v),
                         sorted([list(c) for c in burning]), sorted([list(c) for c in smoky]),
                         None if wind is None else list(wind), [w, h], bool(admit),
                         None if c_n is None else int(c_n), encode_float(t_v)])
        if k != len(ref):
            refuse("%s: %d events, the Part 1d diagnostic recorded %d" % (run, k, len(ref)))

    counts = {"runs": len(bpaths), "decisions": len(rows), "vetoes": sum(1 for r in rows if not r[11])}
    for kind in ("a", "b"):
        mine = [r for r in rows if r[3] == kind]
        counts[kind] = (len(mine), sum(1 for r in mine if not r[11]))
    counts["runs_with_veto"] = len({r[0] for r in rows if not r[11]})
    for key, want in EXPECTED.items():
        if counts[key] != want:
            refuse("count %s = %s, Part 1d 1d.2.6 says %s" % (key, counts[key], want))
    vetoes_c_inf = sum(1 for r in rows if not r[11] and r[12] is None)
    admits_c = sum(1 for r in rows if r[11] and r[12] is not None)

    header = {
        "version": VERSION,
        "what": "every live fix (a)/(b) decision of the urgency screen's 43 arm-M R0 replays with its decision board "
                "and the FROZEN guard's verdict (outputs/urgency_part1d.txt 1d.2.6, 1d.8 (4) T-G7)",
        "frozen_guard": frozen,
        "call": "guard(u, n, v, set(burning), set(smoky), tuple(wind) or None, grid[0], grid[1]) -> (admit, c, T_v)",
        "urgency_root": urgency.replace("\\", "/"),
        "urgency_head": git_head(urgency),
        "mvg_fire_arrival_estimate_sha256_lf": sha_lf(os.path.join(
            MVG_ROOT, "src_extension", "planning", "fire_arrival_estimate.py"))[0],
        "replay_dir": REPLAY_REL,
        "sources": sources,
        "counts": {k: list(v) if isinstance(v, tuple) else v for k, v in counts.items()},
        "vetoes_with_c_infinite": vetoes_c_inf,
        "admits_with_c_finite": admits_c,
        "t_v_encoding": "a JSON number when finite, else the string inf / -inf / nan",
        "python": platform.python_version(),
        "numpy": sys.modules["numpy"].__version__ if "numpy" in sys.modules else "unknown",
    }
    blob = json.dumps({"header": header, "cols": COLS, "decisions": rows}, separators=(",", ":")).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, compresslevel=9, mtime=0) as gz:
        gz.write(blob)
    data = buf.getvalue()
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, out)
    print("frozen guard %s sha256 (LF) %s - urgency HEAD %s" % (FROZEN_REL, frozen["sha256_lf"],
                                                                header["urgency_head"]))
    print("urgency_dispatch %s | FAE urgency %s | FAE mvg %s" % (
        frozen["urgency_dispatch_sha256_lf"][:16], frozen["fire_arrival_estimate_sha256_lf"][:16],
        header["mvg_fire_arrival_estimate_sha256_lf"][:16]))
    print("runs %d | decisions %d | vetoes %d (c infinite %d) | (a) %d / %d vetoed | (b) %d / %d vetoed | "
          "runs with a veto %d" % (counts["runs"], counts["decisions"], counts["vetoes"], vetoes_c_inf,
                                   counts["a"][0], counts["a"][1], counts["b"][0], counts["b"][1],
                                   counts["runs_with_veto"]))
    print("every frozen verdict equals the Part 1d diagnostic's (%s)" % DIAG_JSON)
    print("wrote %s: %d bytes (json %d bytes), sha256 %s" % (out, len(data), len(blob),
                                                            hashlib.sha256(data).hexdigest()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
