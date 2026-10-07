"""Urgency round, the 22.9 per-death review: a REPLAY of one screen run with (1) the fire board recorded at every
firefighter decision and (2) optional KNOCKOUTS of fix (a) / fix (b) decisions. Diagnostics only (maintainer ruling
on report section 9: the set-3 / set-4 deaths show what to guard against and are never the test).

usage: _ud_replay.py --boards <out.json> [--ko <json list>] -- <exactly the _ud_probe.py arguments of the run>

KNOCKOUT. A rule is {"unit": U, "kinds": "ab", "from": s0, "to": s1}; U is a unit id, "*" (every unit) or "!id"
(every unit but id). At an advance of a matching unit on a step s0 <= s <= s1 (s = evaluation_timesteps_counter, the
mv_events step), the fix's PURE choice method (_approach_path_choice for "a", _retreat_on_route_choice for "b")
returns None, so the model runs TODAY's mover for that decision - the exact code path of a switch-0 arm. Nothing
else changes: the switches stay as the run line sets them, every other decision is the fix's own. The wrap is
installed at class level BEFORE the probe's own install, so the probe's shadows read the same (knocked-out) choice.

BOARDS. At every Firefighter.advance entry (a living, placed unit): the step, unit, cell, target, status, exiting
flag, and the digest of the board it decides on (burning + active smoke by agents.fire_board_sets - the units' own
predicates); each distinct board is stored once. Plus the wind label and vector (cfv.wind_vector_from_direction, the
vector U1's FAE reads) and the grid size. RECORD-ONLY: no RNG draw, no print, no attribute set on a model or agent.

The probe record itself is written to the run line's --out exactly as _ud_probe.py writes it.
"""
from __future__ import annotations

import hashlib
import json
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    argv = sys.argv[1:]
    if "--" not in argv:
        print("usage: _ud_replay.py --boards <out> [--ko <json>] -- <_ud_probe.py args>", file=sys.stderr)
        return 2
    own, probe_argv = argv[:argv.index("--")], argv[argv.index("--") + 1:]
    boards_path = own[own.index("--boards") + 1]
    rules = json.loads(own[own.index("--ko") + 1]) if "--ko" in own else []
    inner = probe_argv[probe_argv.index("--") + 1:]
    repo = inner[inner.index("--repo") + 1]
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as ag  # noqa: E402  (the same module object the probe and the model import)
    import common_fixed_variables as cfv  # noqa: E402

    FF = ag.Firefighter
    ko_log = {}
    rec = {"boards": {}, "decisions": [], "wind": None, "grid": None}

    def blocked(unit_id, kind, step):
        for r in rules:
            u = r.get("unit", "*")
            hit = u == "*" or (u.startswith("!") and unit_id != u[1:]) or unit_id == u
            if hit and kind in r.get("kinds", "ab") and int(r.get("from", 0)) <= step <= int(r.get("to", 10 ** 9)):
                return True
        return False

    def ko_wrap(name, kind):
        original = getattr(FF, name)

        def wrapper(self, *a, **k):
            out = original(self, *a, **k)
            if out is None or not rules:
                return out
            uid = str(getattr(self, "unit_id", ""))
            step = int(getattr(self.model, "evaluation_timesteps_counter", 0) or 0)
            if blocked(uid, kind, step):
                ko_log[(step, uid, kind)] = [step, uid, kind, [int(out[0]), int(out[1])]]
                return None
            return out

        setattr(FF, name, wrapper)

    ko_wrap("_approach_path_choice", "a")
    ko_wrap("_retreat_on_route_choice", "b")

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

    probe = runpy.run_path(os.path.join(HERE, "_ud_probe.py"), run_name="ud_probe_module")
    sys.argv = [os.path.join(HERE, "_ud_probe.py")] + probe_argv
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
