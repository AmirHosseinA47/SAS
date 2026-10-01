"""Shared helpers for task A2 (read-only on the repo; recorded JSON only)."""
import sys, os, re, math, collections, statistics
sys.path.insert(0, r'E:\Projects\SAS\outputs')
sys.path.insert(0, r'E:\Projects\SAS')
_saved = sys.argv
sys.argv = ['x']
import _fb3_analyze as A  # noqa
sys.argv = _saved
import numpy as np
from src_extension.knowledge.victim_search_belief import disc_offsets, disc_mask

OUT = os.path.dirname(os.path.abspath(__file__))
RESCREEN = ("fb3bdr", "fb3bfr", "fb3bdr2", "fb3bfr2", "fb3vs3r")
SCREEN = ("fb3bd", "fb3bf", "fb3bd2", "fb3bf2", "fb3vs3")
REF = {"fb3bdr": "fx3mS", "fb3bfr": "fx3mS", "fb3bdr2": "fx3mS2", "fb3bfr2": "fx3mS2", "fb3vs3r": "fb3vs0",
       "fb3bd": "fx3mS", "fb3bf": "fx3mS", "fb3bd2": "fx3mS2", "fb3bf2": "fx3mS2", "fb3vs3": "fb3vs0"}
THRESH = 0.5
DET_RE = re.compile(r"^\[Victim Detection\] step=(\d+) UAV-(\S+) detected (\S+) at")
OFF8 = disc_offsets(8.0)
OFF16 = disc_offsets(16.0)
BAND, STRIDE = 4, 2      # agents.py:2086 SEARCHER_EDGE_BAND = 4; SEARCHER_BELIEF_STRIDE 2 (switches record)
POOL = np.array([(x, y) for x in range(BAND, 50 - BAND) for y in range(BAND, 50 - BAND)
                 if x % STRIDE == 0 and y % STRIDE == 0], dtype=float)   # searcher_targeting.py:195-196


def load(tag):
    return A.load(tag)


def samples(d):
    """[(step, dead_mass, n_unfound, alive_mass)] from fb3.coverage (every 10 steps)."""
    fb = d.get("fb3") or {}
    return [(r[0], r[2]["dead_mass"], r[2]["n_unfound"], r[2]["alive_mass"]) for r in fb.get("coverage") or []
            if isinstance(r, list) and len(r) > 2 and isinstance(r[2], dict)]


def vrow(d, s, v):
    """victim row of v at END of step s (rows_vic[s-1])."""
    if s - 1 >= len(d["rows_vic"]) or s < 1:
        return None
    return next((x for x in d["rows_vic"][s - 1] if x[0] == v), None)


def alive_status(st):
    return st not in ("dead", "rescued") and st is not None


def classify(d):
    """Per victim: (max sampled DEAD share while alive+undetected, step of max, first sampled step > 0.5,
    list of sampled (s, dead)) - the _fb3_r3_check.py rules (lines 30-47), reimplemented."""
    det = A.det_times(d)
    smp = samples(d)
    res = {}
    for v in sorted(det):
        pts = []
        for s, dead, n_unf, alive in smp:
            if det[v] is not None and s >= det[v]:
                continue
            r = vrow(d, s, v)
            st = r[3] if r else None
            if not alive_status(st) or n_unf <= 0:
                continue
            pts.append((s, dead))
        if not pts:
            res[v] = None
            continue
        mx = max(pts, key=lambda p: p[1])
        first = next((s for s, dd in pts if dd > THRESH), None)
        res[v] = {"max": mx[1], "max_step": mx[0], "first": first, "pts": pts}
    return res


def window(d, v):
    """Alive-and-undetected steps of v: s in 1.. with s < first detection and status alive at end of s."""
    det = A.det_times(d).get(v)
    out = []
    for s in range(1, len(d["rows_vic"]) + 1):
        if det is not None and s >= det:
            break
        r = vrow(d, s, v)
        if r is None or not alive_status(r[3]):
            break
        out.append(s)
    return out


def det_uav(tag, seed):
    """{vid: (step, uav id)} first detection from the stdout file."""
    path = os.path.join(r'E:\Projects\SAS\outputs', "_sd_%s_%s.stdout.txt" % (tag, seed))
    out = {}
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8", errors="replace"):
        m = DET_RE.match(line.strip())
        if m and m.group(3) not in out:
            out[m.group(3)] = (int(m.group(1)), m.group(2))
    return out


def cover_stack(d):
    """bool array [T, 50, 50]: cover[t] = union of Euclidean-8 discs of every UAV at END of step t+1."""
    T = len(d["rows_uav"])
    cov = np.zeros((T, 50, 50), dtype=bool)
    for t, row in enumerate(d["rows_uav"]):
        cells = [(int(u[1]), int(u[2])) for u in row if u[1] is not None and u[2] is not None]
        cov[t] = disc_mask(50, 50, cells, OFF8)
    return cov


def disc_cells(c, off):
    xs = np.array([c[0] + dx for dx, dy in off])
    ys = np.array([c[1] + dy for dx, dy in off])
    k = (xs >= 0) & (xs < 50) & (ys >= 0) & (ys < 50)
    return xs[k], ys[k]


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def q(xs, f):
    xs = sorted(xs)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int(f * len(xs)))]


def med(xs):
    return statistics.median(xs) if xs else None


def mean(xs):
    return statistics.mean(xs) if xs else None
