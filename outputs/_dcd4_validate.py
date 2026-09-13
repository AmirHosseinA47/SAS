"""dcd4 round: decide whether a queued run is COMPLETE - the pool's skip test.

`-s file` (non-empty) is not enough in this project: a harness killed between
writing the JSON and writing .stdout.txt leaves a valid JSON with no stdout, and
one run in the dock-fix round had its .stdout.txt overwritten by a redirect and
still passed `-s`. A run is VALID only if ALL of these hold:
  (a) outputs/_ffr_<name>.json parses, and its tag / wind / roles / seed / steps
      and extra_params equal what the queue line asked for;
  (b) --uav-actions was asked for  =>  uav_actions is a list of `steps` rows;
  (c) <name>.stdout.txt exists and sha256 of its text == stdout_sha256, and its
      newline count == stdout_lines (read in text mode: the hash is over the
      in-memory LF text);
  (d) outputs/_ffr_logs/<name>.out contains "seed=<seed>" - the harness prints
      that last, after both files are written;
  (e) no <name>.json.tmp is left over.
Read-only unless --quarantine is given, which MOVES an invalid run's files aside
(never deletes) so a relaunch cannot be confused by them.

usage:
  python outputs/_dcd4_validate.py --queue Q --all [--quarantine DIR]
  python outputs/_dcd4_validate.py --queue Q --one NAME [--quarantine DIR]
prints one line per run: VALID name | INVALID name reason | MISSING name
"""
import argparse
import hashlib
import json
import os
import shlex
import shutil
import sys


def parse_value(raw):
    # identical coercion order to _ffr_harness._parse_value
    text = str(raw).strip()
    low = text.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("none", "null"):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def read_queue(path, outpfx, logdir):
    runs = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            ln = raw.replace("\r", "").rstrip("\n")
            if not ln.strip() or ln.startswith("#"):
                continue
            tag, repo, wind, roles, seed, extra = ln.split("|", 5)
            rr = "def" if roles == "default" else roles
            name = "%s_%s_%s_%s" % (tag, wind, rr, seed)
            toks = shlex.split(extra)
            sets, uav_actions = {}, False
            i = 0
            while i < len(toks):
                if toks[i] == "--set":
                    k, v = toks[i + 1].split("=", 1)
                    sets[k.strip()] = parse_value(v)
                    i += 2
                    continue
                if toks[i] == "--uav-actions":
                    uav_actions = True
                i += 1
            runs.append({
                "name": name, "tag": tag, "wind": wind, "roles": roles, "seed": int(seed),
                "sets": sets, "uav_actions": uav_actions,
                "json": outpfx + name + ".json", "stdout": outpfx + name + ".stdout.txt",
                "out": os.path.join(logdir, name + ".out"), "err": os.path.join(logdir, name + ".err"),
            })
    return runs


def check(run, steps=240):
    j = run["json"]
    if not os.path.exists(j):
        return "MISSING", ""
    if os.path.exists(j + ".tmp"):
        return "INVALID", "leftover .json.tmp"
    try:
        with open(j, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception as exc:  # truncated / not JSON
        return "INVALID", "json does not parse: %s" % type(exc).__name__
    if not isinstance(d, dict):
        return "INVALID", "json is not an object"
    for key, want in (("tag", run["tag"]), ("wind", run["wind"]), ("roles", run["roles"]),
                      ("seed", run["seed"]), ("steps", steps)):
        if d.get(key) != want:
            return "INVALID", "%s=%r, queue wants %r" % (key, d.get(key), want)
    if d.get("extra_params") != run["sets"]:
        return "INVALID", "extra_params %r != queue %r" % (d.get("extra_params"), run["sets"])
    if run["uav_actions"]:
        ua = d.get("uav_actions")
        if not isinstance(ua, list) or len(ua) != steps:
            return "INVALID", "uav_actions missing or not %d rows" % steps
    if not isinstance(d.get("eval"), dict):
        return "INVALID", "no eval"
    s = run["stdout"]
    if not os.path.exists(s) or os.path.getsize(s) == 0:
        return "INVALID", "stdout.txt missing or empty"
    with open(s, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    if hashlib.sha256(text.encode("utf-8", "replace")).hexdigest() != d.get("stdout_sha256"):
        return "INVALID", "stdout.txt sha256 != stdout_sha256"
    if text.count("\n") != d.get("stdout_lines"):
        return "INVALID", "stdout.txt lines %d != %r" % (text.count("\n"), d.get("stdout_lines"))
    o = run["out"]
    if not os.path.exists(o):
        return "INVALID", ".out missing"
    with open(o, "r", encoding="utf-8", errors="replace") as f:
        if ("seed=%d " % run["seed"]) not in f.read():
            return "INVALID", ".out has no seed=%d summary line" % run["seed"]
    return "VALID", ""


def quarantine(run, qdir):
    os.makedirs(qdir, exist_ok=True)
    moved = []
    for key in ("json", "stdout", "out", "err"):
        for p in (run[key], run[key] + ".tmp") if key == "json" else (run[key],):
            if os.path.exists(p):
                try:
                    shutil.move(p, os.path.join(qdir, os.path.basename(p)))
                    moved.append(os.path.basename(p))
                except OSError as exc:  # open in a live process on Windows
                    moved.append("%s(NOT MOVED: %s)" % (os.path.basename(p), type(exc).__name__))
    return moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", required=True)
    ap.add_argument("--outpfx", default="outputs/_ffr_")
    ap.add_argument("--logdir", default="outputs/_ffr_logs")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--one")
    ap.add_argument("--quarantine", default="")
    a = ap.parse_args()
    sys.stdout.reconfigure(newline="\n")
    runs = read_queue(a.queue, a.outpfx, a.logdir)
    if a.one:
        runs = [r for r in runs if r["name"] == a.one]
        if not runs:
            print("INVALID %s not in queue" % a.one)
            return 1
    counts = {"VALID": 0, "INVALID": 0, "MISSING": 0}
    for r in runs:
        status, why = check(r)
        counts[status] += 1
        if status == "INVALID" and a.quarantine:
            why += " -> quarantined %s" % ",".join(quarantine(r, a.quarantine))
        print(("%s %s %s" % (status, r["name"], why)).rstrip())
    if a.all:
        print("SUMMARY total=%d valid=%d invalid=%d missing=%d"
              % (len(runs), counts["VALID"], counts["INVALID"], counts["MISSING"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
