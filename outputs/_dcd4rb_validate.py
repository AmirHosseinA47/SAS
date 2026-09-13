"""dcd4rb round: decide whether a queued job is COMPLETE - the pool's skip test.

Extends outputs/_dcd4_validate.py (whose harness check is imported, unchanged) to a
second job kind: a route_blocked GATE SHARD run by outputs/_rblatch_campaign2.py.

queue line:  kind|tag|repo|wind|roles|seeds|steps|extra
  kind ff  one harness run  (outputs/_ffr_harness.py), seeds = one integer,
           name <tag>_<wind>_<rr>_<seed>, files outputs/_ffr_<name>.json/.stdout.txt,
           outputs/_ffr_logs/<name>.out/.err  - checked by _dcd4_validate.check
  kind rb  one gate shard (outputs/_rblatch_campaign2.py), seeds = comma list,
           roles must be "half" (the campaign derives half roles itself),
           name <tag>_D_<wind>, files outputs/_rblatch_camp2_<name>.json and
           outputs/_ffr_rb_<tag>.log (stdout+stderr, exactly as _ffr_rbgate.sh)

A gate shard is VALID only if ALL of these hold:
  (a) the JSON parses (the campaign writes it with a plain open(); a kill mid-dump
      leaves a truncated file, which fails here);
  (b) tag / scenario "D" / wind / steps / seeds string equal the queue line;
  (c) params carry every --set of the queue line with the ladder-coerced value,
      WIND_DIRECTION == wind, and no key outside the campaign's base keys + sets;
  (d) evals is a list whose seeds are the queue's seeds, in order, each with an
      integer rescued / dead / firefighter_deaths;
  (e) the log has one "<tag> <wind> seed <s> done" line per seed and ends with the
      JSON path, which the campaign prints only after json.dump has closed the file.
Read-only unless --quarantine is given, which MOVES an invalid job's files aside.

usage:
  python outputs/_dcd4rb_validate.py --queue Q --all [--quarantine DIR]
  python outputs/_dcd4rb_validate.py --queue Q --one NAME [--quarantine DIR]
  (--rbdir / --rblogdir exist only so the pool smoke test can point at stubs)
"""
import argparse
import json
import os
import shlex
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _dcd4_validate import check as ff_check, parse_value  # noqa: E402

RB_BASE_KEYS = {"NUM_AGENTS", "NUM_VICTIMS", "NUM_FIREFIGHTERS", "WIND_DIRECTION", "BATCH_SIZE",
                "FIRE_SPREAD_MULTIPLIER", "PROBABILITY_MAP", "NUM_FIRE_TRACKERS",
                "NUM_VICTIM_SEARCHERS"}


def parse_sets(extra):
    toks = shlex.split(extra)
    sets, uav_actions, i = {}, False, 0
    while i < len(toks):
        if toks[i] == "--set":
            k, v = toks[i + 1].split("=", 1)
            sets[k.strip()] = parse_value(v)
            i += 2
            continue
        if toks[i] == "--uav-actions":
            uav_actions = True
        i += 1
    return sets, uav_actions


def read_queue(path, outpfx, logdir, rbdir, rblogdir):
    runs = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            ln = raw.replace("\r", "").rstrip("\n")
            if not ln.strip() or ln.startswith("#"):
                continue
            kind, tag, repo, wind, roles, seeds, steps, extra = ln.split("|", 7)
            sets, uav_actions = parse_sets(extra)
            if kind == "ff":
                rr = "def" if roles == "default" else roles
                name = "%s_%s_%s_%s" % (tag, wind, rr, seeds)
                runs.append({
                    "kind": "ff", "name": name, "tag": tag, "wind": wind, "roles": roles,
                    "seed": int(seeds), "steps": int(steps), "sets": sets,
                    "uav_actions": uav_actions,
                    "json": outpfx + name + ".json", "stdout": outpfx + name + ".stdout.txt",
                    "out": os.path.join(logdir, name + ".out"),
                    "err": os.path.join(logdir, name + ".err"),
                })
            elif kind == "rb":
                if roles != "half":
                    raise SystemExit("rb line with roles=%r (campaign is half-only): %s" % (roles, ln))
                name = "%s_D_%s" % (tag, wind)
                runs.append({
                    "kind": "rb", "name": name, "tag": tag, "wind": wind, "roles": roles,
                    "seeds": seeds, "seed_list": [int(s) for s in seeds.split(",")],
                    "steps": int(steps), "sets": sets,
                    "json": os.path.join(rbdir, "_rblatch_camp2_%s.json" % name),
                    "log": os.path.join(rblogdir, "_ffr_rb_%s.log" % tag),
                })
            else:
                raise SystemExit("unknown kind %r in queue line: %s" % (kind, ln))
    return runs


def rb_check(run):
    j = run["json"]
    if not os.path.exists(j):
        return "MISSING", ""
    try:
        with open(j, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception as exc:
        return "INVALID", "json does not parse: %s" % type(exc).__name__
    if not isinstance(d, dict):
        return "INVALID", "json is not an object"
    for key, want in (("tag", run["tag"]), ("scenario", "D"), ("wind", run["wind"]),
                      ("steps", run["steps"]), ("seeds", run["seeds"])):
        if d.get(key) != want:
            return "INVALID", "%s=%r, queue wants %r" % (key, d.get(key), want)
    params = d.get("params")
    if not isinstance(params, dict):
        return "INVALID", "no params"
    if params.get("WIND_DIRECTION") != run["wind"]:
        return "INVALID", "params WIND_DIRECTION=%r" % params.get("WIND_DIRECTION")
    for k, v in run["sets"].items():
        if k not in params or params[k] != v or type(params[k]) is not type(v):
            return "INVALID", "params[%s]=%r, queue sets %r" % (k, params.get(k), v)
    stray = set(params) - RB_BASE_KEYS - set(run["sets"])
    if stray:
        return "INVALID", "params has keys the queue did not set: %s" % sorted(stray)
    evals = d.get("evals")
    if not isinstance(evals, list) or [e.get("seed") for e in evals] != run["seed_list"]:
        return "INVALID", "evals seeds %r != queue %r" % (
            [e.get("seed") for e in evals] if isinstance(evals, list) else evals, run["seed_list"])
    for e in evals:
        for k in ("rescued", "dead", "firefighter_deaths"):
            if not isinstance(e.get(k), int):
                return "INVALID", "eval seed %s has no integer %s" % (e.get("seed"), k)
    lg = run["log"]
    if not os.path.exists(lg):
        return "INVALID", "log missing"
    with open(lg, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    for s in run["seed_list"]:
        if ("%s %s seed %d done" % (run["tag"], run["wind"], s)) not in text:
            return "INVALID", "log has no done line for seed %d" % s
    last = [ln for ln in text.replace("\r", "").split("\n") if ln.strip()]
    tail = os.path.basename(last[-1].strip()) if last else ""
    if tail != os.path.basename(j):
        return "INVALID", "log does not end with the json path (last line %r)" % (last[-1][-80:] if last else "")
    return "VALID", ""


def check(run):
    if run["kind"] == "ff":
        return ff_check(run, steps=run["steps"])
    return rb_check(run)


def quarantine(run, qdir):
    os.makedirs(qdir, exist_ok=True)
    moved = []
    if run["kind"] == "ff":
        paths = [run["json"], run["json"] + ".tmp", run["stdout"], run["out"], run["err"]]
    else:
        paths = [run["json"], run["log"]]
    for p in paths:
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
    ap.add_argument("--rbdir", default="outputs")
    ap.add_argument("--rblogdir", default="outputs")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--one")
    ap.add_argument("--quarantine", default="")
    a = ap.parse_args()
    sys.stdout.reconfigure(newline="\n")
    runs = read_queue(a.queue, a.outpfx, a.logdir, a.rbdir, a.rblogdir)
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
