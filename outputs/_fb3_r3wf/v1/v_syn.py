import numpy as np
from vsb_copy import VictimSearchBelief, MotionParams, disc_convolve

H = W = 50
# 1. measure algebra + swept at an uncovered target
b = VictimSearchBelief.with_uniform_prior(H, W, 3, excluded=())
b.p[:, :] = 0.0
b.p[24, 16] = 0.4
b.p[40, 40] = 0.4
b.dead = 0.2
T = (24, 16)
s_issue = disc_convolve(b.p, b.offsets)[T]
b.measure([(40, 40)], set(), 1)
print('1 dead', b.dead, 'SpT', disc_convolve(b.p, b.offsets)[T], 's_issue', s_issue, 'sum', b.p.sum() + b.dead)

# 2. counterfactual: X (p_bo 0.1) vs Y (p_bo 0) with off-fire measure only -> off-fire p identical?
rng = np.random.default_rng(1)
p0 = rng.random((H, W)); p0 /= p0.sum()
fire = {(x, y) for x in range(20, 30) for y in range(20, 30)}
X = VictimSearchBelief.with_uniform_prior(H, W, 3, excluded=()); X.p = p0.copy()
Y = VictimSearchBelief.with_uniform_prior(H, W, 3, excluded=()); Y.p = p0.copy()
mp = MotionParams(mode='off')
for t in range(10):
    for B, pbo in ((X, 0.1), (Y, 0.0)):
        B.measure([(5 + 3 * t, 5)], set(), t)   # far from the fire block
        B.burn_over(fire, pbo)
mask = np.ones((H, W), bool)
for c in fire:
    mask[c] = False
print('2 max |X-Y| off fire (measure-only, no predict):', np.abs(X.p - Y.p)[mask].max(), 'X.dead', X.dead, 'Y.dead', Y.dead)

# 3. degenerate z = 0 at p_bo 0 / >0
for pbo, d0 in ((0.0, 0.0), (0.1, 0.3)):
    B = VictimSearchBelief.with_uniform_prior(H, W, 3, excluded=())
    B.p[:, :] = 0.0
    B.p[25, 25] = 1.0 - d0
    B.dead = d0
    B.measure([(25, 25)], set(), 1)
    print('3 pbo', pbo, 'p.sum', B.p.sum(), 'dead', B.dead)

# 4. flee/diffusion retention on a band fire y=20..30
fireband = {(x, y) for x in range(H) for y in range(20, 31)}
for mode in ('diffusion', 'flee'):
    for cell in ((25, 20), (25, 25), (25, 19), (25, 14), (25, 10)):
        B = VictimSearchBelief.with_uniform_prior(H, W, 1, excluded=())
        B.p[:, :] = 0.0
        B.p[cell] = 1.0
        B.predict(fireband, MotionParams(mode=mode))
        into = sum(B.p[c] for c in fireband) if cell not in fireband else None
        print('4', mode, cell, 'stay %.4f' % B.p[cell], 'into fire', into)
print('5 0.9^13 %.4f 0.9^14 %.4f 0.9^25 %.4f' % (0.9 ** 13, 0.9 ** 14, 0.9 ** 25))
