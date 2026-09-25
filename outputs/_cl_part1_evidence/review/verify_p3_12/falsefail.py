import math
from math import comb

def p_loss(lam, kmax=40):
    # flips ~ Poisson(lam), each flip +1/-1 with prob 1/2 (a neutral change); P(sum < 0)
    tot = 0.0
    for k in range(kmax):
        pk = math.exp(-lam) * lam ** k / math.factorial(k)
        # P(S_k < 0): number of -1s j > k/2
        pl = sum(comb(k, j) for j in range(k + 1) if (k - 2 * j) < 0) / 2 ** k
        tot += pk * pl
    return tot

for lam in (0.5, 1.0, 1.5, 2.0, 3.0, 6.0):
    print("lambda=%.1f  P(loss one set)=%.3f" % (lam, p_loss(lam)))

# scenario: stock flips ~ 1.5 per 30-run set, 0.65 per C13; CRN flips ~ 1.0 per 30, 0.45 per C13
s30, s13, c30, c13 = p_loss(1.5), p_loss(0.65), p_loss(1.0), p_loss(0.45)
p3 = 1 - (1 - s13) * (1 - s30) ** 2
p6 = 1 - (1 - s13) * (1 - s30) ** 2 * (1 - c13) * (1 - c30) ** 2
print("neutral change: P(any fail) stock-only 3 comparisons = %.2f ; both instruments 6 = %.2f" % (p3, p6))
