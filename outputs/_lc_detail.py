"""Full surv-record dump for the 12 last_cell-sole-exit events + the C4 unit."""
from __future__ import annotations
import glob, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = {
    ("east_default_101", 101, 38), ("east_default_303", 303, 55),
    ("east_half_303", 303, 55), ("east_half_404", 404, 29),
    ("east_half_505", 505, 63), ("east_half_505", 505, 56),
    ("east_default_202", 202, 213), ("east_default_202", 202, 218),
    ("south_half_101", 101, 133),
}
KEYS = ("step", "ff", "pos", "idle", "target_pos", "exiting", "stalled_pre",
        "origin", "retreat_steps", "last_cell", "on_fire", "smoke",
        "cur_dist", "n_inbounds", "n_free", "n_safe", "n_ideal",
        "best_free_dist", "strictly_better_exists", "free_cells",
        "excl_fire", "excl_lastcell", "excl_leash", "n_candidates",
        "post_pos", "moved", "stalled_post", "post_dist")
for fp in sorted(glob.glob(os.path.join(HERE, "_ir_p3_POST_*.json"))):
    tag = os.path.basename(fp)[len("_ir_p3_POST_"):-len(".json")]
    d = json.load(open(fp))
    for r in d.get("surv") or []:
        k = (tag, r.get("seed"), r.get("step"))
        if k not in TARGETS:
            continue
        print("=" * 74)
        print("%s  seed=%s  step=%s" % (tag, r.get("seed"), r.get("step")))
        for kk in KEYS:
            if kk in r:
                print("   %-24s %s" % (kk, r[kk]))
    # what the fftrace says the unit did in the following steps
    want = {(tag, s, st) for (tag, s, st) in TARGETS if tag == os.path.basename(fp)[len("_ir_p3_POST_"):-len(".json")]}
    for (t, s, st) in sorted(want):
        rows = [x for x in d.get("fftrace") or []
                if x.get("seed") == s and st - 1 <= x.get("step", 0) <= st + 4]
        if rows:
            print("-- fftrace %s seed %s steps %d..%d --" % (t, s, st - 1, st + 4))
            for x in sorted(rows, key=lambda y: (y["step"], y["ff"])):
                print("    step %-4s %-11s pos %-9s dead=%-5s status=%-14s "
                      "assigned=%-5s tgt=%-9s mfd=%-4s free=%-3s cat=%s"
                      % (x["step"], x["ff"], x.get("pos"), x.get("dead"),
                         x.get("status"), x.get("assigned"), x.get("target"),
                         x.get("mfd"), x.get("n_free"), x.get("cat")))
