"""A1 synthetic checks (no simulator, no pytest): belief algebra + planner scale invariance + swept behaviour.
Imports repo modules read-only (python -B)."""
import sys, random
sys.path.insert(0, r"E:\Projects\SAS")
sys.path.insert(0, r"E:\Projects\SAS\tests")
import numpy as np
import agents
import common_fixed_variables as cfv
from src_extension.knowledge.victim_search_belief import VictimSearchBelief, MotionParams, disc_mask, disc_offsets, disc_convolve
from src_extension.planning import searcher_targeting as stg
from src_extension.planning.decision_objects import PathDecision
from test_uav_executor import _bfs_test_model

H = W = 50
STEP = 30

# ---------------- 1. measure algebra -------------------------------------------------------
b = VictimSearchBelief.with_uniform_prior(H, W, 5, excluded=())
b.p = b.p * 0.8; b.dead = 0.2                    # A=0.8, D=0.2
p0 = b.p.copy(); D0 = b.dead
cover = disc_mask(H, W, [(10, 10), (30, 30)], b.offsets)
r = float(p0[cover].sum())
b.measure([(10, 10), (30, 30)], set(), step=1)
print("1. measure: r=%.6f  D0=%.4f  D'=%.6f  D0/(1-r)=%.6f  uncovered ratio p'/p=%.6f  1/(1-r)=%.6f  sum=%.12f"
      % (r, D0, b.dead, D0 / (1 - r), float(b.p[0, 49] / p0[0, 49]), 1 / (1 - r), b.p.sum() + b.dead))

# ---------------- 2. burn_over ---------------------------------------------------------------
burn = {(x, 20) for x in range(10, 30)}
for pbo in (0.0, 0.1, 0.5):
    bb = VictimSearchBelief.with_uniform_prior(H, W, 5, excluded=())
    bb.p = bb.p * 0.9; bb.dead = 0.1
    pb = bb.p.copy(); Db = bb.dead
    mB = sum(float(pb[c]) for c in burn)
    bb.burn_over(burn, pbo)
    off = np.ones((H, W), bool)
    for c in burn: off[c] = False
    print("2. burn_over p_bo=%.1f: dead %.6f -> %.6f (pred %.6f); off-fire cells unchanged: %s; sum=%.12f"
          % (pbo, Db, bb.dead, Db + pbo * mB, bool(np.array_equal(bb.p[off], pb[off])), bb.p.sum() + bb.dead))

# ---------------- 3. planner scale invariance ------------------------------------------------
shipped = {"VICTIM_SEARCHER_HAZARD_RETREAT_RANGE": 99, "SEARCHER_GATE_NEAR_FIELD": 1, "SEARCHER_ROUTE_FIRE_FIELD": 1,
           "SEARCHER_CORNER_ESCAPE": 1, "SEARCHER_TARGETING_COORDINATION": 1, "SEARCHER_TARGETING_REACHABILITY": 1,
           "SEARCHER_TARGETING_BATTERY": 1, "SEARCHER_BELIEF_MOTION": 1, "SEARCHER_BELIEF_STRIDE": 2,
           "SEARCHER_TARGETING_TOP_M": 12, "SEARCHER_TARGETING_L0": 4, "SEARCHER_TARGETING_TILE": 7,
           "SEARCHER_TARGETING_AGE_BUCKET": 10}
for k, v in shipped.items():
    setattr(cfv, k, v)
agents.rtb_trigger_level_at = lambda uav, cell: 0.0


def _uav(uid, pos, battery=100.0):
    u = agents.UAV.__new__(agents.UAV)
    u.unique_id = uid; u.pos = tuple(pos); u.battery_level = float(battery)
    u.battery_drain_per_step = 0.1; u.battery_drain_per_move = 0.2; u.rtb_active = False; u.rtb_docked = False
    return u


def world(searchers, p, fire=(), mode=2, n_brief=3):
    model = _bfs_test_model(fire_cells=set(fire), smoke_cells=set())
    uavs = [_uav(uid, pos) for uid, pos in searchers]
    model.schedule.agents.extend(uavs)
    model.managed_uav_states = {str(u.unique_id): type("S", (), {"role": "victim_searcher"})() for u in uavs}
    model._wind_search_target_state = {}
    model.evaluation_timesteps_counter = STEP
    model._fix3b_true_fire = lambda: (set(fire), set())
    belief = VictimSearchBelief.with_uniform_prior(H, W, n_brief, excluded=())
    belief.p = p.copy()
    model.victim_search_belief = belief
    cfv.SEARCHER_TARGETING = mode
    dec = {str(u.unique_id): PathDecision(decision_id="d%s" % u.unique_id, uav_id=str(u.unique_id),
                                         selected_option_id="wind_aware_victim_search",
                                         next_action="victim_search_wind_aware") for u in uavs}
    return model, dec


def targets(out, uids):
    res = []
    for uid in uids:
        pts = out[str(uid)].waypoints_by_uav.get(str(uid))
        res.append((int(pts[0][0]), int(pts[0][1])) if pts else None)
    return res


rng = np.random.default_rng(7)
fire = {(x, 40) for x in range(H)}
searchers = [(2501, (25, 10)), (2502, (10, 20)), (2503, (40, 25))]
mismatch = 0
trials = 0
for trial in range(12):
    base = rng.gamma(0.3, 1.0, size=(H, W))
    base[rng.random((H, W)) < 0.4] = 0.0
    base /= base.sum()
    ref = None
    for c in (1.0, 0.5, 0.0022, 1e-3, 0.37):
        m, dec = world(searchers, base * c, fire=fire)
        out = stg.apply_searcher_targeting(dec, {"simulation_model": m})
        t = targets(out, [2501, 2502, 2503])
        trials += 1
        if ref is None:
            ref = t
            if trial < 3: print('   sample trial', trial, 'targets', t)
        elif t != ref:
            mismatch += 1
            print("   MISMATCH trial", trial, "c", c, t, ref)
print("3. scale invariance: %d planner calls, %d mismatches against c=1" % (trials, mismatch))

# ---------------- 4. swept rule vs global DEAD growth -----------------------------------------
p = np.zeros((H, W)); p[25, 22] = 0.4; p[45, 5] = 0.4
m, dec = world([(2502, (25, 10))], p, fire=(), mode=2, n_brief=1)
m.victim_search_belief.dead = 0.2
out = stg.apply_searcher_targeting(dec, {"simulation_model": m})
tgt = targets(out, [2502])[0]
st = m._searcher_targeting_state["2502"]
bel = m.victim_search_belief
print("4. issued", tgt, "s_issue=%.4f" % st["s_issue"])
# (a) global DEAD growth by measure elsewhere: cover (45,5) -> r = 0.5
bel.measure([(45, 5)], set(), step=31)
Sp = disc_convolve(bel.p, bel.offsets)
print("   after measure covering the other mass: dead=%.4f  Sp[target]=%.4f  (s_issue %.4f)" % (bel.dead, Sp[tgt], st["s_issue"]))
# (b) burn-over far from the target: none of the target disc burning
bel.burn_over({(45, 5), (0, 0)}, 0.5)
Sp = disc_convolve(bel.p, bel.offsets)
print("   after burn_over off-disc: dead=%.4f  Sp[target]=%.4f" % (bel.dead, Sp[tgt]))
# (c) a uniform downscale of p (no code path does this) would sweep
out = stg.apply_searcher_targeting(dec, {"simulation_model": m})
print("   planner still holds:", targets(out, [2502])[0], "drop_swept=", m._searcher_targeting_stats["2502"].get("drop_swept"))
# (d) burn-over ON the target disc at 0.1: steps to drop
for pbo in (0.1, 0.5):
    p = np.zeros((H, W)); p[25, 22] = 1.0
    m, dec = world([(2502, (25, 10))], p, fire=(), mode=2, n_brief=1)
    stg.apply_searcher_targeting(dec, {"simulation_model": m})
    s0 = m._searcher_targeting_state["2502"]["s_issue"]
    tg = tuple(m._searcher_targeting_state["2502"]["target"])
    bel = m.victim_search_belief
    k = 0
    while True:
        bel.burn_over({(25, 22)}, pbo)
        k += 1
        if float(disc_convolve(bel.p, bel.offsets)[tg]) < 0.25 * s0:
            break
    print("   burn-over %.1f on all of a held disc's mass (no renormalising measure): Sp < rho*S_issue after %d steps"
          % (pbo, k))
