"""Planner round: decide whether a queued job is COMPLETE - the pool's skip test.

queue line:  kind|tag|repo|wind|roles|seeds|steps|extra
  kind ff  one PLAIN harness run (outputs/_ffr_harness.py) - the purity twins plP / plQ
  kind fo  one harness run through the sidecar, stock instrument (outputs/_pl_obs_stock.py)
  kind fc  one harness run through the sidecar, CRN instrument (outputs/_pl_obs_crn.py)
  kind rb  one route_blocked gate shard: <repo>/outputs/_rblatch_campaign2.py (the campaign
           imports the checkout it lives in and writes its JSON NEXT TO ITSELF, i.e. in
           <repo>/outputs/); its log goes to outputs/_ffr_rb_<tag>.log in THIS checkout
ff/fo/fc files: outputs/_ffr_<tag>_<wind>_<rr>_<seed>.json / .stdout.txt, outputs/_ffr_logs/<name>.out/.err,
and for fo/fc the sidecar outputs/_ffr_<name>.plobs.json.

VALID requires the house checks (outputs/_dcd4_validate.check for harness runs,
outputs/_dcd4rb_validate.rb_check for shards) AND, beyond them:
  - the JSON's repo (os.path.abspath as the harness records it) IS the line's repo - the
    two-checkout hazard the house validator does not cover (memory: worktree-round-isolation);
  - fo/fc: the sidecar parses, its json_sha256 is the JSON's sha256, its repo and harness
    are the line's, its argv --out is the line's JSON, and every source module it records
    lies under the line's repo.
QUEUE RULES (a violation makes the whole read fail -> the pool refuses to start):
  tag ^pl[A-Za-z0-9]+$; repo E:/Projects/SAS or E:/Projects/SAS_wt/basedfbfbe7;
  every --set key declared at column 0 in the line's repo's common_fixed_variables.py, EXCEPT
  FM2P_ keys, allowed only on fc lines and there only as exactly FM2P_CRN=1 (and fc lines must
  carry it); fo/ff lines carry no FM2P_ key.
Read-only unless --quarantine is given, which MOVES an invalid job's files aside.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _dcd4_validate import check as ff_check, parse_value  # noqa: E402
from _dcd4rb_validate import rb_check  # noqa: E402

REPOS = {"E:/Projects/SAS", "E:/Projects/SAS_wt/basedfbfbe7"}
TAG_RE = re.compile(r"^pl[A-Za-z0-9]+$")


def norm(p):
    return os.path.normcase(os.path.abspath(p))


def declared_keys(repo):
    keys = set()
    with open(os.path.join(repo, "common_fixed_variables.py"), "r", encoding="utf-8") as f:
        for ln in f:
            m = re.match(r"^([A-Z][A-Z0-9_]*)\s*=", ln)
            if m:
                keys.add(m.group(1))
    return keys


def parse_extra(extra):
    toks = shlex.split(extra)
    sets, raw, uav_actions, i = {}, [], False, 0
    while i < len(toks):
        if toks[i] == "--set":
            k, v = toks[i + 1].split("=", 1)
            sets[k.strip()] = parse_value(v)
            raw.append((k.strip(), v))
            i += 2
            continue
        if toks[i] == "--uav-actions":
            uav_actions = True
        i += 1
    return sets, raw, uav_actions


def read_queue(path, outpfx="outputs/_ffr_", logdir="outputs/_ffr_logs"):
    runs, declared = [], {}
    with open(path, "r", encoding="utf-8") as f:
        for raw_ln in f:
            ln = raw_ln.replace("\r", "").rstrip("\n")
            if not ln.strip() or ln.startswith("#"):
                continue
            kind, tag, repo, wind, roles, seeds, steps, extra = ln.split("|", 7)
            if not TAG_RE.match(tag):
                raise SystemExit("QUEUE REFUSED: tag %r is not a planner tag: %s" % (tag, ln))
            if repo not in REPOS:
                raise SystemExit("QUEUE REFUSED: repo %r: %s" % (repo, ln))
            sets, raw, uav_actions = parse_extra(extra)
            if repo not in declared:
                declared[repo] = declared_keys(repo)
            for k, v in raw:
                if k.startswith("FM2P_"):
                    if kind != "fc" or k != "FM2P_CRN" or v.strip() != "1":
                        raise SystemExit("QUEUE REFUSED: FM2P_ key %s=%s outside a CRN line: %s" % (k, v, ln))
                elif k not in declared[repo]:
                    raise SystemExit("QUEUE REFUSED: --set %s is not declared at column 0 in %s's cfv: %s"
                                     % (k, repo, ln))
            if kind == "fc" and [v.strip() for k, v in raw if k == "FM2P_CRN"] != ["1"]:
                raise SystemExit("QUEUE REFUSED: a CRN line needs exactly one --set FM2P_CRN=1: %s" % ln)
            if kind in ("ff", "fo", "fc"):
                rr = "def" if roles == "default" else roles
                name = "%s_%s_%s_%s" % (tag, wind, rr, seeds)
                runs.append({
                    "kind": kind, "name": name, "tag": tag, "repo": repo, "wind": wind, "roles": roles,
                    "seed": int(seeds), "steps": int(steps), "sets": sets, "uav_actions": uav_actions,
                    "json": outpfx + name + ".json", "stdout": outpfx + name + ".stdout.txt",
                    "out": os.path.join(logdir, name + ".out"), "err": os.path.join(logdir, name + ".err"),
                    "side": outpfx + name + ".plobs.json",
                })
            elif kind == "rb":
                if roles != "half":
                    raise SystemExit("QUEUE REFUSED: rb line with roles=%r: %s" % (roles, ln))
                name = "%s_D_%s" % (tag, wind)
                runs.append({
                    "kind": "rb", "name": name, "tag": tag, "repo": repo, "wind": wind, "roles": roles,
                    "seeds": seeds, "seed_list": [int(s) for s in seeds.split(",")], "steps": int(steps),
                    "sets": sets, "json": os.path.join(repo, "outputs", "_rblatch_camp2_%s.json" % name),
                    "log": os.path.join("outputs", "_ffr_rb_%s.log" % tag),
                })
            else:
                raise SystemExit("QUEUE REFUSED: unknown kind %r: %s" % (kind, ln))
    names = [r["name"] for r in runs]
    if len(set(names)) != len(names):
        raise SystemExit("QUEUE REFUSED: duplicate job names")
    return runs


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(run):
    if run["kind"] == "rb":
        return rb_check(run)
    status, why = ff_check(run, steps=run["steps"])
    if status != "VALID":
        return status, why
    with open(run["json"], "r", encoding="utf-8") as f:
        d = json.load(f)
    if norm(d.get("repo", "")) != norm(run["repo"]):
        return "INVALID", "json repo %r is not the line's %r" % (d.get("repo"), run["repo"])
    if run["kind"] == "ff":
        if os.path.exists(run["side"]):
            return "INVALID", "a plain-harness line has a sidecar beside it"
        return "VALID", ""
    if not os.path.exists(run["side"]):
        return "INVALID", "sidecar missing"
    try:
        with open(run["side"], "r", encoding="utf-8") as f:
            s = json.load(f)
    except Exception as exc:
        return "INVALID", "sidecar does not parse: %s" % type(exc).__name__
    if s.get("json_sha256") != sha256(run["json"]):
        return "INVALID", "sidecar json_sha256 is not the JSON's"
    if norm(s.get("repo", "")) != norm(run["repo"]):
        return "INVALID", "sidecar repo %r" % s.get("repo")
    if s.get("harness") != ("stock" if run["kind"] == "fo" else "crn"):
        return "INVALID", "sidecar harness %r" % s.get("harness")
    argv = s.get("argv") or []
    out = argv[argv.index("--out") + 1] if "--out" in argv else None
    if out is None or norm(out) != norm(run["json"]):
        return "INVALID", "sidecar argv --out %r" % out
    for name, src in (s.get("source") or {}).items():
        if src == "ABSENT":
            continue
        if not norm(src["file"]).startswith(norm(run["repo"]) + os.sep):
            return "INVALID", "SOURCE MISMATCH %s from %s" % (name, src["file"])
    return "VALID", ""


def quarantine(run, qdir):
    os.makedirs(qdir, exist_ok=True)
    if run["kind"] == "rb":
        paths = [run["json"], run["log"]]
    else:
        paths = [run["json"], run["json"] + ".tmp", run["stdout"], run["out"], run["err"], run["side"],
                 run["side"] + ".tmp", run["json"] + ".fm2p.tmp"]
    moved = []
    for p in paths:
        if os.path.exists(p):
            try:
                shutil.move(p, os.path.join(qdir, os.path.basename(p)))
                moved.append(os.path.basename(p))
            except OSError as exc:
                moved.append("%s(NOT MOVED: %s)" % (os.path.basename(p), type(exc).__name__))
    return moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--one")
    ap.add_argument("--quarantine", default="")
    a = ap.parse_args()
    sys.stdout.reconfigure(newline="\n")
    runs = read_queue(a.queue)
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
