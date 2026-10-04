"""bayesprep Part 3 screen analyzer (read-only) - outputs/bayesprep_part1.txt section 7 + the rulings of section 10
(D-6: RW and GP screened too). A development check, not the measurement; nothing here is a result.

usage (worktree root): .venv/Scripts/python.exe outputs/_bp_analyze.py [--section S[,S...]] [--head <sha>] [--write]
                                                                        [--selftest]
  --section  any of PROV ID INSTR GATES RECALL RB INVAR ITEM5 BAND DW FP EXPO COMP PILOT (case-insensitive; repeat or
             comma-separate; bare names work too). Default: all, in that order, then SUMMARY.
  --head     the head every run must carry (default: the worktree's git HEAD; a prefix is accepted)
  --write    also write the report to outputs/_bp_analysis.txt
  --selftest ALIASES the bp tags to existing recorded tags (bpi/bpc -> ut2r/ut2u/ut2u2, bpf r -> ut2bf, bpf u ->
             fb3vs3r, bpd r -> fb3bdr, bpx r / bpp r -> fb3bfr, bpl r -> fb3lo, bpw r -> fb3rw, V1 -> fb3*/ut2bf, rb ->
             utQ) to exercise every section that does not need the instrument, plus cross-checks of this file's
             rules against the reused ones. PROV refusals are then REPORTED, NOT APPLIED (the aliases are other
             heads / repos by construction). Its numbers mean nothing. --write is refused with it.
  --inst-sample PATH  (selftest only, repeatable) run the instrument paths (V2 replay, V3, victim_fire, health,
             bp_switches, the digest) on a real instrumented probe JSON; with two samples also the V1 / V1b rule
             (full_diff) between the first two (e.g. the same line run with and without --instrument).

Expected runs: outputs/_bp_queue.py spec() - the ONE owner of every expected argv (probe runs keyed (tag, cell),
tags = arm + placement r / u / u2; V1 bpv1*; V1b bpnfr / bpnpr; rb bprba/b/c/s). Runs are loaded one at a time
with outputs/_fx3r_analyze.py load_one (the R.load per-file rule: JSON + stdout '[Victim Detection]' events), digested
once, and released (a 360-step run is ~8 MB in memory; 309 runs would not fit next to a running pool).
Measures reused UNCHANGED: _fb3_analyze searcher_o (broad / pocket near r=5 / pocket anywhere r=500 counts), mech,
ff_episodes, det_times, eligible_victims, run_mean_det, _alarms, sec_rbgate; _fx3r_analyze FIELDS / probe_ident's
rule, load_one; _fx3_pockets.pockets (for the pocket episodes' mechanism, checked to give searcher_o's counts);
_mf2_pool.signature (the .argv rule); _sd_probe._parse_value (the --set rule).
Sections (PASS / FAIL where a gate; plain numbers otherwise; both directions; refused / missing runs are listed):
  PROV   every run: repo = the worktree, head, extra_params = the line's --set dict, the sd argv and the pool .argv
         signature = the queue line, CRN as intended with crn_draws > 0 (0 when off), fb3.inst present (absent for
         V1b), the probe sections present, fb3.eff targeting / spawn mode, src_sha = the worktree file's hash raw OR
         after LF (or CRLF) normalisation (the kind is reported). Any mismatch -> REFUSED (excluded everywhere, listed).
  ID     bpir vs ut2r and bpiu vs ut2u 16 / 16, bpiu2_D_W vs ut2u2_D_W 1 / 1: value identity on the fx3m FIELDS + every
         mf2 section (probe_ident's rule).
  INSTR  V1 each bpv1* vs its recorded run on every recorded field (FIELDS, the other non-provenance top-level fields,
         mf2, fx3, fb3 minus timing / inst / bp_switches, ut when both have it; probe version strings skipped), first
         differing path per run; V1b bpnfr vs bpfr and bpnpr vs bppr on the same set; V2 _bp_inst.replay and V3
         _bp_inst.self_check on every Bayes-arm run (bpd bpf bpx bpp bpg). Item-3 risk rule: a V1 failure is REPORTED
         and V1b (fresh, with vs without --instrument) validates the instrument instead; nothing is adjusted.
  GATES  per placement r / u: every arm vs bpc on the same cells, bpc vs bpi: G-N (no terminal_step by 360),
         searcher G-O (broad, pocket near, pocket anywhere; mechanism class, before / after the last detection),
         FIREFIGHTER G-O (_fb3_analyze.ff_episodes; a gate this round). bpw is exempt from searcher G-O (reported).
         The u2 cell D_W is reported per arm.
  RECALL every targeting arm: issued entries and own-strategy labels at / after each searcher's recall trigger,
         lo_continuation_steps, trigger = last detection + 1, post-detection searcher episodes; bpx reported only.
  RB     bprb shards vs utR: rescued not lower, no new per-seed loss, 0 latched; then _fb3_analyze.sec_rbgate (vs fx3gS).
  INVAR  crashes, inline violations, warnings 0; co-location by kind from rows_uav (airborne+airborne 0, docked+docked 0,
         airborne over docked reported); global COLLISION_RISK 0; observer errors reported.
  ITEM5  bpc vs bpi: DRIFT_TOO_HIGH local / global, fire-tracker refusals (all / into a docked cell / within Chebyshev 2
         of a depot footprint), degraded_operation steps, docking (fx3.rtb), co-location, rescued / dead.
  BAND   bpd bpf bpx (+ bpp, bpc): edge-band victims (< 4 on at least half the undetected steps; and by spawn cell),
         detection and first-cover steps band vs non-band, PAIRED bpf vs bpx, outer-ring targets, reach, drop reasons.
  DW     the u2 cell D_W per arm: victim_3 detected and when, closest approach of any UAV / searcher, rescued / dead.
  FP     bpp vs bpf: searcher steps in fire / smoke / within 3 / 6 (search vs return legs), threatened and nearest-fire
         victims' detection (_bp_inst.victim_fire), rescued, dead, give-ups, drops, FIRE episodes, T_hat error, fp_ms.
  EXPO   the 4.6(a) exposure table for every arm.     COMP  belief / plan / fp ms, instrument overhead, wall_s.
  PILOT  E1 per run and the paired SD of bpp-bpc and bpf-bpc per placement.
"""
from __future__ import annotations

import collections
import contextlib
import io
import json
import math
import os
import re
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
SECTION_ORDER = ("PROV", "ID", "INSTR", "GATES", "RECALL", "RB", "INVAR", "ITEM5", "BAND", "DW", "FP", "EXPO",
                 "COMP", "PILOT")


def _parse_args(argv):
    o = {"sections": [], "head": None, "write": False, "selftest": False, "samples": []}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            print(__doc__)
            raise SystemExit(0)
        if a == "--inst-sample":
            if i + 1 >= len(argv):
                raise SystemExit("--inst-sample needs a path")
            o["samples"].append(argv[i + 1])
            i += 2
            continue
        if a in ("--section", "--head"):
            if i + 1 >= len(argv):
                raise SystemExit("%s needs a value" % a)
            v = argv[i + 1]
            i += 2
        elif a.startswith("--section=") or a.startswith("--head="):
            a, v = a.split("=", 1)
            i += 1
        elif a in ("--write", "--selftest"):
            o[a[2:]] = True
            i += 1
            continue
        elif not a.startswith("-"):
            a, v = "--section", a
            i += 1
        else:
            raise SystemExit("unknown argument %r (see --help)" % a)
        if a == "--section":
            o["sections"] += [s.strip().upper() for s in v.split(",") if s.strip()]
        else:
            o["head"] = v
    bad = [s for s in o["sections"] if s not in SECTION_ORDER]
    if bad:
        raise SystemExit("unknown section(s) %s; known: %s" % (bad, " ".join(SECTION_ORDER)))
    if o["samples"] and not o["selftest"]:
        raise SystemExit("--inst-sample is a --selftest option")
    if o["write"] and o["selftest"]:
        raise SystemExit("--write is refused with --selftest (aliased runs; outputs/_bp_analysis.txt is the screen's)")
    return o


OPTS = _parse_args(sys.argv[1:])
sys.argv = sys.argv[:1]                # _fb3_analyze reads sys.argv at import
import _fb3_analyze as A  # noqa: E402
import _bp_queue as Q  # noqa: E402
import _mf2_pool as POOL  # noqa: E402
import _sd_probe as SD  # noqa: E402

R, P = A.R, A.P
SELFTEST = OPTS["selftest"]
WT = Q.WT
HMAX = A.H                                  # 360: the censoring horizon of every detection measure
OWN_LABELS = ("victim_search_targeting", "victim_search_random_walk")
OUTER = (4, 44, 45)                         # the outer pool rings: 4 / 44 (fix off: 4..44) / 45 (fix on: 4..24 + 25..45)
MX, MY = (1, 0, -1, 0), (0, -1, 0, 1)       # the executor's direction order (as _mf2_probe / the dock scan)
FOOT_SPEC = ({(x, y) for x in range(0, 5) for y in range(45, 50)} | {(x, y) for x in range(45, 50) for y in range(0, 5)})
VID_DW = "victim_3"
BASE = "25421865"                           # the round's cut (tag untuned-search)
SRC_ROUND = ("agents.py", "wildfire_model.py", "common_fixed_variables.py")
INST_SRC = {"victim_search_belief.py": os.path.join("src_extension", "knowledge", "victim_search_belief.py"),
            "fire_arrival_estimate.py": os.path.join("src_extension", "planning", "fire_arrival_estimate.py")}
TOP_SKIP = {"probe", "tag", "repo", "head", "src_sha", "argv", "params", "extra_params", "wall_s", "python", "mesa",
            "_det"}
SEC_SKIP = (("mf2", {"probe"}), ("fx3", {"probe"}), ("fb3", {"timing", "inst", "bp_switches", "probe"}),
            ("ut", {"probe"}))
ARMS = Q.ARM_NAMES
TARGETING_ARMS = ("bpl", "bpd", "bpf", "bpx", "bpp", "bpw", "bpg")
BAYES_ARMS = ("bpd", "bpf", "bpx", "bpp", "bpg")
SHADOW_WANT = {"bpd": "BD", "bpf": "BF", "bpx": "BF", "bpp": "BF", "bpg": "BF"}   # V3: modes 3 / 5 -> BF, 2 -> BD
PLACES = ("r", "u", "u2")
ALIAS = {
    "bpir": "ut2r", "bpiu": "ut2u", "bpiu2": "ut2u2", "bpcr": "ut2r", "bpcu": "ut2u", "bpcu2": "ut2u2",
    "bpfr": "ut2bf", "bpfu": "fb3vs3r", "bpdr": "fb3bdr", "bpxr": "fb3bfr", "bppr": "fb3bfr", "bplr": "fb3lo",
    "bpwr": "fb3rw",
    "bpv1bd": "fb3bdr", "bpv1bf": "fb3bf", "bpv1bd2": "fb3bdr2", "bpv1bf2": "fb3bf2", "bpv1vs": "fb3vs3",
    "bpv1ut": "ut2bf", "bpnfr": "ut2bf", "bpnpr": "fb3bfr",
    "bprba": "utQa", "bprbb": "utQb", "bprbc": "utQc", "bprbs": "utQs",
} if SELFTEST else {}
LINES: list = []
VERD: list = []


def out(*a):
    s = " ".join(str(x) for x in a)
    LINES.append(s)
    print(s)


def head(title):
    out("=" * 118)
    out(title)


def verdict(section, item, v):
    VERD.append((section, item, v))
    return v


def real(tag):
    return ALIAS.get(tag, tag)


def _same_path(a, b):
    return Q._same_path(a, b)


def _git(*args):
    try:
        r = subprocess.run(["git", "-C", REPO] + list(args), capture_output=True, text=True, timeout=120)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


EXPECTED_HEAD = OPTS["head"] or (_git("rev-parse", "HEAD") or "").strip() or "unknown"
PROBE_E, RB_E = Q.entries()


def tag_of(arm, place):
    return arm + place


def keys_of(tag):
    return sorted(k for (t, k) in PROBE_E if t == tag)


def med(xs):
    return statistics.median(xs) if xs else None


def quart(xs):
    if not xs:
        return None
    s = sorted(xs)

    def q(f):
        i = f * (len(s) - 1)
        lo = int(math.floor(i))
        hi = min(len(s) - 1, lo + 1)
        return s[lo] + (s[hi] - s[lo]) * (i - lo)
    return q(0.25), q(0.5), q(0.75)


def p95(xs):
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, int(math.ceil(0.95 * len(s))) - 1)]


def fmt(v, f="%.1f"):
    return "n/a" if v is None else (f % v)


# ================================================================================================ instrument (lazy)
_INST = {"mod": None, "err": None, "tried": False}


def inst():
    """outputs/_bp_inst.py, imported lazily: decode / replay / self_check / victim_fire / pos_t."""
    if not _INST["tried"]:
        _INST["tried"] = True
        try:
            import _bp_inst  # noqa: F401
            _INST["mod"] = sys.modules["_bp_inst"]
        except Exception as exc:
            _INST["err"] = "%s: %s" % (type(exc).__name__, str(exc)[:160])
    return _INST["mod"]


def inst_missing_line():
    return "INSTRUMENT MODULE MISSING (outputs/_bp_inst.py not importable: %s)" % _INST["err"]


def _n_mismatch(r):
    m = r.get("mismatches") if isinstance(r, dict) else None
    if m is None and isinstance(r, dict):
        m = r.get("mismatch_steps")
    if isinstance(m, (list, tuple, set, dict)):
        return len(m)
    return int(m) if isinstance(m, (int, float)) else None


def inst_call(fn_name, d):
    """{ok, steps, mismatches, first, err} from _bp_inst.<fn_name>(d), never raising."""
    mod = inst()
    if mod is None:
        return {"err": "MODULE MISSING"}
    if not ((d.get("fb3") or {}).get("inst")):
        return {"err": "no fb3.inst in this run"}
    fn = getattr(mod, fn_name, None)
    if not callable(fn):
        return {"err": "_bp_inst has no %s()" % fn_name}
    try:
        r = fn(d)
    except Exception as exc:
        return {"err": "%s raised %s: %s" % (fn_name, type(exc).__name__, str(exc)[:160])}
    if not isinstance(r, dict):
        return {"err": "%s returned %s, not a dict" % (fn_name, type(r).__name__)}
    return {"ok": r.get("ok"), "steps": r.get("steps"), "mismatches": _n_mismatch(r),
            "first": repr(r.get("first"))[:160], "err": None, "notes": r.get("notes"), "checked": r.get("checked")}


def vf_norm(r):
    """_bp_inst.victim_fire(d) = {victims: {vid: {steps, dist, min_fire_dist, threatened, first_threat}}, t_err:
    [[vid, t, T_hat, actual_delay]]} -> ({vid: {threatened, min_fire_dist}}, [T_hat - actual_delay over the entries
    where both are numbers], note with the undefined-entry counts). Also tolerant of a flat error list."""
    if not isinstance(r, dict):
        return vf_none("victim_fire returned %s" % type(r).__name__)
    cand = r
    for k in ("victims", "per_victim"):
        if isinstance(r.get(k), dict):
            cand = r[k]
    errs = []
    top = False
    te = r.get("t_err")
    if isinstance(te, list) and all(isinstance(x, (list, tuple)) and len(x) >= 4 for x in te):
        num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)  # noqa: E731
        errs = [float(x[2]) - float(x[3]) for x in te if num(x[2]) and num(x[3])]
        top = True
        undefined = (sum(1 for x in te if not num(x[2])), sum(1 for x in te if not num(x[3])))
    else:
        undefined = None
    for k in ("t_hat_errors", "T_hat_errors", "t_errors", "errors"):
        v = r.get(k)
        if not top and isinstance(v, list) and all(isinstance(x, (int, float)) for x in v):
            errs, top = list(v), True
            break
    per = {}
    for vid, rec in cand.items():
        if not isinstance(rec, dict) or not ("threatened" in rec or "min_fire_dist" in rec):
            continue
        per[str(vid)] = {"threatened": rec.get("threatened"), "min_fire_dist": rec.get("min_fire_dist")}
        if not top:
            for k in ("t_hat_err", "T_hat_err", "t_err", "t_hat_errors", "errors"):
                v = rec.get(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    errs.append(v)
                    break
                if isinstance(v, list):
                    errs += [x for x in v if isinstance(x, (int, float)) and not isinstance(x, bool)]
                    break
    note = None if per else "no per-victim records with 'threatened' / 'min_fire_dist' (interface?)"
    return {"per": per, "errs": errs, "note": note, "undef": undefined or (0, 0), "n_entries": len(te or [])}


def vf_none(note):
    return {"per": None, "errs": [], "note": note, "undef": (0, 0), "n_entries": 0}


# ================================================================================================ PROV
def _sha_kinds(path):
    try:
        raw = open(path, "rb").read()
    except OSError:
        return None
    import hashlib
    lf = raw.replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    h = lambda b: hashlib.sha256(b).hexdigest()[:16]  # noqa: E731
    return {"raw": h(raw), "lf": h(lf), "crlf": h(crlf)}


_SHA = {}


def src_check(src_sha):
    """{rel: kind} with kind raw / lf / crlf / MISMATCH / MISSING."""
    res = {}
    for rel, sha in (src_sha or {}).items():
        if rel not in _SHA:
            _SHA[rel] = _sha_kinds(os.path.join(REPO, rel))
        k = _SHA[rel]
        if k is None:
            res[rel] = "MISSING"
            continue
        res[rel] = next((n for n in ("raw", "lf", "crlf") if k[n] == sha), "MISMATCH")
    return res


def expected_extra(e):
    a = e["line"]["argv"]
    sd = a[a.index("--") + 1:]
    ex = {}
    for i, x in enumerate(sd):
        if x == "--set" and i + 1 < len(sd):
            k, v = sd[i + 1].split("=", 1)
            ex[k.strip()] = SD._parse_value(v)
    return ex, sd


def prov_check(d, e, path):
    """The PROV rules for one probe run; returns (reasons, src kinds)."""
    why = []
    if not _same_path(d.get("repo"), WT):
        why.append("repo %s" % d.get("repo"))
    h = str(d.get("head") or "")
    if not (EXPECTED_HEAD != "unknown" and h.startswith(EXPECTED_HEAD)):
        why.append("head %s != %s" % (h[:10], EXPECTED_HEAD[:10]))
    ex, sd = expected_extra(e)
    if d.get("extra_params") != ex:
        why.append("extra_params %s != %s" % (json.dumps(d.get("extra_params"), sort_keys=True),
                                               json.dumps(ex, sort_keys=True)))
    if d.get("argv") != sd:
        why.append("sd argv differs from the queue line")
    try:
        sig = open(path + ".argv", encoding="utf-8").read()
        if sig != POOL.signature(e["line"]):
            why.append(".argv signature differs from the queue line")
    except OSError:
        why.append("no .argv (not a pool run of this line)")
    fb = d.get("fb3") or {}
    crn = fb.get("crn") or {}
    if bool(crn.get("on")) != e["crn"]:
        why.append("crn.on %s, intended %s" % (crn.get("on"), e["crn"]))
    elif e["crn"] and not int(crn.get("crn_draws") or 0) > 0:
        why.append("crn on with crn_draws %s" % crn.get("crn_draws"))
    elif not e["crn"] and int(crn.get("crn_draws") or 0) != 0:
        why.append("crn off with crn_draws %s" % crn.get("crn_draws"))
    if ("inst" in fb and fb.get("inst") is not None) != e["instrument"]:
        why.append("fb3.inst %s, intended %s" % ("present" if fb.get("inst") is not None else "absent",
                                                 "present" if e["instrument"] else "absent"))
    for sec in ("mf2", "fx3", "fb3") + (("ut",) if e.get("layer") == "ut" else ()):
        if not isinstance(d.get(sec), dict):
            why.append("section %s missing" % sec)
    eff = fb.get("eff") or {}
    want_mode = ex.get("SEARCHER_TARGETING", 0)
    if eff.get("searcher_targeting") != want_mode:
        why.append("fb3.eff.searcher_targeting %s != %s" % (eff.get("searcher_targeting"), want_mode))
    if "VICTIM_SPAWN_MODE" in ex and eff.get("victim_spawn_mode") != ex["VICTIM_SPAWN_MODE"]:
        why.append("fb3.eff.victim_spawn_mode %s != %s" % (eff.get("victim_spawn_mode"), ex["VICTIM_SPAWN_MODE"]))
    why += bp_switch_check(fb, ex, e["instrument"])
    # review 3 MINOR-3: detections are parsed from the .stdout.txt only - it must exist and match stdout_sha
    so = path[:-len(".json")] + ".stdout.txt" if path.endswith(".json") else None
    if so is None or not os.path.exists(so):
        why.append("stdout record missing")
    else:
        import hashlib as _hl
        if d.get("stdout_sha") and _hl.sha256(open(so, "rb").read()).hexdigest()[:len(str(d["stdout_sha"]))] != str(
                d["stdout_sha"]):
            why.append("stdout record sha differs from stdout_sha")
    kinds = src_check(d.get("src_sha"))
    if not kinds:
        why.append("no src_sha")
    # the instrument's own source record (fb3.inst.src, LF-normalised): two more files the 11-file src_sha misses
    isrc = (fb.get("inst") or {}).get("src") if isinstance(fb.get("inst"), dict) else None
    if e["instrument"] and isinstance(isrc, dict):
        if "root" in isrc and not _same_path(isrc["root"], WT):
            why.append("fb3.inst.src root %s" % isrc["root"])
        for name, rel in INST_SRC.items():
            if name not in isrc:
                why.append("fb3.inst.src has no %s" % name)
            else:
                kinds.update(src_check({rel: isrc[name]}))
    bad = sorted(rel for rel, k in kinds.items() if k in ("MISMATCH", "MISSING"))
    if bad:
        why.append("src_sha differs: %s" % bad)
    return why, kinds


def bp_switch_check(fb, ex, instrumented):
    """fb3.bp_switches ({name: {raw, eff}}, written by --instrument only): the EFFECTIVE values of the round's two
    switches must be the line's (ships 1, off only on an exact 0); absent without --instrument."""
    bp = fb.get("bp_switches")
    if not instrumented:
        return [] if bp is None else ["fb3.bp_switches present in a run without --instrument"]
    if not isinstance(bp, dict):
        return ["fb3.bp_switches missing (--instrument records it)"]
    why = []
    for name in ("SEARCHER_TARGETING_FIX", "UAV_DOCKED_NOT_OBSTACLE"):
        v = bp.get(name)
        eff = v.get("eff") if isinstance(v, dict) else None
        want = not (name in ex and ex[name] == 0)
        if eff is not want:
            why.append("bp_switches %s eff %r, the line means %s" % (name, eff, want))
    return why


def inst_health(d):
    """None without fb3.inst; else the problems (version / error_count / broken) - [] = healthy."""
    ins = (d.get("fb3") or {}).get("inst")
    if ins is None:
        return None
    if not isinstance(ins, dict):
        return ["fb3.inst is a %s" % type(ins).__name__]
    bad = []
    mod = inst()
    want = getattr(mod, "VERSION", None) if mod is not None else None
    if want is not None and ins.get("version") != want:
        bad.append("version %r != %r" % (ins.get("version"), want))
    if ins.get("error_count"):
        bad.append("instrument errors %s: %s" % (ins.get("error_count"), repr((ins.get("errors") or [""])[0])[:120]))
    if ins.get("broken"):
        bad.append("recording broken")
    return bad


def v3_eval(d):
    """V3 from the run's own record (_bp_inst.self_check): a self-check shadow exists, compared every step, 0 mismatch
    steps, the launch matches, the own belief's inputs equal the instrument's and the burning order is ascending flat."""
    mod = inst()
    if mod is None:
        return {"err": "MODULE MISSING"}
    if not ((d.get("fb3") or {}).get("inst")):
        return {"err": "no fb3.inst in this run"}
    try:
        sc = mod.self_check(d)
    except Exception as exc:
        return {"err": "self_check raised %s: %s" % (type(exc).__name__, str(exc)[:160])}
    if not isinstance(sc, dict) or sc.get("shadow") is None:
        return {"err": "no self-check shadow recorded (%r)" % (sc,)}
    bad = []
    if not sc.get("compared_steps"):
        bad.append("compared_steps %r" % sc.get("compared_steps"))
    if sc.get("mismatch_steps"):
        bad.append("mismatch_steps %s first %r" % (sc.get("mismatch_steps"), repr(sc.get("first_mismatch"))[:120]))
    if sc.get("launch_match") is not True:
        bad.append("launch_match %r" % sc.get("launch_match"))
    if (sc.get("inputs") or {}).get("mismatch"):
        bad.append("inputs mismatch %s first %r" % (sc["inputs"]["mismatch"], repr(sc["inputs"].get("first"))[:120]))
    if (sc.get("order") or {}).get("mismatch"):
        bad.append("burning order mismatch on %s steps" % sc["order"]["mismatch"])
    return {"ok": not bad, "steps": sc.get("compared_steps"), "mismatches": sc.get("mismatch_steps"),
            "first": repr(sc.get("first_mismatch"))[:160], "err": "; ".join(bad) or None, "shadow": sc.get("shadow")}


# ================================================================================================ digests
def last_det(d):
    t = A.det_times(d)
    return max(t.values()) if t and all(v is not None for v in t.values()) else None


def searcher_eps(d):
    """(broad, near, anywhere) episode lists. broad = _fb3_analyze.searcher_o's own list (uid, s0, s1, len, mech,
    {mech: n}); the pocket lists apply searcher_o's exact rule to _fx3_pockets.pockets and add the mechanism; their
    counts are asserted equal to searcher_o's."""
    broad, n_near, n_any = A.searcher_o(d)
    rows = d["rows_uav"]
    lab = {}
    for t, row in enumerate(rows):
        for u in row:
            lab[(t + 1, u[0])] = str(u[8] or "")
    res = {"near": [], "any": []}
    for r, store in ((5, "near"), (500, "any")):
        for e in P.pockets(d, r=r, pre_terminal=False)[0]:
            if e["role"] != "victim_searcher":
                continue
            cells = [[u for u in rows[s - 1] if u[0] == e["uid"]][0][1:3] for s in range(e["start"], e["end"] + 1)]
            if sum(1 for i in range(1, len(cells)) if cells[i] != cells[i - 1]) * 3 >= len(cells):
                c = collections.Counter(A.mech(lab.get((s, e["uid"]))) for s in range(e["start"], e["end"] + 1))
                res[store].append((e["uid"], e["start"], e["end"], e["len"], max(c, key=c.get), dict(c)))
    if len(res["near"]) != n_near or len(res["any"]) != n_any:
        raise RuntimeError("pocket episode lists (%d, %d) disagree with searcher_o (%d, %d)" % (
            len(res["near"]), len(res["any"]), n_near, n_any))
    return list(broad), res["near"], res["any"]


def fleet_alarms(d):
    c = collections.Counter()
    hook = 0
    for row in (d.get("mf2") or {}).get("fleet") or []:
        if isinstance(row, list) and row and row[0] == "HOOK_ERR":
            hook += 1
            continue
        if isinstance(row, list) and len(row) > 3 and isinstance(row[3], dict):
            for k, v in row[3].items():
                c[str(k)] += int(v or 0)
    return c, hook


def coloc(rows):
    """UAV-steps sharing a cell, by kind: (airborne+airborne, docked+docked, airborne over docked)."""
    aa = dd = ad = 0
    for row in rows:
        cells = {}
        for u in row:
            if u[1] is None or u[2] is None:
                continue
            c = cells.setdefault((u[1], u[2]), [0, 0])
            c[1 if u[6] else 0] += 1
        for na, nd in cells.values():
            if na >= 2:
                aa += na
            if nd >= 2:
                dd += nd
            if na >= 1 and nd >= 1:
                ad += na
    return aa, dd, ad


def recall_digest(d, eps, last):
    ut = d.get("ut")
    if not isinstance(ut, dict):
        return {"has_ut": False}
    rows = d["rows_uav"]
    fb = d.get("fb3") or {}
    issued = fb.get("issued") or []

    def field(t, uid, i):
        if not 1 <= t <= len(rows):
            return None
        u = next((u for u in rows[t - 1] if u[0] == uid), None)
        return None if u is None else u[i]

    trips = []
    for uid, ts in sorted((ut.get("recall") or {}).items()):
        if not ts or ts[0].get("trigger_step") is None:
            continue
        T = int(ts[0]["trigger_step"])
        iss = sum(1 for r in issued if str(r[1]) == uid and int(r[0]) >= T)
        lab = sum(1 for t in range(T, len(rows) + 1) for u in rows[t - 1] if u[0] == uid and str(u[8]) in OWN_LABELS)
        # row i = step i + 1: the trip starts in UAV.advance of step T, so row T-1 is on the leg (or docked) and
        # row T-2 (step T - 1) is not (a recall trip starts only from rtb_active False)
        idx_ok = bool((field(T, uid, 5) or field(T, uid, 6)) and (T < 2 or field(T - 1, uid, 5) == 0))
        trips.append((uid, T, ts[0].get("arrival_step"), (T - last) if last is not None else None, iss, lab, idx_ok))
    stats = fb.get("stats") or {}
    lo = sum(int((v or {}).get("lo_continuation_steps", 0) or 0) for v in stats.values())
    post = [e for e in eps if last is not None and e[1] >= last]
    searchers = {u[0] for row in rows for u in row if u[3] == "victim_searcher"}
    return {"has_ut": True, "trips": trips, "lo": lo, "post": post, "last": last,
            "n_searchers": len(searchers), "all_found": last is not None}


def item5_digest(d):
    foot = {tuple(c) for c in ((d.get("depots") or {}).get("cells") or ())}
    near = {(x + dx, y + dy) for x, y in foot for dx in range(-2, 3) for dy in range(-2, 3)}
    mu = (d.get("mf2") or {}).get("uav") or []
    c = collections.Counter()
    for t, row in enumerate(d["rows_uav"]):
        if t >= len(mu):
            break
        docked = {(u[1], u[2]) for u in row if u[6] and u[1] is not None}
        pos = {u[0]: (u[1], u[2]) for u in row}
        for m in mu[t]:
            if len(m) < 4 or m[3] != "refused_occupied" or m[1] != "fire_tracker":
                continue
            c["all"] += 1
            p = pos.get(m[0])
            if p is None or p[0] is None:
                continue
            into = len(m) > 10 and (p[0] + MX[int(m[10]) % 4], p[1] + MY[int(m[10]) % 4]) in docked
            nr = p in near
            c["into_docked"] += into
            c["near_depot"] += nr
            c["into_docked_near"] += into and nr
    ut = d.get("ut") or {}
    degraded = sum(1 for r in ut.get("rows") or [] if len(r) > 7 and r[7] == 3) if ut else None
    dk = collections.Counter()
    legs, cells = [], collections.Counter()
    for uid, v in ((d.get("fx3") or {}).get("rtb") or {}).items():
        dk["trips"] += int(v.get("trips") or 0)
        dk["boxed"] += int(v.get("boxed") or 0)
        dk["delay_steps"] += int(v.get("delay_steps") or 0)
        for e in v.get("log") or []:
            if not isinstance(e, dict):
                continue
            dk["log_entries"] += 1
            if e.get("arrival_step") is not None and e.get("trigger_step") is not None:
                dk["arrived"] += 1
                legs.append(int(e["arrival_step"]) - int(e["trigger_step"]))
            dk["entry_boxed_steps"] += int(e.get("boxed_steps") or 0)
            dk["repicks"] += int(e.get("repicks") or 0)
            dk["release_deferred"] += int(e.get("release_deferred") or 0)
            dk["recall_trips"] += bool(e.get("recall"))
            dk["released"] += e.get("released_step") is not None
            if e.get("dock_cell") is not None:
                cells[tuple(e["dock_cell"])] += 1
    return {"ref": dict(c), "degraded": degraded, "dock": dict(dk), "legs": legs, "dock_cells": dict(cells),
            "foot_ok": foot == FOOT_SPEC}


def band_digest(d):
    H, W = (d.get("grid") or [50, 50])[:2]
    det = A.det_times(d)
    rv, ru = d["rows_vic"], d["rows_uav"]
    spawn = (d.get("fb3") or {}).get("spawn") or {}
    per = {}
    if rv:
        for v in rv[0]:
            per[v[0]] = {"det": det.get(v[0]), "und": 0, "band": 0, "cover": None}

    def edge(x, y):
        return min(x, y, H - 1 - x, W - 1 - y)

    for t, row in enumerate(rv):
        step = t + 1
        upos = [(u[1], u[2]) for u in ru[t] if u[1] is not None] if t < len(ru) else []
        for v in row:
            p = per.get(v[0])
            if p is None or v[1] is None:
                continue
            x, y = v[1], v[2]
            alive = (str(v[3] or "").lower() not in ("dead", "rescued")
                     and str(v[4] or "").lower() not in ("dead", "rescued"))
            if (p["det"] is None or step < p["det"]) and alive:
                p["und"] += 1
                p["band"] += edge(x, y) < 4
            if p["cover"] is None and any((x - a) ** 2 + (y - b) ** 2 <= 64 for a, b in upos):
                p["cover"] = step
    for vid, p in per.items():
        sp = spawn.get(vid) or (next(([v[1], v[2]] for v in rv[0] if v[0] == vid), None) if rv else None)
        p["spawn_band"] = (edge(sp[0], sp[1]) < 4) if sp and sp[0] is not None else None
        p["band_traj"] = p["und"] > 0 and 2 * p["band"] >= p["und"]
        p["eligible"] = p["det"] is None or p["det"] > 1
    return per


def issued_digest(d):
    fb = d.get("fb3") or {}
    iss = fb.get("issued") or []
    rows = d["rows_uav"]
    vals = collections.Counter()
    reach = collections.Counter()
    by = collections.defaultdict(list)
    for r in iss:
        by[str(r[1])].append(r)
    pos = {uid: [None] * len(rows) for uid in by}
    for t, row in enumerate(rows):
        for u in row:
            if u[0] in pos:
                pos[u[0]][t] = (u[1], u[2])
    for uid, lst in by.items():
        lst.sort(key=lambda r: int(r[0]))
        for i, r in enumerate(lst):
            tx, ty = int(r[2][0]), int(r[2][1])
            for v in OUTER:
                vals["x=%d" % v] += tx == v
                vals["y=%d" % v] += ty == v
            cls = ("corner" if tx in OUTER and ty in OUTER else "outer" if tx in OUTER or ty in OUTER else "interior")
            vals["n"] += 1
            vals["outer_any"] += cls != "interior"
            s = int(r[0])
            nxt = int(lst[i + 1][0]) if i + 1 < len(lst) else len(rows) + 1
            win = [p for p in pos[uid][s - 1:nxt - 1] if p is not None and p[0] is not None]
            reach[cls + "|n"] += 1
            reach[cls + "|on"] += any(p == (tx, ty) for p in win)
            reach[cls + "|m2"] += any(abs(p[0] - tx) + abs(p[1] - ty) <= 2 for p in win)
    stats = collections.Counter()
    for v in (fb.get("stats") or {}).values():
        for k, n in (v or {}).items():
            stats[k] += int(n or 0)
    return {"vals": dict(vals), "reach": dict(reach), "stats": dict(stats)}


def dw_digest(d):
    det = A.det_times(d).get(VID_DW)
    best_any = best_s = None
    present = False
    end = None
    for t, row in enumerate(d["rows_vic"]):
        v = next((v for v in row if v[0] == VID_DW), None)
        if v is None or v[1] is None:
            continue
        present = True
        end = (v[1], v[2], v[3])
        if t >= len(d["rows_uav"]):
            continue
        for u in d["rows_uav"][t]:
            if u[1] is None:
                continue
            dist = math.hypot(v[1] - u[1], v[2] - u[2])
            if best_any is None or dist < best_any[0]:
                best_any = (round(dist, 2), t + 1, u[0])
            if u[3] == "victim_searcher" and (best_s is None or dist < best_s[0]):
                best_s = (round(dist, 2), t + 1, u[0])
    ev = d.get("eval") or {}
    return {"present": present, "det": det, "any": best_any, "searcher": best_s, "end": end,
            "rescued": ev.get("rescued"), "dead": ev.get("dead")}


EXPO_CLASSES = ("S_search", "S_ret_battery", "S_ret_recall", "S_ret_unattributed", "S_docked", "T_track", "T_ret",
                "T_docked", "other")


def exposure_digest(d):
    rows = d["rows_uav"]
    mu = (d.get("mf2") or {}).get("uav") or []
    trips = collections.defaultdict(list)
    for uid, v in ((d.get("fx3") or {}).get("rtb") or {}).items():
        for e in v.get("log") or []:
            if isinstance(e, dict) and e.get("trigger_step") is not None:
                trips[uid].append((int(e["trigger_step"]),
                                   int(e["arrival_step"]) if e.get("arrival_step") is not None else None,
                                   bool(e.get("recall"))))
    for v in trips.values():
        v.sort()

    def trip_for(uid, step):
        hit = None
        for tr in trips.get(uid, ()):
            if tr[0] <= step and (tr[1] is None or step <= tr[1]):
                hit = tr
        return hit

    c = {k: collections.Counter() for k in EXPO_CLASSES}
    for t, row in enumerate(rows):
        if t >= len(mu):
            break
        m = {x[0]: x for x in mu[t]}
        for u in row:
            mm = m.get(u[0])
            if mm is None or len(mm) < 7 or not isinstance(mm[4], int):
                continue
            if u[3] == "victim_searcher":
                if u[6]:
                    k = "S_docked"
                elif u[5]:
                    tr = trip_for(u[0], t + 1)
                    k = "S_ret_unattributed" if tr is None else ("S_ret_recall" if tr[2] else "S_ret_battery")
                else:
                    k = "S_search"
            elif u[3] == "fire_tracker":
                k = "T_docked" if u[6] else ("T_ret" if u[5] else "T_track")
            else:
                k = "other"
            cc = c[k]
            cc["n"] += 1
            cc["fire"] += mm[4]
            cc["smoke"] += mm[5]
            cc["near3"] += int(mm[6]) <= 3
            cc["near6"] += int(mm[6]) <= 6
    return {k: dict(v) for k, v in c.items()}


def digest(d, tag, key, need_inst=False, need_vf=False):
    g = {"tag": tag, "key": key, "terminal": d.get("terminal_step"), "crashed": d.get("crashed"),
         "eval": {k: (d.get("eval") or {}).get(k) for k in ("rescued", "dead", "firefighter_deaths", "unreachable")},
         "det": A.det_times(d), "wall": d.get("wall_s"), "steps_done": d.get("steps_done")}
    g["last"] = last_det(d)
    g["broad"], g["near"], g["any"] = searcher_eps(d)
    g["ff"] = A.ff_episodes(d)
    g["recall"] = recall_digest(d, g["broad"] + g["near"] + g["any"], g["last"])
    al, hook = fleet_alarms(d)
    g["alarms"] = dict(al)
    ut = d.get("ut") or {}
    cov_err = sum(1 for r in (d.get("fb3") or {}).get("coverage") or [] if len(r) > 1 and r[1] == "ERR")
    g["inv"] = {"viol": sum(int(v or 0) for v in (d.get("inline_violation_counts") or {}).values()),
                "viol_kinds": dict(d.get("inline_violation_counts") or {}), "warn": int(d.get("warning_count") or 0),
                "obs_err": len(ut.get("errors") or []) + hook + cov_err, "coloc": coloc(d["rows_uav"])}
    g["item5"] = item5_digest(d)
    g["band"] = band_digest(d)
    g["issued"] = issued_digest(d)
    g["dw"] = dw_digest(d) if key == "D_W" else None
    g["expo"] = exposure_digest(d)
    fb = d.get("fb3") or {}
    g["timing"] = {k: list((v or {}).get("raw") or []) for k, v in (fb.get("timing") or {}).items()}
    ins = fb.get("inst")
    g["has_inst"] = ins is not None
    g["inst_overhead"] = ins.get("overhead") if isinstance(ins, dict) else None
    if need_inst:
        g["replay"] = inst_call("replay", d)
        g["self_check"] = v3_eval(d)
    if need_vf:
        mod = inst()
        if mod is None:
            g["vf"] = vf_none("MODULE MISSING")
        elif ins is None:
            g["vf"] = vf_none("no fb3.inst in this run")
        else:
            try:
                g["vf"] = vf_norm(mod.victim_fire(d))
            except Exception as exc:
                g["vf"] = vf_none("victim_fire raised %s: %s" % (type(exc).__name__, str(exc)[:120]))
    return g


# ================================================================================================ the build pass
DIG: dict = {}
INSTH: dict = {}            # (tag, key) -> None (no fb3.inst) | [instrument health problems]
PROVR: dict = {}            # (tag, key) -> (reasons, kinds, None)
MISSING: list = []
CRASHED: list = []          # review 3 MAJOR-2: (tag, key) of every PRESENT run that crashed, refused or not
BUILT = {"done": False}


def run_path(tag, key):
    return os.path.join(HERE, "_sd_%s_%s.json" % (real(tag), key))


def load(tag, key):
    p = run_path(tag, key)
    return R.load_one(p) if os.path.exists(p) else None


def build(sections):
    if BUILT["done"]:
        return
    BUILT["done"] = True
    need_inst = "INSTR" in sections
    need_vf = "FP" in sections
    for (tag, key), e in PROBE_E.items():
        p = run_path(tag, key)
        if not os.path.exists(p):
            MISSING.append((tag, key))
            continue
        d = R.load_one(p)
        if d.get("crashed"):
            CRASHED.append((tag, key))
        why, kinds = prov_check(d, e, p)
        INSTH[(tag, key)] = inst_health(d)
        if e["group"] == "screen":
            arm = e["arm"]
            try:
                DIG[(tag, key)] = digest(d, tag, key, need_inst=need_inst and e["instrument"],
                                         need_vf=need_vf and arm in ("bpf", "bpp"))
            except Exception as exc:          # a broken record is REFUSED and listed, never skipped silently
                why = why + ["DIGEST ERROR %s: %s" % (type(exc).__name__, str(exc)[:160])]
                if SELFTEST:
                    raise
        PROVR[(tag, key)] = (why, kinds, None)
        del d


def usable(tag, key):
    if (tag, key) not in DIG:
        return False
    return SELFTEST or not PROVR[(tag, key)][0]


def runs(tag):
    return {k: DIG[(t, k)] for (t, k) in DIG if t == tag and usable(t, k)}


def status(tag):
    """'present usable / expected' and the excluded keys."""
    ks = keys_of(tag)
    use = [k for k in ks if usable(tag, k)]
    miss = [k for k in ks if (tag, k) in MISSING]
    ref = [k for k in ks if (tag, k) in PROVR and PROVR[(tag, k)][0]]
    return len(use), len(ks), miss, ref


def inc(tag):
    """'' when every expected run of the tag is usable, else ' [usable/expected, missing ..., refused ...]'."""
    n, m, _miss, _ref = status(tag)
    return "" if n == m else " [%s]" % status_str(tag)


def status_str(tag):
    n, m, miss, ref = status(tag)
    s = "%d/%d" % (n, m)
    if miss:
        s += " missing %s" % (miss if len(miss) <= 4 else "%d cells" % len(miss))
    if ref:
        s += " refused %s%s" % (ref if len(ref) <= 4 else "%d cells" % len(ref),
                                " (SELFTEST: not applied)" if SELFTEST else "")
    return s


# ================================================================================================ sections
def sec_prov():
    head("PROV - every run: repo / head / extra_params / sd argv / pool .argv / CRN / fb3.inst / sections / eff /"
         " src_sha (raw or LF- or CRLF-normalised). Expected head %s. A mismatch REFUSES the run%s." % (
             EXPECTED_HEAD[:12], " (SELFTEST: reported, NOT applied)" if SELFTEST else ""))
    tags = []
    for (t, k) in PROBE_E:
        if t not in tags:
            tags.append(t)
    kinds_all = collections.Counter()
    n_ref = n_ok = 0
    for tag in tags:
        ks = keys_of(tag)
        present = [k for k in ks if (tag, k) in PROVR]
        refused = [(k, PROVR[(tag, k)][0]) for k in present if PROVR[(tag, k)][0]]
        miss = [k for k in ks if (tag, k) in MISSING]
        kc = collections.Counter()
        for k in present:
            for rel, kind in PROVR[(tag, k)][1].items():
                kc["%s:%s" % (os.path.basename(rel), kind)] += 1
                kinds_all[kind] += 1
        n_ref += len(refused)
        n_ok += len(present) - len(refused)
        alias = (" <- %s" % real(tag)) if real(tag) != tag else ""
        if not present and (SELFTEST or not miss):
            out("  %-8s%s expected %2d | present 0" % (tag, alias, len(ks)))
            continue
        out("  %-8s%s expected %2d | present %2d | REFUSED %2d | missing %s" % (
            tag, alias, len(ks), len(present), len(refused), (miss if len(miss) <= 6 else "%d cells" % len(miss))
            if miss else "none"))
        for k, why in refused[:3 if SELFTEST else None]:
            out("      REFUSED %s_%s: %s" % (tag, k, "; ".join(why)))
        if SELFTEST and len(refused) > 3:
            out("      ... %d more refused runs of %s (same rules)" % (len(refused) - 3, tag))
    out("  src hash match kinds over every present run's src_sha (11 files) + fb3.inst.src (2 files): %s  (raw = the"
        " worktree file as on disk; lf / crlf ="
        " equal after line-ending normalisation)" % dict(kinds_all))
    per_file = collections.Counter()
    for (t, k), (why, kinds, _n) in PROVR.items():
        for rel, kind in kinds.items():
            per_file[(rel, kind)] += 1
    for (rel, kind), n in sorted(per_file.items()):
        if kind != "raw":
            out("      %-55s %-8s %d runs" % (rel, kind, n))
    covered = set()
    for (t, k), (why, kinds, _n) in PROVR.items():
        covered |= {os.path.normpath(r) for r in kinds}
    changed = _git("diff", "--name-only", BASE, "--", "*.py")
    if changed is not None:
        ch = sorted(os.path.normpath(p) for p in changed.split() if not p.startswith(("outputs/", "tests/")))
        nc = [p for p in ch if p not in covered]
        out("  round source files changed since %s (working tree) NOT covered by src_sha (head-only provenance): %s"
            % (BASE, nc or "none"))
    dirty = _git("status", "--porcelain", "--", *SRC_ROUND, "src_extension")
    if dirty is not None:
        dl = [ln for ln in dirty.splitlines() if ln.strip()]
        out("  uncommitted source changes NOW (the head check cannot vouch for them): %s" % (
            [ln[3:] for ln in dl] if dl else "none"))
    rbs = rb_prov()
    for tag, why in rbs.items():
        out("  rb %-6s %s" % (tag, "OK" if not why else "REFUSED: " + "; ".join(why)))
    out("  TOTAL probe runs present %d: usable %d, REFUSED %d%s | missing %d of %d expected" % (
        n_ok + n_ref, n_ok, n_ref, " (not applied)" if SELFTEST else "", len(MISSING), len(PROBE_E)))
    verdict("PROV", "refused probe runs", "%d%s" % (n_ref, " (selftest)" if SELFTEST else ""))


_RBPROV: dict = {}


def rb_path(tag, wind):
    return os.path.join(HERE, "_rblatch_camp2_%s_D_%s.json" % (real(tag), wind))


def rb_prov():
    if _RBPROV:
        return _RBPROV
    for tag, e in RB_E.items():
        why = []
        p = rb_path(tag, e["wind"])
        if not os.path.exists(p):
            _RBPROV[tag] = ["MISSING %s" % os.path.basename(p)]
            continue
        try:
            sig = open(p + ".argv", encoding="utf-8").read()
            if sig != POOL.signature(e["line"]):
                why.append(".argv signature differs from the queue line (script / cwd / argv)")
        except OSError:
            why.append("no .argv")
        s = json.load(open(p, encoding="utf-8"))
        try:   # review 3 MINOR-5: the shard JSON has no head / source record - it must postdate the head commit
            import subprocess as _sp
            ct = int(_sp.run(["git", "-C", WT, "log", "-1", "--format=%ct", "HEAD"], capture_output=True,
                             text=True, timeout=30).stdout.strip())
            if os.path.getmtime(p) < ct:
                why.append("shard older than the head commit")
        except Exception as exc:
            why.append("head time check failed %r" % (exc,))
        if s.get("tag") != tag:
            why.append("tag %s" % s.get("tag"))
        if (s.get("params") or {}).get("SEARCHER_UNTUNED") != 1:
            why.append("params SEARCHER_UNTUNED %s" % (s.get("params") or {}).get("SEARCHER_UNTUNED"))
        _RBPROV[tag] = why
    return _RBPROV


def ident(da, db):
    """_fx3r_analyze.probe_ident's per-cell rule: the fx3m FIELDS + every mf2 section but probe."""
    diff = [k for k in R.FIELDS if da.get(k) != db.get(k)]
    for k in sorted(set(da.get("mf2") or {}) | set(db.get("mf2") or {})):
        if k != "probe" and (da.get("mf2") or {}).get(k) != (db.get("mf2") or {}).get(k):
            diff.append("mf2." + k)
    return diff


def _key_order(k):
    s = str(k)
    return (0, int(s), "") if s.lstrip("-").isdigit() else (1, 0, s)


def first_path(x, y, path=""):
    if x == y:
        return None
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y), key=_key_order):
            if k not in x or k not in y:
                return "%s.%s (only in %s)" % (path, k, "ours" if k in x else "the reference")
            p = first_path(x[k], y[k], "%s.%s" % (path, k))
            if p:
                return p
        return path + " (?)"
    if isinstance(x, list) and isinstance(y, list):
        for i in range(min(len(x), len(y))):
            p = first_path(x[i], y[i], "%s[%d]" % (path, i))
            if p:
                return p
        return "%s (length %d != %d)" % (path, len(x), len(y))
    return "%s: %s != %s" % (path, repr(x)[:70], repr(y)[:70])


def full_diff(a, b):
    """Every recorded field but provenance: [field, ...] in the order FIELDS, other top-level, mf2, fx3, fb3, ut."""
    secs = {s for s, _ in SEC_SKIP}
    top = [k for k in R.FIELDS] + sorted((set(a) | set(b)) - TOP_SKIP - secs - set(R.FIELDS))
    diffs = [k for k in top if a.get(k) != b.get(k)]
    for sec, skip in SEC_SKIP:
        sa, sb = a.get(sec), b.get(sec)
        if sec == "ut" and not (isinstance(sa, dict) and isinstance(sb, dict)):
            continue
        if not (isinstance(sa, dict) and isinstance(sb, dict)):
            if sa != sb:
                diffs.append("%s (present in one run only)" % sec)
            continue
        for k in sorted((set(sa) | set(sb)) - skip):
            if sa.get(k) != sb.get(k):
                diffs.append("%s.%s" % (sec, k))
    return diffs


def _field_get(d, f):
    if "." in f and f.split(".")[0] in {s for s, _ in SEC_SKIP}:
        s, k = f.split(".", 1)
        return (d.get(s) or {}).get(k)
    return d.get(f.split(" ")[0])


def compare_pair(tag, key, ref_tag, ref_key, rule):
    """(verdict, line); ours is (tag, key) through PROV, the reference a recorded run read as-is."""
    if (tag, key) in MISSING or (tag, key) not in PROVR:
        return None, "%s_%s MISSING" % (tag, key)
    if PROVR[(tag, key)][0] and not SELFTEST:
        return False, "%s_%s REFUSED by PROV - not compared (counts as a failure)" % (tag, key)
    rp = os.path.join(HERE, "_sd_%s_%s.json" % (real(ref_tag), ref_key))
    if not os.path.exists(rp):
        return None, "reference %s_%s MISSING" % (ref_tag, ref_key)
    a, b = load(tag, key), R.load_one(rp)
    diff = rule(a, b)
    if not diff:
        return True, "%s_%s == %s_%s" % (tag, key, ref_tag, ref_key)
    f = diff[0]
    fp = first_path(_field_get(a, f), _field_get(b, f), f.split(" ")[0])
    return False, "%s_%s DIFFERS from %s_%s in %d fields %s | first path %s" % (
        tag, key, ref_tag, ref_key, len(diff), diff[:8], fp)


def sec_id():
    head("ID - bpi (every new switch 0, --instrument) vs the recorded untune references: value identity on the fx3m"
         " FIELDS + every mf2 section (_fx3r_analyze.probe_ident's rule)")
    for tag, ref, n_want in (("bpir", "ut2r", 16), ("bpiu", "ut2u", 16), ("bpiu2", "ut2u2", 1)):
        same, miss, lines = 0, 0, []
        for key in keys_of(tag):
            ok, ln = compare_pair(tag, key, ref, key, ident)
            same += ok is True
            miss += ok is None
            if ok is not True:
                lines.append(ln)
        n_fail = len(keys_of(tag)) - same - miss
        v = ("PASS" if same == n_want == len(keys_of(tag)) else "FAIL - STOP" if n_fail
             else "INCOMPLETE (%d missing)" % miss)
        out("  %-6s vs %-6s %2d / %d identical  => %s" % (tag, ref, same, n_want, v))
        for ln in lines:
            out("      " + ln)
        verdict("ID", "%s vs %s" % (tag, ref), v)


def sec_instr():
    head("INSTR - V1 reproduction of recorded runs (every recorded field but provenance / timing / inst / bp_switches /"
         " probe strings), V1b fresh with vs without --instrument, V2 offline replay, V3 self-check")
    v1 = v1_missing = 0
    for e in [e for e in PROBE_E.values() if e["group"] == "v1"]:
        ok, ln = compare_pair(e["tag"], e["key"], e["ref"], e["ref_key"], full_diff)
        v1 += ok is True
        v1_missing += ok is None
        out("  V1  %-8s <- %-8s %s" % (e["tag"], e["ref"], ("IDENTICAL" if ok else ln)))
    n1 = sum(1 for e in PROBE_E.values() if e["group"] == "v1")
    if v1 == n1:
        v1v = "PASS"
    elif v1_missing:
        v1v = "INCOMPLETE (%d missing)" % v1_missing
    else:
        v1v = "FAIL"
    out("  V1 %d / %d  => %s%s" % (v1, n1, v1v, "" if v1v != "FAIL" else
                                  " - REPORTED under the item-3 risk rule: the instrument is validated against FRESH"
                                  " recordings (V1b) instead; it is never adjusted to make an old run match"))
    verdict("INSTR", "V1 reproduction %d/%d" % (v1, n1), v1v if v1v != "FAIL" else "FAIL (reported; risk rule -> V1b)")
    vb = nb = vb_missing = 0
    for e in [e for e in PROBE_E.values() if e["group"] == "v1b"]:
        nb += 1
        ok, ln = compare_pair(e["tag"], e["key"], e["ref"], e["ref_key"], full_diff)
        vb_missing += ok is None
        if ok is True and (e["ref"], e["ref_key"]) in PROVR and PROVR[(e["ref"], e["ref_key"])][0] and not SELFTEST:
            ok, ln = False, "%s: its twin %s_%s is REFUSED by PROV" % (e["tag"], e["ref"], e["ref_key"])
        vb += ok is True
        if ok is None and ln.startswith("reference"):
            ln += " (the twin is a line of the arms wave; outputs/_bp_queue.py twins runs the two alone)"
        out("  V1b %-8s vs %-8s %s" % (e["tag"], e["ref"], "IDENTICAL" if ok else ln))
    vbv = "PASS" if vb == nb else ("INCOMPLETE (%d missing)" % vb_missing if vb_missing else "FAIL - STOP")
    out("  V1b %d / %d  => %s" % (vb, nb, vbv))
    verdict("INSTR", "V1b fresh with/without %d/%d" % (vb, nb), vbv)
    # instrument health on EVERY run that should carry it (record-only in every arm, belief or not)
    n_inst = n_bad = 0
    bad_h = []
    for (tag, key), e in PROBE_E.items():
        if not e["instrument"] or (tag, key) not in INSTH or ((tag, key) in PROVR and PROVR[(tag, key)][0]
                                                             and not SELFTEST):
            continue
        h = INSTH[(tag, key)]
        n_inst += 1
        if h is None or h:
            n_bad += 1
            bad_h.append("%s_%s %s" % (tag, key, "fb3.inst ABSENT" if h is None else "; ".join(h)))
    vh = "PASS" if n_inst and not n_bad else ("FAIL" if n_bad else "MISSING (0 runs)")
    out("  instrument health (fb3.inst present, version, error_count 0, not broken) on %d usable instrumented runs:"
        " %d bad  => %s" % (n_inst, n_bad, vh))
    for b in bad_h[:12]:
        out("      " + b)
    if len(bad_h) > 12:
        out("      ... %d more" % (len(bad_h) - 12))
    verdict("INSTR", "instrument health", vh)
    if inst() is None:
        out("  V2 / V3: " + inst_missing_line() + "  => NOT EVALUATED (FAIL)")
        verdict("INSTR", "V2 replay", "NOT EVALUATED - INSTRUMENT MODULE MISSING")
        verdict("INSTR", "V3 self-check", "NOT EVALUATED - INSTRUMENT MODULE MISSING")
        return
    for name, fld, arms_ in (("V2 replay", "replay", ARMS), ("V3 self-check", "self_check", BAYES_ARMS)):
        tot = ok = 0
        bad = []
        shadows = collections.Counter()
        expected = sum(len(keys_of(tag_of(a, pl))) for a in arms_ for pl in PLACES)
        for arm in arms_:
            for place in PLACES:
                tag = tag_of(arm, place)
                for key, g in sorted(runs(tag).items()):
                    if fld == "self_check" and arm not in BAYES_ARMS:
                        continue
                    r = g.get(fld) or {"err": "not computed (INSTR section not selected at build)"}
                    tot += 1
                    good = r.get("err") is None and r.get("ok") is True and r.get("mismatches") == 0
                    if fld == "self_check" and good and r.get("shadow") != SHADOW_WANT[arm]:
                        good = False
                        r = dict(r, err="self-check shadow %r, the arm's own belief is %s" % (r.get("shadow"),
                                                                                           SHADOW_WANT[arm]))
                    ok += good
                    shadows[r.get("shadow")] += fld == "self_check"
                    if not good:
                        bad.append("%s_%s %s" % (tag, key, r.get("err") or "ok=%s steps=%s mismatches=%s first=%s%s" % (
                            r.get("ok"), r.get("steps"), r.get("mismatches"), r.get("first"),
                            (" notes %r" % r.get("notes")) if r.get("notes") else "")))
        # review 3 MAJOR-3: every expected run must be there - a missing or refused one is not a pass
        v = ("FAIL" if ok < tot else ("PASS" if tot == expected and tot else "INCOMPLETE %d/%d" % (tot, expected)))
        out("  %-14s %d / %d runs exact of %d expected (arms %s, every placement)%s  => %s" % (
            name, ok, tot, expected, " ".join(arms_),
            (" | self-check shadows %s" % dict(shadows)) if fld == "self_check" else "", v))
        for b in bad[:20]:
            out("      " + b)
        if len(bad) > 20:
            out("      ... %d more" % (len(bad) - 20))
        verdict("INSTR", name, v)


def _o_sum(gs):
    return (sum(len(g["broad"]) for g in gs), sum(len(g["near"]) for g in gs), sum(len(g["any"]) for g in gs),
            sum(len(g["ff"]) for g in gs))


def _ep_lines(tag, gs):
    lines = []
    for k, g in sorted(gs.items()):
        last = g["last"]
        for kind in ("broad", "near", "any"):
            for e in g[kind]:
                lines.append("        %s %s %-5s uid %s steps %d-%d (%d) mech %s %s | %s last detection %s" % (
                    tag, k, kind, e[0], e[1], e[2], e[3], e[4], e[5],
                    "AFTER" if last is not None and e[1] >= last else "before", last))
        for e in g["ff"]:
            lines.append("        %s %s ff    unit %s steps %d-%d (%d)" % (tag, k, e[0], e[1], e[2], e[3]))
    return lines


def sec_gates():
    head("GATES (bayesprep 7.2, D-6): per placement, every arm vs bpc on the same cells and bpc vs bpi. G-N = runs"
         " without terminal_step by 360; G-O searcher = broad / pocket near / pocket anywhere, each must not rise;"
         " FIREFIGHTER G-O must not rise (a gate this round); target 0. bpw: searcher G-O exempt (reported).")
    for place in ("r", "u"):
        out("  -- placement %s" % place)
        pairs = [("bpc", "bpi")] + [(a, "bpc") for a in ARMS if a not in ("bpi", "bpc")]
        for arm, ref in pairs:
            ta, tr = tag_of(arm, place), tag_of(ref, place)
            ga, gr = runs(ta), runs(tr)
            common = sorted(set(ga) & set(gr))
            if not common:
                out("  %-6s vs %-6s no common runs (%s | %s)" % (ta, tr, status_str(ta), status_str(tr)))
                for g in ("G-N", "G-O searcher", "G-O firefighter"):
                    verdict("GATES", "%s %s vs %s" % (g, ta, tr), "MISSING")
                continue
            A_, R_ = [ga[k] for k in common], [gr[k] for k in common]
            na = [k for k in common if not ga[k]["terminal"]]
            nr = [k for k in common if not gr[k]["terminal"]]
            ba, pa, aa, fa = _o_sum(A_)
            br, pr, ar, fr = _o_sum(R_)
            full = len(common) == 16
            inc = "" if full else " INCOMPLETE %d/16" % len(common)
            gn = ("PASS" if len(na) <= len(nr) else "FAIL") + inc
            go = ("REPORTED (exempt)" if arm == "bpw" else ("PASS" if ba <= br and pa <= pr and aa <= ar else "FAIL")
                  + inc)
            gf = ("PASS" if fa <= fr else "FAIL") + inc
            mech = collections.Counter(e[4] for g in A_ for kind in ("broad", "near", "any") for e in g[kind])
            when = collections.Counter(
                ("after" if g["last"] is not None and e[1] >= g["last"] else "before")
                for g in A_ for kind in ("broad", "near", "any") for e in g[kind])
            out("  %-6s vs %-6s [%s] N %d %s -> %d %s %s | O broad %d->%d near %d->%d any %d->%d %s | ff %d->%d %s"
                " | target 0: N %s O %s ff %s" % (
                    ta, tr, Q.LABEL[arm], len(nr), nr or "", len(na), na or "", gn, br, ba, pr, pa, ar, aa, go, fr, fa,
                    gf, "met" if not na else "not met", "met" if not (ba or pa or aa) else "not met",
                    "met" if not fa else "not met"))
            if mech:
                out("        %s searcher episodes by mechanism %s, %s" % (ta, dict(mech), dict(when)))
            for ln in _ep_lines(ta, {k: ga[k] for k in common}):
                out(ln)
            verdict("GATES", "G-N %s vs %s" % (ta, tr), gn)
            verdict("GATES", "G-O searcher %s vs %s" % (ta, tr), go)
            verdict("GATES", "G-O firefighter %s vs %s" % (ta, tr), gf)
    out("  -- the u2 cell D_W (seed 9636), reported per arm (one run; not a gate)")
    ref = runs("bpcu2").get("D_W")
    for arm in ARMS:
        g = runs(tag_of(arm, "u2")).get("D_W")
        if g is None:
            out("  %-7s D_W %s" % (tag_of(arm, "u2"), status_str(tag_of(arm, "u2"))))
            continue
        b, n, a, f = _o_sum([g])
        out("  %-7s D_W terminal %s | O broad %d near %d any %d | ff %d%s" % (
            tag_of(arm, "u2"), g["terminal"], b, n, a, f,
            "" if ref is None else " | bpcu2: terminal %s O %d/%d/%d ff %d" % ((ref["terminal"],) + _o_sum([ref]))))
        for ln in _ep_lines(tag_of(arm, "u2"), {"D_W": g}):
            out(ln)


def sec_recall():
    head("RECALL (bayesprep 1.2 pre-registered check) - every targeting arm: per searcher with a recall trip (ut.recall):"
         " issued-log entries and own-strategy exec labels (rows_uav u[8], row i = step i+1) at a step >= its trigger"
         " -> 0; lo_continuation_steps 0; trigger = last detection + 1; post-detection searcher episodes 0. bpx ="
         " the fix-off control, reported only.")
    for arm in TARGETING_ARMS:
        for place in PLACES:
            tag = tag_of(arm, place)
            gs = runs(tag)
            if not gs:
                out("  %-7s %s" % (tag, status_str(tag)))
                if place != "u2" and arm != "bpx":
                    verdict("RECALL", tag, "MISSING")
                continue
            c = collections.Counter()
            bad = []
            for k, g in sorted(gs.items()):
                rc = g["recall"]
                if not rc.get("has_ut"):
                    c["no_ut"] += 1
                    continue
                c["runs"] += 1
                c["all_found"] += rc["all_found"]
                c["searchers"] += rc["n_searchers"]
                c["lo"] += rc["lo"]
                c["post"] += len(rc["post"])
                for uid, T, arr, lag, iss, lab, idx_ok in rc["trips"]:
                    c["trips"] += 1
                    c["iss_after"] += iss
                    c["lab_after"] += lab
                    c["idx_ok"] += idx_ok
                    c["lag1"] += lag == 1
                    if iss or lab or lag != 1 or not idx_ok:
                        bad.append("%s %s uid %s trigger %d arrival %s lag %s issued>=T %d labels>=T %d index %s" % (
                            tag, k, uid, T, arr, lag, iss, lab, "ok" if idx_ok else "MISMATCH"))
                if rc["lo"]:
                    bad.append("%s %s lo_continuation_steps %d" % (tag, k, rc["lo"]))
                for e in rc["post"]:
                    bad.append("%s %s post-detection episode uid %s %d-%d (%d) %s" % (tag, k, e[0], e[1], e[2], e[3],
                                                                                     e[4]))
            ok = (c["iss_after"] == 0 and c["lab_after"] == 0 and c["lo"] == 0 and c["lag1"] == c["trips"]
                  and c["post"] == 0 and not c["no_ut"])
            full = len(gs) == len(keys_of(tag))
            v = ("PASS" if ok else "FAIL") + ("" if full else " INCOMPLETE %s" % status_str(tag))
            if arm == "bpx" or place == "u2":
                v = "REPORTED (%s)" % ("fix-off control" if arm == "bpx" else "single cell")
            out("  %-7s runs %2d (all victims found in %d) | recall trips %d (row index check ok %d) | trigger = last+1"
                " %d | issued >= T %d | own labels >= T %d | lo_continuation %d | post-detection episodes %d%s  => %s" % (
                    tag, c["runs"], c["all_found"], c["trips"], c["idx_ok"], c["lag1"], c["iss_after"], c["lab_after"],
                    c["lo"], c["post"], " | NO ut SECTION in %d runs" % c["no_ut"] if c["no_ut"] else "", v))
            for b in bad[:12]:
                out("        " + b)
            if len(bad) > 12:
                out("        ... %d more" % (len(bad) - 12))
            if not v.startswith("REPORTED"):
                verdict("RECALL", tag, v)


def sec_rb():
    head("RB - the route_blocked shards at the new defaults (bprb = utR's argv on the worktree) vs utR: rescued not"
         " lower, no new per-seed loss, 0 latched at the end")
    rbp = rb_prov()
    pooled = collections.Counter()
    complete = True
    for tag, e in RB_E.items():
        fa, fr = rb_path(tag, e["wind"]), os.path.join(HERE, "_rblatch_camp2_%s_D_%s.json" % (e["ref"], e["wind"]))
        if rbp.get(tag) and not SELFTEST:
            out("  %-6s REFUSED (%s) - not compared" % (tag, "; ".join(rbp[tag])))
            complete = False
            continue
        if not (os.path.exists(fa) and os.path.exists(fr)):
            out("  %-6s MISSING (%s / %s)" % (tag, os.path.exists(fa), os.path.exists(fr)))
            complete = False
            continue
        s, z = json.load(open(fa, encoding="utf-8")), json.load(open(fr, encoding="utf-8"))
        ez = {int(x["seed"]): x for x in (z.get("evals") or [])}
        es_ = {int(x["seed"]): x for x in (s.get("evals") or [])}
        loss = [(sd, ez[sd].get("rescued"), es_[sd].get("rescued")) for sd in sorted(set(ez) & set(es_))
                if (es_[sd].get("rescued") or 0) < (ez[sd].get("rescued") or 0)]
        gain = [(sd, ez[sd].get("rescued"), es_[sd].get("rescued")) for sd in sorted(set(ez) & set(es_))
                if (es_[sd].get("rescued") or 0) > (ez[sd].get("rescued") or 0)]
        r0 = sum(x.get("rescued") or 0 for x in ez.values())
        r1 = sum(x.get("rescued") or 0 for x in es_.values())
        out("  %-6s vs %-5s %-5s seeds %d/%d | rescued %d -> %d | dead %d -> %d | NEW losses %s gains %s | recoveries"
            " %d -> %d | latched %d" % (
                tag, e["ref"], e["wind"], len(set(ez) & set(es_)), len(ez), r0, r1,
                sum(x.get("dead") or 0 for x in ez.values()), sum(x.get("dead") or 0 for x in es_.values()),
                loss or "none", gain or "none", len(z.get("recoveries") or []), len(s.get("recoveries") or []),
                len(s.get("latched") or [])))
        pooled["r0"] += r0
        pooled["r1"] += r1
        pooled["new"] += len(loss)
        pooled["latched"] += len(s.get("latched") or [])
        complete &= set(ez) == set(es_)
    ok = pooled["r1"] >= pooled["r0"] and pooled["new"] == 0 and pooled["latched"] == 0 and complete
    v = "PASS" if ok else ("FAIL" if complete else "INCOMPLETE")
    out("  POOLED rescued %d -> %d | NEW per-seed losses %d | latched at end %d  => %s" % (
        pooled["r0"], pooled["r1"], pooled["new"], pooled["latched"], v))
    verdict("RB", "bprb vs utR", v)
    if not all(os.path.exists(rb_path(t, e["wind"])) for t, e in RB_E.items()):
        out("  -- the reused _fb3_analyze.sec_rbgate view: SKIPPED until all 4 shards exist (it skips a missing shard and"
            " still prints PASS on what remains)")
        return
    out("  -- the reused _fb3_analyze.sec_rbgate view (its reference is fx3gS; its header text is stale):")
    A.RB_TAG = real("bprba")[:-1]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        A.sec_rbgate()
    for ln in buf.getvalue().splitlines():
        out("    " + ln)


def _all_tags():
    return [tag_of(a, p) for a in ARMS for p in PLACES]


def sec_invar():
    head("INVAR - crashes, inline violations, warnings 0; co-location (UAV-steps sharing a cell, rows_uav): airborne+"
         "airborne 0, docked+docked 0, airborne over docked reported; COLLISION_RISK|global 0; observer errors reported")
    crashed = sorted("%s_%s" % tk for tk in CRASHED)
    out("  CRASHED present runs (every run on disk, refused or not): %d %s  => %s" % (
        len(crashed), crashed[:12], "PASS" if not crashed else "FAIL"))
    verdict("INVAR", "crashed (all present runs)", "PASS" if not crashed else "FAIL %d" % len(crashed))
    for tag in _all_tags():
        gs = runs(tag)
        if not gs:
            out("  %-7s %s" % (tag, status_str(tag)))
            verdict("INVAR", tag, "MISSING")
            continue
        c = collections.Counter()
        kinds = collections.Counter()
        for g in gs.values():
            c["crash"] += bool(g["crashed"])
            c["viol"] += g["inv"]["viol"]
            kinds.update(g["inv"]["viol_kinds"])
            c["warn"] += g["inv"]["warn"]
            c["obs"] += g["inv"]["obs_err"]
            aa, dd, ad = g["inv"]["coloc"]
            c["aa"] += aa
            c["dd"] += dd
            c["ad"] += ad
            c["gcoll"] += g["alarms"].get("COLLISION_RISK|global", 0)
            c["lcoll"] += g["alarms"].get("COLLISION_RISK|local", 0)
        ok = not (c["crash"] or c["viol"] or c["warn"] or c["aa"] or c["dd"] or c["gcoll"])
        v = "PASS" if ok else "FAIL"
        out("  %-7s runs %2d | crashed %d | inline violations %d %s | warnings %d | co-location airborne+airborne %d"
            " docked+docked %d airborne-over-docked %d | COLLISION_RISK global %d (local %d, reported) | observer"
            " errors %d  => %s%s" % (tag, len(gs), c["crash"], c["viol"], dict(kinds) or "", c["warn"], c["aa"],
                                     c["dd"], c["ad"], c["gcoll"], c["lcoll"], c["obs"], v, inc(tag)))
        verdict("INVAR", tag, v + ("" if not inc(tag) else " INCOMPLETE"))


def _sum_item5(gs):
    c = collections.Counter()
    legs, cells = [], collections.Counter()
    for g in gs:
        c["drift_local"] += g["alarms"].get("DRIFT_TOO_HIGH|local", 0)
        c["drift_global"] += g["alarms"].get("DRIFT_TOO_HIGH|global", 0)
        for k, v in g["item5"]["ref"].items():
            c["ref_" + k] += v
        if g["item5"]["degraded"] is not None:
            c["degraded"] += g["item5"]["degraded"]
        for k, v in g["item5"]["dock"].items():
            c["dock_" + k] += v
        legs += g["item5"]["legs"]
        cells.update({"%d,%d" % tuple(map(int, k)): v for k, v in g["item5"]["dock_cells"].items()})
        aa, dd, ad = g["inv"]["coloc"]
        c["aa"] += aa
        c["dd"] += dd
        c["ad"] += ad
        c["rescued"] += int(g["eval"].get("rescued") or 0)
        c["dead"] += int(g["eval"].get("dead") or 0)
        c["foot_bad"] += not g["item5"]["foot_ok"]
    return c, legs, cells


def sec_item5():
    head("ITEM5 - UAV_DOCKED_NOT_OBSTACLE: bpc (ON) vs bpi (OFF), same cells. Prediction (fixed in 5.3): DRIFT alarms"
         " fall toward the pre-recall level 136 / 74 / 76 / 120; no rescue direction predicted. Refusals = mf2 uav"
         " moved_class refused_occupied of fire trackers; 'into docked' = pos + delta(selected_dir) holds a UAV docked"
         " after that step; 'near depot' = the tracker within Chebyshev 2 of a footprint cell")
    tot = {"bpi": [], "bpc": []}
    for place in PLACES:
        gi, gc = runs(tag_of("bpi", place)), runs(tag_of("bpc", place))
        common = sorted(set(gi) & set(gc))
        out("  -- placement %s: %d common cells (%s | %s)" % (place, len(common), status_str(tag_of("bpi", place)),
                                                              status_str(tag_of("bpc", place))))
        if not common:
            continue
        for arm, gs in (("bpi", gi), ("bpc", gc)):
            sel = [gs[k] for k in common]
            if place != "u2":
                tot[arm] += sel
            _item5_line("%s%s" % (arm, place), sel)
    out("  -- set 1 totals (r + u)")
    for arm in ("bpi", "bpc"):
        _item5_line("%s r+u" % arm, tot[arm])


def _item5_line(name, sel):
    c, legs, cells = _sum_item5(sel)
    out("    %-9s runs %2d | DRIFT local %d global %d sum %d (the 5.3 numbers are this sum) | tracker refusals %d, into a"
        " docked cell %d, near a depot %d (both %d) | degraded_operation steps %d | rescued %d dead %d" % (
            name, len(sel), c["drift_local"], c["drift_global"], c["drift_local"] + c["drift_global"], c["ref_all"],
            c["ref_into_docked"],
            c["ref_near_depot"], c["ref_into_docked_near"], c["degraded"], c["rescued"], c["dead"]))
    out("              docking: trips %d (log %d) arrived %d leg steps median %s max %s | boxed %d (entry boxed %d) |"
        " repicks %d | release_deferred %d | released %d | recall trips %d | co-location airborne+airborne %d"
        " docked+docked %d airborne-over-docked %d%s" % (
            c["dock_trips"], c["dock_log_entries"], c["dock_arrived"], fmt(med(legs), "%g"), max(legs) if legs else
            "n/a", c["dock_boxed"], c["dock_entry_boxed_steps"], c["dock_repicks"], c["dock_release_deferred"],
            c["dock_released"], c["dock_recall_trips"], c["aa"], c["dd"], c["ad"],
            " | DEPOT FOOTPRINT != NW+SE spec in %d runs" % c["foot_bad"] if c["foot_bad"] else ""))
    out("              dock cells %s" % dict(sorted(cells.items(), key=lambda kv: -kv[1])[:12]))


def _cens(t):
    return min(t, HMAX) if t is not None else HMAX


def _det_summary(vals):
    """vals: [det or None] -> 'n, median (censored at 360), never'."""
    if not vals:
        return "n 0"
    return "n %3d median %5s never %2d" % (len(vals), fmt(med([_cens(t) for t in vals]), "%g"),
                                           sum(1 for t in vals if t is None))


def sec_band():
    head("BAND - edge-band victims (edge distance min(x, y, 49-x, 49-y) < 4 of the TRUE cell on at least half of the"
         " alive undetected steps; and by spawn cell), eligible = first detection > 1; detection = first '[Victim"
         " Detection]'; first cover = first step the true cell is in any UAV's Euclidean-8 disc (dx^2+dy^2 <= 64)")
    for place in ("r", "u"):
        out("  -- placement %s" % place)
        for arm in ("bpd", "bpf", "bpx", "bpp", "bpc"):
            tag = tag_of(arm, place)
            gs = runs(tag)
            if not gs:
                out("    %-6s %s" % (tag, status_str(tag)))
                continue
            grp = collections.defaultdict(list)
            cov = collections.defaultdict(list)
            vals, reach, stats = collections.Counter(), collections.Counter(), collections.Counter()
            for g in gs.values():
                for vid, p in g["band"].items():
                    if not p["eligible"]:
                        continue
                    grp["traj band" if p["band_traj"] else "traj non-band"].append(p["det"])
                    grp["spawn band" if p["spawn_band"] else "spawn non-band"].append(p["det"])
                    cov["band" if p["band_traj"] else "non-band"].append(p["cover"])
                vals.update(g["issued"]["vals"])
                reach.update(g["issued"]["reach"])
                stats.update(g["issued"]["stats"])
            out("    %-6s [%s] runs %d%s" % (tag, Q.LABEL[arm], len(gs), inc(tag)))
            for k in ("traj band", "traj non-band", "spawn band", "spawn non-band"):
                out("        detection %-15s %s" % (k, _det_summary(grp[k])))
            for k in ("band", "non-band"):
                out("        first cover %-9s %s" % (k, _det_summary(cov[k])))
            n = vals.get("n", 0)
            if n:
                out("        issued targets %d | outer ring (x or y in %s) %d = %.1f%% | per value %s" % (
                    n, OUTER, vals.get("outer_any", 0), 100.0 * vals.get("outer_any", 0) / n,
                    {k: v for k, v in sorted(vals.items()) if k not in ("n", "outer_any")}))
                out("        reach by target class (searcher ON the target / within Manhattan 2, before its next issue):"
                    " %s" % ", ".join("%s %d: on %.2f m2 %.2f" % (
                        cl, reach[cl + "|n"], reach[cl + "|on"] / reach[cl + "|n"], reach[cl + "|m2"] / reach[cl + "|n"])
                        for cl in ("interior", "outer", "corner") if reach.get(cl + "|n")))
            drops = {k: v for k, v in sorted(stats.items()) if k.startswith(("drop_", "giveup_", "skip_", "fallback_"))}
            if drops:
                out("        drop / give-up / skip / fallback reasons %s" % drops)
        # PAIRED bpf vs bpx
        gf, gx = runs(tag_of("bpf", place)), runs(tag_of("bpx", place))
        common = sorted(set(gf) & set(gx))
        out("    PAIRED bpf%s - bpx%s per victim (same cell, same victim id, eligible in both; censored at %d):"
            " %d common cells" % (place, place, HMAX, len(common)))
        if not common:
            continue
        pr = collections.defaultdict(list)
        for k in common:
            for vid, pf in gf[k]["band"].items():
                px = gx[k]["band"].get(vid)
                if px is None or not (pf["eligible"] and px["eligible"]):
                    continue
                dlt = _cens(pf["det"]) - _cens(px["det"])
                pr["spawn band" if px["spawn_band"] else "spawn non-band"].append(dlt)
                pr["traj band (bpx run)" if px["band_traj"] else "traj non-band (bpx run)"].append(dlt)
        for k in ("spawn band", "spawn non-band", "traj band (bpx run)", "traj non-band (bpx run)"):
            v = pr[k]
            if v:
                out("        %-24s n %3d mean %+6.1f median %+6.1f | bpf earlier %d later %d equal %d" % (
                    k, len(v), statistics.mean(v), statistics.median(v), sum(x < 0 for x in v), sum(x > 0 for x in v),
                    sum(x == 0 for x in v)))


def _dw_line(name, g):
    w = g["dw"]
    if not w or not w["present"]:
        return "  %-9s %s not in this run" % (name, VID_DW)
    return ("  %-9s %s detected %s | closest approach any UAV %s, searcher %s (dist, step, uid) | end cell %s |"
            " run rescued %s dead %s" % (name, VID_DW, ("step %d" % w["det"]) if w["det"] is not None else "NEVER",
                                         w["any"], w["searcher"], w["end"], w["rescued"], w["dead"]))


def sec_dw():
    head("DW - uniform set 2, D_W, seed 9636 (bayesprep 1.3): %s per arm; closest approach Euclidean over all steps"
         % VID_DW)
    rp = os.path.join(HERE, "_sd_ut2u2_D_W.json")
    if os.path.exists(rp):
        d = R.load_one(rp)
        out(_dw_line("ut2u2 ref", {"dw": dw_digest(d)}))
        del d
    for arm in ARMS:
        tag = tag_of(arm, "u2")
        g = runs(tag).get("D_W")
        out(_dw_line(tag, g) if g else "  %-9s %s" % (tag, status_str(tag)))


def _expo_sum(gs, classes):
    c = {k: collections.Counter() for k in classes}
    for g in gs:
        for k in classes:
            c[k].update(g["expo"].get(k) or {})
    return c


def _rate(c, k):
    return "%d/%d=%.2f%%" % (c[k], c["n"], 100.0 * c[k] / c["n"]) if c["n"] else "0/0"


def sec_fp():
    head("FP - front priority (bpp) vs Bayes-flee (bpf), same cells: searcher steps in fire / smoke / within Manhattan"
         " 3 / 6 of a burning cell (mf2 uav u[4] / u[5] / u[6]) on SEARCH steps vs RETURN legs; threatened victims"
         " (threatened in the bpf run, _bp_inst.victim_fire) and each run's nearest-fire victim; outcomes")
    for place in ("r", "u"):
        gp, gf = runs(tag_of("bpp", place)), runs(tag_of("bpf", place))
        common = sorted(set(gp) & set(gf))
        out("  -- placement %s: %d common cells (%s | %s)" % (place, len(common), status_str(tag_of("bpp", place)),
                                                              status_str(tag_of("bpf", place))))
        if not common:
            continue
        for arm, gs in (("bpp", gp), ("bpf", gf)):
            sel = [gs[k] for k in common]
            ex = _expo_sum(sel, EXPO_CLASSES)
            ret = collections.Counter()
            for k in ("S_ret_battery", "S_ret_recall", "S_ret_unattributed"):
                ret.update(ex[k])
            s = ex["S_search"]
            stats = collections.Counter()
            for g in sel:
                stats.update(g["issued"]["stats"])
            fire_eps = sum(1 for g in sel for kind in ("broad", "near", "any") for e in g[kind] if e[4] == "FIRE")
            fp = [x for g in sel for x in g["timing"].get("fp_ms", [])]
            out("    %s%s SEARCH steps %d: fire %s smoke %s within3 %s within6 %s" % (
                arm, place, s["n"], _rate(s, "fire"), _rate(s, "smoke"), _rate(s, "near3"), _rate(s, "near6")))
            out("         RETURN legs %d: fire %s smoke %s within3 %s within6 %s" % (
                ret["n"], _rate(ret, "fire"), _rate(ret, "smoke"), _rate(ret, "near3"), _rate(ret, "near6")))
            out("         rescued %d dead %d | give-ups %s | drops %s | FIRE-class episodes %d | fp_ms median %s p95 %s"
                " (n %d)" % (
                    sum(int(g["eval"].get("rescued") or 0) for g in sel), sum(int(g["eval"].get("dead") or 0)
                                                                              for g in sel),
                    {k: v for k, v in sorted(stats.items()) if k.startswith("giveup_")} or 0,
                    {k: v for k, v in sorted(stats.items()) if k.startswith("drop_")} or 0, fire_eps,
                    fmt(med(fp), "%.2f"), fmt(p95(fp), "%.2f"), len(fp)))
            vfs = [g.get("vf") or vf_none("FP not selected at build") for g in sel]
            errs = [x for v in vfs for x in v["errs"]]
            notes = collections.Counter(v["note"] for v in vfs if v["note"])
            undef = (sum(v["undef"][0] for v in vfs), sum(v["undef"][1] for v in vfs))
            q = quart(errs)
            out("         T_hat - actual delay (steps, victim-steps alive + undetected): %s | entries %d, without T_hat"
                " %d, cell never burnt in the run %d%s" % (
                    ("n %d Q1 %.1f median %.1f Q3 %.1f" % ((len(errs),) + q)) if q else "no values",
                    sum(v["n_entries"] for v in vfs), undef[0], undef[1],
                    (" | " + "; ".join("%s x%d" % (k, v) for k, v in notes.items())) if notes else ""))
        # threatened victims (by the bpf run) and the nearest-fire victim
        thr, near = [], []
        why = collections.Counter()
        for k in common:
            vf_f = gf[k].get("vf") or vf_none("FP not selected at build")
            vf_p = gp[k].get("vf") or vf_none("FP not selected at build")
            if vf_f["per"] is None:
                why[vf_f["note"]] += 1
                continue
            el = _eligible(gf[k]["det"], gp[k]["det"])
            for vid, rec in vf_f["per"].items():
                if rec.get("threatened") and vid in el:
                    thr.append(_cens(gp[k]["det"].get(vid)) - _cens(gf[k]["det"].get(vid)))
            for name, vf, g in (("bpf", vf_f, gf[k]), ("bpp", vf_p, gp[k])):
                if vf["per"] is None:
                    continue
                cand = [(rec["min_fire_dist"], vid) for vid, rec in vf["per"].items()
                        if isinstance(rec.get("min_fire_dist"), (int, float))]
                if cand:
                    vid = min(cand)[1]
                    near.append((name, k, vid, g["det"].get(vid), gp[k]["det"].get(vid), gf[k]["det"].get(vid)))
        if why:
            out("    threatened / nearest-fire: NOT EVALUATED for %s" % dict(why))
        if thr:
            out("    THREATENED (bpf run) eligible victims: bpp - bpf detection n %d mean %+.1f median %+.1f | bpp"
                " earlier %d later %d equal %d" % (len(thr), statistics.mean(thr), statistics.median(thr),
                                                   sum(x < 0 for x in thr), sum(x > 0 for x in thr),
                                                   sum(x == 0 for x in thr)))
        elif not why:
            out("    THREATENED (bpf run): none")
        for name in ("bpf", "bpp"):
            sel = [x for x in near if x[0] == name]
            dl = [_cens(x[4]) - _cens(x[5]) for x in sel]
            if dl:
                out("    NEAREST-FIRE victim of each %s run (min alive-undetected Manhattan distance to fire): bpp - bpf"
                    " detection n %d mean %+.1f median %+.1f | %s" % (
                        name, len(dl), statistics.mean(dl), statistics.median(dl),
                        " ".join("%s:%s:%s/%s" % (x[1], x[2], x[4], x[5]) for x in sel)))


def sec_expo():
    head("EXPO - the 4.6(a) table: UAV-steps in fire / on smoke (mf2 uav u[4] / u[5]) by class - searcher SEARCH"
         " (airborne, no leg), searcher RETURN legs split battery / recall (fx3.rtb trips: trigger .. arrival, the"
         " 'recall' flag), tracker TRACKING, tracker RETURN legs; docked steps excluded (counted)")
    out("    %-7s %-24s %-24s %-24s %-24s %-24s %s" % ("tag", "S search fire|smoke", "S ret battery", "S ret recall",
                                                       "T tracking", "T return", "docked S/T, unattributed"))
    for tag in _all_tags():
        gs = runs(tag)
        if not gs:
            continue
        ex = _expo_sum(gs.values(), EXPO_CLASSES)

        def cell(k):
            c = ex[k]
            if not c["n"]:
                return "n 0"
            return "%d: %d %.2f%% | %d %.2f%%" % (c["n"], c["fire"], 100.0 * c["fire"] / c["n"], c["smoke"],
                                                  100.0 * c["smoke"] / c["n"])
        out("    %-7s %-24s %-24s %-24s %-24s %-24s %d/%d, %d%s" % (
            tag, cell("S_search"), cell("S_ret_battery"), cell("S_ret_recall"), cell("T_track"), cell("T_ret"),
            ex["S_docked"]["n"], ex["T_docked"]["n"], ex["S_ret_unattributed"]["n"], inc(tag)))


def _num_leaves(x, pre=""):
    if isinstance(x, bool):
        return []
    if isinstance(x, (int, float)):
        return [(pre or "value", float(x))]
    if isinstance(x, dict):
        res = []
        for k, v in x.items():
            if k == "raw":
                continue
            res += _num_leaves(v, "%s.%s" % (pre, k) if pre else str(k))
        return res
    return []


def sec_comp():
    head("COMP - per-step ms (fb3.timing raw: belief_ms, plan_ms, fp_ms), the instrument overhead (fb3.inst.overhead),"
         " wall_s per arm x placement")
    for tag in _all_tags():
        gs = runs(tag)
        if not gs:
            continue
        parts = []
        for name in ("belief_ms", "plan_ms", "fp_ms"):
            xs = [x for g in gs.values() for x in g["timing"].get(name, [])]
            if xs:
                parts.append("%s median %.2f p95 %.2f max %.1f" % (name, med(xs), p95(xs), max(xs)))
        walls = [g["wall"] for g in gs.values() if isinstance(g["wall"], (int, float))]
        ov = collections.defaultdict(list)
        share = []
        for g in gs.values():
            for k, v in _num_leaves(g["inst_overhead"]):
                ov[k].append(v)
            o = g["inst_overhead"] if isinstance(g["inst_overhead"], dict) else {}
            if isinstance(o.get("total_ms"), (int, float)) and isinstance(g["wall"], (int, float)) and g["wall"] > 0:
                share.append(100.0 * (float(o["total_ms"]) + float(o.get("launch_ms") or 0.0)) / 1000.0 / g["wall"])
        out("  %-7s runs %2d | wall_s median %s mean %s max %s | %s | inst overhead (medians) %s%s%s%s" % (
            tag, len(gs), fmt(med(walls), "%.0f"), fmt(statistics.mean(walls) if walls else None, "%.0f"),
            fmt(max(walls) if walls else None, "%.0f"), " | ".join(parts) or "no planner timing",
            {k: round(med(v), 3) for k, v in ov.items()} or "not recorded",
            (" = %.2f%% of wall (median; max %.2f%%)" % (med(share), max(share))) if share else "",
            "" if all(g["has_inst"] for g in gs.values()) else " (fb3.inst absent in %d runs)" % sum(
                not g["has_inst"] for g in gs.values()), inc(tag)))


def _eligible(det_a, det_b):
    """_fb3_analyze.eligible_victims' rule on two det dicts: not detected at step <= 1 in EITHER run."""
    return {v for v in det_a if not ((det_a[v] is not None and det_a[v] <= 1)
                                     or (det_b.get(v) is not None and det_b[v] <= 1))}


def _e1(g, eligible=None):
    vals = [_cens(t) for v, t in g["det"].items()
            if (eligible is None and (t is None or t > 1)) or (eligible is not None and v in eligible)]
    return statistics.mean(vals) if vals else None


def sec_pilot():
    head("PILOT - E1 per run = mean over eligible victims (first detection > 1) of min(T_detect, 360); paired SD of"
         " bpp - bpc and bpf - bpc per placement (pair eligibility: not detected at step <= 1 in EITHER run,"
         " _fb3_analyze.eligible_victims' rule)")
    for place in ("r", "u"):
        out("  -- placement %s" % place)
        for arm in ARMS:
            gs = runs(tag_of(arm, place))
            if gs:
                e = {k: _e1(g) for k, g in sorted(gs.items())}
                vals = [v for v in e.values() if v is not None]
                out("    %-6s E1 mean %s | %s%s" % (tag_of(arm, place), fmt(statistics.mean(vals) if vals else None),
                                                   " ".join("%s:%.1f" % (k, v) for k, v in e.items() if v is not None),
                                                   inc(tag_of(arm, place))))
        gc = runs(tag_of("bpc", place))
        for arm in ("bpp", "bpf"):
            ga = runs(tag_of(arm, place))
            common = sorted(set(ga) & set(gc))
            diffs = []
            for k in common:
                el = _eligible(gc[k]["det"], ga[k]["det"])
                a, b = _e1(ga[k], el), _e1(gc[k], el)
                if a is not None and b is not None:
                    diffs.append(a - b)
            if len(diffs) >= 2:
                out("    PAIRED %s%s - bpc%s: n %d mean %+.2f SD %.2f (sample) median %+.2f" % (
                    arm, place, place, len(diffs), statistics.mean(diffs), statistics.stdev(diffs),
                    statistics.median(diffs)))
            else:
                out("    PAIRED %s%s - bpc%s: %d pairs (%s | %s)" % (arm, place, place, len(diffs),
                                                                  status_str(tag_of(arm, place)),
                                                                  status_str(tag_of("bpc", place))))


def sec_summary():
    head("SUMMARY - every gate verdict%s" % (" (SELFTEST: aliased runs, numbers meaningless)" if SELFTEST else ""))
    by = collections.Counter()
    for s, item, v in VERD:
        by[(s, v.split(" ")[0])] += 1
        out("  %-7s %-42s %s" % (s, item, v))
    # review 3 MAJOR-1: only an exact "PASS" (or a REPORTED line) passes - "PASS INCOMPLETE ..." does not
    fails = [x for x in VERD if not (str(x[2]) == "PASS" or str(x[2]).startswith("REPORTED")) and x[0] != "PROV"]
    out("  gates not PASS: %d of %d" % (len(fails), sum(1 for x in VERD if x[0] != "PROV")))


# ================================================================================================ selftest
def sec_selftest():
    head("SELFTEST - aliases %s" % ", ".join("%s<-%s" % (k, v) for k, v in sorted(ALIAS.items())))
    # (1) this file's identity rule == _fx3r_analyze.probe_ident on a real pair
    s_r, n_r, _ = R.probe_ident("utdf3r", "ut2r")
    same = 0
    keys = sorted(set(R.load("utdf3r")) & set(R.load("ut2r")))
    for k in keys:
        same += not ident(R.load("utdf3r")[k], R.load("ut2r")[k])
    R._CACHE.clear()
    out("  (1) ident rule utdf3r vs ut2r: this file %d/%d, R.probe_ident %d/%d  => %s" % (
        same, len(keys), s_r, n_r, "AGREE" if (same, len(keys)) == (s_r, n_r) else "DISAGREE"))
    # (2) the queue's cells == the recorded references' scenario / wind / seed
    for place, ref in (("r", "ut2r"), ("u", "ut2u"), ("u2", "ut2u2")):
        ok = n = 0
        for key in keys_of(tag_of("bpc", place)):
            e = PROBE_E[(tag_of("bpc", place), key)]
            sd = e["line"]["argv"][e["line"]["argv"].index("--") + 1:]
            rec = json.load(open(os.path.join(HERE, "_sd_%s_%s.json.argv" % (ref, key)), encoding="utf-8"))["argv"]
            rsd = rec[rec.index("--") + 1:]
            n += 1
            ok += all(sd[sd.index(f) + 1] == rsd[rsd.index(f) + 1] for f in ("--scenario", "--wind", "--seed")) and (
                [x for x in rsd if x.startswith("VICTIM_SPAWN_MODE")] == [x for x in sd if x.startswith("VICTIM_SPAWN")])
        out("  (2) bpc%s cells vs %s scenario/wind/seed/spawn: %d/%d equal" % (place, ref, ok, n))
    # (3) V1 mirrors differ from the recorded argv only by the stated additions
    for e in [e for e in PROBE_E.values() if e["group"] == "v1"]:
        a = e["line"]["argv"]
        rec = e["recorded_argv"]
        own_a, sd_a = a[1:a.index("--")], a[a.index("--") + 1:]
        own_r, sd_r = rec[1:rec.index("--")], rec[rec.index("--") + 1:]
        exp_sd = ["--repo", WT] + [(e["line"]["out"] if (i > 0 and sd_r[i - 1] == "--out") else
                                    ("%s_%s" % (e["tag"], e["key"]) if (i > 0 and sd_r[i - 1] == "--tag") else x))
                                   for i, x in enumerate(sd_r)]
        for s in e["added_sets"]:
            exp_sd += ["--set", s]
        ok = own_a == own_r + ["--instrument"] and sd_a == exp_sd and os.path.basename(a[0]) == os.path.basename(rec[0])
        out("  (3) V1 %-8s mirrors %-8s: %s | added %s | CRN %s" % (e["tag"], e["ref"], "EXACT" if ok else "WRONG",
                                                                    e["added_sets"], e["crn"]))
    # (4) LF normalisation explains the one recorded src_sha that differs raw
    d = R.load_one(os.path.join(HERE, "_sd_ut2r_A_E.json"))
    out("  (4) ut2r_A_E src_sha kinds vs this worktree: %s" % dict(collections.Counter(src_check(d["src_sha"]).values())))
    nonraw = {os.path.basename(k): v for k, v in src_check(d["src_sha"]).items() if v != "raw"}
    out("      non-raw files: %s" % nonraw)
    # (5) the recall row-index rule on ut2bf (fix off: the known 13 continuation steps must be FOUND)
    c = collections.Counter()
    for k in sorted(R.load("ut2bf")):
        g = R.load("ut2bf")[k]
        rc = recall_digest(g, [], last_det(g))
        for t in rc["trips"]:
            c["trips"] += 1
            c["idx_ok"] += t[6]
            c["lag1"] += t[3] == 1
            c["lab"] += t[5]
            c["iss"] += t[4]
        c["lo"] += rc["lo"]
    R._CACHE.clear()
    out("  (5) ut2bf recall (fix-off data): trips %d, row index ok %d, trigger = last+1 %d, own labels >= T %d,"
        " issued >= T %d, lo_continuation %d  (mapping record: 13 recalls, 13 continuation steps, 13 targeting"
        " labels) => %s" % (c["trips"], c["idx_ok"], c["lag1"], c["lab"], c["iss"], c["lo"],
                            "DETECTED" if c["lo"] == 13 and c["lab"] >= 13 and c["idx_ok"] == c["trips"] else "CHECK"))
    # (6) the D_W record: closest approach 9.22 at step 57 by searcher 2502 (bayesprep 1.3)
    d = R.load_one(os.path.join(HERE, "_sd_ut2u2_D_W.json"))
    w = dw_digest(d)
    out("  (6) ut2u2_D_W victim_3: detected %s, closest any %s, searcher %s (record: never, searcher 2502 9.22 at 57)"
        "  => %s" % (w["det"], w["any"], w["searcher"],
                     "AGREE" if w["det"] is None and w["searcher"] and w["searcher"][:3] == (9.22, 57, "2502")
                     else "CHECK"))
    # (7) item-5 refusal scan on ut2r2 (record: 309 refused tracker moves into a docked UAV's cell)
    n_into = n_all = 0
    for k in sorted(R.load("ut2r2")):
        r5 = item5_digest(R.load("ut2r2")[k])["ref"]
        n_into += r5.get("into_docked", 0)
        n_all += r5.get("all", 0)
    R._CACHE.clear()
    out("  (7) ut2r2 tracker refusals %d, into a docked cell %d (record: 309 of 403)  => %s" % (
        n_all, n_into, "AGREE" if (n_all, n_into) == (403, 309) else "CHECK"))
    # (8) the instrument paths on real instrumented records (--inst-sample; no PROV: scratch smoke runs)
    samples = []
    for path in OPTS["samples"]:
        d = R.load_one(path)
        samples.append(d)
        g = digest(d, "sample", "X", need_inst=True, need_vf=True)
        fb = d.get("fb3") or {}
        ex = dict(d.get("extra_params") or {})
        v = g.get("vf") or vf_none("?")
        q = quart(v["errs"])
        out("  (8) sample %s: steps %s, mode %s | inst health %s | bp_switches %s | V2 replay %s | V3 %s" % (
            os.path.basename(path), d.get("steps_done"), (fb.get("eff") or {}).get("searcher_targeting"),
            inst_health(d), bp_switch_check(fb, ex, "inst" in fb) or "OK",
            {k: g["replay"].get(k) for k in ("ok", "steps", "mismatches", "err", "notes", "checked")},
            {k: g["self_check"].get(k) for k in ("ok", "steps", "mismatches", "shadow", "err")}))
        out("      victim_fire: victims %s | threatened %s | min_fire_dist %s | T_hat - actual %s | entries %d,"
            " undefined %s | note %s" % (
                len(v["per"] or {}), sorted(k for k, r in (v["per"] or {}).items() if r.get("threatened")),
                {k: r.get("min_fire_dist") for k, r in (v["per"] or {}).items()},
                ("n %d Q1 %.1f median %.1f Q3 %.1f" % ((len(v["errs"]),) + q)) if q else "no values",
                v["n_entries"], v["undef"], v["note"]))
        out("      overhead %s | timing keys %s | fp_ms n %d | recall %s | expo S_search %s" % (
            g["inst_overhead"], sorted(g["timing"]), len(g["timing"].get("fp_ms", [])),
            {k: g["recall"].get(k) for k in ("has_ut", "trips", "lo")}, g["expo"]["S_search"]))
    if len(samples) >= 2:
        diff = full_diff(samples[0], samples[1])
        f = diff[0] if diff else None
        out("  (8) full_diff (the V1 / V1b rule) %s vs %s: %s%s" % (
            os.path.basename(OPTS["samples"][0]), os.path.basename(OPTS["samples"][1]),
            "IDENTICAL" if not diff else "%d fields %s" % (len(diff), diff[:8]),
            "" if not f else " | first path %s" % first_path(_field_get(samples[0], f), _field_get(samples[1], f),
                                                             f.split(" ")[0])))
        out("      (ident rule: %s)" % (ident(samples[0], samples[1]) or "IDENTICAL"))
    del samples
    out("  NOT EXERCISABLE without new screen runs: the PROV positive path (no worktree pool run exists yet), V2 / V3 /"
        " FP threatened / T_hat / COMP overhead on 360-step screen runs (only on --inst-sample records), bpg (no"
        " recorded GP+BF CRN arm), every u2 arm but bpi/bpc")


# ================================================================================================ main
SECTIONS = {"PROV": sec_prov, "ID": sec_id, "INSTR": sec_instr, "GATES": sec_gates, "RECALL": sec_recall,
            "RB": sec_rb, "INVAR": sec_invar, "ITEM5": sec_item5, "BAND": sec_band, "DW": sec_dw, "FP": sec_fp,
            "EXPO": sec_expo, "COMP": sec_comp, "PILOT": sec_pilot}


def main() -> int:
    names = [s for s in SECTION_ORDER if s in OPTS["sections"]] if OPTS["sections"] else list(SECTION_ORDER)
    out("bayesprep screen analysis | worktree %s | expected head %s | sections %s%s" % (
        REPO, EXPECTED_HEAD[:12], " ".join(names), " | SELFTEST" if SELFTEST else ""))
    if SELFTEST:
        sec_selftest()
    if any(n not in ("RB",) for n in names):
        build(names)
        if "PROV" not in names:
            n_ref = sum(1 for v in PROVR.values() if v[0])
            out("(PROV not printed: %d runs present, %d REFUSED%s, %d missing - run --section PROV for the list)" % (
                len(PROVR), n_ref, " (not applied)" if SELFTEST else "", len(MISSING)))
    for n in names:
        SECTIONS[n]()
    sec_summary()
    if OPTS["write"]:
        path = os.path.join(HERE, "_bp_analysis.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(LINES) + "\n")
        print("written %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
