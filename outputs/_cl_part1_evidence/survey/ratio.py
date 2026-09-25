import re, os, statistics
os.chdir(r"E:\Projects\SAS\outputs")
pat = re.compile(r"^\[(\d\d:\d\d:\d\d)\] DONE (\S+) rc=(\d+) (\d+)s .* seed=(\d+) .*wall=(\d+)s")
def walls(lg):
    d = {}
    for ln in open(lg, encoding="utf-8", errors="replace"):
        m = pat.match(ln)
        if m:
            d[m.group(2)] = int(m.group(6))
    return d
ug = walls("_ug_wave.log")
uh = walls("_uh_wave.log")
for a240, a360 in (("ugC", "uhC"), ("ugD", "uhD"), ("ugY", "uhY")):
    rs = []
    w240 = []
    w360 = []
    for n, w in uh.items():
        if not n.startswith(a360 + "_"):
            continue
        k = a240 + n[len(a360):]
        if k in ug:
            rs.append(w / ug[k])
            w240.append(ug[k]); w360.append(w)
    if rs:
        print(a240, a360, "pairs", len(rs), "mean240=%.0f mean360=%.0f median240=%.0f median360=%.0f ratio_median=%.2f ratio_mean=%.2f" % (
            statistics.mean(w240), statistics.mean(w360), statistics.median(w240), statistics.median(w360), statistics.median(rs), statistics.mean(rs)))
# concurrency: parse LAUNCH lines running=
for lg in ("_uh_wave.log", "_ug_wave.log", "_xs_wave.log", "_sfx_wave.log"):
    runs = [int(m.group(1)) for m in re.finditer(r"LAUNCH \S+ running=(\d+)", open(lg, encoding="utf-8", errors="replace").read())]
    sims = [int(m.group(1)) for m in re.finditer(r"sims_boxwide=(\d+)", open(lg, encoding="utf-8", errors="replace").read())]
    thr = open(lg, encoding="utf-8", errors="replace").read().count("THROTTLE")
    print(lg, "max running at launch", max(runs) if runs else None, "max sims_boxwide", max(sims) if sims else None, "THROTTLE lines", thr)
