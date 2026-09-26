"""carrying-leg round: decide whether a queued job is COMPLETE - the pool's skip test.

Wraps outputs/_dcd4rb_validate.py (imported, unchanged; it imports _dcd4_validate) and,
for kind ff only, adds these checks AFTER its check returns VALID
(outputs/_cl_tooling_spec.txt section G):
  (1) FM2P_ keys in the line's extra  ->  d["fm2p"]["config"] equals exactly those keys
      and values, value types equal (True != 1); no FM2P_ key  ->  "fm2p" not in d;
  (2) no leftover <json>.fm2p.tmp (the CRN probe's atomic-replace temp);
  (3) the sidecar <stem>.clobs.json (outputs/_cl_obs.py) exists and parses, "version"
      is the integer 1, and its "switches" match the line's --set FF_EXIT_LEG_* values
      (0 where not set): mode an int equal to MODE, hold a bool equal to HOLD != 0,
      served an int equal to SERVED. "ABSENT" is allowed only when the line's repo is
      the 6160438 control worktree AND the line sets that switch to 0 / not at all; on
      that worktree all three MUST be "ABSENT" (it has no accessor). A line value
      outside MODE 0/1/2, HOLD 0/1, SERVED 0/1 (exact int) is INVALID (D-1: SERVED
      rung 2 is not built). No leftover <stem>.clobs.json.tmp.
      Binding (spec F keys): "harness" is "crn" iff the line has an FM2P_ key, else
      "stock"; the sidecar "repo" equals the line's repo (os.path.abspath); its "argv"
      names this run (--out basename, --seed, --tag);
  (4) the JSON's "repo" equals the queue line's repo, both through os.path.abspath.
  CL review fixes (2026-09-26):
  (5) BINDING TO THIS JSON: the sidecar's "json_sha256" equals sha256 of the harness
      JSON's bytes on disk (argv repeats across reruns of a line; this does not);
  (6) SOURCE: the sidecar's "source_sha256" has exactly the four files of the pool's
      src= digest and each equals sha256 of that file in the line's repo NOW, and its
      "src12" equals the pool's src_digest of them. A failure's reason starts with
      "SOURCE MISMATCH" - the pool REFUSES to start (moves nothing) on such a run;
  (7) WRAPS: "absent" is [] off the 6160438 worktree and exactly BASE_ABSENT (the eight
      carrying-leg names that commit lacks) on it - a missing wrap target would
      otherwise zero its counters silently and pass H1(f)/H12 vacuously;
  (8) COUNTERS: model_steps == the line's steps, models_built == 1, observer_errors == 0
      (exact ints).
  CL Part 3 (2026-09-26, before the D-9 probe wave):
  (9) PROBE: outputs/_cl_probe.sidecar_problem(line sets, sidecar) is empty. A line
      with CLP_ keys is VALID only with the sidecar evidence that _cl_probe.py ran and
      resolved exactly its one kill (a CLP line run through _cl_obs_stock.py /
      _cl_obs_crn.py kills nobody and exits 0 - it must never read VALID); a line
      without them must carry no probe_ counter or event. Reason prefix "PROBE: ".
  Every queue tag must be a carrying-leg tag (^cl[A-Za-z0-9]+$), else SystemExit: a
  run of an earlier round has no sidecar and would read INVALID, and the pool moves
  INVALID runs aside - this validator must never be pointed at another round's queue.
An ff job whose JSON is MISSING but whose sidecar / sidecar temp / fm2p temp is left
over is INVALID (an orphan from a moved run), so the pool moves it aside before a
relaunch can be paired with it.
Everything else - CLI, the VALID / INVALID / MISSING / SUMMARY lines, rb shards - is
_dcd4rb_validate's. --quarantine moves _dcd4rb_validate's file set (its own quarantine
function) plus, for ff, the sidecar, the sidecar temp and the fm2p temp - all into
DIR, or, when a file of that name is already in DIR (a second move of the same job in
one pool run), into the first DIR/dupN that holds none of them: a moved copy is never
overwritten.

Read-only unless --quarantine is given. --dry-run never writes: with --quarantine it
only reports what WOULD be moved (no directory is created, nothing is moved). This file
sets sys.dont_write_bytecode, so the pool's plain `$PY outputs/_cl_validate.py` leaves
no __pycache__ entry for the modules it imports.

usage:
  python -B outputs/_cl_validate.py --queue Q --all [--quarantine DIR] [--dry-run]
  python -B outputs/_cl_validate.py --queue Q --one NAME [--quarantine DIR] [--dry-run]
  (--outpfx / --logdir / --rbdir / --rblogdir as _dcd4rb_validate)
"""
import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _dcd4rb_validate as rbv  # noqa: E402
import _cl_probe  # noqa: E402  (check (9): sidecar_problem is pure; importing runs nothing)

BASE_WORKTREE = os.path.abspath("E:/Projects/SAS_wt/base6160438")
TAG_RE = re.compile(r"^cl[A-Za-z0-9]+$")
# sidecar name -> (cfv key, allowed exact-int values on a queue line)
SWITCHES = (("mode", "FF_EXIT_LEG_MODE", (0, 1, 2)),
            ("hold", "FF_EXIT_LEG_HOLD", (0, 1)),
            ("served", "FF_EXIT_LEG_SERVED", (0, 1)))
# the pool's src_digest files, in its order (== _cl_obs.SOURCE_FILES)
SOURCE_FILES = ("agents.py", "wildfire_model.py", "common_fixed_variables.py",
                "src_extension/planning/rescue_planner.py")
# what _cl_obs.install records as absent at 6160438 (observed in a clB sidecar, 2026-09-26)
BASE_ABSENT = frozenset((
    "agents.ff_exit_leg_mode", "agents.ff_exit_leg_hold", "agents.ff_exit_leg_served",
    "Firefighter._exit_leg_enclosed", "Firefighter._exit_leg_hold", "Firefighter._exit_leg_step",
    "WildFireModel._exit_leg_held_cell", "WildFireModel._exit_leg_custody"))

_SRC_CACHE = {}


def _queue_lines(path):
    """The queue's job lines, filtered exactly as _dcd4rb_validate.read_queue does."""
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            ln = raw.replace("\r", "").rstrip("\n")
            if not ln.strip() or ln.startswith("#"):
                continue
            out.append(ln)
    return out


def read_queue(path, outpfx, logdir, rbdir, rblogdir):
    runs = rbv.read_queue(path, outpfx, logdir, rbdir, rblogdir)
    bad = sorted({r["tag"] for r in runs if not TAG_RE.match(r["tag"])})
    if bad:
        raise SystemExit("CL VALIDATE: non-carryleg tags %s in %s - refusing (a run of another round "
                         "has no sidecar and would be judged INVALID)" % (bad, path))
    lines = _queue_lines(path)
    if len(lines) != len(runs):
        raise SystemExit("CL VALIDATE: %d queue lines but _dcd4rb_validate read %d jobs" % (len(lines), len(runs)))
    for r, ln in zip(runs, lines):
        kind, tag, repo, _w, _roles, _seeds, _steps, extra = ln.split("|", 7)
        if kind != r["kind"] or tag != r["tag"]:
            raise SystemExit("CL VALIDATE: line/job mismatch %r vs %s" % (ln, r["name"]))
        r["repo"] = repo
        r["extra"] = extra
        if kind == "ff":
            if not r["json"].endswith(".json"):
                raise SystemExit("CL VALIDATE: json path without .json: %s" % r["json"])
            r["clobs"] = r["json"][:-len(".json")] + ".clobs.json"
            r["clobs_tmp"] = r["clobs"] + ".tmp"
            r["fm2p_tmp"] = r["json"] + ".fm2p.tmp"
    return runs


def _argv_flag(argv, flag):
    for i, a in enumerate(argv):
        if not isinstance(a, str):
            continue
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return None


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def src12(shas):
    """outputs/_cl_pool.sh src_digest (Git Bash sha256sum lines "<hex> *<path>")."""
    text = "".join("%s *%s\n" % (shas[rel], rel) for rel in SOURCE_FILES)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def repo_source(repo):
    """{rel: sha256} of the four source files in `repo` now (None for an unreadable one)."""
    if repo not in _SRC_CACHE:
        shas = {}
        for rel in SOURCE_FILES:
            try:
                shas[rel] = file_sha256(os.path.join(repo, *rel.split("/")))
            except OSError:
                shas[rel] = None
        _SRC_CACHE[repo] = shas
    return _SRC_CACHE[repo]


def _exact_int(v):
    return type(v) is int


def cl_check(run):
    """The CL checks for an ff run the wrapped check already found VALID."""
    with open(run["json"], "r", encoding="utf-8") as f:
        d = json.load(f)
    fm2p_want = {k: v for k, v in run["sets"].items() if k.startswith("FM2P_")}

    # (1) fm2p record vs the line's FM2P_ keys
    if fm2p_want:
        fm = d.get("fm2p")
        cfg = fm.get("config") if isinstance(fm, dict) else None
        if not isinstance(cfg, dict):
            return "INVALID", "line sets %s but the json has no fm2p.config" % sorted(fm2p_want)
        if set(cfg) != set(fm2p_want) or any(
                cfg[k] != v or type(cfg[k]) is not type(v) for k, v in fm2p_want.items()):
            return "INVALID", "fm2p.config %r != queue FM2P_ sets %r" % (cfg, fm2p_want)
    elif "fm2p" in d:
        return "INVALID", "json has an fm2p record but the line sets no FM2P_ key"

    # (2) the CRN probe's temp
    if os.path.exists(run["fm2p_tmp"]):
        return "INVALID", "leftover .json.fm2p.tmp"

    # (4) the harness JSON's repo
    want_repo = os.path.abspath(run["repo"])
    if not isinstance(d.get("repo"), str) or os.path.abspath(d["repo"]) != want_repo:
        return "INVALID", "json repo %r != queue repo %r" % (d.get("repo"), run["repo"])

    # (3) the sidecar
    if os.path.exists(run["clobs_tmp"]):
        return "INVALID", "leftover .clobs.json.tmp"
    if not os.path.exists(run["clobs"]):
        return "INVALID", "sidecar .clobs.json missing"
    try:
        with open(run["clobs"], "r", encoding="utf-8") as f:
            sc = json.load(f)
    except Exception as exc:
        return "INVALID", "sidecar does not parse: %s" % type(exc).__name__
    if not isinstance(sc, dict):
        return "INVALID", "sidecar is not an object"
    if type(sc.get("version")) is not int or sc.get("version") != 1:
        return "INVALID", "sidecar version %r != 1" % (sc.get("version"),)
    want_h = "crn" if fm2p_want else "stock"
    if sc.get("harness") != want_h:
        return "INVALID", "sidecar harness %r, the line's instrument is %r" % (sc.get("harness"), want_h)
    if not isinstance(sc.get("repo"), str) or os.path.abspath(sc["repo"]) != want_repo:
        return "INVALID", "sidecar repo %r != queue repo %r" % (sc.get("repo"), run["repo"])
    argv = sc.get("argv")
    if not isinstance(argv, list):
        return "INVALID", "sidecar argv is not a list"
    got_out = _argv_flag(argv, "--out")
    for flag, got, want in (("--out", os.path.basename(got_out) if got_out else None,
                             os.path.basename(run["json"])),
                            ("--seed", _argv_flag(argv, "--seed"), str(run["seed"])),
                            ("--tag", _argv_flag(argv, "--tag"), run["tag"])):
        if got != want:
            return "INVALID", "sidecar argv %s %r, this run is %r" % (flag, got, want)

    # (5) CL review: the sidecar belongs to THIS json (bytes), not merely to this line
    js = sc.get("json_sha256")
    if not isinstance(js, str) or js != file_sha256(run["json"]):
        return "INVALID", "sidecar json_sha256 %r != sha256 of the json on disk (a sidecar of another run of this line)" % (
            js[:12] + ".." if isinstance(js, str) else js,)

    # (6) CL review: the source the run imported == the line's repo's source now
    ss = sc.get("source_sha256")
    if not isinstance(ss, dict) or set(ss) != set(SOURCE_FILES):
        return "INVALID", "SOURCE MISMATCH: sidecar source_sha256 %r does not name exactly %s" % (
            sorted(ss) if isinstance(ss, dict) else ss, list(SOURCE_FILES))
    now = repo_source(want_repo)
    for rel in SOURCE_FILES:
        if now[rel] is None:
            return "INVALID", "SOURCE MISMATCH: cannot read %s in %s" % (rel, want_repo)
        if ss[rel] != now[rel]:
            return "INVALID", "SOURCE MISMATCH: %s imported sha256 %s.., the line's repo has %s.. now" % (
                rel, str(ss[rel])[:12], now[rel][:12])
    if sc.get("src12") != src12(now):
        return "INVALID", "SOURCE MISMATCH: sidecar src12 %r != src_digest %s of the line's repo" % (
            sc.get("src12"), src12(now))

    # (3) switches
    sw = sc.get("switches")
    if sw == "ABSENT":
        sw = {name: "ABSENT" for name, _k, _a in SWITCHES}
    if not isinstance(sw, dict) or set(sw) != {name for name, _k, _a in SWITCHES}:
        return "INVALID", "sidecar switches %r is not {mode, hold, served}" % (sw,)
    on_base = want_repo == BASE_WORKTREE
    for name, key, allowed in SWITCHES:
        v = run["sets"].get(key, 0)
        if type(v) is not int or v not in allowed:
            return "INVALID", "queue sets %s=%r, not one of %s" % (key, v, allowed)
        got = sw[name]
        if got == "ABSENT":
            if not on_base:
                return "INVALID", "sidecar switch %s ABSENT outside the 6160438 worktree" % name
            if v != 0:
                return "INVALID", "sidecar switch %s ABSENT but the line sets %s=%d" % (name, key, v)
            continue
        if on_base:
            return "INVALID", "sidecar switch %s=%r on the 6160438 worktree, which has no accessor (ABSENT expected)" % (
                name, got)
        if name == "hold":
            ok = type(got) is bool and got == (v != 0)
        else:
            ok = type(got) is int and got == v
        if not ok:
            return "INVALID", "sidecar switch %s=%r, queue %s=%r" % (name, got, key, v)

    # (7) CL review: every wrap target present (the base worktree lacks exactly BASE_ABSENT)
    ab = sc.get("absent")
    if not isinstance(ab, list) or not all(isinstance(x, str) for x in ab):
        return "INVALID", "sidecar absent %r is not a list of names" % (ab,)
    if on_base:
        if len(ab) != len(set(ab)) or set(ab) != BASE_ABSENT:
            return "INVALID", "sidecar absent on the 6160438 worktree %s != the %d expected %s" % (
                ab, len(BASE_ABSENT), sorted(BASE_ABSENT))
    elif ab:
        return "INVALID", "sidecar absent %s on the carryleg checkout (a wrap target is missing)" % ab

    # (8) CL review: one model, stepped exactly the line's steps, no observer error
    ct = sc.get("counters")
    if not isinstance(ct, dict):
        return "INVALID", "sidecar counters is not an object"
    for key, want in (("model_steps", run["steps"]), ("models_built", 1), ("observer_errors", 0)):
        got = ct.get(key)
        if not _exact_int(got) or got != want:
            return "INVALID", "sidecar counters.%s=%r, expected %d" % (key, got, want)

    # (9) CL Part 3: the D-9 probe's own evidence (and no probe trace on any other line)
    why = _cl_probe.sidecar_problem(run["sets"], sc)
    if why:
        return "INVALID", "PROBE: " + why
    return "VALID", ""


def _orphans(run):
    return [p for p in (run["clobs"], run["clobs_tmp"], run["fm2p_tmp"]) if os.path.exists(p)]


def check(run):
    status, why = rbv.check(run)
    if run["kind"] != "ff":
        return status, why
    if status == "MISSING":
        left = _orphans(run)
        if left:
            return "INVALID", "json missing but left over: %s" % ",".join(os.path.basename(p) for p in left)
        return status, why
    if status != "VALID":
        return status, why
    return cl_check(run)


def _paths(run):
    """Every file --quarantine moves: _dcd4rb_validate.quarantine's set + the CL extras."""
    if run["kind"] == "ff":
        base = [run["json"], run["json"] + ".tmp", run["stdout"], run["out"], run["err"]]
        return base, [run["clobs"], run["clobs_tmp"], run["fm2p_tmp"]]
    return [run["json"], run["log"]], []


def _target_dir(qdir, names):
    """qdir, or the first qdir/dupN holding none of `names` (CL review: a second move of
    the same job into the same directory would overwrite the first moved copy)."""
    cand, n = qdir, 0
    while any(os.path.lexists(os.path.join(cand, nm)) for nm in names):
        n += 1
        cand = os.path.join(qdir, "dup%d" % n)
    return cand


def quarantine(run, qdir, dry_run=False):
    base, extra = _paths(run)
    present = [p for p in base + extra if os.path.exists(p)]
    tdir = _target_dir(qdir, [os.path.basename(p) for p in present])
    sub = "" if tdir == qdir else os.path.basename(tdir) + "/"
    if dry_run:
        return ["%s%s(DRY RUN, not moved)" % (sub, os.path.basename(p)) for p in present]
    moved = [sub + m for m in rbv.quarantine(run, tdir)]  # the wrapped file set, moved by its own code
    for p in extra:
        if os.path.exists(p):
            try:
                shutil.move(p, os.path.join(tdir, os.path.basename(p)))
                moved.append(sub + os.path.basename(p))
            except OSError as exc:  # open in a live process on Windows
                moved.append("%s%s(NOT MOVED: %s)" % (sub, os.path.basename(p), type(exc).__name__))
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
    ap.add_argument("--dry-run", action="store_true",
                    help="never write: --quarantine only reports what it would move")
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
            if a.dry_run:
                why += " -> would quarantine %s" % ",".join(quarantine(r, a.quarantine, dry_run=True))
            else:
                why += " -> quarantined %s" % ",".join(quarantine(r, a.quarantine))
        print(("%s %s %s" % (status, r["name"], why)).rstrip())
    if a.all:
        print("SUMMARY total=%d valid=%d invalid=%d missing=%d"
              % (len(runs), counts["VALID"], counts["INVALID"], counts["MISSING"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
