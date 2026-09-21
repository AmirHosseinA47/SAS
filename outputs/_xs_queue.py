"""Exit-stall round, Part 1: write the probe queue (outputs/exitstall_prereg.txt).

Every line runs outputs/_xs_probe.py (HARNESS=outputs/_xs_probe.py in the pool), which
runs _ffr_harness.py unchanged - or _fm2_probe_harness.py for the CRN lines.

  xsTD   trace, shipped ungated (uhD recipe)            the 5 shipped stalled legs
  xsTY   trace, positioning-only (uhY recipe)           the 2 positioning-only legs
  xsTK   trace, CONTROL code 11c3661, CRN (ugKC recipe) the 4 control stalled legs
  xsRED / xsREY  XS_RESET=exit    on the 7 legs, no trace
  xsRAD / xsRAY  XS_RESET=assign  on the 7 legs, no trace

Steps: each run stops a few steps after its stalled leg completes, since a prefix of a
longer run equals the shorter run (checked value for value in the horizon round). The
analyzer compares each run with the recorded run's first `steps` steps.

  .venv/Scripts/python.exe -B outputs/_xs_queue.py   -> outputs/_xs_queue.txt
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FLIP = "E:/Projects/SAS"
CTRL = "E:/Projects/SAS_wt/base11c3661"
D = "--uav-actions --set BATCH_SIZE=360"
Y = D + " --set FF_FIREFIGHT_DRY_RUN=1"
K = "--uav-actions --set FM2P_CRN=1"

# (wind, roles, seed, steps): the leg ends +8
SHIPPED = [("east", "half", 2070841104, 120), ("east", "half", 294124329, 151),
           ("east", "half", 1433805104, 290), ("south", "half", 1048395951, 271),
           ("east", "default", 1749069988, 207)]
POSITIONING = [("east", "half", 2070841104, 120), ("east", "half", 294124329, 151)]
CONTROL_CRN = [("east", "half", 294124329, 179), ("east", "half", 2070841104, 127),
               ("east", "default", 1420331661, 158), ("south", "half", 903347495, 82)]


def line(tag, repo, t, extra):
    w, r, s, n = t
    return "ff|%s|%s|%s|%s|%d|%d|%s" % (tag, repo, w, r, s, n, extra)


def main():
    lines = []
    lines += [line("xsTD", FLIP, t, D + " --set XS_TRACE=1") for t in SHIPPED]
    lines += [line("xsTY", FLIP, t, Y + " --set XS_TRACE=1") for t in POSITIONING]
    lines += [line("xsTK", CTRL, t, K + " --set XS_TRACE=1") for t in CONTROL_CRN]
    lines += [line("xsRED", FLIP, t, D + " --set XS_RESET=exit") for t in SHIPPED]
    lines += [line("xsREY", FLIP, t, Y + " --set XS_RESET=exit") for t in POSITIONING]
    lines += [line("xsRAD", FLIP, t, D + " --set XS_RESET=assign") for t in SHIPPED]
    lines += [line("xsRAY", FLIP, t, Y + " --set XS_RESET=assign") for t in POSITIONING]
    with open(os.path.join(HERE, "_xs_queue.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("_xs_queue.txt %d lines" % len(lines))


if __name__ == "__main__":
    main()
