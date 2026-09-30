"""fix3a Part 1 PROTOTYPE (not the Part 2 code): scenario B with the B1 team, B2's launch charges and
B3's return delay applied by MONKEYPATCH in this process only - no source file is edited.

usage: _fx3_bproto.py --b2 0|1 --b3 none|low|crit -- <_sd_probe.py args ...>
  run it with --scenario B --uavs 4 --victims 4 --firefighters 3 (the B1 team; roles by the half
  rule: 2 trackers + 2 searchers, trackers first by index).
  --b2 1   launch charges replace B's 0.5 fraction: searchers 85 / 65 (in index order), trackers
           78 / 72 (in index order); the prototype passes --set REDUCED_LAUNCH_BATTERY=0 itself so the
           fraction is not applied on top.
  --b3     the return delay for a victim searcher: at the return trigger (battery <= 0.3 d + 39.23,
           d = Manhattan to the berth the trigger test uses), DELAY while every other victim searcher
           is away (rtb_active or rtb_docked) and battery > FLOOR(d) = 0.3 d + A + 1.70 + 0.60
             A = 30 (LOW_BATTERY_THRESHOLD)          --b3 low
             A = 15 (BATTERY_CRITICAL_THRESHOLD)     --b3 crit
           1.70 = 17 blocked steps x 0.1 (the recorded maximum return-leg standoff, cfv derivation);
           0.60 = one more delayed step moving away (-0.3 battery, +0.3 threshold).
Adds d["bproto"] = {"b2": ..., "b3": ..., "delays": [[step, uid, battery, trigger, floor, d], ...]}.
"""
from __future__ import annotations

import json
import os
import runpy
import sys


def main() -> int:
    argv = sys.argv[1:]
    cut = argv.index("--")
    opts, probe_args = argv[:cut], argv[cut + 1:]
    b2 = int(opts[opts.index("--b2") + 1])
    b3 = opts[opts.index("--b3") + 1]
    out_path = probe_args[probe_args.index("--out") + 1]
    repo = r"E:\Projects\SAS"
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am  # noqa: E402

    DELAYS = []

    if b2:
        def bases(roles):
            roles = [str(r) for r in roles]
            s_vals, t_vals = [85.0, 65.0], [78.0, 72.0]
            out, si, ti = [], 0, 0
            for r in roles:
                if r == "victim_searcher":
                    out.append(s_vals[min(si, len(s_vals) - 1)])
                    si += 1
                else:
                    out.append(t_vals[min(ti, len(t_vals) - 1)])
                    ti += 1
            return out
        am.staggered_launch_bases = bases
        probe_args += ["--set", "REDUCED_LAUNCH_BATTERY=0"]

    if b3 in ("low", "crit"):
        arrival = 30.0 if b3 == "low" else 15.0
        otrig = am.UAV._rtb_trigger_level

        def trig(self, berth):
            level = otrig(self, berth)
            try:
                if str(getattr(self, "current_role", "")) != "victim_searcher":
                    return level
                if float(self.battery_level) > level:
                    return level                      # the return would not start anyway
                others = [a for a in self.model.schedule.agents
                          if type(a) is am.UAV and a is not self
                          and str(getattr(a, "current_role", "")) == "victim_searcher"]
                if not others or not all(bool(a.rtb_active) or bool(a.rtb_docked) for a in others):
                    return level
                dist = abs(int(self.pos[0]) - berth[0]) + abs(int(self.pos[1]) - berth[1])
                floor = 0.3 * dist + arrival + 1.70 + 0.60
                if float(self.battery_level) > floor:
                    DELAYS.append([int(self.model.evaluation_timesteps_counter), str(self.unique_id),
                                   round(float(self.battery_level), 3), round(level, 3), round(floor, 3), dist])
                    return floor                      # battery > floor: the trigger test does not fire
            except Exception as exc:
                DELAYS.append(["ERR", repr(exc)[:120]])
            return level

        am.UAV._rtb_trigger_level = trig

    probe = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_sd_probe.py"),
                           run_name="sd_probe_module")
    sys.argv = [sys.argv[0]] + probe_args
    rc = probe["main"]()
    try:
        with open(out_path, encoding="utf-8") as fh:
            d = json.load(fh)
        d["bproto"] = {"b2": b2, "b3": b3, "delays": DELAYS, "probe": "fx3_bproto v1"}
        tmp = out_path + ".bptmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, separators=(",", ":"))
        os.replace(tmp, out_path)
    except Exception as exc:
        print("BPROTO WRITE FAILED %r" % (exc,), file=sys.stderr)
        return 5
    return rc


if __name__ == "__main__":
    sys.exit(main())
