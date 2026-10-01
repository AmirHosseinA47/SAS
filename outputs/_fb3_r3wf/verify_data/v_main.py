"""Independent verification of analysis 'data' (A2). Read-only on recorded JSON."""
import sys, re, os, math, statistics, collections
sys.path.insert(0, r'E:\Projects\SAS\outputs'); sys.argv = ['x']
import numpy as np
import _fb3_analyze as A

OUT = r'E:\Projects\SAS\outputs'
RES = ('fb3bdr', 'fb3bfr', 'fb3bdr2', 'fb3bfr2', 'fb3vs3r')
SCR = ('fb3bd', 'fb3bf', 'fb3bd2', 'fb3bf2', 'fb3vs3')
REF = {'fb3bdr': 'fx3mS', 'fb3bfr': 'fx3mS', 'fb3bdr2': 'fx3mS2', 'fb3bfr2': 'fx3mS2', 'fb3vs3r': 'fb3vs0'}
H = W = 50
R8 = [(dx, dy) for dx in range(-8, 9) for dy in range(-8, 9) if dx * dx + dy * dy <= 64]
DET = re.compile(r'\[Victim Detection\] step=(\d+) UAV-(\S+) detected (\S+) at \((\-?\d+), (\-?\d+)\)')
POOL = [(x, y) for x in range(4, 46) for y in range(4, 46) if x % 2 == 0 and y % 2 == 0]
POOL_A = np.array(POOL, dtype=float)


def disc(cells):
    m = np.zeros((H, W), bool)
    off = np.array(R8)
    for cx, cy in cells:
        xs = off[:, 0] + cx; ys = off[:, 1] + cy
        k = (xs >= 0) & (xs < H) & (ys >= 0) & (ys < W)
        m[xs[k], ys[k]] = True
    return m


def det_lines(tag, seed):
    p = os.path.join(OUT, '_sd_%s_%s.stdout.txt' % (tag, seed))
    res = {}
    for line in open(p, encoding='utf-8', errors='replace'):
        m = DET.search(line)
        if m and m.group(3) not in res:
            res[m.group(3)] = (int(m.group(1)), m.group(2), (int(m.group(4)), int(m.group(5))))
    return res


def vstat(d, s, v):
    row = d['rows_vic'][s - 1] if 1 <= s <= len(d['rows_vic']) else None
    if not row:
        return None
    return next((x for x in row if x[0] == v), None)


def samples(d):
    return [(r[0], r[2]['dead_mass'], r[2]['n_unfound'], r[2]['alive_mass']) for r in d['fb3']['coverage']
            if isinstance(r, list) and len(r) > 2 and isinstance(r[2], dict)]


def classify(tag):
    runs = A.load(tag)
    flagged, nonfl = [], []
    mono_bad = 0
    nunf_bad_le = nunf_bad_lt = ntot = 0
    for seed, d in sorted(runs.items()):
        sm = samples(d)
        det = A.det_times(d)
        nb = len(d['rows_vic'][0])
        for i in range(1, len(sm)):
            if sm[i][1] < sm[i - 1][1] - 1e-9:
                mono_bad += 1
        for s, dead, nu, al in sm:
            ntot += 1
            if nu != nb - sum(1 for v, t in det.items() if t is not None and t <= s):
                nunf_bad_le += 1
            if nu != nb - sum(1 for v, t in det.items() if t is not None and t < s):
                nunf_bad_lt += 1
        for v in sorted(det):
            pts = []
            for s, dead, nu, al in sm:
                if det[v] is not None and s >= det[v]:
                    continue
                x = vstat(d, s, v)
                if x is None or x[3] in ('dead', 'rescued') or nu <= 0:
                    continue
                pts.append((s, dead))
            if not pts:
                continue
            mx = max(pts, key=lambda p: p[1])
            first = next((s for s, dd in pts if dd > 0.5), None)
            rec = dict(tag=tag, seed=seed, v=v, max=mx[1], at=mx[0], first=first, det=det[v], pts=pts)
            (flagged if first is not None else nonfl).append(rec)
    return flagged, nonfl, mono_bad, nunf_bad_le, nunf_bad_lt, ntot


def main():
    print('=' * 100, '\nF0 classification')
    FL, NF = [], []
    for tag in RES:
        f, n, mb, b1, b2, nt = classify(tag)
        FL += f; NF += n
        print(tag, 'flagged', len(f), 'nonflagged', len(n), 'mono_bad', mb, 'nunf mismatch (<=s)', b1, '(<s)', b2, 'of', nt)
    for r in FL:
        d = A.load(r['tag'])[r['seed']]
        fate = d['rows_vic'][-1]
        fin = next(x[3] for x in fate if x[0] == r['v'])
        print('  %-8s %s %-9s first %s max %.4f@%d det %s final %s spawn %s' % (
            r['tag'], r['seed'], r['v'], r['first'], r['max'], r['at'], r['det'], fin, d['rows_vic'][0] and
            next((x[1], x[2]) for x in d['rows_vic'][0] if x[0] == r['v'])))
    pairs = {(('set1' if r['tag'] in ('fb3bdr', 'fb3bfr') else 'set2' if r['tag'] in ('fb3bdr2', 'fb3bfr2') else 'vs'), r['seed'], r['v']) for r in FL}
    print('flagged', len(FL), 'distinct pairs', len(pairs), 'nonflagged', len(NF))

    # ---------------- F1 target distances
    print('=' * 100, '\nF1 issued target distance')

    def window(d, r):
        end = (r['det'] - 1) if r['det'] is not None else len(d['rows_vic'])
        out = []
        for s in range(1, end + 1):
            x = vstat(d, s, r['v'])
            if x is None or x[3] in ('dead', 'rescued'):
                continue
            out.append(s)
        return out

    def issue_stats(group, late):
        dists, ch8, ch16, n8, n16 = [], [], [], 0, 0
        for r in group:
            d = A.load(r['tag'])[r['seed']]
            ws = set(window(d, r))
            lo = (r['first'] if late == 'first' else 70 if late == 70 else 0)
            for row in d['fb3']['issued']:
                s = row[0]
                if s not in ws or s < lo:
                    continue
                x = vstat(d, s, r['v'])
                vx, vy = x[1], x[2]
                t = row[2]
                dd = math.hypot(t[0] - vx, t[1] - vy)
                dists.append(dd)
                n8 += dd <= 8; n16 += dd <= 16
                pd = np.hypot(POOL_A[:, 0] - vx, POOL_A[:, 1] - vy)
                ch8.append((pd <= 8).mean()); ch16.append((pd <= 16).mean())
        n = len(dists)
        if not n:
            return 'n=0'
        return 'n=%d min %.1f med %.1f w8 %.3f (ch %.3f, %.2fx) w16 %.3f (ch %.3f, %.2fx)' % (
            n, min(dists), statistics.median(dists), n8 / n, np.mean(ch8), (n8 / n) / np.mean(ch8), n16 / n,
            np.mean(ch16), (n16 / n) / np.mean(ch16))
    print('FLAGGED full   ', issue_stats(FL, 0))
    print('FLAGGED >=first', issue_stats(FL, 'first'))
    print('NONFL full     ', issue_stats(NF, 0))
    print('NONFL >=70     ', issue_stats(NF, 70))

    # moves / window length
    def motion(group):
        mv, wl, mps = [], [], []
        for r in group:
            d = A.load(r['tag'])[r['seed']]
            ws = window(d, r)
            if not ws:
                continue
            pos = [tuple(vstat(d, s, r['v'])[1:3]) for s in ws]
            m = sum(1 for i in range(1, len(pos)) if pos[i] != pos[i - 1])
            mv.append(m); wl.append(len(ws))
        return 'moves med %s, total moves/steps %.3f, window med %s' % (statistics.median(mv), sum(mv) / sum(wl), statistics.median(wl))
    print('motion FL', motion(FL)); print('motion NF', motion(NF))

    # ---------------- F2 coverage
    print('=' * 100, '\nF2 coverage around victims')
    cover_cache = {}

    def covers(tag, seed, d):
        k = (tag, seed)
        if k not in cover_cache:
            cover_cache[k] = [disc([(u[1], u[2]) for u in row if u[1] is not None]) for row in d['rows_uav']]
        return cover_cache[k]

    def cov_stats(group, late):
        acc = collections.defaultdict(list)
        for r in group:
            d = A.load(r['tag'])[r['seed']]
            C = covers(r['tag'], r['seed'], d)
            lo = r['first'] if late == 'first' else 70 if late == 70 else 0
            for s in window(d, r):
                if s < lo:
                    continue
                x = vstat(d, s, r['v']); vx, vy = x[1], x[2]
                dm = disc([(vx, vy)])
                prev30 = np.zeros((H, W), bool)
                for t in range(max(1, s - 30), s):
                    prev30 |= C[t - 1]
                prev10 = np.zeros((H, W), bool)
                for t in range(max(1, s - 10), s):
                    prev10 |= C[t - 1]
                ever = np.zeros((H, W), bool)
                last = None
                for t in range(1, s):
                    ever |= C[t - 1]
                    if C[t - 1][vx, vy]:
                        last = t
                acc['d8_p10'].append(prev10[dm].mean()); acc['g_p10'].append(prev10.mean())
                acc['d8_p30'].append(prev30[dm].mean()); acc['g_p30'].append(prev30.mean())
                acc['d8_ever'].append(ever[dm].mean()); acc['g_ever'].append(ever.mean())
                acc['own'].append(last is not None)
                if last is not None:
                    acc['age'].append(s - last)
                e = min(vx, vy, H - 1 - vx, W - 1 - vy)
                acc['edge'].append(e); acc['edge4'].append(e <= 4)
        n = len(acc['own'])
        return ('n=%d d8p10 %.3f (g %.3f) d8p30 %.3f (g %.3f) ever %.3f (g %.3f) own %.3f age med %s edge med %s <=4 %.3f' % (
            n, np.mean(acc['d8_p10']), np.mean(acc['g_p10']), np.mean(acc['d8_p30']), np.mean(acc['g_p30']),
            np.mean(acc['d8_ever']), np.mean(acc['g_ever']), np.mean(acc['own']),
            statistics.median(acc['age']) if acc['age'] else None, statistics.median(acc['edge']), np.mean(acc['edge4'])))
    print('FL >=first', cov_stats(FL, 'first'))
    print('NF >=70   ', cov_stats(NF, 70))
    print('FL full   ', cov_stats(FL, 0))
    print('NF full   ', cov_stats(NF, 0))
    for r in FL:
        print('   per-victim own-covered', r['tag'], r['seed'], r['v'], cov_stats([r], 'first'))

    # ---------------- F3 detection attribution
    print('=' * 100, '\nF3 detection attribution')
    cnt = collections.Counter(); cntN = collections.Counter()
    for grp, cn in ((FL, cnt), (NF, cntN)):
        for r in grp:
            if r['det'] is None:
                if grp is FL:
                    print('   never detected', r['tag'], r['seed'], r['v'])
                continue
            d = A.load(r['tag'])[r['seed']]
            dl = det_lines(r['tag'], r['seed'])[r['v']]
            t, uid, vpos = dl
            if grp is NF and t < 10:
                continue
            u_t = next((u for u in d['rows_uav'][t - 1] if u[0] == uid), None)
            u_p = next((u for u in d['rows_uav'][t - 2] if u[0] == uid), None) if t >= 2 else None
            key = (u_t[3], A.mech(u_t[8]), A.mech(u_p[8]) if u_p else None)
            cn[key] += 1
            if grp is FL:
                vx, vy = vpos
                vrow = vstat(d, t, r['v'])
                dt = math.hypot(u_t[1] - vx, u_t[2] - vy); dp = math.hypot(u_p[1] - vx, u_p[2] - vy)
                # active target: latest issued for uid at step <= t
                iss = [row for row in d['fb3']['issued'] if row[1] == uid and row[0] <= t]
                at = iss[-1] if iss else None
                atd = math.hypot(at[2][0] - vx, at[2][1] - vy) if at else None
                print('   %-8s %s %-9s det %d UAV %s key %s d_t %.1f d_t-1 %.1f vpos %s rowvic %s lastissue %s dist %s' % (
                    r['tag'], r['seed'], r['v'], t, uid, key, dt, dp, vpos, vrow[1:3], at, None if atd is None else round(atd, 1)))
    print('FLAGGED', dict(cnt)); print('NONFL det>=10', dict(cntN), 'total', sum(cntN.values()))

    # ---------------- F4 paired detection delay
    print('=' * 100, '\nF4 paired reference')
    deltas = []
    for r in FL:
        d = A.load(r['tag'])[r['seed']]
        ref = A.load(REF[r['tag']]).get(r['seed'])
        if ref is None:
            print('  no ref', r); continue
        p0a = [tuple(x[:3]) for x in d['rows_vic'][0]]; p0b = [tuple(x[:3]) for x in ref['rows_vic'][0]]
        same0 = p0a == p0b
        tr = A.det_times(ref).get(r['v'])
        ta = r['det']
        div = None
        for s in range(1, min(len(d['rows_vic']), len(ref['rows_vic'])) + 1):
            a = vstat(d, s, r['v']); b = vstat(ref, s, r['v'])
            if a is None or b is None or a[1:3] != b[1:3]:
                div = s; break
        A_ = ta if ta is not None else 361; B_ = tr if tr is not None else 361
        if A_ != 361 and B_ != 361 and A_ > B_:
            deltas.append(A_ - B_)
        print('  %-8s %s %-9s arm %s ref %s delta %s same_t1 %s diverge %s ref_before_div %s' % (
            r['tag'], r['seed'], r['v'], ta, tr, A_ - B_, same0, div, (tr is not None and div is not None and tr < div) or (tr is not None and div is None)))
    print('finite positive deltas', sorted(deltas), 'median', statistics.median(deltas) if deltas else None)

    # ---------------- F5 G vs DEAD
    print('=' * 100, '\nF5 G vs DEAD')
    for fam, tags in (('diff', ('fb3bdr', 'fb3bdr2')), ('flee', ('fb3bfr', 'fb3bfr2', 'fb3vs3r'))):
        for rule in ('prev', 'nearest'):
            lo, hi = [], []
            for tag in tags:
                for seed, d in A.load(tag).items():
                    sm = samples(d)
                    for row in d['fb3']['issued']:
                        if row[4] is None:
                            continue
                        s = row[0]
                        if rule == 'prev':
                            c = [x for x in sm if x[0] <= s - 1]
                            if not c:
                                continue
                            dead = c[-1][1]
                        else:
                            dead = min(sm, key=lambda x: abs(x[0] - s))[1]
                        (hi if dead > 0.5 else lo).append(row[4])
            print('  %s %-7s DEAD<=.5 n %d med %.4f  <5e-6 %d | DEAD>.5 n %d med %.4f <5e-6 %d' % (
                fam, rule, len(lo), statistics.median(lo), sum(1 for g in lo if g < 5e-6), len(hi),
                statistics.median(hi) if hi else float('nan'), sum(1 for g in hi if g < 5e-6)))

    # ---------------- F6 counters
    print('=' * 100, '\nF6 counters')
    flr = {(r['tag'], r['seed']) for r in FL}
    W_, WO = collections.defaultdict(list), collections.defaultdict(list)
    for tag in RES:
        for seed, d in A.load(tag).items():
            tot = collections.Counter()
            for uid, c in d['fb3']['stats'].items():
                tot.update(c)
            bd = tot['delivered_steps'] - tot['lo_continuation_steps']
            g = W_ if (tag, seed) in flr else WO
            g['swept'].append(tot['drop_swept']); g['bd'].append(bd)
            g['swept_per_bd'].append(tot['drop_swept'] / bd if bd else 0.0)
            g['sel'].append(tot['selections'])
    for name, g in (('WITH', W_), ('WITHOUT', WO)):
        print('  %s runs %d swept mean %.2f med %s per-bd mean %.3f bd med %s sel mean %.1f' % (
            name, len(g['swept']), np.mean(g['swept']), statistics.median(g['swept']), np.mean(g['swept_per_bd']),
            statistics.median(g['bd']), np.mean(g['sel'])))

    # ---------------- F7 per-arm
    print('=' * 100, '\nF7 per arm')
    for tag in SCR + RES:
        f, n, *_ = classify(tag)
        allp = [dd for r in f + n for s, dd in r['pts']]
        runs = A.load(tag)
        d100 = [next(x[1] for x in samples(d) if x[0] == 100) for d in runs.values()]
        d360 = [samples(d)[-1][1] for d in runs.values()]
        bo = {str(d['fb3']['switches'].get('SEARCHER_BELIEF_BURNOVER')) for d in runs.values()}
        print('  %-8s bo %s n %d max %.4f med %.4f share>.5 %.3f victims>.5 %d/%d DEAD@100 %.3f @360 %.3f' % (
            tag, bo, len(allp), max(allp), statistics.median(allp), sum(1 for x in allp if x > 0.5) / len(allp),
            len(f), len(f) + len(n), statistics.median(d100), statistics.median(d360)))


main()
