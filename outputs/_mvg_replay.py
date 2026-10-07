"""MVG round, the per-death attribution (Part 1d 1d.6.5, amendment 1d.13.2 - wave W3, BEFORE the verdict): a REPLAY of
one run with (1) the fire board recorded at every firefighter decision and (2) optional KNOCKOUTS of guarded fix (a) /
fix (b) decisions and of the stranding guard. A port of urgency:outputs/_ud_replay.py (5dba5bcb); it wraps
outputs/_mvg_probe.py exactly as that wrapped _ud_probe.py.

usage: _mvg_replay.py --boards <out.json> [--ko <json list>] -- <exactly the _mvg_probe.py arguments of the run>

KNOCKOUT. A rule is {"unit": U, "kinds": K, "from": s0, "to": s1}; U is a unit id (a non-empty string, not "*", not
starting with "!", no surrounding whitespace), "*" (every unit) or "!" + a unit id (every unit but that one); K is a
non-empty subset of "abg" (default "ab"); s0 / s1 are JSON integers (never a bool, a float or a string; defaults 0 and
10**9; s0 <= s1). At an advance of a matching unit on a step s0 <= s <= s1 (s =
evaluation_timesteps_counter, the mv_events step):
  a / b  the fix's PURE choice method (_approach_path_choice for "a", _retreat_on_route_choice for "b") returns None,
         so the model runs TODAY's mover for that decision - the exact code path of a switch-0 arm - and the guard is
         not evaluated (Firefighter._guarded returns None for None). In arm G a vetoed decision is already today's
         step: an a / b knockout changes only the decisions the guard admitted.
  g      KO-GUARD: Firefighter._stranding_guard_verdict returns (True, c_n, T_v) - the guard off for the matched unit
         and steps: a decision the guard would have vetoed is taken as the fix's step. The verdict is still computed
         (its c_n and T_v are kept); a knockout is logged only where the true verdict was a veto.
Nothing else changes: the switches stay as the run line sets them, every other decision is the run's own. The wraps
are installed at class level BEFORE the probe's own install, so the probe's shadows read the same (knocked-out)
choice, and the probe's model_admit is the knocked-out verdict (its instrument verdict - the frozen-function replica -
and its cross-check movement_paths.stranding_guard are computed by the instrument directly and stay the true ones).

BOARDS. At every Firefighter.advance entry (a living, placed unit): the step, unit, cell, target, status, exiting
flag, and the digest of the board it decides on (burning + active smoke by agents.fire_board_sets - the units' own
predicates); each distinct board is stored once. Plus the wind label and vector (cfv.wind_vector_from_direction, the
vector the guard's FAE reads) and the grid size. RECORD-ONLY: no RNG draw, no print, no attribute set on a model or
agent. ko_applied = sorted [step, unit, kind, cell] (cell = the knocked-out choice for a / b, the vetoed step cell
for g), one per (step, unit, kind). replay_sha / probe_sha = sha256 of the LF-normalised bytes of this file and of
outputs/_mvg_probe.py, read when the replay starts (the tools that wrote the boards and the record).

WHAT ko_applied MEANS - TWO DIFFERENT THINGS BY KIND (read it with the record, not alone):
  a / b  an entry is logged for EVERY knocked-out pure choice that returned a cell: the wrap sits on the pure choice
         method itself, so it logs
           - decisions the guard would have VETOED (in arm G): the knockout is then a NO-OP - today's step runs
             either way - and the entry does not mean the trajectory changed;
           - calls from the PROBE's own shadow (mv_shadow calls the same class functions, captured after these wraps):
             a decision the model itself never asked the fix about (e.g. a fix whose switch is off) is logged too;
         one entry per (step, unit, kind) however many calls matched. Whether a knockout CHANGED a step is read from
         the record: the unknocked run's mv_events 'ran' at that (step, unit, kind) (the analyzer tests only that
         membership: its KO-OWN / KO-OTHERS reading, ko_first).
  g      an entry is logged ONLY where the model's true verdict was a VETO and the knockout turned it into an admit
         (a TRUE veto knocked out); an admitted decision is passed through and not logged. Only the model's own guard
         calls are wrapped (the instrument never calls _stranding_guard_verdict).

The probe record itself is written to the run line's --out exactly as _mvg_probe.py writes it. A malformed --ko (not
JSON, not a list, a rule with an unknown key, a bad unit, kinds or bound, from > to) is REFUSED (exit 2, "MVG REPLAY
REFUSED" on stderr) before anything runs.
"""
from __future__ import annotations

import hashlib
import json
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KINDS = "abg"


def lf_sha256(path):
    """sha256 of a file's LF-normalised bytes (CRLF read as LF; _mvg_probe.lf_sha256's rule)."""
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()


def _unit_id_ok(uid):
    """A unit id as a rule may name it: a non-empty string, not "*", not starting with "!", no surrounding whitespace
    (an id that could never equal a unit's would make a silent no-op rule)."""
    return isinstance(uid, str) and bool(uid) and uid == uid.strip() and uid != "*" and not uid.startswith("!")


def parse_rules(text):
    """The --ko rules, validated STRICTLY (no cast, no coercion - the bare int() cast defect class): a JSON list of
    dicts with only the keys unit / kinds / from / to; unit (default "*") = a unit id (_unit_id_ok), "*", or "!" + a
    unit id; kinds (default "ab") = a non-empty string over "abg"; from / to, when present, JSON integers - type int,
    never bool (True is an int in Python), float or string - with from <= to (defaults 0 and 10**9). Raises
    ValueError on anything else (a JSON syntax error is a ValueError too)."""
    rules = json.loads(text)
    if not isinstance(rules, list):
        raise ValueError("--ko must be a JSON list")
    for r in rules:
        if not isinstance(r, dict) or set(r) - {"unit", "kinds", "from", "to"}:
            raise ValueError("bad rule %r" % (r,))
        unit = r.get("unit", "*")
        if not (unit == "*" or _unit_id_ok(unit)
                or (isinstance(unit, str) and unit.startswith("!") and _unit_id_ok(unit[1:]))):
            raise ValueError("bad unit in %r (a unit id, \"*\" or \"!\" + a unit id)" % (r,))
        kinds = r.get("kinds", "ab")
        if not isinstance(kinds, str) or not kinds or set(kinds) - set(KINDS):
            raise ValueError("bad kinds in %r (a subset of %r)" % (r, KINDS))
        for key in ("from", "to"):
            if key in r and type(r[key]) is not int:
                raise ValueError("bad %s in %r (a JSON integer: not a bool, float, string or null)" % (key, r))
        lo, hi = r.get("from", 0), r.get("to", 10 ** 9)
        if lo > hi:
            raise ValueError("from > to in %r" % (r,))
    return rules


def matches(rules, unit_id, kind, step):
    """True iff a rule knocks out `kind` of `unit_id` at `step` (the _ud_replay test, with kind g). `rules` are
    parse_rules-validated (from / to are ints already: no cast here)."""
    for r in rules:
        u = r.get("unit", "*")
        hit = u == "*" or (u.startswith("!") and unit_id != u[1:]) or unit_id == u
        if hit and kind in r.get("kinds", "ab") and r.get("from", 0) <= step <= r.get("to", 10 ** 9):
            return True
    return False


def install_ko(ag, rules, ko_log):
    """The knockout wraps (class level; call BEFORE the probe's install). `rules` is read at call time (a list the
    caller may change), `ko_log` collects {(step, unit, kind): [step, unit, kind, cell]}."""
    FF = ag.Firefighter

    def ko_wrap(name, kind):
        original = getattr(FF, name)

        def wrapper(self, *a, **k):
            out = original(self, *a, **k)
            if out is None or not rules:
                return out
            uid = str(getattr(self, "unit_id", ""))
            step = int(getattr(self.model, "evaluation_timesteps_counter", 0) or 0)
            if matches(rules, uid, kind, step):
                ko_log[(step, uid, kind)] = [step, uid, kind, [int(out[0]), int(out[1])]]
                return None
            return out

        setattr(FF, name, wrapper)

    def ko_guard_wrap():
        original = FF._stranding_guard_verdict

        def wrapper(self, step_cell, *a, **k):
            out = original(self, step_cell, *a, **k)
            if not rules or out[0]:
                return out
            uid = str(getattr(self, "unit_id", ""))
            step = int(getattr(self.model, "evaluation_timesteps_counter", 0) or 0)
            if matches(rules, uid, "g", step):
                ko_log[(step, uid, "g")] = [step, uid, "g", [int(step_cell[0]), int(step_cell[1])]]
                return (True, out[1], out[2])
            return out

        FF._stranding_guard_verdict = wrapper

    ko_wrap("_approach_path_choice", "a")
    ko_wrap("_retreat_on_route_choice", "b")
    ko_guard_wrap()


def install_boards(ag, cfv, rec):
    """The board recorder: wraps Firefighter.advance (class level) to add, at every advance entry of a living placed
    unit, a decision row and its board to `rec` (RECORD-ONLY)."""
    FF = ag.Firefighter
    o_advance = FF.advance

    def advance(self, *a, **k):
        try:
            if getattr(self, "pos", None) is not None and not getattr(self, "dead", False):
                m = self.model
                if rec["grid"] is None:
                    rec["grid"] = [int(m.grid.width), int(m.grid.height)]
                    label = getattr(getattr(m, "wind", None), "wind_direction", None)
                    vec = cfv.wind_vector_from_direction(label)
                    rec["wind"] = {"label": label, "vector": None if vec is None else [float(vec[0]), float(vec[1])]}
                burning, smoky = ag.fire_board_sets(m)
                b = sorted([int(x), int(y)] for x, y in burning)
                s = sorted([int(x), int(y)] for x, y in smoky)
                dig = hashlib.sha1(json.dumps([b, s]).encode()).hexdigest()[:16]
                if dig not in rec["boards"]:
                    rec["boards"][dig] = {"burning": b, "smoky": s}
                tgt = getattr(self, "target_pos", None)
                rec["decisions"].append([
                    int(getattr(m, "evaluation_timesteps_counter", 0) or 0), str(getattr(self, "unit_id", "")),
                    [int(self.pos[0]), int(self.pos[1])], None if not tgt else [int(tgt[0]), int(tgt[1])],
                    str(getattr(self, "status", "") or ""), bool(getattr(self, "exiting", False)), dig])
        except Exception as exc:  # noqa: BLE001 - recorded, never raised into the model
            rec.setdefault("errors", []).append(repr(exc))
        return o_advance(self, *a, **k)

    FF.advance = advance


def main() -> int:
    argv = sys.argv[1:]
    if "--" not in argv:
        print("usage: _mvg_replay.py --boards <out> [--ko <json>] -- <_mvg_probe.py args>", file=sys.stderr)
        return 2
    own, probe_argv = argv[:argv.index("--")], argv[argv.index("--") + 1:]
    if "--boards" not in own:
        print("MVG REPLAY REFUSED: --boards is required", file=sys.stderr)
        return 2
    try:
        boards_path = own[own.index("--boards") + 1]
        rules = parse_rules(own[own.index("--ko") + 1]) if "--ko" in own else []
    except (ValueError, IndexError, TypeError) as exc:
        print("MVG REPLAY REFUSED: %s" % (exc,), file=sys.stderr)
        return 2
    if "--" not in probe_argv or "--repo" not in probe_argv[probe_argv.index("--") + 1:]:
        print("MVG REPLAY REFUSED: the probe arguments need '-- --repo <repo>'", file=sys.stderr)
        return 2
    inner = probe_argv[probe_argv.index("--") + 1:]
    repo = inner[inner.index("--repo") + 1]
    probe_path = os.path.join(HERE, "_mvg_probe.py")
    # the tools that write the boards and the record, read before anything runs
    shas = {"replay_sha": lf_sha256(os.path.abspath(__file__)), "probe_sha": lf_sha256(probe_path)}
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as ag  # noqa: E402  (the same module object the probe and the model import)
    import common_fixed_variables as cfv  # noqa: E402

    ko_log = {}
    rec = {"boards": {}, "decisions": [], "wind": None, "grid": None}
    rec.update(shas)
    install_ko(ag, rules, ko_log)
    install_boards(ag, cfv, rec)

    probe = runpy.run_path(probe_path, run_name="mvg_probe_module")
    sys.argv = [os.path.join(HERE, "_mvg_probe.py")] + probe_argv
    rc = probe["main"]()
    rec["ko_rules"] = rules
    rec["ko_applied"] = sorted(ko_log.values())
    rec["argv"] = argv
    tmp = boards_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rec, fh, separators=(",", ":"))
    os.replace(tmp, boards_path)
    return rc


if __name__ == "__main__":
    sys.exit(main())
