"""NEGATIVE CONTROL for the _belief_gap_critical round.

The `arm` run (count-correct predicate) came out byte-identical to `live`.
That is only evidence of inertness if the arming MECHANISM has teeth -- i.e.
if a patch that really does change the returned value DOES change the run.

This driver reuses _bgc_probe wholesale and changes exactly one thing:
`corrected_belief_gap_critical` is replaced by a constant-False function.
Because _bgc_probe.install(arm=True) returns
    corr if arm else live
and resolves `corrected_belief_gap_critical` as a module global at CALL time,
patching the module attribute before install() makes the live predicate
return False on every one of the 240 calls -- the maximal counterfactual.

  falsearm  _belief_gap_critical == False always   (critical_collapse never set)
  truearm   _belief_gap_critical == True  always   (== live; sanity check that
            the harness reproduces `live` exactly when the value is unchanged)

If falsearm is ALSO identical to live, `critical_collapse` is inert outright.
If falsearm DIFFERS from live, the harness has teeth and the corrected-predicate
null result is a real equivalence, not a dead patch.
"""
from __future__ import annotations
import argparse, json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(BASE))

import _bgc_probe as P  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["falsearm", "truearm"], default="falsearm")
    ap.add_argument("--seed", type=int, default=101)
    ap.add_argument("--wind", default="east")
    ap.add_argument("--roles", choices=["half", "default"], default="half")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--out")
    a = ap.parse_args()

    forced = (a.mode == "truearm")
    # the single-line counterfactual
    P.corrected_belief_gap_critical = lambda bg, s, t: forced

    ft, vs = (2, 2) if a.roles == "half" else (None, None)
    p = P.params(a.wind, ft, vs)
    label = "D/%s/%s" % (a.wind, a.roles)

    P.install(arm=True)          # arm=True -> the hook RETURNS the patched value
    base = P.run(a.seed, p, a.steps, True)

    res = dict(P.REC)
    res.update({"label": label, "seed": a.seed, "steps": a.steps, "mode": a.mode,
                "eval": base["eval"], "stdout_sha256": base["stdout_sha256"],
                "agent_positions_sha256": base["agent_positions_sha256"]})
    ser = P._mode_series(res)
    returned_true = sum(1 for c in res["crit"] if c["corrected"])
    print("%-9s %s|%-4d crit=%d returned_True=%d live_would_be_True=%d | "
          "first_nonnormal=%s | rescued=%s dead=%s ff=%s nd=%s ts=%s | modes=%s"
          % (a.mode, label, a.seed, res["crit_calls"], returned_true,
             sum(1 for c in res["crit"] if c["live"]),
             next((s for s, m in ser if m != "normal"), None),
             base["eval"].get("rescued"), base["eval"].get("dead"),
             base["eval"].get("firefighter_deaths"),
             base["eval"].get("never_detected"),
             base["eval"].get("terminal_step"),
             json.dumps(P._runlen(ser))[:160]),
          flush=True)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, default=str)
