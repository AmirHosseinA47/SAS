"""Extra independent checks: F1 nearest-searcher + active-target, F4 X3 medians, F5 correlations, F6 steered share."""
import sys, math, statistics, collections
sys.path.insert(0, r'C:\Users\ahrar\AppData\Local\Temp\claude\E--Projects-SAS\aeac90fa-d510-40d8-a309-ad58f8606230\scratchpad\r3wf\verify_data')
sys.path.insert(0, r'E:\Projects\SAS\outputs'); sys.argv = ['x']
import numpy as np
import _fb3_analyze as A
import importlib.util
spec = importlib.util.spec_from_file_location('vm', r'C:\Users\ahrar\AppData\Local\Temp\claude\E--Projects-SAS\aeac90fa-d510-40d8-a309-ad58f8606230\scratchpad\r3wf\verify_data\v_main.py')
src = open(spec.origin).read().replace('\nmain()\n', '\n')
vm = {}
exec(compile(src, 'v_main', 'exec'), vm)
RES = vm['RES']; classify = vm['classify']; vstat = vm['vstat']; samples = vm['samples']

FL, NF = [], []
for tag in RES:
    f, n, *_ = classify(tag); FL += f; NF += n


def window(d, r):
    end = (r['det'] - 1) if r['det'] is not None else len(d['rows_vic'])
    return [s for s in range(1, end + 1) if (lambda x: x is not None and x[3] not in ('dead', 'rescued'))(vstat(d, s, r['v']))]


def airborne(u):
    return not (u[5] or u[6])


print('F1 nearest searcher distance, active target within 8')
for name, grp in (('FL', FL), ('NF', NF)):
    nd_all, nd_air = [], []
    act_full, act_late = [], []
    for r in grp:
        d = A.load(r['tag'])[r['seed']]
        iss = collections.defaultdict(list)
        for row in d['fb3']['issued']:
            iss[row[1]].append(row)
        lo = r['first'] if name == 'FL' else 70
        for s in window(d, r):
            x = vstat(d, s, r['v']); vx, vy = x[1], x[2]
            row = d['rows_uav'][s - 1]
            sr = [u for u in row if u[3] == 'victim_searcher']
            if sr:
                nd_all.append(min(math.hypot(u[1] - vx, u[2] - vy) for u in sr))
            sa = [u for u in sr if airborne(u)]
            if sa:
                nd_air.append(min(math.hypot(u[1] - vx, u[2] - vy) for u in sa))
            for u in sr:
                if u[8] != 'victim_search_targeting':
                    continue
                prev = [q for q in iss[u[0]] if q[0] <= s]
                if not prev:
                    continue
                t = prev[-1][2]
                w8 = math.hypot(t[0] - vx, t[1] - vy) <= 8
                act_full.append(w8)
                if s >= lo:
                    act_late.append(w8)
    print('  %s nearest searcher med (any) %.1f (airborne) %.1f | active-target within 8: full %.3f (n %d) late %.3f (n %d)' % (
        name, statistics.median(nd_all), statistics.median(nd_air), np.mean(act_full), len(act_full), np.mean(act_late), len(act_late)))

print('F4 X3: first step a searcher within 8 of (40,25); victim_0 first detection; medians over seeds')
for tag in ('fx3mS', 'fb3bdr', 'fb3bfr', 'fx3mS2', 'fb3bdr2', 'fb3bfr2'):
    fs, dv, fs_any = [], [], []
    for seed, d in A.load(tag).items():
        f = next((t + 1 for t, row in enumerate(d['rows_uav']) if any(u[3] == 'victim_searcher' and math.hypot(u[1] - 40, u[2] - 25) <= 8 for u in row)), 361)
        fa = next((t + 1 for t, row in enumerate(d['rows_uav']) if any(math.hypot(u[1] - 40, u[2] - 25) <= 8 for u in row)), 361)
        fs.append(f); fs_any.append(fa)
        t0 = A.det_times(d).get('victim_0'); dv.append(t0 if t0 is not None else 361)
    print('  %-8s searcher-within-8 med %s | any UAV %s | victim_0 det med %s' % (tag, statistics.median(fs), statistics.median(fs_any), statistics.median(dv)))

print('F5 correlations G vs n_unf*alive (nearest sample, n_unf = n_brief - #det<=s-1)')


def rank(a):
    a = np.asarray(a); o = a.argsort(); r = np.empty(len(a)); r[o] = np.arange(len(a))
    # average ties
    vals, inv, cnt = np.unique(a, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, r); return (sums / cnt)[inv]


pool_lo, pool_hi = [], []
for fam, tags in (('diff', ('fb3bdr', 'fb3bdr2')), ('flee', ('fb3bfr', 'fb3bfr2', 'fb3vs3r'))):
    G, X = [], []
    for tag in tags:
        for seed, d in A.load(tag).items():
            sm = samples(d); det = A.det_times(d); nb = len(d['rows_vic'][0])
            for row in d['fb3']['issued']:
                if row[4] is None:
                    continue
                s = row[0]
                smp = min(sm, key=lambda x: abs(x[0] - s))
                nu = nb - sum(1 for t in det.values() if t is not None and t <= s - 1)
                G.append(row[4]); X.append(nu * smp[3])
                (pool_hi if smp[1] > 0.5 else pool_lo).append(row[4])
    G = np.array(G); X = np.array(X)
    pe = np.corrcoef(G, X)[0, 1]; sp = np.corrcoef(rank(G), rank(X))[0, 1]
    k = (G > 0) & (X > 0)
    ll = np.corrcoef(np.log(G[k]), np.log(X[k]))[0, 1]
    print('  %s n %d pearson %.3f spearman %.3f loglog %.3f' % (fam, len(G), pe, sp, ll))
print('  pooled G median DEAD<=.5 %.4f  DEAD>.5 %.4f' % (statistics.median(pool_lo), statistics.median(pool_hi)))

print('F6 steered share of airborne searcher steps while an undetected victim remains, by DEAD side')
for tag in RES:
    c = collections.Counter()
    for seed, d in A.load(tag).items():
        sm = samples(d); det = A.det_times(d)
        last_det = max((t for t in det.values() if t is not None), default=0)
        never = any(t is None for t in det.values())
        for s in range(1, len(d['rows_uav']) + 1):
            if not never and s >= last_det:
                continue
            prv = [x for x in sm if x[0] <= s]; nxt = [x for x in sm if x[0] >= s]
            if prv and prv[-1][1] > 0.5:
                side = 'hi'
            elif nxt and nxt[0][1] <= 0.5:
                side = 'lo'
            else:
                continue
            for u in d['rows_uav'][s - 1]:
                if u[3] == 'victim_searcher' and airborne(u):
                    c[(side, 'n')] += 1
                    c[(side, 'tg')] += u[8] == 'victim_search_targeting'
            c[(side, 'iss')] += sum(1 for row in d['fb3']['issued'] if row[0] == s)
    print('  %-8s steered lo %.3f hi %.3f | issues/searcher-step lo %.3f hi %.3f' % (
        tag, c[('lo', 'tg')] / c[('lo', 'n')], c[('hi', 'tg')] / max(1, c[('hi', 'n')]),
        c[('lo', 'iss')] / c[('lo', 'n')], c[('hi', 'iss')] / max(1, c[('hi', 'n')])))
