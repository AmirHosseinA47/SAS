"""Managing system: victim-search belief (fix3b, session 3b; outputs/fix3b_part1.txt sections 2 and 15).

Knowledge for the searcher-targeting strategies (SEARCHER_TARGETING 1, 2, 3, 5). It holds:

  p        the posterior over the cell of ONE unfound victim, alive (a sub-probability; the rest is DEAD).
           Under the i.i.d. uniform prior every unfound victim has this same posterior, so the expected
           count of unfound, alive victims per cell is lambda = N_unf * p (fix3b_part1.txt 2.1).
  dead     the mass of the absorbing DEAD state (caught by the fire; never detectable).
  last_cover  per cell, the last step it lay inside ANY UAV's detection disc (-1: never). The least-
           observed baseline reads it; the visibility map is not a record of victim search (F2).

The per-step update (2.6) is PREDICT (motion, driven by the fire of this step) -> MEASURE (the post-move
detection discs of every UAV) -> BURN-OVER -> detections (N_unf). It draws no random numbers.

The likelihood is DERIVED from the model's detection rule (wildfire_model._detect_victims_in_uav_radius):
a victim is detected with certainty iff some UAV is within Euclidean distance UAV_OBSERVATION_RADIUS,
whatever the smoke. P_d is a named parameter (SEARCHER_BELIEF_PD = 1); SEARCHER_BELIEF_PD_SMOKE is the
P_d the belief ASSUMES in smoke cells - 1.0 matches the simulator, < 1 is the misspecification sensitivity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np

# Direction order of the executor (_MOVE_X / _MOVE_Y): 0 (+x), 1 (-y), 2 (-x), 3 (+y) is NOT assumed here;
# the belief's motion is direction-agnostic, so it uses its own (dx, dy) list.
_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def disc_offsets(radius: float) -> list[tuple[int, int]]:
    """The lattice offsets (dx, dy) with dx^2 + dy^2 <= radius^2 - the detection disc (197 at radius 8)."""
    r = int(math.floor(radius))
    r2 = float(radius) * float(radius)
    return [(dx, dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1) if dx * dx + dy * dy <= r2]


def disc_mask(height: int, width: int, centres: Iterable[tuple[int, int]],
              offsets: list[tuple[int, int]]) -> np.ndarray:
    """Boolean H x W mask: the union of the discs around `centres` (clipped to the grid)."""
    mask = np.zeros((height, width), dtype=bool)
    if not offsets:
        return mask
    off = np.asarray(offsets, dtype=np.int64)
    for cx, cy in centres:
        xs = off[:, 0] + int(cx)
        ys = off[:, 1] + int(cy)
        keep = (xs >= 0) & (xs < height) & (ys >= 0) & (ys < width)
        mask[xs[keep], ys[keep]] = True
    return mask


def disc_convolve(field_: np.ndarray, offsets: list[tuple[int, int]]) -> np.ndarray:
    """S[x, y] = sum over the disc around (x, y) of field_ (zero outside the grid): the mass a sensor
    footprint centred at (x, y) would cover."""
    h, w = field_.shape
    r = max((max(abs(dx), abs(dy)) for dx, dy in offsets), default=0)
    padded = np.zeros((h + 2 * r, w + 2 * r), dtype=field_.dtype)
    padded[r:r + h, r:r + w] = field_
    out = np.zeros_like(field_)
    for dx, dy in offsets:
        out += padded[r + dx:r + dx + h, r + dy:r + dy + w]
    return out


def dilate(mask: np.ndarray, offsets: list[tuple[int, int]]) -> np.ndarray:
    """The union of the discs around every True cell of `mask`."""
    h, w = mask.shape
    r = max((max(abs(dx), abs(dy)) for dx, dy in offsets), default=0)
    padded = np.zeros((h + 2 * r, w + 2 * r), dtype=bool)
    padded[r:r + h, r:r + w] = mask
    out = np.zeros_like(mask)
    for dx, dy in offsets:
        out |= padded[r + dx:r + dx + h, r + dy:r + dy + w]
    return out


def _distance_to_cells(height: int, width: int, cells: Iterable[tuple[int, int]]) -> np.ndarray:
    """Exact Euclidean distance of every cell to the nearest cell of `cells` (inf when empty)."""
    pts = np.asarray(list(cells), dtype=np.float64)
    if pts.size == 0:
        return np.full((height, width), np.inf)
    gx, gy = np.meshgrid(np.arange(height, dtype=np.float64), np.arange(width, dtype=np.float64),
                         indexing="ij")
    best = np.full((height, width), np.inf)
    for start in range(0, len(pts), 256):            # chunked: memory O(256 * cells)
        chunk = pts[start:start + 256]
        d2 = (gx[None, :, :] - chunk[:, 0, None, None]) ** 2 + (gy[None, :, :] - chunk[:, 1, None, None]) ** 2
        best = np.minimum(best, np.sqrt(d2.min(axis=0)))
    return best


@dataclass
class MotionParams:
    mode: str = "diffusion"          # "diffusion" | "flee" | "off"
    q: float = 0.1                   # diffusion move probability
    d50: float = 5.0                 # flee: alarm midpoint (cells, Euclidean)
    s: float = 1.5                   # flee: alarm scale
    p_go: float = 0.8                # flee: an alarmed victim moves with this probability
    beta: float = 1.5                # flee: softmax weight on the fire-distance gain
    q_calm: float = 0.02             # flee: an unalarmed victim's move probability
    burnover: float = 0.1            # alive mass on a burning cell -> DEAD with this probability (R-3)
    # bayesprep F1-a (SEARCHER_TARGETING_FIX): the lazy walk REFLECTS - q / 4 per direction and a move off the grid
    # or into a burning cell stays (design 2.4). False = the fix3b rule, q / k per AVAILABLE neighbour, whose
    # stationary density is proportional to k (edge rows and corners drain; mass is pushed off burning cells).
    reflect: bool = False


@dataclass
class VictimSearchBelief:
    height: int
    width: int
    n_brief: int
    radius: float = 8.0
    p: np.ndarray = field(default=None)            # type: ignore[assignment]
    dead: float = 0.0
    last_cover: np.ndarray = field(default=None)   # type: ignore[assignment]
    detected_ids: set = field(default_factory=set)
    step: int = 0
    updates: int = 0
    offsets: list = field(default_factory=list)

    @classmethod
    def with_uniform_prior(cls, height: int, width: int, n_brief: int, excluded: Iterable[tuple[int, int]],
                           radius: float = 8.0) -> "VictimSearchBelief":
        """Prior H0 (fix3b_part1.txt 2.2): uniform over the cells minus `excluded` (the depot footprints and
        the cells burning at t0) - mission-briefing information only."""
        b = cls(height=int(height), width=int(width), n_brief=int(n_brief), radius=float(radius))
        support = np.ones((b.height, b.width), dtype=np.float64)
        for x, y in excluded:
            if 0 <= int(x) < b.height and 0 <= int(y) < b.width:
                support[int(x), int(y)] = 0.0
        total = support.sum()
        b.p = support / total if total > 0 else support
        b.last_cover = np.full((b.height, b.width), -1, dtype=np.int64)
        b.offsets = disc_offsets(radius)
        return b

    # ---- the three update stages -----------------------------------------------------------------
    def predict(self, burning: set[tuple[int, int]], motion: MotionParams) -> None:
        """The motion model (2.4). Mass conserving: alive mass only moves between alive cells."""
        if motion.mode == "off":
            return
        h, w = self.height, self.width
        burn = np.zeros((h, w), dtype=bool)
        for x, y in burning:
            if 0 <= x < h and 0 <= y < w:
                burn[x, y] = True
        avail = []                                  # avail[k][x, y]: neighbour k of (x, y) in bounds, not burning
        for dx, dy in _NEIGHBOURS:
            a = np.zeros((h, w), dtype=bool)
            xs = slice(max(0, -dx), h - max(0, dx))
            ys = slice(max(0, -dy), w - max(0, dy))
            xt = slice(max(0, dx), h - max(0, -dx))
            yt = slice(max(0, dy), w - max(0, -dy))
            a[xs, ys] = ~burn[xt, yt]
            avail.append(a)
        k = sum(a.astype(np.float64) for a in avail)            # number of available neighbours
        # Move weights per neighbour (w_n) and stay weight (w_stay), per source cell.
        if motion.mode == "diffusion":
            if motion.reflect:
                share = np.full((h, w), float(motion.q) / 4.0)
            else:
                share = np.where(k > 0, float(motion.q) / np.maximum(k, 1.0), 0.0)
            w_n = [np.where(a, share, 0.0) for a in avail]
            w_stay = 1.0 - sum(w_n)
        else:                                                   # "flee"
            d = _distance_to_cells(h, w, burning)
            if not np.isfinite(d).any():
                alarm = np.zeros((h, w))
                d = np.full((h, w), 1e6)
            else:
                alarm = 1.0 / (1.0 + np.exp(-(float(motion.d50) - d) / max(float(motion.s), 1e-9)))
            if motion.reflect:
                calm_share = np.full((h, w), float(motion.q_calm) / 4.0)
            else:
                calm_share = np.where(k > 0, float(motion.q_calm) / np.maximum(k, 1.0), 0.0)
            # softmax over {stay} + available neighbours, utility beta * (d(n) - d(c)); stay utility 0.
            beta = float(motion.beta)
            exps = []
            for (dx, dy), a in zip(_NEIGHBOURS, avail):
                dn = np.full((h, w), -np.inf)
                xs = slice(max(0, -dx), h - max(0, dx))
                ys = slice(max(0, -dy), w - max(0, dy))
                xt = slice(max(0, dx), h - max(0, -dx))
                yt = slice(max(0, dy), w - max(0, -dy))
                dn[xs, ys] = d[xt, yt]
                gain = np.where(a, np.clip(dn - d, -50.0, 50.0), 0.0)
                exps.append(np.where(a, np.exp(beta * gain), 0.0))
            z = 1.0 + sum(exps)
            p_go = float(motion.p_go)
            w_n = [alarm * p_go * (e / z) + (1.0 - alarm) * np.where(a, calm_share, 0.0)
                   for e, a in zip(exps, avail)]
            w_stay = 1.0 - sum(w_n)
        new = self.p * w_stay
        for (dx, dy), wn in zip(_NEIGHBOURS, w_n):
            moved = self.p * wn
            xs = slice(max(0, -dx), h - max(0, dx))
            ys = slice(max(0, -dy), w - max(0, dy))
            xt = slice(max(0, dx), h - max(0, -dx))
            yt = slice(max(0, dy), w - max(0, -dy))
            new[xt, yt] += moved[xs, ys]
        self.p = new

    def measure(self, uav_cells: Iterable[tuple[int, int]], smoke: set[tuple[int, int]], step: int,
                pd: float = 1.0, pd_smoke: float = 1.0) -> np.ndarray:
        """Negative information from the detection discs of every UAV (2.3); returns the covered mask."""
        cover = disc_mask(self.height, self.width, uav_cells, self.offsets)
        pd_grid = np.where(cover, float(pd), 0.0)
        if smoke and float(pd_smoke) != float(pd):
            for x, y in smoke:
                if 0 <= x < self.height and 0 <= y < self.width and cover[x, y]:
                    pd_grid[x, y] = float(pd_smoke)
        self.p = self.p * (1.0 - pd_grid)
        z = float(self.p.sum()) + float(self.dead)
        if z > 0.0:
            self.p = self.p / z
            self.dead = float(self.dead) / z
        self.last_cover[cover] = int(step)
        return cover

    def burn_over(self, burning: set[tuple[int, int]], p_bo: float) -> None:
        """Alive mass on a burning cell goes to DEAD with probability p_bo (2.4)."""
        if not burning or p_bo <= 0.0:
            return
        moved = 0.0
        for x, y in burning:
            if 0 <= x < self.height and 0 <= y < self.width:
                m = float(self.p[x, y]) * float(p_bo)
                if m:
                    self.p[x, y] -= m
                    moved += m
        self.dead = float(self.dead) + moved

    # ---- derived quantities ----------------------------------------------------------------------
    @property
    def n_unfound(self) -> int:
        return max(0, int(self.n_brief) - len(self.detected_ids))

    def intensity(self) -> np.ndarray:
        """lambda: the expected number of unfound, ALIVE victims per cell."""
        return float(self.n_unfound) * self.p

    def expected_unfound_alive(self) -> float:
        return float(self.n_unfound) * float(self.p.sum())

    def coverage_share(self) -> float:
        return float((self.last_cover >= 0).mean())

    def summary(self) -> dict[str, Any]:
        return {"step": int(self.step), "n_unfound": self.n_unfound, "alive_mass": round(float(self.p.sum()), 6),
                "dead_mass": round(float(self.dead), 6), "expected_unfound_alive": round(self.expected_unfound_alive(), 4),
                "coverage_share": round(self.coverage_share(), 4)}
