"""Read-only reliability of the DEAD share: every (run, sampled step 10..360, undetected victim) triple,
binned by the recorded dead_mass; the fraction of those victims truly dead (rows_vic[s-1] status) per bin.
Triples are correlated within a run (one D per step, shared by all undetected victims) - descriptive only."""
import sys
sys.path.insert(0, r'E:\Projects\SAS\outputs'); sys.argv=['x']
import _fb3_analyze as A
BINS = [0.0, 0.25, 0.5, 0.75, 0.9, 1.0001]
def rel(tags):
    cnt = [[0, 0, 0.0, set()] for _ in BINS[:-1]]   # n, dead, sum D, runs
    for tag in tags:
        for k, d in sorted(A.load(tag).items()):
            det = A.det_times(d)
            for r in d['fb3']['coverage']:
                if not (isinstance(r, list) and len(r) > 2 and isinstance(r[2], dict)): continue
                s, D = r[0], r[2]['dead_mass']
                row = d['rows_vic'][s - 1]
                for x in row:
                    if det.get(x[0]) is not None and s >= det[x[0]]: continue
                    if x[3] == 'rescued': continue
                    b = next(i for i in range(len(BINS) - 1) if BINS[i] <= D < BINS[i + 1])
                    c = cnt[b]; c[0] += 1; c[1] += (x[3] == 'dead'); c[2] += D; c[3].add((tag, k, x[0]))
    for i, c in enumerate(cnt):
        if c[0]:
            print('   D in [%.2f,%.2f): victim-steps %4d  mean D %.3f  truly dead %.3f  (distinct victims %d)'
                  % (BINS[i], min(BINS[i + 1], 1.0), c[0], c[2] / c[0], c[1] / c[0], len(c[3])))
print('RE-SCREEN, burn-over 0.1, diffusion (fb3bdr, fb3bdr2)'); rel(("fb3bdr", "fb3bdr2"))
print('RE-SCREEN, burn-over 0.1, flee (fb3bfr, fb3bfr2, fb3vs3r)'); rel(("fb3bfr", "fb3bfr2", "fb3vs3r"))
print('SCREEN, burn-over 0.5, diffusion (fb3bd, fb3bd2)'); rel(("fb3bd", "fb3bd2"))
print('SCREEN, burn-over 0.5, flee (fb3bf, fb3bf2, fb3vs3)'); rel(("fb3bf", "fb3bf2", "fb3vs3"))
