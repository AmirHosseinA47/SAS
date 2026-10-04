"""bayesprep item 3: the record-only calibration instrument - shared arithmetic and the offline readers.

fix3b_part1.txt 18.4 (the one instrument), 10.5 / 18.6 (POS(t)); bayesprep_part1.txt section 3 and rulings 10.
The LIVE recorder is outputs/_fb3_probe.py --instrument: it writes d["fb3"]["inst"] and d["fb3"]["bp_switches"].
This module holds the arithmetic the live recorder and the offline replay SHARE (one owner: removed mass, one
post-move update, scalars, hashes, the flat-index encoding) and the offline readers. It is a pure library:
importing it has no side effect (stdlib + numpy). The repo's own belief / estimate modules are loaded by FILE PATH,
only inside replay() / prior_share(), from the run's recorded repo or an explicit one.

THE RECORD d["fb3"]["inst"] (version "bp_inst v1"; floats are full precision, Python float repr):
  W, H, n_brief, radius, mode (the run's SEARCHER_TARGETING, effective)
  shadows      [names]; "BF" in every arm, plus "BD", "OFF", "BF0", "BF02", "BF05" in the Bayes arms (2, 3, 5)
  shadow_cfg   {name: {mode, burnover}}  (SHADOWS below; every other motion parameter as the run's own belief)
  motion       the shared motion parameters the run saw (q, d50, s, p_go, beta, q_calm); reflect; pd; pd_smoke
  own_cfg      None or the run's own belief: {mode, burnover, bayes}  (mode 1 = measure only)
  fp_params    front_priority_params() (fields) and fp_derived (head_rate, length_to_width, eccentricity)
  wind         [ux, uy] from common_fixed_variables.wind_vector_from_direction(model.wind.wind_direction)
  src          LF-normalised sha256[:16] of the belief / estimate source files the run imported
  launch       {uav_cells [[uid, x, y]], excluded, smoke, burning (sorted flat x*W+y), own, sh}  (step 0: the
               prior + the launch measure; own / sh as in steps, bo None)
  steps        one per post-move update: {t, burn_on, burn_off, smoke_on, smoke_off (flat deltas vs the previous
               entry; the first vs launch), uav [[uid, x, y]] (the cells the belief measured), det [sorted ids,
               accumulated], own None | {alive, dead, n_unf, r_k, bo, phash}, sh {name: {alive, dead, r_k, bo,
               phash}}, vic [[vid, x, y, {belief: a_v}, T_hat]] (every victim truly alive and undetected), wind
               only when it changed}
               r_k  = sum(p * pd_grid) before the measure renormalises (the alive mass the negative update removes)
               bo   = dead after - dead before burn_over (None where the belief has no burn-over stage: mode 1)
               a_v  = p[disc(true cell)].sum() / p.sum();  T_hat = the FP arrival estimate at the true cell (inf ->
               None)
  swept        [[step, uid, target, {kind, cov, mot, bo, since, n, disc_issue, disc_now}]] at every drop_swept /
               drop_covered: the held target's DISC mass change of p accumulated per stage since issue (predict =
               mot, measure incl. renormalisation = cov, burn_over = bo); disc = the target's full disc D_t
  self_check   V3: {mode, shadow, compared_steps, mismatch_steps, first_mismatch, launch_match, inputs {compared,
               mismatch, first}, order {steps, mismatch}}; shadow = the one whose (mode, burnover) is the own
               belief's (modes 3 / 5 -> BF, 2 -> BD; MOTION 0 -> OFF; a p_bo sensitivity point -> BF0 / BF02 / BF05)
  overhead     per-step instrument ms {n, median, p95, max, total_ms, launch_ms}
  errors, error_count, broken   (an observer exception is recorded, never raised; broken = recording stopped)

LIBRARY (load with importlib.util.spec_from_file_location("_bp_inst", <outputs>/_bp_inst.py)):
  load(path) -> d
  decode(d) -> {t, burning, smoke, uav, det, own, sh, vic, wind, contiguous}; index 0 = launch, i = the i-th
      post-move update (index == step when contiguous). burning / smoke: sets of (x, y), each built in ascending
      flat order - the model's own insertion order (Fire agents are created row-major and never removed), which
      burn_over's float sum depends on. uav: [(uid, x, y)]; det: set of ids; own / sh: the recorded scalars.
  replay(d, repo=None) -> {ok, steps, mismatches, first, checked, notes}  V2: rebuild the own belief (configuration
      derived from the recorded fb3 switches / bp_switches / eff, cross-checked with own_cfg) and every shadow from
      the recorded inputs alone; compare launch + every step's alive, dead, n_unf, r_k, bo, phash and every a_v /
      T_hat by repr - EXACT, no tolerance.
  self_check(d) -> the recorded V3 result (inst["self_check"]).
  victim_fire(d, threat=3) -> {victims: {vid: {steps, dist [[t, d]], min_fire_dist, threatened, first_threat}},
      t_err: [[vid, t, T_hat, actual_delay]]}; d = Manhattan distance to the nearest burning cell (None: no fire);
      threatened = d <= threat at some alive-undetected step; actual_delay = (first step t' >= t whose burning set
      holds the cell) - t, 0 when it already burns at t (T_hat is 0 there), None if never within the run.
  pos_t(d, belief="BF") -> [[t, POS]]: POS(t) = 1 - prod_{k<=t} (1 - r_k), k = 0 the launch measure (10.5 / 18.6);
      belief "own" gives the run's own belief (None entries where it has none).
  prior_share(d, x, y, repo=None) -> u_v: the disc's share of the prior's support (r_v = a_v / u_v, 18.4 M2).
  validate(d, repo=None, do_replay=True) -> {ok, why[], ...}: instrument present, 0 errors, not broken, V3, inputs,
      order, V2.
SHARED WITH THE LIVE RECORDER: phash, flat, cell_set, pd_grid, removed_mass, motion_params, shadow_names, launch,
  advance, scalars, mass_share, SHADOWS, BAYES_MODES, OWN_MODE, MOTION_FIELDS.

CLI: python _bp_inst.py <probe.json> [...] [--repo PATH] [--no-replay]   one line per file; exit 1 if any fails.
"""
from __future__ import annotations

import bisect
import hashlib
import importlib.util
import json
import math
import os
import sys

import numpy as np

VERSION = "bp_inst v1"
BAYES_MODES = (2, 3, 5)
OWN_MODE = {2: "diffusion", 3: "flee", 5: "flee"}          # wildfire_model._fix3b_motion_params
# name -> (motion mode, burn-over). BF at the primary 0.1 in EVERY arm (POS under one model); the rest in Bayes arms.
SHADOWS = (("BF", "flee", 0.1), ("BD", "diffusion", 0.1), ("OFF", "off", 0.1),
           ("BF0", "flee", 0.0), ("BF02", "flee", 0.2), ("BF05", "flee", 0.5))
EVERY_ARM = ("BF",)
MOTION_FIELDS = (("q", "SEARCHER_BELIEF_DIFFUSION_Q", 0.1), ("d50", "SEARCHER_BELIEF_FLEE_D50", 5.0),
                 ("s", "SEARCHER_BELIEF_FLEE_S", 1.5), ("p_go", "SEARCHER_BELIEF_FLEE_P_GO", 0.8),
                 ("beta", "SEARCHER_BELIEF_FLEE_BETA", 1.5), ("q_calm", "SEARCHER_BELIEF_FLEE_Q_CALM", 0.02))
SCALAR_KEYS = ("alive", "dead", "n_unf", "r_k", "bo", "phash")


# ---- shared arithmetic (the live recorder and the replay call exactly these) -------------------------------------
def phash(p) -> str:
    return hashlib.sha256(p.tobytes()).hexdigest()[:16]


def flat(cells, width: int) -> list:
    """Sorted flat indices x * W + y of an iterable of (x, y)."""
    return sorted(int(x) * int(width) + int(y) for x, y in cells)


def cell_set(flats, width: int) -> set:
    """The set of (x, y) built by inserting in ASCENDING flat order (the model's insertion order)."""
    out: set = set()
    w = int(width)
    for f in sorted(int(v) for v in flats):
        out.add((f // w, f % w))
    return out


def pd_grid(belief, cells, smoke, pd, pd_smoke, disc_mask):
    """P_d per cell exactly as VictimSearchBelief.measure builds it."""
    cover = disc_mask(belief.height, belief.width, cells, belief.offsets)
    grid = np.where(cover, float(pd), 0.0)
    if smoke and float(pd_smoke) != float(pd):
        for x, y in smoke:
            if 0 <= x < belief.height and 0 <= y < belief.width and cover[x, y]:
                grid[x, y] = float(pd_smoke)
    return grid


def removed_mass(belief, cells, smoke, pd, pd_smoke, disc_mask) -> float:
    """r_k: the alive mass the negative update removes BEFORE renormalising = sum(p * pd_grid)."""
    return float((belief.p * pd_grid(belief, cells, smoke, pd, pd_smoke, disc_mask)).sum())


def motion_params(motion_cls, mode: str, burnover: float, reflect: bool, param):
    """MotionParams built like wildfire_model._fix3b_motion_params, with the given mode / burn-over / reflect;
    param(name, default) is agents.fix3b_param (live) or _param over the recorded switches (offline)."""
    kw = {k: param(name, default) for k, name, default in MOTION_FIELDS}
    return motion_cls(mode=mode, burnover=float(burnover), reflect=bool(reflect), **kw)


def shadow_names(mode: int) -> list:
    return [n for n, _, _ in SHADOWS if n in EVERY_ARM or int(mode) in BAYES_MODES]


def shadow_cfg(name: str) -> tuple:
    for n, m, b in SHADOWS:
        if n == name:
            return m, b
    raise KeyError(name)


def launch(belief_cls, height, width, n_brief, excluded, radius, cells, smoke, pd, pd_smoke, disc_mask):
    """The prior H0 + the launch measure, exactly as wildfire_model._init_victim_search_belief. -> (belief, r_0)."""
    b = belief_cls.with_uniform_prior(int(height), int(width), int(n_brief), excluded, radius=float(radius))
    r0 = removed_mass(b, cells, smoke, pd, pd_smoke, disc_mask)
    b.measure(cells, smoke, 0, pd=pd, pd_smoke=pd_smoke)
    return b, r0


def advance(belief, motion, burning, smoke, cells, step, pd, pd_smoke, detected, disc_mask, bayes=True):
    """One post-move update exactly as wildfire_model._update_victim_search_belief: PREDICT -> MEASURE -> BURN-OVER
    -> detections (bayes False = mode 1: measure only). -> (r_k, bo)."""
    if bayes:
        belief.predict(burning, motion)
    r_k = removed_mass(belief, cells, smoke, pd, pd_smoke, disc_mask)
    belief.measure(cells, smoke, step, pd=pd, pd_smoke=pd_smoke)
    bo = None
    if bayes:
        d0 = belief.dead
        belief.burn_over(burning, motion.burnover)
        bo = float(belief.dead) - float(d0)
    for vid in detected:
        belief.detected_ids.add(str(vid))
    belief.step = int(step)
    belief.updates += 1
    return r_k, bo


def scalars(belief, r_k, bo, own: bool = False) -> dict:
    out = {"alive": float(belief.p.sum()), "dead": float(belief.dead)}
    if own:
        out["n_unf"] = int(belief.n_unfound)
    out["r_k"] = r_k
    out["bo"] = bo
    out["phash"] = phash(belief.p)
    return out


def mass_share(belief, mask):
    """a_v = p[mask].sum() / p.sum() (None when no alive mass is left)."""
    tot = float(belief.p.sum())
    return float(belief.p[mask].sum()) / tot if tot > 0.0 else None


def src_sha(path: str) -> str | None:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()[:16]
    except OSError:
        return None


# ---- the accessor semantics, mirrored for the recorded (JSON) switch values ---------------------------------------
def _exact_integer(raw):
    """agents._exact_integer for JSON values (bool, int, float, str, None)."""
    try:
        if isinstance(raw, int):
            return int(raw)
        if isinstance(raw, float):
            return int(raw) if float.is_integer(raw) else None
        if isinstance(raw, str):
            try:
                return int(raw.strip())
            except ValueError:
                return None
        return None
    except Exception:
        return None


def _switch_on(raw) -> bool:
    """agents._fix2_switch: off only on an exact 0."""
    v = _exact_integer(raw)
    return True if v is None else v != 0


def _param(raw, default) -> float:
    """agents.fix3b_param."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return float(default)
    return value if value == value else float(default)


def own_config(d: dict) -> dict:
    """The run's own belief configuration DERIVED from the recorded fb3 switches / eff / bp_switches (not from the
    instrument's own_cfg, which replay() cross-checks against this)."""
    fb3 = d["fb3"]
    sw = fb3.get("switches") or {}
    bps = fb3.get("bp_switches") or {}
    eff = fb3.get("eff") or {}
    notes = []
    mode = eff.get("searcher_targeting")
    raw_mode = _exact_integer(sw.get("SEARCHER_TARGETING", 0))
    derived_mode = raw_mode if raw_mode in (0, 1, 2, 3, 4, 5) else 0
    if mode != derived_mode:
        notes.append("eff.searcher_targeting %r != switches-derived %r" % (mode, derived_mode))
    if "SEARCHER_TARGETING_FIX" not in bps:
        notes.append("bp_switches has no SEARCHER_TARGETING_FIX")
    reflect = _switch_on((bps.get("SEARCHER_TARGETING_FIX") or {}).get("raw", 1))
    motion_on = _switch_on(sw.get("SEARCHER_BELIEF_MOTION", 1))
    own_mode = OWN_MODE.get(derived_mode, "diffusion") if motion_on else "off"
    has_own = derived_mode in (1,) + BAYES_MODES
    if bool(eff.get("belief_built")) != has_own:
        notes.append("eff.belief_built %r != derived %r" % (eff.get("belief_built"), has_own))

    def param(name, default):
        return _param(sw.get(name, default), default)

    return {"mode": derived_mode, "own": has_own, "bayes": derived_mode in BAYES_MODES, "own_mode": own_mode,
            "burnover": param("SEARCHER_BELIEF_BURNOVER", 0.1), "reflect": reflect,
            "pd": param("SEARCHER_BELIEF_PD", 1.0), "pd_smoke": param("SEARCHER_BELIEF_PD_SMOKE", 1.0),
            "param": param, "notes": notes}


# ---- repo modules (by file path; registered under private names so dataclasses resolve) ---------------------------
_REPO_CACHE: dict = {}


def _repo_modules(repo: str) -> dict:
    key = os.path.abspath(repo)
    if key in _REPO_CACHE:
        return _REPO_CACHE[key]
    tag = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
    out = {}
    for short, rel in (("vsb", ("src_extension", "knowledge", "victim_search_belief.py")),
                       ("fae", ("src_extension", "planning", "fire_arrival_estimate.py"))):
        path = os.path.join(key, *rel)
        name = "_bp_repo_%s_%s" % (short, tag)
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        out[short] = mod
        out[short + "_sha"] = src_sha(path)
    _REPO_CACHE[key] = out
    return out


# ---- offline readers ----------------------------------------------------------------------------------------------
def load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _inst(d: dict) -> dict:
    inst = ((d or {}).get("fb3") or {}).get("inst")
    if not isinstance(inst, dict):
        raise ValueError("no fb3.inst in this record (run without --instrument?)")
    return inst


def decode(d: dict) -> dict:
    inst = _inst(d)
    W = int(inst["W"])
    la = inst["launch"]
    burn = set(int(v) for v in la["burning"])
    smk = set(int(v) for v in la["smoke"])
    wind = tuple(inst["wind"]) if inst.get("wind") is not None else None
    out = {"W": W, "H": int(inst["H"]), "t": [0], "burning": [cell_set(burn, W)], "smoke": [cell_set(smk, W)],
           "uav": [[(str(u), int(x), int(y)) for u, x, y in la["uav_cells"]]], "det": [set()],
           "own": [la.get("own")], "sh": {n: [la["sh"].get(n)] for n in inst["shadows"]}, "vic": [[]],
           "wind": [wind]}
    for e in inst["steps"]:
        burn = (burn - set(e["burn_off"])) | set(e["burn_on"])
        smk = (smk - set(e["smoke_off"])) | set(e["smoke_on"])
        if e.get("wind") is not None:
            wind = tuple(e["wind"])
        out["t"].append(int(e["t"]))
        out["burning"].append(cell_set(burn, W))
        out["smoke"].append(cell_set(smk, W))
        out["uav"].append([(str(u), int(x), int(y)) for u, x, y in e["uav"]])
        out["det"].append(set(str(v) for v in e["det"]))
        out["own"].append(e.get("own"))
        for n in inst["shadows"]:
            out["sh"][n].append((e.get("sh") or {}).get(n))
        out["vic"].append(e.get("vic") or [])
        out["wind"].append(wind)
    out["contiguous"] = out["t"] == list(range(len(out["t"])))
    return out


def self_check(d: dict) -> dict:
    return _inst(d).get("self_check")


def _same(a, b) -> bool:
    return repr(a) == repr(b)


def replay(d: dict, repo: str | None = None, check_vic: bool = True) -> dict:
    """V2: exact offline replay of the own belief and every shadow from the recorded inputs alone."""
    inst = _inst(d)
    repo = repo or d.get("repo")
    mods = _repo_modules(repo)
    vsb, fae = mods["vsb"], mods["fae"]
    VSB, MP, disc_mask = vsb.VictimSearchBelief, vsb.MotionParams, vsb.disc_mask
    dec = decode(d)
    H, W = dec["H"], dec["W"]
    cfg = own_config(d)
    notes = list(cfg["notes"])
    src = inst.get("src") or {}
    for short, fname in (("vsb", "victim_search_belief.py"), ("fae", "fire_arrival_estimate.py")):
        if src.get(fname) != mods[short + "_sha"]:
            notes.append("source %s differs from the run's (%r vs %r)" % (fname, mods[short + "_sha"], src.get(fname)))
    rec_own = inst.get("own_cfg")
    if cfg["own"]:
        derived = {"mode": cfg["own_mode"], "burnover": cfg["burnover"], "bayes": cfg["bayes"]}
        if rec_own != derived:
            notes.append("own_cfg recorded %r != derived %r" % (rec_own, derived))
    elif rec_own is not None:
        notes.append("own_cfg recorded %r but no own belief derived" % (rec_own,))
    rec_motion = inst.get("motion") or {}
    for k, name, default in MOTION_FIELDS:
        if not _same(rec_motion.get(k), cfg["param"](name, default)):
            notes.append("motion %s recorded %r != derived %r" % (k, rec_motion.get(k), cfg["param"](name, default)))
    for k in ("reflect", "pd", "pd_smoke"):
        if not _same(inst.get(k), cfg[k]):
            notes.append("%s recorded %r != derived %r" % (k, inst.get(k), cfg[k]))
    if list(inst["shadows"]) != shadow_names(cfg["mode"]):
        notes.append("shadows recorded %r != expected %r" % (inst["shadows"], shadow_names(cfg["mode"])))
    pd, pd_s, param, reflect = cfg["pd"], cfg["pd_smoke"], cfg["param"], cfg["reflect"]
    n_brief, radius = int(inst["n_brief"]), float(inst["radius"])
    excluded = {(int(f) // W, int(f) % W) for f in inst["launch"]["excluded"]}
    fpp = fae.FrontPriorityParams(**inst["fp_params"]) if inst.get("fp_params") else None

    mism: list = []
    count = {"n": 0, "scalars": 0, "vic": 0}

    def cmp(i, who, field, rec, got):
        count["scalars" if field != "vic" else "vic"] += 1
        if not _same(rec, got):
            count["n"] += 1
            if len(mism) < 50:
                mism.append({"i": i, "t": dec["t"][i], "who": who, "field": field, "rec": rec, "got": got})

    beliefs = {}
    cells0 = [(x, y) for _, x, y in dec["uav"][0]]
    if cfg["own"]:
        b, r0 = launch(VSB, H, W, n_brief, excluded, radius, cells0, dec["smoke"][0], pd, pd_s, disc_mask)
        beliefs["own"] = b
        got = scalars(b, r0, None, own=True)
        for k in SCALAR_KEYS:
            cmp(0, "own", k, (dec["own"][0] or {}).get(k, "MISSING"), got[k])
    elif any(o is not None for o in dec["own"]):
        notes.append("own scalars recorded but no own belief derived")
    for name in inst["shadows"]:
        b, r0 = launch(VSB, H, W, n_brief, excluded, radius, cells0, dec["smoke"][0], pd, pd_s, disc_mask)
        beliefs[name] = b
        got = scalars(b, r0, None)
        for k in SCALAR_KEYS[:2] + SCALAR_KEYS[3:]:
            cmp(0, name, k, (dec["sh"][name][0] or {}).get(k, "MISSING"), got[k])
    own_motion = None
    for i in range(1, len(dec["t"])):
        t = dec["t"][i]
        burning, smoke, det = dec["burning"][i], dec["smoke"][i], dec["det"][i]
        cells = [(x, y) for _, x, y in dec["uav"][i]]
        if cfg["own"]:
            own_motion = motion_params(MP, cfg["own_mode"], cfg["burnover"], reflect, param)
            r, bo = advance(beliefs["own"], own_motion, burning, smoke, cells, t, pd, pd_s, det, disc_mask,
                            bayes=cfg["bayes"])
            got = scalars(beliefs["own"], r, bo, own=True)
            for k in SCALAR_KEYS:
                cmp(i, "own", k, (dec["own"][i] or {}).get(k, "MISSING"), got[k])
        for name in inst["shadows"]:
            mode, p_bo = shadow_cfg(name)
            r, bo = advance(beliefs[name], motion_params(MP, mode, p_bo, reflect, param), burning, smoke, cells, t,
                            pd, pd_s, det, disc_mask)
            got = scalars(beliefs[name], r, bo)
            for k in SCALAR_KEYS[:2] + SCALAR_KEYS[3:]:
                cmp(i, name, k, (dec["sh"][name][i] or {}).get(k, "MISSING"), got[k])
        if check_vic and dec["vic"][i]:
            tgrid = None
            if fpp is not None:
                tgrid = fae.arrival_time(H, W, burning, dec["wind"][i], fpp)
            offsets = next(iter(beliefs.values())).offsets
            names = (["own"] if cfg["own"] else []) + list(inst["shadows"])
            for row in dec["vic"][i]:
                vid, x, y, shares, t_hat = row
                mask = disc_mask(H, W, [(int(x), int(y))], offsets)
                if sorted(shares) != sorted(names):
                    cmp(i, vid, "vic", sorted(shares), sorted(names))
                for n in names:
                    cmp(i, "%s/%s" % (vid, n), "vic", shares.get(n, "MISSING"), mass_share(beliefs[n], mask))
                if tgrid is not None:
                    v = float(tgrid[int(x), int(y)])
                    cmp(i, "%s/T_hat" % vid, "vic", t_hat, v if math.isfinite(v) else None)
    ok = count["n"] == 0 and not notes
    return {"ok": ok, "steps": len(dec["t"]) - 1, "mismatches": count["n"], "first": mism[0] if mism else None,
            "mismatch_list": mism, "checked": {"scalars": count["scalars"], "vic": count["vic"]}, "notes": notes}


def victim_fire(d: dict, threat: int = 3) -> dict:
    dec = decode(d)
    per: dict = {}
    queries = []
    for i in range(1, len(dec["t"])):
        rows = dec["vic"][i]
        if not rows:
            continue
        t = dec["t"][i]
        burn = dec["burning"][i]
        arr = np.asarray(sorted(burn), dtype=np.int64).reshape(-1, 2)
        for vid, x, y, _shares, t_hat in rows:
            x, y = int(x), int(y)
            dist = int(np.min(np.abs(arr[:, 0] - x) + np.abs(arr[:, 1] - y))) if arr.size else None
            v = per.setdefault(str(vid), {"steps": 0, "dist": [], "min_fire_dist": None, "threatened": False,
                                          "first_threat": None})
            v["steps"] += 1
            v["dist"].append([t, dist])
            if dist is not None:
                if v["min_fire_dist"] is None or dist < v["min_fire_dist"]:
                    v["min_fire_dist"] = dist
                if dist <= threat and not v["threatened"]:
                    v["threatened"], v["first_threat"] = True, t
            queries.append((str(vid), t, i, x, y, t_hat))
    burn_idx: dict = {}
    t_err = []
    for vid, t, i, x, y, t_hat in queries:
        cell = (x, y)
        if cell not in burn_idx:
            burn_idx[cell] = [j for j in range(len(dec["t"])) if cell in dec["burning"][j]]
        idx = burn_idx[cell]
        k = bisect.bisect_left(idx, i)
        delay = dec["t"][idx[k]] - t if k < len(idx) else None
        t_err.append([vid, t, t_hat, delay])
    return {"victims": per, "t_err": t_err}


def pos_t(d: dict, belief: str = "BF") -> list:
    inst = _inst(d)
    rows = [(0, inst["launch"].get("own") if belief == "own" else (inst["launch"].get("sh") or {}).get(belief))]
    for e in inst["steps"]:
        rows.append((int(e["t"]), e.get("own") if belief == "own" else (e.get("sh") or {}).get(belief)))
    out = []
    surv = 1.0
    for t, r in rows:
        if r is None or r.get("r_k") is None:
            out.append([t, None])
            continue
        surv *= (1.0 - float(r["r_k"]))
        out.append([t, 1.0 - surv])
    return out


def prior_share(d: dict, x: int, y: int, repo: str | None = None) -> float:
    inst = _inst(d)
    mods = _repo_modules(repo or d.get("repo"))
    H, W = int(inst["H"]), int(inst["W"])
    support = np.ones((H, W), dtype=bool)
    for f in inst["launch"]["excluded"]:
        support[int(f) // W, int(f) % W] = False
    mask = mods["vsb"].disc_mask(H, W, [(int(x), int(y))], mods["vsb"].disc_offsets(float(inst["radius"])))
    return float((mask & support).sum()) / float(support.sum())


def validate(d: dict, repo: str | None = None, do_replay: bool = True) -> dict:
    why = []
    try:
        inst = _inst(d)
    except ValueError as exc:
        return {"ok": False, "why": [str(exc)]}
    if inst.get("version") != VERSION:
        why.append("version %r" % inst.get("version"))
    if inst.get("error_count"):
        why.append("instrument errors %d: %s" % (inst["error_count"], (inst.get("errors") or [""])[0]))
    if inst.get("broken"):
        why.append("recording broken")
    sc = inst.get("self_check") or {}
    if sc.get("shadow") is not None:
        if sc.get("mismatch_steps") or sc.get("launch_match") is False:
            why.append("V3 %d mismatch steps, launch %r, first %r" % (sc.get("mismatch_steps") or 0,
                                                                     sc.get("launch_match"), sc.get("first_mismatch")))
    if (sc.get("inputs") or {}).get("mismatch"):
        why.append("own-belief inputs differ from the instrument's: %r" % (sc["inputs"].get("first"),))
    if (sc.get("order") or {}).get("mismatch"):
        why.append("burning-set order differs from ascending flat on %d steps" % sc["order"]["mismatch"])
    out = {"ok": False, "why": why, "v3": sc}
    if do_replay:
        rp = replay(d, repo=repo)
        out["v2"] = {k: rp[k] for k in ("ok", "steps", "mismatches", "first", "checked", "notes")}
        if not rp["ok"]:
            why.append("V2 replay: %d mismatches, notes %r, first %r" % (rp["mismatches"], rp["notes"], rp["first"]))
    out["ok"] = not why
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    repo = None
    if "--repo" in argv:
        k = argv.index("--repo")
        repo = argv[k + 1]
        del argv[k:k + 2]
    do_replay = "--no-replay" not in argv
    paths = [a for a in argv if a != "--no-replay"]
    if not paths:
        print("usage: _bp_inst.py <probe.json> [...] [--repo PATH] [--no-replay]", file=sys.stderr)
        return 2
    bad = 0
    for path in paths:
        try:
            d = load(path)
            res = validate(d, repo=repo, do_replay=do_replay)
            inst = d["fb3"]["inst"]
            sc = inst.get("self_check") or {}
            ov = inst.get("overhead") or {}
            v2 = res.get("v2") or {}
            print("%s %s mode=%s steps=%d shadows=%s V3[%s] %s/%s launch=%s inputs=%s/%s order=%s/%s V2=%s(%s mism, "
                  "%s scalars, %s vic) swept=%d inst_kb=%.0f ovh_ms med=%s p95=%s tot=%s why=%s" % (
                      "OK  " if res["ok"] else "FAIL", os.path.basename(path), inst.get("mode"), len(inst["steps"]),
                      ",".join(inst["shadows"]), sc.get("shadow"), sc.get("mismatch_steps"), sc.get("compared_steps"),
                      sc.get("launch_match"), (sc.get("inputs") or {}).get("mismatch"),
                      (sc.get("inputs") or {}).get("compared"), (sc.get("order") or {}).get("mismatch"),
                      (sc.get("order") or {}).get("steps"), v2.get("ok"), v2.get("mismatches"),
                      (v2.get("checked") or {}).get("scalars"), (v2.get("checked") or {}).get("vic"),
                      len(inst.get("swept") or []), len(json.dumps(inst, separators=(",", ":"))) / 1024.0,
                      ov.get("median"), ov.get("p95"), ov.get("total_ms"), res["why"]))
            bad += not res["ok"]
        except Exception as exc:  # a reader failure is a FAIL line, never a silent skip
            print("FAIL %s %r" % (os.path.basename(path), exc))
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
