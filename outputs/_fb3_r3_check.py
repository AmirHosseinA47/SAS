"""fix3b R-3 check (read-only, recorded runs only): did the belief ever put more than half of an ALIVE,
UNDETECTED victim's probability on DEAD?

The belief is one posterior p (over cells + an absorbing DEAD state, p.sum() + dead = 1) shared by every
undetected victim (i.i.d. uniform prior), so a victim's DEAD share at step s is the recorded dead_mass,
for every victim that is truly alive (rows_vic status not 'dead') and not yet detected (s < first
detection) at s. Detected victims leave the belief.

INSTRUMENT LIMIT: _fb3_probe.py records the belief summary every 10 steps and at the last step, not
every step. The maxima below are over that sample - a LOWER BOUND on the per-step maximum.

usage (repo root): .venv/Scripts/python.exe -B outputs/_fb3_r3_check.py [tag ...]
  default: the re-screen Bayes arms (burn-over 0.1) and, for reference, the screen's (burn-over 0.5).
"""
import sys

sys.path.insert(0, r"E:\Projects\SAS\outputs")
TAGS, sys.argv = sys.argv[1:], sys.argv[:1]
import _fb3_analyze as A  # noqa: E402

RESCREEN = ("fb3bdr", "fb3bfr", "fb3bdr2", "fb3bfr2", "fb3vs3r")
SCREEN = ("fb3bd", "fb3bf", "fb3bd2", "fb3bf2", "fb3vs3")
THRESH = 0.5


def check(tag):
    rows_out, fails = [], []
    for seed, d in sorted(A.load(tag).items()):
        fb = d.get("fb3") or {}
        samples = [(r[0], r[2]["dead_mass"], r[2]["n_unfound"]) for r in fb.get("coverage") or []
                   if isinstance(r, list) and len(r) > 2 and isinstance(r[2], dict)]
        det = A.det_times(d)
        for v in sorted(det):
            best = None                       # (dead share, step) over sampled steps alive + undetected
            for s, dead, n_unf in samples:
                if det[v] is not None and s >= det[v]:
                    continue
                row = d["rows_vic"][s - 1] if s - 1 < len(d["rows_vic"]) else None
                st = next((x[3] for x in row if x[0] == v), None) if row else None
                if st in ("dead", "rescued") or st is None:
                    continue
                if n_unf <= 0:                # the belief holds no unfound victim (cannot happen while v is)
                    continue
                if best is None or dead > best[0]:
                    best = (dead, s)
                if dead > THRESH:
                    fails.append((seed, v, s, round(dead, 4)))
            if best is None:
                continue                      # never alive and undetected at a sampled step
            fate = ("found at %d" % det[v]) if det[v] is not None else "never found"
            final = next((x[3] for x in d["rows_vic"][-1] if x[0] == v), "?")
            rows_out.append((seed, v, round(best[0], 4), best[1], fate, final))
    return rows_out, fails


def main():
    for group, tags in (("RE-SCREEN (burn-over 0.1) - the R-3 check", TAGS or RESCREEN),
                        ("SCREEN (burn-over 0.5) - reference only", () if TAGS else SCREEN)):
        if not tags:
            continue
        print("=" * 110)
        print(group + ": max DEAD share of an alive, undetected victim (sampled every 10 steps); FAIL > %.2f" % THRESH)
        for tag in tags:
            rows, fails = check(tag)
            if not rows:
                print("  %-8s no belief samples" % tag)
                continue
            mx = max(rows, key=lambda r: r[2])
            over = [r for r in rows if r[2] > THRESH]
            print("  %-8s victims %d | max %.4f (%s %s step %d, %s, final %s) | victims > %.2f: %d | FAIL samples %d"
                  % (tag, len(rows), mx[2], mx[0], mx[1], mx[3], mx[4], mx[5], THRESH, len(over), len(fails)))
            for r in sorted(rows, key=lambda r: -r[2])[:5]:
                print("           top: %s %-9s max DEAD %.4f at step %d | %s | final %s" % r)
            firsts = {}
            for f in fails:
                firsts.setdefault((f[0], f[1]), f[2])
            for r in sorted(over, key=lambda r: (r[0], r[1])):
                print("           *** FAIL: run %s %-9s first > %.2f at step %d | max %.4f at step %d | %s | final %s" % (
                    r[0], r[1], THRESH, firsts[(r[0], r[1])], r[2], r[3], r[4], r[5]))
            for f in fails:
                print("           sample > %.2f: run %s %s step %d DEAD share %.4f" % ((THRESH,) + f))
            for r in rows:
                print("           all: %s %-9s %.4f @%d | %s | %s" % r)


if __name__ == "__main__":
    main()
