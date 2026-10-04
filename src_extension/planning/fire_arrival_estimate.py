"""Managing system, PLAN: an OPERATOR-SIDE estimate of when the fire reaches each cell, and the front-priority
urgency weight built on it (bayesprep round item 2; outputs/bayesprep_part1.txt section 2, rulings section 10).

This is deliberately NOT the simulator's spread rule (agents.Fire: stochastic, 28 Euclidean-3 offsets weighted
d^-2, a LINE-shaped boost of the three directly-upwind sources, a tick every 3 steps). It never reads a simulator
fire constant (FIRE_SPREAD_*, MU, fuel). Its inputs are what the managing system already holds: the believed burning
cells (assumption A3) and the constant wind's direction (A4).

ESTIMATE. Elliptical fire spread with the ignition at the rear focus (Van Wagner 1969; Catchpole, de Mestre & Gill
1982): the spread rate at angle theta from the downwind direction is R(theta) = R_H (1 - e) / (1 - e cos theta). The
arrival time at a cell c is the Huygens envelope over the believed front (Anderson, Catchpole, de Mestre & Parkes
1982; Richards 1990) - for homogeneous conditions the minimum over burning cells b of the wavelet travel time:
    T(c) = min_b ( |v| - e (v . u) ) / ( R_H (1 - e) ),   v = c - b,  u = the downwind unit vector.
PARAMETERS (each cited; bayesprep_part1.txt 2.3):
    R_H = ROS_WIND_FRACTION x U10 (the 10% rule, Cruz & Alexander 2019) in m/s, divided by the free walking speed
          (Weidmann 1993) - 1 cell / step is the fleeing person's movement quantum (A6) - giving cells / step;
    z   = min(1 + LW_PER_MPH x U_mf, LW_MAX), the length-to-width ratio (Andrews 2018, after Anderson 1983), with
          U_mf = WAF x U10 / K_20FT the midflame wind in mi/h (Albini & Baughman 1979; Turner & Lawson 1978);
    e   = sqrt(z^2 - 1) / z.
WEIGHT. w(c) = 1 + KAPPA exp(-T(c) / TAU) (the evacuation trigger-buffer idea: space ranked by fire travel time,
Cova, Dennison, Kim & Moritz 2005). w = 1 on burning cells and everywhere when nothing burns. Draws no random numbers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np

_KMH_PER_MPH = 1.609344


@dataclass(frozen=True)
class FrontPriorityParams:
    u10_kmh: float = 20.0
    ros_wind_fraction: float = 0.1
    walk_speed_ms: float = 1.34
    waf: float = 0.4
    k_20ft: float = 1.15
    lw_per_mph: float = 0.25
    lw_max: float = 8.0
    kappa: float = 1.0
    tau: float = 16.0

    @property
    def head_rate(self) -> float:
        """R_H in cells / step."""
        return max(0.0, float(self.ros_wind_fraction) * float(self.u10_kmh) / 3.6) / max(float(self.walk_speed_ms), 1e-9)

    @property
    def length_to_width(self) -> float:
        u_mf = float(self.waf) * float(self.u10_kmh) / max(float(self.k_20ft), 1e-9) / _KMH_PER_MPH
        return max(1.0, min(1.0 + float(self.lw_per_mph) * max(0.0, u_mf), float(self.lw_max)))

    @property
    def eccentricity(self) -> float:
        z = self.length_to_width
        return math.sqrt(max(0.0, z * z - 1.0)) / z


def front_priority_params() -> FrontPriorityParams:
    """The SEARCHER_FP_* parameters read at call time (so --set reaches them)."""
    import agents as agents_module  # lazy: agents is a root module

    f = agents_module.fix3b_param
    return FrontPriorityParams(
        u10_kmh=f("SEARCHER_FP_U10_KMH", 20.0), ros_wind_fraction=f("SEARCHER_FP_ROS_WIND_FRACTION", 0.1),
        walk_speed_ms=f("SEARCHER_FP_WALK_SPEED_MS", 1.34), waf=f("SEARCHER_FP_WAF", 0.4),
        k_20ft=f("SEARCHER_FP_10M_TO_20FT", 1.15), lw_per_mph=f("SEARCHER_FP_LW_PER_MPH", 0.25),
        lw_max=f("SEARCHER_FP_LW_MAX", 8.0), kappa=f("SEARCHER_FP_KAPPA", 1.0), tau=f("SEARCHER_FP_TAU", 16.0))


def arrival_time(height: int, width: int, burning: Iterable[tuple[int, int]], wind: tuple[float, float] | None,
                 params: FrontPriorityParams) -> np.ndarray:
    """T[x, y] in steps (0 on burning cells, inf when nothing burns or the head rate is 0)."""
    pts = np.asarray([(int(x), int(y)) for x, y in burning if 0 <= int(x) < height and 0 <= int(y) < width],
                     dtype=np.float64).reshape(-1, 2)
    out = np.full((height, width), np.inf)
    r_h = params.head_rate
    if pts.size == 0 or r_h <= 0.0:
        return out
    ux, uy = (0.0, 0.0) if wind is None else (float(wind[0]), float(wind[1]))
    norm = math.hypot(ux, uy)
    e = params.eccentricity if norm > 0.0 else 0.0
    if norm > 0.0:
        ux, uy = ux / norm, uy / norm
    gx, gy = np.meshgrid(np.arange(height, dtype=np.float64), np.arange(width, dtype=np.float64), indexing="ij")
    denom = r_h * (1.0 - e)
    for start in range(0, len(pts), 256):            # chunked: memory O(256 * cells)
        chunk = pts[start:start + 256]
        vx = gx[None, :, :] - chunk[:, 0, None, None]
        vy = gy[None, :, :] - chunk[:, 1, None, None]
        travel = (np.sqrt(vx * vx + vy * vy) - e * (vx * ux + vy * uy)) / denom
        out = np.minimum(out, travel.min(axis=0))
    out = np.maximum(out, 0.0)
    out[pts[:, 0].astype(int), pts[:, 1].astype(int)] = 0.0
    return out


def urgency_weight(height: int, width: int, burning: Iterable[tuple[int, int]], wind: tuple[float, float] | None,
                   params: FrontPriorityParams) -> np.ndarray:
    """w[x, y] = 1 + kappa exp(-T / tau); 1 on burning cells (their alive mass is ~0) and with no fire."""
    burning = list(burning)
    w = np.ones((height, width))
    if not burning:
        return w
    t = arrival_time(height, width, burning, wind, params)
    tau = max(float(params.tau), 1e-9)
    finite = np.isfinite(t)
    w[finite] = 1.0 + float(params.kappa) * np.exp(-t[finite] / tau)
    for x, y in burning:
        if 0 <= int(x) < height and 0 <= int(y) < width:
            w[int(x), int(y)] = 1.0
    return w
