"""MVG round, THE FLIP: the isTrue 19.12(c) check (outputs/urgency_part1d.txt 1d.6.3 THE FLIP: "the isTrue 19.12(c)
check").

WHAT 19.12(c) REQUIRES (outputs/fix3b_part1.txt 19.12 (c)), at the merged head - here the flip commit 980d9338 (later
commits change only outputs/ and documentation, so every run-loaded file is identical):
  (1) the isTrue reach census (outputs/_ist3_reach.py, the record-only wrapper around outputs/_ut_probe.py that adds
      <out>.reach.json): no numpy value at any F-2 site in the shipped runs;
  (2) shipped vs both isTrue switches 0 (MR1_TRUTHINESS_FIX=0, NUMPY_SCALAR_FLAGS=0) on the 12 configurations of the
      isTrue K arm (outputs/_ist3_configs.json, the configurations flagged k_arm), 24 runs: every recorded field equal
      except mr.mr1_list, which must equal the LITERAL accumulation at 0 and the CORRECTED one when shipped
      (outputs/isTrue_report.txt 4.4: G-A, G-K, G1-a, G1-b).
  Any difference STOPS the measurement round until it is explained.

usage (from the mvg worktree root, with E:/Projects/SAS/.venv/Scripts/python.exe -B, PYTHONDONTWRITEBYTECODE=1):
  python outputs/_mvg_ist.py write              writes the FROZEN queue outputs/_mvg_q_ist.jsonl (24 lines, for
                                                outputs/_mf2_pool.py) and the launch freeze record
                                                outputs/_mvg_ist/_freeze_launch.json; refuses to re-write a different
                                                queue; refuses on a tag collision or a tree that is not clean
  python outputs/_mvg_ist.py analyze [--partial]  validity, reach census, S vs K, G1-a / G1-b; prints a per-configuration
                                                table and "19.12(c) => PASS/FAIL"; writes the same text to
                                                outputs/_mvg_ist_result.txt (and outputs/_mvg_ist/_freeze_complete.json)

ARMS (each run through E:/Projects/SAS_wt/mvg/outputs/_ist3_reach.py with --repo E:/Projects/SAS_wt/mvg):
  S  the configuration's own --set list = the isTrue F12 line: FF_APPROACH_PATH, FF_RETREAT_KEEP_APPROACH,
     FF_FIX_STRANDING_GUARD, MR1_TRUTHINESS_FIX and NUMPY_SCALAR_FLAGS at their shipped defaults (1; set by nothing)
  K  + --set MR1_TRUTHINESS_FIX=0 --set NUMPY_SCALAR_FLAGS=0 = the isTrue K line
THE RUN LINE: the FROZEN isTrue line (outputs/_ist3_q.jsonl: ist3_F12_<cid> for S, ist3_K_<cid> for K; both re-derived
  with outputs/_ist3_queue.py line() and checked equal), verbatim, with exactly four tokens replaced: argv[0] (the
  wrapper: this worktree's outputs/_ist3_reach.py), the --repo value (this worktree), the --out value
  (outputs/_mvg_ist/_sd_mvgist_<arm>_<cid>.json) and the --tag value (mvgist_<arm>_<cid>); cwd = this worktree. The
  configuration's scenario / wind / seed / steps / --set list are the isTrue K configuration's, unchanged.

ANALYZE (comparison and accumulation functions imported from outputs/_ist3_analyze.py: full_diff with its TOP_SKIP /
  SEC_SKIP sets and params compared without the two isTrue keys, _mr1_acc, _poollog):
  G-V   per run: complete, crashed None, steps_done == steps; repo == this worktree; head == 980d9338's full sha;
        src_sha == the launch freeze record; tag / argv / extra_params / .argv sidecar == the queue line; the arm took
        effect (eff searcher_targeting / victim_spawn_mode, FIX3B keys, SEARCHER_FP_* keys, global_planner_mode,
        SEARCHER_TARGETING_FIX, params' MR1_TRUTHINESS_FIX / NUMPY_SCALAR_FLAGS exactly the arm's own --set, no FF_*
        movement switch in params or extra_params); CRN on with draws > 0; fb3.inst error_count 0 and not broken;
        mr / ut / reach error lists empty; no observer error marker in mf2 / fx3; reach chain_exit 0 and f2_present;
        mr record one row per step.
  SW    the switch accessors the run read, reconstructed from its recorded params in a fresh interpreter at this
        worktree (agents.ff_approach_path / ff_retreat_keep_approach / ff_fix_stranding_guard / mr1_truthiness_fix /
        numpy_scalar_flags): S all True; K the two isTrue accessors False, the three movement accessors True. The
        chain records no movement switch, so this and the freeze are the evidence that the flipped defaults ran.
  REACH S: no numpy-typed value at any F-2 site (truthy x4, maintain, safe_float, plain_scalar inputs) or any evaluated
        parameter / context value (the isTrue analyzer's per-arm numpy total); K reported.
  SvK   S vs K: every recorded field equal except mr.mr1_list (isTrue G-A / G-K shape; full_diff skip_mr1_list).
  G1-a  S: mr.mr1_list == the CORRECTED accumulation (mr1_steps row[2]), bit-equal.
  G1-b  K: mr.mr1_list == the LITERAL accumulation (mr1_steps row[1]), bit-equal.
  MR1-chg  MR1 differs between S and K exactly where the corrected and literal per-step counts differ.
  LOG   the pool logs of S and K equal line for line (tag, wall= tokens and the checkout path normalised).
  INFO (never gating): S vs the isTrue F12 record and K vs the isTrue K record of the same configuration (head
        6904b1f8, before the movement round): whether the flipped head changed the run.
FREEZE: the launch record hashes every tracked file outside outputs/ and the chain / pool / analysis files in outputs/;
  analyze re-hashes them. A change to a run-loaded file (any tracked file outside outputs/, tests/ and *.md / *.txt,
  or a chain file) FAILS the check; anything else is a NOTE.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
WT = r"E:\Projects\SAS_wt\mvg"
MAIN = r"E:\Projects\SAS"
HEAD = "980d933838403312dcfadc5c2ced7e1e195e21b4"
PY = os.path.join(MAIN, ".venv", "Scripts", "python.exe")
WRAPPER = os.path.join(WT, "outputs", "_ist3_reach.py")
QUEUE = os.path.join(HERE, "_mvg_q_ist.jsonl")
OUT_DIR = os.path.join(HERE, "_mvg_ist")
RESULT = os.path.join(HERE, "_mvg_ist_result.txt")
FREEZE_LAUNCH = os.path.join(OUT_DIR, "_freeze_launch.json")
FREEZE_COMPLETE = os.path.join(OUT_DIR, "_freeze_complete.json")
TAG_PREFIX = "mvgist_"
ARMS = ("S", "K")
SRC_ARM = {"S": "F12", "K": "K"}                 # the isTrue line each arm reproduces
ISTRUE_KEYS = ("MR1_TRUTHINESS_FIX", "NUMPY_SCALAR_FLAGS")
FF_KEYS = ("FF_APPROACH_PATH", "FF_RETREAT_KEEP_APPROACH", "FF_FIX_STRANDING_GUARD")
ACCESSORS = ("ff_approach_path", "ff_retreat_keep_approach", "ff_fix_stranding_guard", "mr1_truthiness_fix",
             "numpy_scalar_flags")
WANT_ACC = {"S": {a: True for a in ACCESSORS},
            "K": dict({a: True for a in ACCESSORS}, mr1_truthiness_fix=False, numpy_scalar_flags=False)}
WANT_PARAMS = {"S": {}, "K": {"MR1_TRUTHINESS_FIX": 0, "NUMPY_SCALAR_FLAGS": 0}}
CHAIN_FILES = ("outputs/_ist3_reach.py", "outputs/_ut_probe.py", "outputs/_fb3_probe.py", "outputs/_fx3_probe.py",
               "outputs/_mf2_probe.py", "outputs/_sd_probe.py", "outputs/_bp_inst.py", "outputs/_fm2_probe_harness.py",
               "outputs/_ffr_harness.py", "outputs/_mf2_pool.py", "outputs/_ist3_queue.py",
               "outputs/_ist3_configs.json", "outputs/_ist3_q.jsonl", "outputs/_ist3_analyze.py")
SITES = ("fail_safe_planner", "global_mission_planner", "local_uav_path_planner", "rescue_planner")


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(*args) -> str:
    r = subprocess.run(["git", "-C", WT] + list(args), capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    if r.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), r.stderr.strip()[:300]))
    return r.stdout


def _sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _same_path(a, b) -> bool:
    return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


# ---------------------------------------------------------------------------------------------------------------- queue
def k_configs(Q):
    """The isTrue K configurations, from _ist3_queue.configs(), checked equal to the frozen _ist3_configs.json."""
    cfgs = Q.configs()
    with open(os.path.join(HERE, "_ist3_configs.json"), encoding="utf-8") as fh:
        frozen = json.load(fh)
    if frozen.get("configs") != json.loads(json.dumps(cfgs)):
        raise SystemExit("STOP: outputs/_ist3_configs.json differs from _ist3_queue.configs()")
    ks = [c for c in cfgs if c.get("k_arm")]
    if len(ks) != 12:
        raise SystemExit("STOP: %d K configurations, not 12" % len(ks))
    return ks


def ist3_lines():
    with open(os.path.join(HERE, "_ist3_q.jsonl"), encoding="utf-8") as fh:
        return {ln["name"]: ln for ln in (json.loads(x) for x in fh if x.strip())}


def build_lines(Q) -> list[dict]:
    frozen = ist3_lines()
    lines = []
    for c in k_configs(Q):
        src = {}
        for arm in ARMS:
            iname = "ist3_%s_%s" % (SRC_ARM[arm], c["cid"])
            ref = frozen.get(iname)
            if ref is None or json.loads(json.dumps(Q.line(c, SRC_ARM[arm]))) != ref:
                raise SystemExit("STOP: the frozen isTrue line %s is missing or differs from _ist3_queue.line()" % iname)
            src[arm] = ref
        # K = S + the two isTrue switches, inserted after the configuration's --set list
        a_s, a_k = src["S"]["argv"], src["K"]["argv"]
        i = a_s.index("--steps")
        exp_k = a_s[:i] + ["--set", "MR1_TRUTHINESS_FIX=0", "--set", "NUMPY_SCALAR_FLAGS=0"] + a_s[i:]
        exp_k[exp_k.index("--out") + 1] = src["K"]["out"]
        exp_k[exp_k.index("--tag") + 1] = src["K"]["name"]
        if a_k != exp_k or src["K"]["cwd"] != src["S"]["cwd"]:
            raise SystemExit("STOP: the isTrue K line of %s is not its F12 line + the two isTrue switches" % c["cid"])
        for arm in ARMS:
            ref = src[arm]
            argv = list(ref["argv"])
            tag = "%s%s_%s" % (TAG_PREFIX, arm, c["cid"])
            out = os.path.join(OUT_DIR, "_sd_%s.json" % tag)
            if argv[0] != Q.PROBE:
                raise SystemExit("STOP: argv[0] of %s is %s" % (ref["name"], argv[0]))
            argv[0] = WRAPPER
            for flag, old, new in (("--repo", ref["cwd"], WT), ("--out", ref["out"], out), ("--tag", ref["name"], tag)):
                j = argv.index(flag) + 1
                if argv[j] != old or argv.count(flag) != 1:
                    raise SystemExit("STOP: %s of %s is not the expected token" % (flag, ref["name"]))
                argv[j] = new
            changed = [k for k, (x, y) in enumerate(zip(argv, ref["argv"])) if x != y]
            if len(argv) != len(ref["argv"]) or len(changed) != 4:
                raise SystemExit("STOP: %s differs from its isTrue line in %s positions" % (tag, changed))
            lines.append({"name": tag, "argv": argv, "out": out, "cwd": WT})
    return lines


# --------------------------------------------------------------------------------------------------------------- freeze
def freeze_record(phase: str) -> dict:
    head = _git("rev-parse", "HEAD").strip()
    status = _git("status", "--porcelain", "--untracked-files=no")
    untracked = [ln[3:] for ln in _git("status", "--porcelain", "--untracked-files=normal").splitlines()
                 if ln.startswith("?? ") and not ln[3:].startswith("outputs/")]
    tracked = [p for p in _git("ls-files", "-z", "--", ".", ":(exclude)outputs").split("\0") if p]
    files = sorted([p for p in tracked if not p.startswith("outputs/")] + list(CHAIN_FILES))
    sha = {}
    for p in files:
        fp = os.path.join(WT, *p.split("/"))
        sha[p] = _sha256(fp) if os.path.exists(fp) else "missing"
    return {"phase": phase, "head": head, "status": status, "untracked_outside_outputs": untracked, "sha": sha}


def run_loaded(p: str) -> bool:
    if p in CHAIN_FILES:
        return True
    return not (p.startswith("outputs/") or p.startswith("tests/") or p.lower().endswith((".md", ".txt", ".rst")))


# ---------------------------------------------------------------------------------------------------------------- write
def write() -> int:
    Q = _load("_ist3_queue_mvgist", "_ist3_queue.py")
    lines = build_lines(Q)
    text = "".join(json.dumps(x) + "\n" for x in lines)
    if os.path.exists(QUEUE):
        with open(QUEUE, encoding="utf-8") as fh:
            if fh.read() != text:
                print("STOP: %s exists and differs (frozen; never re-written)" % QUEUE)
                return 2
        print("unchanged (frozen): %s (%d lines)" % (QUEUE, len(lines)))
        return 0
    # tag collision: no file carrying these tags in outputs/ of this worktree or of the main checkout (single-level
    # listings only), none tracked in either repository, and no output directory yet
    own = ("_mvg_q_ist.jsonl", "_mvg_ist", "_mvg_ist_result.txt")
    hits = []
    for d in (HERE, os.path.join(MAIN, "outputs")):
        hits += [os.path.join(d, n) for n in os.listdir(d) if TAG_PREFIX in n or n in own]
    for repo in (WT, MAIN):
        r = subprocess.run(["git", "-C", repo, "ls-files", "outputs/"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        if r.returncode != 0:
            print("STOP: git ls-files failed in %s" % repo)
            return 2
        hits += ["tracked in %s: %s" % (repo, p) for p in r.stdout.splitlines()
                 if TAG_PREFIX in p or p.split("/", 1)[-1].split("/")[0] in own]
    if hits:
        print("STOP: tag collision: %s" % hits[:10])
        return 2
    fr = freeze_record("launch")
    probs = []
    if fr["head"] != HEAD:
        probs.append("HEAD %s != %s" % (fr["head"], HEAD))
    if fr["status"].strip():
        probs.append("tracked files modified: %r" % fr["status"][:300])
    if fr["untracked_outside_outputs"]:
        probs.append("untracked files outside outputs/: %s" % fr["untracked_outside_outputs"][:10])
    if any(v == "missing" for v in fr["sha"].values()):
        probs.append("missing files: %s" % [k for k, v in fr["sha"].items() if v == "missing"][:10])
    if probs:
        print("STOP: the tree is not the clean flip commit: %s" % probs)
        return 2
    os.makedirs(OUT_DIR, exist_ok=False)
    with open(FREEZE_LAUNCH, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fr, fh, indent=1, sort_keys=True)
        fh.write("\n")
    with open(QUEUE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote %s (%d lines: S and K x %d configurations) and %s (%d files hashed, head %s)"
          % (QUEUE, len(lines), len(lines) // 2, FREEZE_LAUNCH, len(fr["sha"]), fr["head"][:8]))
    return 0


# ------------------------------------------------------------------------------------------------- accessor rebuild
def _accessors_child() -> int:
    """Child mode: stdin {"repo", "runs": {name: params}} -> stdout {name: {accessor: value}} (fresh interpreter)."""
    req = json.load(sys.stdin)
    repo = req["repo"]
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am  # noqa: E402
    import common_fixed_variables as cfv  # noqa: E402
    for m in (am, cfv):
        if not os.path.abspath(m.__file__).lower().startswith(repo.lower() + os.sep):
            print(json.dumps({"_error": "import mismatch %s" % m.__file__}))
            return 3
    out = {}
    missing = object()
    for name, params in req["runs"].items():
        saved = {k: getattr(cfv, k, missing) for k in params}
        for k, v in params.items():          # apply_scenario_config: setattr on the cfv module
            setattr(cfv, k, v)
        out[name] = {a: getattr(am, a)() for a in ACCESSORS}
        for k, v in saved.items():
            if v is missing:
                delattr(cfv, k)
            else:
                setattr(cfv, k, v)
    out["_raw"] = {k: getattr(cfv, k, None) for k in FF_KEYS + ISTRUE_KEYS}
    print(json.dumps(out))
    return 0


def rebuild_accessors(runs: dict) -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([PY, "-B", os.path.abspath(__file__), "_accessors"], input=json.dumps({"repo": WT, "runs": runs}),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=WT, env=env,
                       timeout=600)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"_error": "accessor child failed rc=%s: %s" % (r.returncode, (r.stderr or r.stdout)[-400:])}


# -------------------------------------------------------------------------------------------------------------- analyze
def _paths_only(diffs):
    out = []
    for s in diffs:
        out.append(s.split(": ", 1)[0] if ": " in s else s)
    return out


def analyze(partial: bool) -> int:
    lines_out: list[str] = []

    def say(s=""):
        lines_out.append(s)
        print(s)

    Q = _load("_ist3_queue_mvgist", "_ist3_queue.py")
    A = _load("_ist3_analyze_mvgist", "_ist3_analyze.py")
    SD = _load("_sd_probe_mvgist", "_sd_probe.py")
    FB3 = _load("_fb3_probe_keys_mvgist", "_fb3_probe.py")
    lines = build_lines(Q)
    with open(QUEUE, encoding="utf-8") as fh:
        qfile = [json.loads(x) for x in fh if x.strip()]
    if qfile != json.loads(json.dumps(lines)):
        print("STOP: %s differs from the re-derived queue" % QUEUE)
        return 3
    ks = k_configs(Q)
    say("isTrue 19.12(c) CHECK at the flip head %s (outputs/fix3b_part1.txt 19.12 (c); urgency_part1d.txt 1d.6.3)"
        % HEAD)
    say("QUEUE OK: %s, %d lines = S and K x %d isTrue K configurations (seeds %s)"
        % (QUEUE, len(lines), len(ks), ", ".join(str(c["seed"]) for c in ks)))

    # ---- freeze
    global_probs, notes = [], []
    with open(FREEZE_LAUNCH, encoding="utf-8") as fh:
        f0 = json.load(fh)
    f1 = freeze_record("complete")
    with open(FREEZE_COMPLETE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(f1, fh, indent=1, sort_keys=True)
        fh.write("\n")
    if f0["head"] != HEAD or f0["status"].strip() or f0["untracked_outside_outputs"]:
        global_probs.append("launch record: head %s, status %r, untracked %s"
                            % (f0["head"][:8], f0["status"][:80], f0["untracked_outside_outputs"][:5]))
    changed = sorted(p for p in set(f0["sha"]) | set(f1["sha"]) if f0["sha"].get(p) != f1["sha"].get(p))
    bad_changed = [p for p in changed if run_loaded(p)]
    if bad_changed:
        global_probs.append("run-loaded files changed since launch: %s" % bad_changed[:10])
    if [p for p in changed if not run_loaded(p)]:
        notes.append("non-run-loaded files changed since launch: %s" % [p for p in changed if not run_loaded(p)][:10])
    if f1["head"] != f0["head"]:
        notes.append("HEAD moved since launch: %s -> %s (run-loaded files %s)"
                     % (f0["head"][:8], f1["head"][:8], "unchanged" if not bad_changed else "CHANGED"))
    if f1["status"].strip():
        st_bad = [ln for ln in f1["status"].splitlines() if run_loaded(ln[3:])]
        (global_probs if st_bad else notes).append("tracked status at analysis: %r" % f1["status"][:300])
    if f1["untracked_outside_outputs"]:
        global_probs.append("untracked files outside outputs/ at analysis: %s" % f1["untracked_outside_outputs"][:10])
    say("FREEZE: %d files hashed at launch (head %s); at analysis %d changed, %d of them run-loaded"
        % (len(f0["sha"]), f0["head"][:8], len(changed), len(bad_changed)))

    # ---- per run validity (G-V)
    runs, logs, reach, gv = {}, {}, {}, {}
    missing = []
    for ln in lines:
        name, out = ln["name"], ln["out"]
        arm = name.split("_")[1]
        if not os.path.exists(out):
            missing.append(name)
            continue
        probs = []
        try:
            with open(out, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception as exc:
            gv[name] = ["unparseable (%r)" % (exc,)]
            continue
        after = ln["argv"][ln["argv"].index("--") + 1:]
        sets = {}
        for i, tok in enumerate(after):
            if tok == "--set":
                k, v = after[i + 1].split("=", 1)
                sets[k.strip()] = SD._parse_value(v)
        steps = int(after[after.index("--steps") + 1])
        if not d.get("complete") or d.get("crashed") is not None or d.get("steps_done") != steps:
            probs.append("complete=%s crashed=%s steps_done=%s" % (d.get("complete"), d.get("crashed") is not None,
                                                                   d.get("steps_done")))
        if not _same_path(d.get("repo"), WT):
            probs.append("repo %s" % d.get("repo"))
        if d.get("head") != HEAD:
            probs.append("head %s != %s" % (d.get("head"), HEAD))
        if d.get("tag") != name:
            probs.append("tag %s" % d.get("tag"))
        ss = d.get("src_sha") or {}
        if not ss:
            probs.append("src_sha missing")
        for fname, h in ss.items():
            rel = fname.replace("\\", "/")
            if (f0["sha"].get(rel) or "")[:16] != h:
                probs.append("src_sha %s %s != launch freeze %s" % (rel, h, (f0["sha"].get(rel) or "")[:16]))
        if d.get("extra_params") != sets:
            probs.append("extra_params %s != %s" % (d.get("extra_params"), sets))
        if d.get("argv") != after:
            probs.append("argv differs from the queue line")
        try:
            with open(out + ".argv", encoding="utf-8") as fh:
                sig = json.load(fh)
            if sig != {"argv": ln["argv"], "cwd": ln["cwd"]}:
                probs.append(".argv sidecar differs")
        except Exception:
            probs.append(".argv sidecar missing")
        fb3 = d.get("fb3") or {}
        eff = fb3.get("eff") or {}
        if eff.get("searcher_targeting") != int(sets.get("SEARCHER_TARGETING", 0)):
            probs.append("eff searcher_targeting %s" % eff.get("searcher_targeting"))
        if eff.get("victim_spawn_mode") != int(sets.get("VICTIM_SPAWN_MODE", 0)):
            probs.append("eff victim_spawn_mode %s" % eff.get("victim_spawn_mode"))
        for k, v in sets.items():
            if k in FB3.FIX3B_KEYS and (fb3.get("switches") or {}).get(k) != v:
                probs.append("switch %s recorded %s != %s" % (k, (fb3.get("switches") or {}).get(k), v))
            if k.startswith("SEARCHER_FP_"):
                rec = (fb3.get("bp_switches") or {}).get(k) or {}
                if rec.get("raw") != v or rec.get("eff") is None or float(rec["eff"]) != float(v):
                    probs.append("FP %s recorded %s != %s" % (k, rec, v))
        gpm_eff = (d.get("effective") or {}).get("global_planner_mode")
        if gpm_eff != int(sets.get("GLOBAL_PLANNER_MODE", 0)):
            probs.append("effective global_planner_mode %s" % gpm_eff)
        stf = (fb3.get("bp_switches") or {}).get("SEARCHER_TARGETING_FIX") or {}
        want_stf = sets.get("SEARCHER_TARGETING_FIX", 1)
        if stf.get("raw") != want_stf or stf.get("eff") is not (want_stf != 0):
            probs.append("SEARCHER_TARGETING_FIX recorded %s != %s" % (stf, want_stf))
        params = d.get("params") or {}
        for k in ISTRUE_KEYS:
            if params.get(k) != WANT_PARAMS[arm].get(k):
                probs.append("params %s = %s, the arm sets %s" % (k, params.get(k), WANT_PARAMS[arm].get(k)))
        for k in FF_KEYS:
            if k in params or k in (d.get("extra_params") or {}):
                probs.append("movement switch %s set explicitly (%s)" % (k, params.get(k)))
        crn = fb3.get("crn") or {}
        if not (crn.get("on") and (crn.get("crn_draws") or 0) > 0):
            probs.append("CRN not on with draws > 0: %s" % crn)
        inst = fb3.get("inst")
        if not isinstance(inst, dict) or inst.get("error_count") or inst.get("broken"):
            probs.append("fb3.inst missing / error_count / broken")
        mr = d.get("mr") or {}
        if mr.get("errors"):
            probs.append("mr errors %s" % mr["errors"][:2])
        if (d.get("ut") or {}).get("errors"):
            probs.append("ut errors %s" % d["ut"]["errors"][:2])
        for sec in ("mf2", "fx3"):
            if A.ERR_RE.search(json.dumps(d.get(sec))):
                probs.append("%s carries an observer error marker" % sec)
        ms = mr.get("mr1_steps")
        n_uav = len(mr.get("mr1_list") or [])
        if not (isinstance(ms, list) and len(ms) == steps and [x[0] for x in ms] == list(range(1, steps + 1))
                and all(len(x[1]) == n_uav and len(x[2]) == n_uav for x in ms) and mr.get("n_observations")
                and n_uav == int(params.get("NUM_AGENTS", n_uav))):
            probs.append("mr record malformed (%s rows, %s UAVs)" % (len(ms or []), n_uav))
        try:
            with open(out + ".reach.json", encoding="utf-8") as fh:
                rch = json.load(fh)
            if rch.get("chain_exit") not in (0, None) or rch.get("errors"):
                probs.append("reach exit %s errors %s" % (rch.get("chain_exit"), (rch.get("errors") or [])[:2]))
            if rch.get("f2_present") is not True:
                probs.append("reach f2_present %s" % rch.get("f2_present"))
            if not _same_path(rch.get("repo"), WT):
                probs.append("reach repo %s" % rch.get("repo"))
            reach[name] = rch
        except Exception as exc:
            probs.append("reach record missing (%r)" % (exc,))
        gv[name] = probs
        runs[name] = d
        logs[name] = A._poollog(out + ".poollog", (WT,), name)
    n_gv_fail = sum(1 for p in gv.values() if p)
    say("RUNS present %d / %d; G-V failures %d; global problems %d"
        % (len(runs), len(lines), n_gv_fail, len(global_probs)))
    for g in global_probs:
        say("  GLOBAL FAIL %s" % g)
    for name, p in gv.items():
        if p:
            say("  G-V FAIL %s: %s" % (name, "; ".join(p)))
    for nn in notes:
        say("  NOTE %s" % nn)
    if missing and not partial:
        say("STOP: %d runs missing (e.g. %s); use --partial for an interim report" % (len(missing), missing[:3]))
        return 3

    # ---- SW: the accessors the run read, reconstructed from its recorded params
    acc = rebuild_accessors({n: d.get("params") or {} for n, d in runs.items()})
    sw = {}
    if "_error" in acc:
        global_probs.append("SW: %s" % acc["_error"])
        say("  GLOBAL FAIL SW: %s" % acc["_error"])
    else:
        for n in runs:
            arm = n.split("_")[1]
            got = acc.get(n) or {}
            sw[n] = [a for a in ACCESSORS if got.get(a) is not WANT_ACC[arm][a]]
        say("SW: module defaults at this worktree: %s" % acc.get("_raw"))

    # ---- gates per configuration
    gates = {g: [0, 0] for g in ("SvK", "G1-a", "G1-b", "MR1-chg", "LOG", "SW")}
    fails, table, info = [], [], []
    lit_after3, lit_nz = 0, []

    def numpy_count(rch):
        n = 0
        for site in SITES:
            n += sum(v for k, v in ((rch.get("truthy") or {}).get(site) or {}).items() if k.startswith("numpy."))
        for key in ("maintain", "safe_float", "plain_scalar", "plain_scalar_converted"):
            n += sum(v for k, v in (rch.get(key) or {}).items() if k.startswith("numpy."))
        for key in ("params", "context"):
            for cnt in (rch.get(key) or {}).values():
                n += sum(cnt.values())
        return n

    for c in ks:
        names = {arm: "%s%s_%s" % (TAG_PREFIX, arm, c["cid"]) for arm in ARMS}
        r = {arm: runs.get(names[arm]) for arm in ARMS}
        row = {"cid": c["cid"], "seed": c["seed"]}

        def gate(g, ok, why=""):
            gates[g][0 if ok else 1] += 1
            if not ok:
                fails.append("%s %s: %s" % (g, c["cid"], why))
            return "ok" if ok else "FAIL"

        for arm in ARMS:
            row["gv" + arm] = "-" if r[arm] is None else ("ok" if not gv.get(names[arm]) else "FAIL")
            row["np" + arm] = numpy_count(reach[names[arm]]) if names[arm] in reach else "-"
            if names[arm] in sw:
                row["sw" + arm] = gate("SW", not sw[names[arm]], "%s accessors %s not as the arm"
                                       % (arm, sw[names[arm]]))
            else:
                row["sw" + arm] = "-"
        d_s, d_k = r["S"], r["K"]
        if d_s is not None:
            mr = d_s["mr"]
            nobs = float(mr["n_observations"])
            cor = A._mr1_acc(len(mr["mr1_list"]), [x[2] for x in mr["mr1_steps"]], nobs)
            row["g1a"] = gate("G1-a", cor == list(mr["mr1_list"]), "S mr1_list != corrected accumulation")
        if d_k is not None:
            mr = d_k["mr"]
            nobs = float(mr["n_observations"])
            lit = A._mr1_acc(len(mr["mr1_list"]), [x[1] for x in mr["mr1_steps"]], nobs)
            row["g1b"] = gate("G1-b", lit == list(mr["mr1_list"]), "K mr1_list != literal accumulation")
            lit_after3 += sum(1 for x in mr["mr1_steps"] if x[0] > 3 and any(x[1]))
            nz = sum(1 for x in mr["mr1_steps"] if any(x[1]))
            if nz:
                lit_nz.append("%s:%d" % (c["cid"], nz))
        if d_s is not None and d_k is not None:
            dd = A.full_diff(d_s, d_k, skip_mr1_list=True)
            row["svk"] = gate("SvK", not dd, "; ".join(dd[:6]))
            ch = d_s["mr"]["mr1_list"] != d_k["mr"]["mr1_list"]
            expect = any(x[1] != x[2] for x in d_s["mr"]["mr1_steps"])
            row["chg"] = gate("MR1-chg", ch == expect, "MR1 changed %s, corrected != literal on some step %s"
                              % (ch, expect)) + ("(chg)" if ch else "(same)")
            ls, lk = logs.get(names["S"]), logs.get(names["K"])
            row["log"] = gate("LOG", ls == lk, "S vs K pool log differs (first: %s)"
                              % (next((p for p in zip(ls or [], lk or []) if p[0] != p[1]), "length"),))
        # INFO: against the isTrue record of the same configuration (pre-movement-round head), never gating
        for arm in ARMS:
            ref_path = os.path.join(HERE, "_sd_ist3_%s_%s.json" % (SRC_ARM[arm], c["cid"]))
            if r[arm] is None or not os.path.exists(ref_path):
                row["ref" + arm] = "-"
                continue
            with open(ref_path, encoding="utf-8") as fh:
                ref = json.load(fh)
            dd = A.full_diff(r[arm], ref, skip_mr1_list=False)
            row["ref" + arm] = "same" if not dd else "differs"
            if dd:
                info.append("%s %s vs isTrue %s: %d%s differing fields, first %s"
                            % (c["cid"], arm, SRC_ARM[arm], len(dd), "+ (listing capped)" if len(dd) >= 12 else "",
                               _paths_only(dd)[:5]))
        table.append(row)

    say("")
    say("PER CONFIGURATION (G-V / SW per arm; np = numpy-typed values at the F-2 sites and evaluated params/context;")
    say("  SvK = S vs K every field except mr.mr1_list; G1-a = S corrected; G1-b = K literal; MR1-chg; LOG;")
    say("  ref = INFO only: the run vs the isTrue record of the same configuration at 6904b1f8)")
    hdr = "%-18s %6s | %-4s %-4s | %-4s %-4s | %5s %5s | %-4s | %-4s | %-4s | %-9s | %-4s | %-7s %-7s" % (
        "config", "seed", "GV-S", "GV-K", "SW-S", "SW-K", "np-S", "np-K", "SvK", "G1-a", "G1-b", "MR1-chg", "LOG",
        "ref-S", "ref-K")
    say(hdr)
    say("-" * len(hdr))
    for row in table:
        say("%-18s %6s | %-4s %-4s | %-4s %-4s | %5s %5s | %-4s | %-4s | %-4s | %-9s | %-4s | %-7s %-7s" % (
            row["cid"], row["seed"], row["gvS"], row["gvK"], row["swS"], row["swK"], row["npS"], row["npK"],
            row.get("svk", "-"), row.get("g1a", "-"), row.get("g1b", "-"), row.get("chg", "-"), row.get("log", "-"),
            row["refS"], row["refK"]))

    # ---- reach census per arm
    say("")
    say("REACH CENSUS (record-only, outputs/_ist3_reach.py), summed per arm: calls = values seen at the site; numpy =")
    say("  numpy-typed values there (maintain: calls of _is_maintain_option; plain_scalar: every call)")
    per_arm = defaultdict(lambda: defaultdict(Counter))
    calls = defaultdict(Counter)
    np_total = Counter()
    for name, rch in reach.items():
        arm = name.split("_")[1]
        rc = rch.get("calls") or {}
        for site in SITES:
            cnt = (rch.get("truthy") or {}).get(site) or {}
            per_arm[arm]["truthy." + site].update({k: v for k, v in cnt.items() if k.startswith("numpy.")})
            calls[arm]["truthy." + site] += sum(cnt.values())
        for key in ("maintain", "safe_float", "plain_scalar", "plain_scalar_converted"):
            cnt = rch.get(key) or {}
            per_arm[arm][key].update({k: v for k, v in cnt.items() if k.startswith("numpy.")})
            if key == "plain_scalar":
                calls[arm][key] += int(rc.get("plain_scalar", 0))
            elif key == "maintain":
                calls[arm][key] += int(rc.get("_is_maintain_option", 0))
            else:
                calls[arm][key] += sum(cnt.values())
        calls[arm]["evaluate_option"] += int(rc.get("evaluate_option", 0))
        calls[arm]["runs"] += 1
        for key in ("params", "context"):
            for k2, cnt in (rch.get(key) or {}).items():
                per_arm[arm]["%s.%s" % (key, k2)].update(cnt)
        np_total[arm] += numpy_count(rch)
    for arm in ARMS:
        if arm not in calls:
            continue
        say("  arm %s (%d runs):" % (arm, calls[arm]["runs"]))
        for site in sorted((set(per_arm[arm]) | set(calls[arm])) - {"runs"}):
            say("    %-40s calls %10d  numpy %s" % (site, calls[arm].get(site, 0), dict(per_arm[arm].get(site, {}))))
    say("numpy-typed values at any F-2 site or evaluated parameter / context value, per arm: %s"
        % {a: np_total[a] for a in ARMS if a in calls})
    census_ok = "S" in calls and np_total["S"] == 0 and calls["S"]["runs"] == len(ks)

    say("")
    say("K literal MR1 counts after step 3 (expected 0): %d; K runs with a non-zero literal count: %d %s"
        % (lit_after3, len(lit_nz), lit_nz))
    say("")
    say("INFO (not gating): runs that differ from the isTrue record of the same configuration (head 6904b1f8):")
    say("  S %d / %d, K %d / %d" % (sum(1 for t in table if t["refS"] == "differs"), len(table),
                                    sum(1 for t in table if t["refK"] == "differs"), len(table)))
    for x in info:
        say("  %s" % x)

    say("")
    say("GATES (pass / fail):")
    for g, (p, f) in gates.items():
        say("  %-8s %3d / %d" % (g, p, f))
    say("  G-V      %3d / %d (runs)" % (len(runs) - n_gv_fail, n_gv_fail))
    say("  REACH-S  %s (numpy values in arm S: %s; arm K: %s)" % ("PASS" if census_ok else "FAIL", np_total.get("S"),
                                                                 np_total.get("K")))
    for f in fails:
        say("  FAIL %s" % f)
    ok = (not missing and not global_probs and not n_gv_fail and census_ok
          and not any(f for _p, f in gates.values())
          and gates["SvK"][0] == len(ks) and gates["G1-a"][0] == len(ks) and gates["G1-b"][0] == len(ks)
          and gates["SW"][0] == 2 * len(ks))
    say("")
    say("19.12(c) => %s" % ("PASS" if ok else ("INCOMPLETE" if missing else "FAIL")))
    with open(RESULT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines_out) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "write":
        raise SystemExit(write())
    if cmd == "analyze":
        raise SystemExit(analyze("--partial" in sys.argv[2:]))
    if cmd == "_accessors":
        raise SystemExit(_accessors_child())
    print(__doc__)
    raise SystemExit(2)
