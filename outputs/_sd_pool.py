"""sysdebug round: a small memory-aware pool for outputs/_sd_probe.py runs.

usage: _sd_pool.py <queue.jsonl> <log> [--maxpar N] [--min-free-gb G]
Each queue line: {"name": "...", "args": [...], "script": "probe"|"hooks"|"cf"} (script optional;
hooks/cf lines carry their own flags, then "--", then the probe args). A run writes
outputs/_sd_<name>.json (+ .stdout.txt) and outputs/_sd_<name>.log (probe stdout+stderr).
A run is SKIPPED only when its JSON exists, parses, carries probe "sd_probe v1" and the
same argv as the queue line (so a changed line is re-run, never silently reused).
Launches only while running < maxpar and free commit (ullAvailPageFile) > min-free-gb.
Writes START / LAUNCH / DONE / FAIL / SKIP lines and ALL_SD_COMPLETE <queue> at the end.
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
PROBE = os.path.join(REPO, "outputs", "_sd_probe.py")
SCRIPTS = {"probe": PROBE,
           "hooks": os.path.join(REPO, "outputs", "_sd_hooks.py"),
           "cf": os.path.join(REPO, "outputs", "_sd_cf.py"),
           "cf2": os.path.join(REPO, "outputs", "_sd_cf2.py")}


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


def out_paths(name: str):
    base = os.path.join(REPO, "outputs", "_sd_%s" % name)
    return base + ".json", base + ".log"


def valid(name: str, argv: list) -> bool:
    jp, _ = out_paths(name)
    if not os.path.exists(jp):
        return False
    try:
        with open(jp, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return False
    probe_argv = argv[argv.index("--") + 1:] if "--" in argv else argv
    return d.get("probe") == "sd_probe v1" and d.get("argv") == probe_argv


def main() -> int:
    queue_path, log_path = sys.argv[1], sys.argv[2]
    maxpar = 8
    min_free = 3.0
    rest = sys.argv[3:]
    if "--maxpar" in rest:
        maxpar = int(rest[rest.index("--maxpar") + 1])
    if "--min-free-gb" in rest:
        min_free = float(rest[rest.index("--min-free-gb") + 1])
    lock = log_path + ".lock"
    if os.path.exists(lock):
        print("LOCKED %s" % lock, file=sys.stderr)
        return 2
    open(lock, "w").close()
    jobs = []
    with open(queue_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                jobs.append(json.loads(line))
    fh = open(log_path, "a", encoding="utf-8", newline="\n")
    log(fh, "START queue=%s jobs=%d maxpar=%d min_free=%.1f pid=%d" % (queue_path, len(jobs), maxpar, min_free, os.getpid()))
    running = {}
    pending = []
    scripts = []
    for j in jobs:
        jp, lp = out_paths(j["name"])
        argv = list(j["args"]) + ["--out", jp, "--tag", j["name"]]
        if valid(j["name"], argv):
            log(fh, "SKIP %s (valid output exists)" % j["name"])
            continue
        pending.append((j["name"], argv, lp))
        scripts.append((j["name"], j.get("script", "probe")))
    fails = 0
    try:
        while pending or running:
            for name in list(running):
                p, t0, lf = running[name]
                rc = p.poll()
                if rc is None:
                    continue
                lf.close()
                del running[name]
                jp, _ = out_paths(name)
                ok = os.path.exists(jp)
                if rc == 0 and ok:
                    log(fh, "DONE %s rc=0 %.0fs" % (name, time.time() - t0))
                else:
                    fails += 1
                    log(fh, "FAIL %s rc=%s json=%s %.0fs" % (name, rc, ok, time.time() - t0))
            while pending and len(running) < maxpar:
                fc = free_commit_gb()
                if fc < min_free:
                    break
                name, argv, lp = pending.pop(0)
                lf = open(lp, "w", encoding="utf-8")
                script = SCRIPTS.get(dict(scripts).get(name, "probe"), PROBE)
                p = subprocess.Popen([PY, "-B", script] + argv, cwd=REPO, stdout=lf, stderr=subprocess.STDOUT,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                running[name] = (p, time.time(), lf)
                log(fh, "LAUNCH %s pid=%d free_commit=%.1fGB running=%d pending=%d" % (name, p.pid, fc, len(running), len(pending)))
                time.sleep(3)
            time.sleep(5)
        log(fh, "ALL_SD_COMPLETE %s fails=%d" % (queue_path, fails))
    finally:
        fh.close()
        try:
            os.remove(lock)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
