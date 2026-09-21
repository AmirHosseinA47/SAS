"""Ungated round, horizon measurement (outputs/ungated_horizon_prereg.txt): write the queue.

The SAME 30 fresh seeds (U30, outputs/_ug_seeds.py), stock, 360 steps. Every line is the
recorded 240-step line of the same arm with exactly two changes: --steps 360 and
--set BATCH_SIZE=360 (the model exits once it passes BATCH_SIZE + 1 steps,
wildfire_model.py:5808). Control and shipped arms first - the decision rests on them -
then the positioning-only arm. LF line endings.

  .venv/Scripts/python.exe -B outputs/_uh_queue.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _ug_queue as Q  # noqa: E402  (FLIP, CTRL, u30)

H = 360
BS = "--set BATCH_SIZE=%d" % H


def line(tag, repo, t, extra):
    w, r, s = t
    return "ff|%s|%s|%s|%s|%d|%d|%s" % (tag, repo, w, r, s, H, ("--uav-actions " + extra).strip())


def main():
    U30 = Q.u30()
    q = []
    for t in U30:
        q += [line("uhC", Q.CTRL, t, BS), line("uhD", Q.FLIP, t, BS)]
    for t in U30:
        q.append(line("uhY", Q.FLIP, t, BS + " --set FF_FIREFIGHT_DRY_RUN=1"))
    with open(os.path.join(HERE, "_uh_queue.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(q) + "\n")
    print("_uh_queue.txt %d lines" % len(q))


if __name__ == "__main__":
    main()
