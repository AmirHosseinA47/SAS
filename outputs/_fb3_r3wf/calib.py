"""Read-only calibration of the belief's DEAD state against the TRUE fate of the undetected victims.
At each sampled step s (every 10 steps): predicted dead-undetected = n_unfound * dead_mass, predicted
alive-undetected = n_unfound * alive_mass; actual = the undetected victims (det is None or det > s... strictly
s < det, as _fb3_r3_check) by their rows_vic status at s (rows_vic[s-1])."""
import sys
sys.path.insert(0, r'E:\Projects\SAS\outputs'); sys.argv=['x']
import _fb3_analyze as A
CHECK = (100, 150, 200, 250, 300)
def run(tag):
    tot = {s: [0.0, 0.0, 0, 0, 0] for s in CHECK}   # pred dead, pred alive, act dead, act alive, n_unf
    for k, d in sorted(A.load(tag).items()):
        det = A.det_times(d)
        for r in d['fb3']['coverage']:
            if not (isinstance(r, list) and len(r) > 2 and isinstance(r[2], dict)): continue
            s = r[0]
            if s not in tot: continue
            sm = r[2]
            row = d['rows_vic'][s - 1]
            und = [x for x in row if (det.get(x[0]) is None or s < det[x[0]])]
            ad = sum(1 for x in und if x[3] == 'dead'); aa = sum(1 for x in und if x[3] not in ('dead', 'rescued'))
            t = tot[s]
            t[0] += sm['n_unfound'] * sm['dead_mass']; t[1] += sm['n_unfound'] * sm['alive_mass']
            t[2] += ad; t[3] += aa; t[4] += sm['n_unfound']
    print(tag)
    for s in CHECK:
        t = tot[s]
        print('   step %3d  n_unfound %3d | predicted dead %.2f alive %.2f | actual undetected dead %d alive %d'
              % (s, t[4], t[0], t[1], t[2], t[3]))
for tag in ("fb3bdr","fb3bfr","fb3bdr2","fb3bfr2","fb3vs3r","fb3bd","fb3bf","fb3bd2","fb3bf2","fb3vs3"):
    run(tag)
