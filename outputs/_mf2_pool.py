"""fix2 (mf2): the fix1 memory-aware pool (outputs/_mf1_pool.py), copied unchanged except this line and the completion marker.

usage: _mf2_pool.py <queue.jsonl> <log> [--maxpar N] [--min-free-gb G]
Each queue line: {"name": "...", "argv": [script, args...], "out": "<json the run must
write>", "cwd": "<optional working dir>"}. The run is `<.venv python> argv...` with stdout
and stderr to <out>.poollog. A run is SKIPPED only when <out> exists, parses as JSON and
<out>.argv holds exactly this line's argv + cwd (a changed line is re-run, never reused).
A run whose process exits non-zero, or exits 0 without a parseable <out>, is a FAIL line
(never a silent success - the fix1 item-1 lesson). Launches only while running < maxpar
and free commit (ullAvailPageFile) > min-free-gb. Ends with ALL_MF2_COMPLETE <queue>
<n_ok>/<n_total> <n_fail> FAIL.
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time

REPO = r"E:\Projects\SAS"
PY = os.path.join(REPO, ".venv", "Scripts", "python.exe")


class MEMSTAT(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def free_commit_gb() -> float:
    st = MEMSTAT()
    st.dwLength = ctypes.sizeof(MEMSTAT)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
    return st.ullAvailPageFile / 2**30


def log(fh, msg: str) -> None:
    fh.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    fh.flush()


def signature(line: dict) -> str:
    return json.dumps({"argv": line["argv"], "cwd": line.get("cwd") or REPO}, sort_keys=True)


def valid(line: dict) -> bool:
    out = line["out"]
    try:
        with open(out, encoding="utf-8") as fh:
            json.load(fh)
        with open(out + ".argv", encoding="utf-8") as fh:
            return fh.read() == signature(line)
    except Exception:
        return False


def main() -> int:
    queue_path, log_path = sys.argv[1], sys.argv[2]
    maxpar = 12
    min_free = 2.5
    if "--maxpar" in sys.argv:
        maxpar = int(sys.argv[sys.argv.index("--maxpar") + 1])
    if "--min-free-gb" in sys.argv:
        min_free = float(sys.argv[sys.argv.index("--min-free-gb") + 1])
    with open(queue_path, encoding="utf-8") as fh:
        lines = [json.loads(x) for x in fh if x.strip()]
    names = [ln["name"] for ln in lines]
    if len(set(names)) != len(names):
        print("DUPLICATE NAMES IN QUEUE", file=sys.stderr)
        return 2
    fh = open(log_path, "a", encoding="utf-8")
    log(fh, "START %s %d runs maxpar=%d min_free=%.1f" % (queue_path, len(lines), maxpar, min_free))
    pending = []
    for ln in lines:
        if valid(ln):
            log(fh, "SKIP %s (valid, same argv)" % ln["name"])
        else:
            pending.append(ln)
    running: dict = {}
    n_ok = len(lines) - len(pending)
    n_fail = 0
    while pending or running:
        for name, (proc, ln, t0, lfh) in list(running.items()):
            rc = proc.poll()
            if rc is None:
                continue
            lfh.close()
            del running[name]
            ok = rc == 0
            if ok:
                try:
                    with open(ln["out"], encoding="utf-8") as jf:
                        json.load(jf)
                except Exception:
                    ok = False
            if ok:
                with open(ln["out"] + ".argv", "w", encoding="utf-8") as af:
                    af.write(signature(ln))
                n_ok += 1
                log(fh, "DONE %s rc=0 %.0fs" % (name, time.time() - t0))
            else:
                n_fail += 1
                log(fh, "FAIL %s rc=%s %.0fs (see %s.poollog)" % (name, rc, time.time() - t0, ln["out"]))
        while pending and len(running) < maxpar and free_commit_gb() > min_free:
            ln = pending.pop(0)
            lfh = open(ln["out"] + ".poollog", "w", encoding="utf-8")
            proc = subprocess.Popen([PY] + ln["argv"], cwd=ln.get("cwd") or REPO, stdout=lfh,
                                    stderr=subprocess.STDOUT)
            running[ln["name"]] = (proc, ln, time.time(), lfh)
            log(fh, "LAUNCH %s pid=%d free=%.1fGB running=%d" % (ln["name"], proc.pid, free_commit_gb(), len(running)))
            time.sleep(2)
        time.sleep(5)
    log(fh, "ALL_MF2_COMPLETE %s %d/%d %d FAIL" % (queue_path, n_ok, len(lines), n_fail))
    fh.close()
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
