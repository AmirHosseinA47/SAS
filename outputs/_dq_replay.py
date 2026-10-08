"""Dispatch round 2, the per-death attribution (outputs/dispatch2_part1.txt 11.2, 12.3, 13 (9); rulings section 19):
a REPLAY of one dq1 run with optional dispatch KNOCKOUTS under the OVERRIDE semantics of 11.2 (frozen). A port of
outputs/_mvg_replay.py: it runs outputs/_dq_probe.py in-process (runpy, its main()) exactly as _mvg_replay ran
_mvg_probe, with the knockout wraps installed BEFORE the probe's own install, so the probe records the knocked-out
behaviour.

usage:
  _dq_replay.py --kolog <ko.json> [--ko <json list>] -- <exactly the _dq_probe.py arguments of the run>
  _dq_replay.py compare <X.json> <R0.json>   R0 against X (r0_reproduces: every per-step row, dp.commands, dp.j_events,
                                             mv_events, eval, stdout) plus a full-record diff; exit 0 iff it reproduces
  _dq_replay.py selftest                     the pure rules on hand cases (no run, nothing written)

KNOCKOUT RULES. --ko is a JSON list of rules {"unit": U, "from": s0, "to": s1, "phase": p}: U REQUIRED - a unit id (a
non-empty string, not "*", not starting with "!", no surrounding whitespace), "*" (every unit) or "!" + a unit id (every
unit but that one); s0 / s1 JSON integers (never a bool, float or string; defaults 0 and 10**9; s0 <= s1); phase
optional, "pre" or "post" (default: both). A rule is ACTIVE at a J point (step s = evaluation_timesteps_counter, phase)
when s0 <= s <= s1 and the phase matches; K = the union of the units the active rules name ("!U" and "*" resolved
against the model's firefighter_marker_agents ids). A rule naming a unit the model does not have is an ERROR (logged,
never a silent no-op). Malformed --ko (not JSON, not a list, an unknown key, a bad unit / bound / phase, from > to) is
REFUSED (exit 2, "DQ REPLAY REFUSED" on stderr) before anything runs. KO-OWN(U, t) = [{"unit": U, "from": 0, "to": t}],
KO-OTHERS(U, t) = [{"unit": "!U", "from": 0, "to": t}], KO-LAST = [{"unit": U, "from": s, "to": s, "phase": p}].

THE OVERRIDE (11.2), at every J point where K is non-empty (and DISPATCH_JOINT is on):
  (0) J RUNS AS IN R0: the model's OWN WildFireModel._joint_dispatch_point runs, unmodified, on the run's own state;
      every unit of K stays in every candidate set (nothing is removed from J's view). Only J's APPLY calls are
      intercepted (class-level wraps of WildFireModel._dispatch_fill_bind - J's stage-2 fill and stage-4 second fill -
      and WildFireModel._dispatch_replace - J's stage-3 REPLACE / LATCH-FILL), and J's control flow is fed what R0's
      would have been: a dropped bind returns True (J's binds of free units to waiting victims pass every apply guard -
      J's view enforces them), a dropped replacement returns True and its released incumbent is, for J's step-4
      availability test only, free again iff the replacement was a REPLACE (an active incumbent; a released latched
      unit stays route_blocked - the model's own release rule). J's pure functions see no knockout effect: the ledger
      J passes to solve_fill / plan_replacements_detail AFTER a ko_today bind is the live ledger minus that bind's
      increment (an inner wrap of the joint_dispatch module functions, under the probe's _cap recorders).
  (3) THE COUNTERFACTUAL: legacy_pairs (outputs/_dq_probe.py's own function, the 11.2 rule the record's j_calls
      'legacy' holds) on J's own snapshot (WildFireModel._dispatch_view at J entry): W + W_L, victim-index order,
      Manhattan-nearest unchosen free unit, ties to the smaller id string. Its pairs with a unit of K are the KO PAIRS.
      A KO pair equal to one of J's stage-2 fill decisions (same victim, same unit) is J's own choice: it is NOT
      changed (J's bind stands; no ko_today). Every other KO pair is bound "ko_today": through the executor's fill path
      (a replica of _dispatch_fill_bind: RescueDecision assign with payload reason "ko_today" and distance = the
      Manhattan distance; on success the pending cause is popped and the binding's progress state initialised at the
      bind cell, as J's own fill does; a model dispatch event kind "ko_today" / "ko_today_refused", stage 2), in
      victim-index order, BEFORE J's first bind is applied (at J's first apply call; at J's return when J applies
      nothing - e.g. PRE false). The victims of those pairs are the KO VICTIMS.
  (1) / (2) / (3) / consequence, per J apply call, in this precedence (classify_bind / classify_replace):
      stage-2 / stage-4 bind (v, u): u in K -> drop_bind; v a KO victim -> drop_victim (u stays free until the next J
        point); u the incumbent of a dropped replacement in this frame (stage 4) -> drop_unreleased; else applied.
      stage-3 replacement (v, new, [old]): new in K -> drop_challenger (2); an old unit in K -> drop_release (1); v a
        KO victim -> drop_victim; else applied.
  (4) every other J decision is applied unchanged (the model's own call).
  An EMPTY knockout (nothing changes at any J point of its range) therefore reproduces R0 exactly; the W3 generator
  (outputs/_dq_w3_queue.py) decides emptiness from the dq1 record with jpoint_changes() below - the same precedence.

THE KNOCKOUT LOG (--kolog, written whatever the run's return code; LF JSON): version, replay_sha / probe_sha (sha256
of the LF-normalised bytes of this file and of outputs/_dq_probe.py, read when the replay starts), argv, ko_rules,
ko_log = every changed decision in application order: [step, phase, unit, victim, kind, j_did, applied] (kind one of
KINDS; j_did = J's decision [fill | second_fill | replace | latch_fill, victim, unit, [old units]] or None for a
ko_today; applied = None for a drop, ["ko_today", victim, unit, manhattan, ok, message] for a ko_today), ko_applied =
the sorted change KEYS [step, phase, unit, victim, kind] (change_order), jpoints = every J point where K was non-empty:
[step, phase, K, legacy, ko_pairs, same, n_changes], joint_on_seen, errors. The KO-EVIDENCE check (11.2): the first
changed J decision the W3 generator predicts from the dq1 record (first_change) must be in ko_applied.

R0 = the run line with no --ko through this tool; it must reproduce the record (r0_reproduces). The probe record is
written to the run line's --out exactly as _dq_probe.py writes it.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = "dq_replay v1"
PROBE_FILE = "_dq_probe.py"
PHASES = ("pre", "post")
PHASE_RANK = {"pre": 0, "post": 1}
KINDS = ("drop_bind", "drop_release", "drop_challenger", "drop_victim", "drop_unreleased", "ko_today")
KIND_RANK = {k: i for i, k in enumerate(KINDS)}
RULE_KEYS = ("unit", "from", "to", "phase")
TO_MAX = 10 ** 9
ROW_KINDS = ("rows_ff", "rows_vic", "rows_uav", "rows_dec", "rows_trig")
_TRAILING_INT = re.compile(r"(\d+)$")


# ============================================================================================== pure helpers
def lf_sha256(path):
    """sha256 of a file's LF-normalised bytes (CRLF read as LF; the probes' rule)."""
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()


def id_index(identifier):
    """The integer tie-break key (joint_dispatch.id_index's rule): trailing integer, then the id."""
    text = str(identifier)
    match = _TRAILING_INT.search(text)
    return (int(match.group(1)) if match else 10 ** 9, text)


def _unit_id_ok(uid):
    """A unit id as a rule may name it: a non-empty string, not "*", not starting with "!", no surrounding
    whitespace."""
    return isinstance(uid, str) and bool(uid) and uid == uid.strip() and uid != "*" and not uid.startswith("!")


def parse_rules(text):
    """The --ko rules, validated STRICTLY (no cast, no coercion - the bare int() cast defect class): a JSON list of
    dicts with only the keys unit / from / to / phase; unit REQUIRED (a unit id, "*" or "!" + a unit id); from / to,
    when present, JSON integers (type int, never bool, float or string) with from <= to; phase, when present, "pre" or
    "post". Raises ValueError on anything else (a JSON syntax error is a ValueError too)."""
    rules = json.loads(text)
    if not isinstance(rules, list):
        raise ValueError("--ko must be a JSON list")
    for r in rules:
        if not isinstance(r, dict) or set(r) - set(RULE_KEYS):
            raise ValueError("bad rule %r (keys %s only)" % (r, "/".join(RULE_KEYS)))
        if "unit" not in r:
            raise ValueError("rule %r has no unit" % (r,))
        unit = r["unit"]
        if not (unit == "*" or _unit_id_ok(unit)
                or (isinstance(unit, str) and unit.startswith("!") and _unit_id_ok(unit[1:]))):
            raise ValueError("bad unit in %r (a unit id, \"*\" or \"!\" + a unit id)" % (r,))
        for key in ("from", "to"):
            if key in r and type(r[key]) is not int:
                raise ValueError("bad %s in %r (a JSON integer: not a bool, float, string or null)" % (key, r))
        if r.get("from", 0) > r.get("to", TO_MAX):
            raise ValueError("from > to in %r" % (r,))
        if "phase" in r and r["phase"] not in PHASES:
            raise ValueError("bad phase in %r (pre or post)" % (r,))
    return rules


def rule_active(rule, step, phase):
    """True iff `rule` acts at the J point (step, phase). `rule` is parse_rules-validated."""
    return (rule.get("from", 0) <= step <= rule.get("to", TO_MAX)
            and ("phase" not in rule or rule["phase"] == phase))


def rule_units(rule, all_units):
    """The unit ids a rule names, resolved against `all_units`."""
    u = rule["unit"]
    if u == "*":
        return set(all_units)
    if u.startswith("!"):
        return set(all_units) - {u[1:]}
    return {u}


def active_units(rules, step, phase, all_units):
    """K at the J point (step, phase): the union of the units the active rules name."""
    out = set()
    for r in rules:
        if rule_active(r, step, phase):
            out |= rule_units(r, all_units)
    return out


def rule_named_units(rules):
    """The unit ids the rules name explicitly (U of "U" and of "!U")."""
    return sorted({r["unit"].lstrip("!") for r in rules if r["unit"] != "*"}, key=id_index)


def change_order(key):
    """The canonical order of change keys [step, phase, unit, victim, kind]."""
    return (int(key[0]), PHASE_RANK.get(key[1], 9), id_index(key[2]), id_index(key[3]), KIND_RANK.get(key[4], 99))


def first_change(keys):
    """The first change key (change_order), or None."""
    keys = [list(k[:5]) for k in keys]
    return min(keys, key=change_order) if keys else None


def ko_today_split(legacy, K, s2_pairs):
    """The counterfactual's pairs with a unit of K (legacy order), split: (today [(victim, unit)] - bound ko_today,
    same {(victim, unit)} - equal to one of J's stage-2 fill decisions, J's choice, unchanged)."""
    s2 = {(str(v), str(u)) for v, u in s2_pairs}
    ko = [(str(v), str(u)) for v, u in legacy if str(u) in K]
    same = {p for p in ko if p in s2}
    return [p for p in ko if p not in same], same


def classify_bind(stage, vid, uid, K, same, ko_victims, unreleased):
    """The override of one J bind (stage 2 fill / stage 4 second fill) of `uid` on `vid`: a KINDS value or None
    (applied unchanged). Precedence: J's own choice equal to the counterfactual's (stage 2) -> None; uid in K ->
    drop_bind (1); vid a KO victim -> drop_victim (3); uid the incumbent of a dropped replacement -> drop_unreleased."""
    if int(stage) == 2 and (vid, uid) in same:
        return None
    if uid in K:
        return "drop_bind"
    if vid in ko_victims:
        return "drop_victim"
    if uid in unreleased:
        return "drop_unreleased"
    return None


def classify_replace(vid, new, olds, K, ko_victims):
    """The override of one J replacement (stage 3: REPLACE / LATCH-FILL) of `olds` by `new` on `vid`: (kind, unit) or
    (None, None). Precedence: new in K -> drop_challenger (2); an old unit in K -> drop_release (1, the first such old
    unit); vid a KO victim -> drop_victim (3)."""
    if new in K:
        return "drop_challenger", new
    for o in olds:
        if o in K:
            return "drop_release", o
    if vid in ko_victims:
        return "drop_victim", new
    return None, None


def jpoint_changes(step, phase, legacy, s2, s3, s4, K):
    """THE OVERRIDE of one J point on its RECORDED decisions (the W3 generator's emptiness rule and the KO-evidence
    prediction): legacy [[victim, unit]] (the record's j_calls legacy), s2 / s4 [[victim, unit, ok]] (J's stage-2 / 4
    bind attempts, refused ones included), s3 [[kind, victim, new, [olds], ok]] (J's stage-3 replacements, aborted ones
    included), K a set of unit ids. Returns the change keys [step, phase, unit, victim, kind] in change_order. The
    replay applies the same precedence at run time (classify_bind / classify_replace); ko_today keys come from the
    counterfactual (ko_today_split)."""
    K = {str(u) for u in K}
    today, same = ko_today_split(legacy, K, [(r[0], r[1]) for r in s2])
    ko_victims = {v for v, _u in today}
    out = []
    for r in s2:
        kind = classify_bind(2, str(r[0]), str(r[1]), K, same, ko_victims, ())
        if kind:
            out.append([step, phase, str(r[1]), str(r[0]), kind])
    unreleased = set()
    for r in s3:
        kind, who = classify_replace(str(r[1]), str(r[2]), [str(o) for o in r[3]], K, ko_victims)
        if kind:
            out.append([step, phase, who, str(r[1]), kind])
            unreleased |= {str(o) for o in r[3]}
    for r in s4:
        kind = classify_bind(4, str(r[0]), str(r[1]), K, same, ko_victims, unreleased)
        if kind:
            out.append([step, phase, str(r[1]), str(r[0]), kind])
    for v, u in today:
        out.append([step, phase, u, v, "ko_today"])
    return sorted(out, key=change_order)


# ============================================================================================== R0 reproduction
def stdout_path(path):
    return path[:-5] + ".stdout.txt" if path.endswith(".json") else path + ".stdout.txt"


def r0_reproduces(x, r0, x_stdout, r0_stdout):
    """11.2: R0 must reproduce X's record EXACTLY - every per-step row (rows_ff / vic / uav / dec / trig), the commands,
    the J events, the movement events, eval and stdout. Returns the differing fields ([] = reproduces)."""
    diff = [k for k in ROW_KINDS if k not in x or x.get(k) != r0.get(k)]
    for sec, key in (("dp", "commands"), ("dp", "j_events")):
        a, b = (x.get(sec) or {}), (r0.get(sec) or {})
        if key not in a or a.get(key) != b.get(key):
            diff.append("%s.%s" % (sec, key))
    if "mv_events" not in x or x.get("mv_events") != r0.get("mv_events"):
        diff.append("mv_events")
    if "eval" not in x or x.get("eval") != r0.get("eval"):
        diff.append("eval")
    if x_stdout is None or x_stdout != r0_stdout:
        diff.append("stdout")
    return diff


def json_diff(a, b, path="", out=None, limit=400):
    """Every JSON path where a and b differ (dict keys, list lengths and leaves), at most `limit`."""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in list(a) + [k for k in b if k not in a]:
            if k not in a or k not in b:
                out.append("%s.%s (only in %s)" % (path, k, "R0" if k not in a else "X"))
            else:
                json_diff(a[k], b[k], "%s.%s" % (path, k), out, limit)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append("%s (len %d != %d)" % (path, len(a), len(b)))
        for i, (p, q) in enumerate(zip(a, b)):
            json_diff(p, q, "%s[%d]" % (path, i), out, limit)
    elif a != b or type(a) is not type(b):
        out.append(path)
    return out


# the fields that differ between two runs of one line by wall-clock or by the run's own name/path (never a decision)
VOLATILE = re.compile(
    r"^\.(tag|wall_s|argv(\[\d+\])?)$"
    r"|\.timing(\.|\[|$)|\.j_timing(\[|$)|^\.dp\.j_calls\[\d+\]\[2\]$"
    r"|^\.mv\.rows\[\d+\]\[(%s)\]$"
    r"|^\.mvg\.guard\.rows\[\d+\]\[(%s)\]$"
    r"|^\.ud\.kicks\[\d+\]\[(%s)\]$")


def classify_diff(paths, mv_cols=None, guard_cols=None, kick_cols=None):
    """Split json_diff paths into (volatile, other): volatile = wall-clock / ms fields and the run's tag and argv."""
    def idx(cols, names):
        return "|".join(str(cols.index(n)) for n in names if cols and n in cols) or "-1"
    rx = re.compile(VOLATILE.pattern % (idx(mv_cols, ("fix_ms", "inst_ms")), idx(guard_cols, ("ms_guard", "ms_inst")),
                                        idx(kick_cols, ("ms", "inst_ms", "ms_model"))))
    vol, other = [], []
    for p in paths:
        base = p.split(" (")[0]
        (vol if rx.search(base) else other).append(p)
    return vol, other


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def compare(x_path, r_path):
    """`compare` sub-command: r0_reproduces + the full-record diff split into volatile and other paths."""
    x, r = load_json(x_path), load_json(r_path)
    rep = r0_reproduces(x, r, read_text(stdout_path(x_path)), read_text(stdout_path(r_path)))
    paths = json_diff(x, r, limit=5000)
    mv_cols = (x.get("mv") or {}).get("cols")
    gcols = ((x.get("mvg") or {}).get("guard") or {}).get("cols")
    vol, other = classify_diff(paths, mv_cols, gcols, None)
    print("r0_reproduces (rows_ff/vic/uav/dec/trig, dp.commands, dp.j_events, mv_events, eval, stdout): %s" % (
        "REPRODUCES" if not rep else "DIFFERS %s" % rep))
    print("full-record diff: %d paths differ, %d volatile (wall-clock / ms / tag / argv), %d other" % (
        len(paths), len(vol), len(other)))
    for p in vol[:12]:
        print("  volatile " + p)
    for p in other[:60]:
        print("  OTHER    " + p)
    return 0 if not rep else 1


# ============================================================================================== the knockout wraps
def install_ko(ag, wf, rules, kolog, legacy_fn):
    """The knockout wraps (class level on WildFireModel, and on the joint_dispatch module object wildfire_model calls
    through, wf._jd) - call BEFORE the probe's install. `rules` is parse_rules-validated, `kolog` the knockout log dict,
    legacy_fn the probe's legacy_pairs(view). Every wrap is a pass-through outside an open knockout J point."""
    WM = wf.WildFireModel
    jd = getattr(wf, "_jd", None)
    joint_on = getattr(ag, "dispatch_joint", None) or (lambda: False)
    stack = []
    state = {"checked": False}
    o_jpoint = getattr(WM, "_joint_dispatch_point", None)
    o_fill = getattr(WM, "_dispatch_fill_bind", None)
    o_replace = getattr(WM, "_dispatch_replace", None)
    o_avail = getattr(WM, "_firefighter_available_for_dispatch", None)
    if None in (o_jpoint, o_fill, o_replace, o_avail, jd):
        if rules:
            kolog["errors"].append("install: this checkout has no corrected J point (_joint_dispatch_point, "
                                   "_dispatch_fill_bind, _dispatch_replace or wildfire_model._jd missing)")
        return
    o_solve, o_plan = jd.solve_fill, jd.plan_replacements_detail

    def step_of(m):
        return int(getattr(m, "evaluation_timesteps_counter", 0) or 0)

    def ctx_of(model):
        return stack[-1] if stack and stack[-1]["model"] is model else None

    def log(ctx, unit, victim, kind, j_did, applied):
        kolog["ko_log"].append([ctx["step"], ctx["phase"], str(unit), str(victim), kind, j_did, applied])
        ctx["n"] += 1

    def ko_fill_bind(model, ctx, vid, uid):
        """A ko_today bind: _dispatch_fill_bind's path (the executor's pairing apply) with reason "ko_today" and the
        Manhattan distance; the bookkeeping of J's own fill on success; a model dispatch event."""
        view = ctx["view"]
        info = view["victims"][vid]
        unit = view["units"][uid]
        cell = info["cell"]
        dist = abs(int(unit.pos[0]) - int(cell[0])) + abs(int(unit.pos[1]) - int(cell[1]))
        decision = wf.RescueDecision(
            decision_id=f"ko-today-assign-{vid}-{uid}-{ctx['step']}",
            selected_option_id="ko_today",
            rescue_action="assign",
            victim_id=vid,
            firefighter_id=uid,
            route_choice="",
            payload={"reason": "ko_today", "distance": int(dist)},
            confidence_score=1.0,
            uncertainty_context={"ko_today": True},
            comparison_summary={"summary": f"Knockout: today's choice {uid} -> {vid}"},
            explanation=f"Knockout: today's choice (manhattan={int(dist)})",
        )
        ledger = model._dispatch_state("_dispatch_ledger", dict)
        before = int(ledger.get((uid, vid), 0) or 0)
        result = model._physical_rescue_executor().apply_physical_pairing_decision(
            model, decision, victim_marker=info["marker"])
        ok = bool(result.get("success"))
        grown = int(ledger.get((uid, vid), 0) or 0) - before
        if grown:
            ctx["ledger_minus"][(uid, vid)] = ctx["ledger_minus"].get((uid, vid), 0) + grown
        if ok:
            model._dispatch_state("_dispatch_pending_cause", dict).pop(vid, None)
            model._dispatch_state("_dispatch_progress", dict)[(uid, vid)] = wf._jd.new_progress(
                (int(unit.pos[0]), int(unit.pos[1])))
        msg = str(result.get("message", "") or "")
        model._dispatch_record(phase=ctx["phase"], kind="ko_today" if ok else "ko_today_refused", stage=2,
                               victim_id=vid, unit=uid, old_units=[], reason="ko_today", distance=int(dist),
                               message=msg)
        return ok, msg, int(dist)

    def apply_today(model, ctx):
        """(3): the counterfactual's binds of K's units, once per J point, BEFORE J's first bind is applied."""
        if ctx["today_done"]:
            return
        ctx["today_done"] = True
        today, same = ko_today_split(ctx["legacy"], ctx["K"], ctx["s2"] or [])
        ctx["same"] = same
        ctx["ko_victims"] = {v for v, _u in today}
        for vid, uid in today:
            ok, msg, dist = ko_fill_bind(model, ctx, vid, uid)
            log(ctx, uid, vid, "ko_today", None, ["ko_today", vid, uid, dist, ok, msg])

    def shield(ctx, ledger):
        """The ledger J's pure functions see after a ko_today bind: the live ledger minus the ko_today increments of
        this J point (J runs as in R0)."""
        if ctx is None or not ctx["ledger_minus"]:
            return ledger
        out = dict(ledger)
        for key, n in ctx["ledger_minus"].items():
            left = int(out.get(key, 0) or 0) - n
            if left > 0:
                out[key] = left
            else:
                out.pop(key, None)
        return out

    def _with_ledger(args, kwargs, ctx):
        if "ledger" in kwargs:
            kwargs = dict(kwargs, ledger=shield(ctx, kwargs["ledger"]))
        elif len(args) > 3:
            args = tuple(args[:3]) + (shield(ctx, args[3]),) + tuple(args[4:])
        return args, kwargs

    def solve_fill(*args, **kwargs):
        ctx = stack[-1] if stack else None
        if ctx is None:
            return o_solve(*args, **kwargs)
        args, kwargs = _with_ledger(args, kwargs, ctx)
        out = o_solve(*args, **kwargs)
        if not ctx["plan_seen"] and ctx["s2"] is None and not ctx["today_done"]:
            ctx["s2"] = [(str(p.victim), str(p.unit)) for p in out]
        return out

    def plan_replacements_detail(*args, **kwargs):
        ctx = stack[-1] if stack else None
        if ctx is None:
            return o_plan(*args, **kwargs)
        ctx["plan_seen"] = True
        args, kwargs = _with_ledger(args, kwargs, ctx)
        return o_plan(*args, **kwargs)

    jd.solve_fill = solve_fill
    jd.plan_replacements_detail = plan_replacements_detail

    def fill_bind(self, view, vid, uid, distance, phase, *, kind, stage):
        ctx = ctx_of(self)
        if ctx is None:
            return o_fill(self, view, vid, uid, distance, phase, kind=kind, stage=stage)
        apply_today(self, ctx)
        v, u = str(vid), str(uid)
        what = classify_bind(stage, v, u, ctx["K"], ctx["same"], ctx["ko_victims"], ctx["unreleased"])
        if what is None:
            return o_fill(self, view, vid, uid, distance, phase, kind=kind, stage=stage)
        log(ctx, u, v, what, [str(kind), v, u, []], None)
        return True                                   # R0's control flow: the bind applies (see (0))

    def replace(self, view, vid, old_units, new_uid, reason, distance, phase, *, kind, stage):
        ctx = ctx_of(self)
        if ctx is None:
            return o_replace(self, view, vid, old_units, new_uid, reason, distance, phase, kind=kind, stage=stage)
        apply_today(self, ctx)
        v, new, olds = str(vid), str(new_uid), [str(o) for o in old_units]
        what, who = classify_replace(v, new, olds, ctx["K"], ctx["ko_victims"])
        if what is None:
            return o_replace(self, view, vid, old_units, new_uid, reason, distance, phase, kind=kind, stage=stage)
        log(ctx, who, v, what, [str(kind), v, new, olds], None)
        for o in olds:
            # R0 releases o: free again iff it was an ACTIVE incumbent (a REPLACE); a released latched unit stays
            # route_blocked (_release_other_claimants) - read by J's step-4 availability test only
            ctx["unreleased"][o] = str(kind) == "replace"
        return True                                   # R0's control flow: the replacement applies (see (0))

    def avail(self, ff_marker):
        ctx = ctx_of(self)
        if ctx is not None and ctx["unreleased"]:
            for uid, m in ctx["view"]["units"].items():
                if m is ff_marker and uid in ctx["unreleased"]:
                    return ctx["unreleased"][uid]
        return o_avail(self, ff_marker)

    def jpoint(self, phase):
        if not rules or not joint_on():
            return o_jpoint(self, phase)
        kolog["joint_on_seen"] = True
        step = step_of(self)
        units_all = sorted((str(k) for k in (getattr(self, "firefighter_marker_agents", None) or {})), key=id_index)
        if not state["checked"]:
            state["checked"] = True
            unknown = [u for u in rule_named_units(rules) if u not in units_all]
            if unknown:
                kolog["errors"].append("rules name units the model does not have: %s (model units %s)"
                                       % (unknown, units_all))
        K = active_units(rules, step, str(phase), units_all)
        if not K:
            return o_jpoint(self, phase)
        view = self._dispatch_view()
        legacy = [[str(v), str(u)] for v, u in legacy_fn(view)]
        ctx = {"model": self, "step": step, "phase": str(phase), "K": K, "view": view, "legacy": legacy,
               "s2": None, "same": set(), "today_done": False, "ko_victims": set(), "plan_seen": False,
               "unreleased": {}, "ledger_minus": {}, "n": 0}
        stack.append(ctx)
        try:
            out = o_jpoint(self, phase)
        finally:
            stack.pop()
        apply_today(self, ctx)                        # J applied nothing at this J point (no-op if already done)
        kolog["jpoints"].append([step, str(phase), sorted(K, key=id_index), legacy,
                                 [[v, u] for v, u in legacy if u in K],
                                 sorted([v, u] for v, u in ctx["same"]), ctx["n"]])
        return out

    WM._joint_dispatch_point = jpoint
    WM._dispatch_fill_bind = fill_bind
    WM._dispatch_replace = replace
    WM._firefighter_available_for_dispatch = avail


# ============================================================================================== self-test
def _fake_world(script):
    """A fake (ag, wf) whose WildFireModel._joint_dispatch_point runs the REAL J order on scripted decisions: step 2
    solve_fill -> _dispatch_fill_bind per pair (bound sets from the returns); step 3 plan_replacements_detail ->
    _dispatch_replace per replacement (released from the returns); step 4 the released units J's availability test
    admits x the W victims step 2 left -> solve_fill -> _dispatch_fill_bind (stage 4). The executor, the binds and
    the replacements are recorded (`calls`), never simulated beyond a ledger increment and the released unit's
    availability."""
    import types
    calls = []

    class Marker:
        def __init__(self, name, pos, free):
            self.name, self.pos, self.free = name, pos, free

    def pair(v, u):
        return types.SimpleNamespace(victim=v, unit=u, distance=1)

    def solve_fill(units, victims, distance, ledger, *, clean=None, capped=()):
        calls.append(["solve_fill", sorted(units), sorted(victims), dict(ledger)])
        key = "s2" if not any(c[0] == "plan" for c in calls) else "s4"
        return [pair(v, u) for v, u in script[key] if u in units and v in victims]

    def plan_replacements_detail(contests, spares, distance, ledger, clean, *, stall_steps, margin_persist):
        calls.append(["plan", sorted(spares), dict(ledger)])
        reps = [types.SimpleNamespace(victim=v, old_unit=o, new_unit=n, latched=lat, distance=2, cause="stall")
                for v, n, o, lat in script["s3"] if n in spares]
        return reps, []

    jd = types.SimpleNamespace(solve_fill=solve_fill, plan_replacements_detail=plan_replacements_detail,
                               new_progress=lambda cell: ("progress", cell))

    class Executor:
        def __init__(self, model):
            self.model = model

        def apply_physical_pairing_decision(self, model, decision, victim_marker=None):
            calls.append(["executor_assign", decision.victim_id, decision.firefighter_id, decision.payload["reason"]])
            key = (decision.firefighter_id, decision.victim_id)
            model._dispatch_ledger[key] = model._dispatch_ledger.get(key, 0) + 1
            return {"success": True, "message": "dispatched"}

    class WM:
        def __init__(self):
            self.evaluation_timesteps_counter = script["step"]
            self.units = {u: Marker(u, (i, 0), u in script["free"]) for i, u in enumerate(script["units"])}
            self.firefighter_marker_agents = dict(self.units)
            self.victims = {v: {"marker": Marker(v, (0, 5 + i), False), "cell": (0, 5 + i), "binders": []}
                            for i, v in enumerate(script["victims"])}
            self._dispatch_ledger = dict(script["ledger"])
            self._dispatch_events = []

        def _dispatch_view(self):
            return {"victims": self.victims, "units": self.units, "free": list(script["free"]),
                    "waiting": list(script["waiting"]), "latched": list(script["latched"])}

        def _dispatch_state(self, name, factory):
            if getattr(self, name, None) is None:
                setattr(self, name, factory())
            return getattr(self, name)

        def _dispatch_record(self, **event):
            self._dispatch_events.append(event)

        def _physical_rescue_executor(self):
            return Executor(self)

        def _firefighter_available_for_dispatch(self, marker):
            return marker.free

        def _dispatch_fill_bind(self, view, vid, uid, distance, phase, *, kind, stage):
            calls.append(["fill_bind", int(stage), vid, uid])
            return True

        def _dispatch_replace(self, view, vid, old_units, new_uid, reason, distance, phase, *, kind, stage):
            calls.append(["replace", vid, new_uid, list(old_units), kind])
            for o in old_units:
                self.units[o].free = kind == "replace"
            return True

        def _joint_dispatch_point(self, phase):
            view = self._dispatch_view()
            ledger = self._dispatch_state("_dispatch_ledger", dict)
            free, waiting = view["free"], view["waiting"]
            bound_u, bound_v = set(), set()
            for p in wf.jd_mod.solve_fill(free, waiting, {}, ledger, clean={}):
                if self._dispatch_fill_bind(view, p.victim, p.unit, p.distance, phase, kind="fill", stage=2):
                    bound_u.add(p.unit)
                    bound_v.add(p.victim)
            spares = [u for u in free if u not in bound_u]
            released = []
            reps, _barred = wf.jd_mod.plan_replacements_detail([], spares, {}, ledger, {}, stall_steps=10,
                                                               margin_persist=3)
            for r in reps:
                if self._dispatch_replace(view, r.victim, [r.old_unit], r.new_unit, "x", r.distance, phase,
                                          kind="latch_fill" if r.latched else "replace", stage=3):
                    released.append(r.old_unit)
            again = [u for u in released if self._firefighter_available_for_dispatch(view["units"][u])]
            still = [v for v in waiting if v not in bound_v]
            if again and still:
                for p in wf.jd_mod.solve_fill(again, still, {}, ledger, clean={}):
                    self._dispatch_fill_bind(view, p.victim, p.unit, p.distance, phase, kind="second_fill", stage=4)

    wf = types.SimpleNamespace(WildFireModel=WM, _jd=jd, RescueDecision=lambda **k: types.SimpleNamespace(**k))
    wf.jd_mod = jd                       # the fake J reads its pure functions through the module at call time
    ag = types.SimpleNamespace(dispatch_joint=lambda: True)
    return ag, wf, calls


def fake_model_cases():
    """R-13 / R-14 (selftest): the run-time override on a fake model (_fake_world)."""
    script = {"step": 50, "units": ["ff_unit_0", "ff_unit_1", "ff_unit_3", "ff_unit_5", "ff_unit_6"],
              "free": ["ff_unit_0", "ff_unit_1", "ff_unit_3"], "victims": ["victim_1", "victim_2", "victim_3",
                                                                           "victim_7", "victim_8"],
              "waiting": ["victim_1", "victim_2", "victim_3"], "latched": [],
              "ledger": {("ff_unit_3", "victim_1"): 1},
              "legacy": [["victim_1", "ff_unit_3"], ["victim_2", "ff_unit_0"]],
              "s2": [("victim_1", "ff_unit_0")],
              "s3": [("victim_7", "ff_unit_1", "ff_unit_5", False), ("victim_8", "ff_unit_3", "ff_unit_6", False)],
              "s4": [("victim_2", "ff_unit_5"), ("victim_3", "ff_unit_6")]}
    # R-13: KO of ff_unit_3 at this J point
    ag, wf, calls = _fake_world(script)
    kolog = {"ko_log": [], "jpoints": [], "errors": [], "joint_on_seen": False}
    install_ko(ag, wf, [{"unit": "ff_unit_3", "from": 50, "to": 50}], kolog, lambda view: script["legacy"])
    m = wf.WildFireModel()
    m._joint_dispatch_point("post")
    keys = sorted(([e[0], e[1], e[2], e[3], e[4]] for e in kolog["ko_log"]), key=change_order)
    recorded = jpoint_changes(50, "post", script["legacy"],
                              [[v, u, True] for v, u in script["s2"]],
                              [["latch_fill" if lat else "replace", v, n, [o], True] for v, n, o, lat in script["s3"]],
                              [[v, u, True] for v, u in script["s4"]], {"ff_unit_3"})
    first_apply = next(i for i, c in enumerate(calls) if c[0] in ("fill_bind", "replace", "executor_assign"))
    plan = next(c for c in calls if c[0] == "plan")
    model_calls = [c for c in calls if c[0] in ("fill_bind", "replace", "executor_assign")]
    want_calls = [["executor_assign", "victim_1", "ff_unit_3", "ko_today"],
                  ["replace", "victim_7", "ff_unit_1", ["ff_unit_5"], "replace"],
                  ["fill_bind", 4, "victim_2", "ff_unit_5"]]
    s4 = [c for c in calls if c[0] == "solve_fill"][-1]
    ok13 = (calls[first_apply] == want_calls[0] and model_calls == want_calls
            and plan[1] == ["ff_unit_1", "ff_unit_3"]                      # U0 (its dropped bind) is no spare: R0's
            and plan[2] == {("ff_unit_3", "victim_1"): 1}                  # shielded: R0's ledger
            and s4[3] == {("ff_unit_3", "victim_1"): 1}
            and m._dispatch_ledger == {("ff_unit_3", "victim_1"): 2}       # live: the ko_today bind counted
            and s4[1] == ["ff_unit_5", "ff_unit_6"] and s4[2] == ["victim_2", "victim_3"]
            and keys == recorded and [k[4] for k in keys] == ["drop_victim", "ko_today", "drop_challenger",
                                                              "drop_unreleased"]
            and [e["kind"] for e in m._dispatch_events] == ["ko_today"]
            and not kolog["errors"] and len(kolog["jpoints"]) == 1)
    r13 = {"ok": ok13, "detail": {"calls": calls, "log": keys, "recorded": recorded}}
    # R-14: R0 (no rule) and a rule whose range excludes step 50
    res = []
    for rules in ([], [{"unit": "ff_unit_3", "from": 0, "to": 49}]):
        ag, wf, calls = _fake_world(script)
        kolog = {"ko_log": [], "jpoints": [], "errors": [], "joint_on_seen": False}
        install_ko(ag, wf, rules, kolog, lambda view: script["legacy"])
        m = wf.WildFireModel()
        m._joint_dispatch_point("post")
        model_calls = [c for c in calls if c[0] in ("fill_bind", "replace", "executor_assign")]
        res.append(model_calls == [["fill_bind", 2, "victim_1", "ff_unit_0"],
                                   ["replace", "victim_7", "ff_unit_1", ["ff_unit_5"], "replace"],
                                   ["replace", "victim_8", "ff_unit_3", ["ff_unit_6"], "replace"],
                                   ["fill_bind", 4, "victim_2", "ff_unit_5"], ["fill_bind", 4, "victim_3", "ff_unit_6"]]
                   and [c for c in calls if c[0] == "plan"][0][2] == {("ff_unit_3", "victim_1"): 1}
                   and not kolog["ko_log"] and not kolog["jpoints"] and not m._dispatch_events)
    r14 = {"ok": all(res), "detail": res}
    return r13, r14


def selftest():
    fails, lines = [], []

    def case(name, cond, detail=""):
        lines.append("%-4s %s%s" % ("PASS" if cond else "FAIL", name, ("  | " + str(detail)[:300]) if detail else ""))
        if not cond:
            fails.append(name)

    good = parse_rules('[{"unit":"ff_unit_0","from":0,"to":40},{"unit":"!ff_unit_1","to":9,"phase":"post"},'
                       '{"unit":"*"}]')
    bad = []
    for text in ('{"unit":"ff_unit_0"}', '[{"from":0}]', '[{"unit":"ff_unit_0","kinds":"ab"}]',
                 '[{"unit":" ff_unit_0"}]', '[{"unit":"!"}]', '[{"unit":"ff_unit_0","to":true}]',
                 '[{"unit":"ff_unit_0","to":4.0}]', '[{"unit":"ff_unit_0","from":"1"}]',
                 '[{"unit":"ff_unit_0","from":5,"to":4}]', '[{"unit":"ff_unit_0","phase":"mid"}]', 'not json',
                 '[{"unit":"ff_unit_0","to":null}]', '[{"unit":5}]'):
        try:
            parse_rules(text)
            bad.append(text)
        except ValueError:
            pass
    case("R-1 parse_rules accepts the three rule forms (id, !id, *) with optional from / to / phase and refuses 13 "
         "malformed ones (not a list, no unit, unknown key, whitespace, bare !, bool / float / string / null bound, "
         "from > to, bad phase, bad JSON, non-string unit)", len(good) == 3 and not bad, bad)
    units = ["ff_unit_0", "ff_unit_1", "ff_unit_2"]
    case("R-2 active_units: KO-OWN acts at J points 0..t of both phases; '!U' = every other unit; a phase rule acts "
         "at that phase only; outside the range nothing",
         active_units([good[0]], 40, "post", units) == {"ff_unit_0"}
         and active_units([good[0]], 41, "pre", units) == set()
         and active_units([good[1]], 9, "post", units) == {"ff_unit_0", "ff_unit_2"}
         and active_units([good[1]], 9, "pre", units) == set()
         and active_units([good[2]], 10 ** 6, "pre", units) == set(units))
    # the swap of B_W 9608 (round 1's step 15): legacy v2->u0, v3->u1; J v2->u1, v3->u0
    leg = [["victim_2", "ff_unit_0"], ["victim_3", "ff_unit_1"]]
    s2 = [["victim_2", "ff_unit_1", True], ["victim_3", "ff_unit_0", True]]
    ch = jpoint_changes(15, "post", leg, s2, [], [], {"ff_unit_0"})
    case("R-3 KO-OWN(u0) on a swap: J's bind of u0 (v3) dropped, J's bind on u0's counterfactual victim v2 (u1) "
         "dropped, u0 bound ko_today to v2",
         ch == [[15, "post", "ff_unit_0", "victim_2", "ko_today"], [15, "post", "ff_unit_0", "victim_3", "drop_bind"],
                [15, "post", "ff_unit_1", "victim_2", "drop_victim"]], ch)
    ch2 = jpoint_changes(15, "post", leg, s2, [], [], {"ff_unit_0", "ff_unit_1"})
    case("R-4 KO of both units on the swap: both J binds dropped (drop_bind), both counterfactual binds made",
         sorted(c[4] for c in ch2) == ["drop_bind", "drop_bind", "ko_today", "ko_today"], ch2)
    same = jpoint_changes(9, "post", [["victim_2", "ff_unit_0"]], [["victim_2", "ff_unit_0", True]], [], [],
                          {"ff_unit_0"})
    same_ref = jpoint_changes(9, "post", [["victim_2", "ff_unit_0"]], [["victim_2", "ff_unit_0", False]], [], [],
                              {"ff_unit_0"})
    case("R-5 J's choice equal to the counterfactual's (successful or refused) is unchanged: EMPTY", same == []
         and same_ref == [], (same, same_ref))
    wl = jpoint_changes(30, "pre", [["victim_4", "ff_unit_2"]], [], [], [], {"ff_unit_2"})
    case("R-6 a counterfactual second claim on a latched-held victim at a J point where J binds nothing (PRE false) is "
         "a change (ko_today)", wl == [[30, "pre", "ff_unit_2", "victim_4", "ko_today"]], wl)
    s3 = [["replace", "victim_1", "ff_unit_2", ["ff_unit_0"], True], ["latch_fill", "victim_3", "ff_unit_1",
                                                                         ["ff_unit_4"], True]]
    s4 = [["victim_5", "ff_unit_0", True]]
    c_new = jpoint_changes(50, "post", [], [], s3, s4, {"ff_unit_2"})
    c_old = jpoint_changes(50, "post", [], [], s3, s4, {"ff_unit_0"})
    c_lf = jpoint_changes(50, "post", [], [], s3, [], {"ff_unit_1"})
    case("R-7 stage 3: a K challenger -> drop_challenger and its incumbent's second fill -> drop_unreleased; a K "
         "incumbent -> drop_release and its own second fill -> drop_bind; a K LATCH-FILL challenger -> drop_challenger",
         c_new == [[50, "post", "ff_unit_0", "victim_5", "drop_unreleased"],
                   [50, "post", "ff_unit_2", "victim_1", "drop_challenger"]]
         and c_old == [[50, "post", "ff_unit_0", "victim_1", "drop_release"],
                       [50, "post", "ff_unit_0", "victim_5", "drop_bind"]]
         and c_lf == [[50, "post", "ff_unit_1", "victim_3", "drop_challenger"]], (c_new, c_old, c_lf))
    c_v = jpoint_changes(60, "post", [["victim_1", "ff_unit_3"]], [], [s3[0]], [], {"ff_unit_3"})
    case("R-8 a J replacement on a KO victim (the counterfactual binds a K unit there) -> drop_victim; the K unit "
         "bound ko_today", c_v == [[60, "post", "ff_unit_2", "victim_1", "drop_victim"],
                                   [60, "post", "ff_unit_3", "victim_1", "ko_today"]], c_v)
    keys = [[16, "pre", "ff_unit_1", "victim_3", "drop_bind"], [15, "post", "ff_unit_1", "victim_2", "drop_victim"],
            [15, "pre", "ff_unit_2", "victim_9", "ko_today"]]
    case("R-9 first_change orders by step, then pre before post (not alphabetical)",
         first_change(keys) == [15, "pre", "ff_unit_2", "victim_9", "ko_today"], first_change(keys))
    x = {"rows_ff": [[1]], "rows_vic": [], "rows_uav": [], "rows_dec": [], "rows_trig": [], "eval": {"r": 1},
         "mv_events": [], "dp": {"commands": [[1]], "j_events": [{"k": 1}]}, "wall_s": 3.0}
    y = json.loads(json.dumps(x))
    y["wall_s"] = 4.0
    z = json.loads(json.dumps(x))
    z["dp"]["j_events"] = []
    no_eval = {k: v for k, v in x.items() if k != "eval"}
    case("R-10 r0_reproduces: equal records and stdout reproduce (wall_s ignored); a changed J event list or stdout "
         "does not; a field missing from X never reproduces (also when R0 lacks it too)",
         r0_reproduces(x, y, "a", "a") == [] and r0_reproduces(x, z, "a", "a") == ["dp.j_events"]
         and r0_reproduces(x, y, "a", "b") == ["stdout"] and r0_reproduces(no_eval, no_eval, "a", "a") == ["eval"]
         and r0_reproduces(x, y, None, None) == ["stdout"])
    vol, other = classify_diff([".wall_s", ".tag", ".argv[21]", ".dp.timing.j_ms_total", ".dp.j_calls[3][2]",
                                ".mv.rows[4][35]", ".dp.commands[0][1]"], mv_cols=["x"] * 35 + ["fix_ms", "inst_ms"])
    case("R-11 classify_diff: wall-clock / ms / tag / argv paths are volatile, a command field is not",
         len(vol) == 6 and other == [".dp.commands[0][1]"], (vol, other))
    refused = []
    saved_argv, saved_err = sys.argv, sys.stderr
    try:
        sys.stderr = open(os.devnull, "w")
        probe_tail = ["--", "--crn", "--", "--repo", "E:/x"]
        for args in (probe_tail, ["--ko", "[]"] + probe_tail, ["--kolog", "k.json", "--ko", "nope"] + probe_tail,
                     ["--kolog", "k.json", "--ko", "[]", "--ko", "[]"] + probe_tail,
                     ["--kolog", "k.json", "--boards", "b.json"] + probe_tail, ["--kolog", "--ko", "[]"] + probe_tail,
                     ["--kolog", "k.json", "--", "--crn", "--", "--scenario", "A"], ["--kolog", "k.json"]):
            sys.argv = ["_dq_replay.py"] + args
            refused.append(main())
    finally:
        sys.stderr.close()
        sys.argv, sys.stderr = saved_argv, saved_err
    case("R-12 the replay REFUSES (exit 2, before any import or run) without --kolog, with a malformed --ko, a "
         "repeated or unknown replay flag, a flag without its value, no '-- --repo', or no probe arguments",
         refused == [2] * 8, refused)
    r13, r14 = fake_model_cases()
    case("R-13 THE RUN-TIME OVERRIDE on a fake model whose J point calls the model's apply methods and J's pure "
         "functions in the real J order (stage 2 fill, stage 3 plan + replacements, stage 4 second fill): the ko_today "
         "bind reaches the executor BEFORE J's first apply; the dropped decisions (drop_victim, drop_challenger, "
         "drop_unreleased) never reach the model and J's control flow sees them as applied (the unit of the dropped "
         "stage-2 bind is no stage-3 spare, as in R0; the dropped replacement's incumbent joins J's step-4 set as R0's "
         "released active unit, and its second fill is dropped as unreleased); the undropped REPLACE and second fill "
         "go through; the plan and the stage-4 fill saw the ledger WITHOUT the ko_today increment (the live ledger has "
         "it); and the run-time log equals jpoint_changes on the decisions R0 records", r13["ok"], r13["detail"])
    case("R-14 R0 and a knockout whose range excludes the J point are pure pass-throughs on the fake model (every J "
         "apply reaches the model, the ledger unshielded, no log entry)", r14["ok"], r14["detail"])
    lines.append("")
    lines.append("DQ REPLAY SELF-TEST %s (%d cases, %d failed)" % ("PASS" if not fails else "FAIL",
                                                                  sum(1 for x_ in lines if x_[:4] in ("PASS", "FAIL")),
                                                                  len(fails)))
    print("\n".join(lines))
    return 1 if fails else 0


# ============================================================================================== main
def main() -> int:
    argv = sys.argv[1:]
    if argv[:1] == ["selftest"]:
        return selftest()
    if argv[:1] == ["compare"] and len(argv) == 3:
        return compare(argv[1], argv[2])
    if "--" not in argv:
        print("usage: _dq_replay.py --kolog <out> [--ko <json>] -- <_dq_probe.py args> | compare X R0 | selftest",
              file=sys.stderr)
        return 2
    own, probe_argv = argv[:argv.index("--")], argv[argv.index("--") + 1:]
    if "--kolog" not in own:
        print("DQ REPLAY REFUSED: --kolog is required", file=sys.stderr)
        return 2
    try:
        flags, values = own[0::2], own[1::2]
        if (len(own) % 2 or len(set(flags)) != len(flags) or set(flags) - {"--kolog", "--ko"}
                or set(values) & {"--kolog", "--ko"}):
            raise ValueError("the replay arguments are --kolog <path> [--ko <json>], each once: %r" % (own,))
        kolog_path = own[own.index("--kolog") + 1]
        rules = parse_rules(own[own.index("--ko") + 1]) if "--ko" in own else []
    except (ValueError, IndexError, TypeError) as exc:
        print("DQ REPLAY REFUSED: %s" % (exc,), file=sys.stderr)
        return 2
    if "--" not in probe_argv or "--repo" not in probe_argv[probe_argv.index("--") + 1:]:
        print("DQ REPLAY REFUSED: the probe arguments need '-- --repo <repo>'", file=sys.stderr)
        return 2
    inner = probe_argv[probe_argv.index("--") + 1:]
    repo = inner[inner.index("--repo") + 1]
    probe_path = os.path.join(HERE, PROBE_FILE)
    # the tools that write the knockout log and the record, read before anything runs
    kolog = {"version": VERSION, "replay_sha": lf_sha256(os.path.abspath(__file__)), "probe_sha": lf_sha256(probe_path),
             "argv": argv, "ko_rules": rules, "ko_log": [], "ko_applied": [], "jpoints": [], "joint_on_seen": False,
             "errors": []}
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    # the probe's own first three imports, in its order (the same module objects the probe and the model use)
    import agents as ag  # noqa: E402
    import common_fixed_variables as cfv  # noqa: E402,F401
    import wildfire_model as wf  # noqa: E402

    probe = runpy.run_path(probe_path, run_name="dq_probe_module")
    install_ko(ag, wf, rules, kolog, probe["legacy_pairs"])
    sys.argv = [probe_path] + probe_argv
    rc = None
    try:
        rc = probe["main"]()
    finally:
        if rules and not kolog["joint_on_seen"]:
            kolog["errors"].append("knockout rules given but DISPATCH_JOINT was never on at a J point")
        kolog["ko_applied"] = sorted(([e[0], e[1], e[2], e[3], e[4]] for e in kolog["ko_log"]), key=change_order)
        kolog["rc"] = rc
        tmp = kolog_path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(kolog, fh, separators=(",", ":"), default=str)
        os.replace(tmp, kolog_path)
    return rc


if __name__ == "__main__":
    sys.exit(main())
