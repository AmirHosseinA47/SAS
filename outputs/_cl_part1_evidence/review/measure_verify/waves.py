import re, sys, os
from datetime import datetime, timedelta

OUT = r"E:\Projects\SAS\outputs"
LOGS = sys.argv[1:]

ts_re = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\]")
launch_re = re.compile(r"LAUNCH (\S+) running=(\d+) free_kb=(\d+)")
done_re = re.compile(r"DONE (\S+) rc=(\d+) (\d+)s .*?wall=(\d+)s")
done2_re = re.compile(r"DONE (\S+) rc=(\d+) (\d+)s")
start_re = re.compile(r"POOL START .*maxpar=(\d+) minfree_kb=(\d+)")
thr_re = re.compile(r"THROTTLE")
alive_re = re.compile(r"running=(\d+) .*free_kb=(\d+)")

def secs(m, day):
    return day * 86400 + int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))

for name in LOGS:
    p = os.path.join(OUT, name)
    if not os.path.exists(p):
        print(name, "missing"); continue
    day = 0; last = None
    launches = {}; dones = []; maxpar = None; minfree = None; thr = 0
    free_by_running = {}
    first = None; lastt = None
    rb_like = 0
    with open(p, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = ts_re.match(line)
            if not m: continue
            t = secs(m, day)
            if last is not None and t < last - 3600:
                day += 1; t = secs(m, day)
            last = t
            if first is None: first = t
            s = start_re.search(line)
            if s: maxpar = int(s.group(1)); minfree = int(s.group(2))
            l = launch_re.search(line)
            if l:
                launches[l.group(1)] = t
                free_by_running.setdefault(int(l.group(2)), []).append(int(l.group(3)))
            d = done_re.search(line) or done2_re.search(line)
            if d and " DONE " in line:
                w = int(d.group(4)) if d.re is done_re else int(d.group(3))
                dones.append((d.group(1), t, w))
                lastt = t
            if thr_re.search(line): thr += 1
    if not dones:
        print(name, "no DONE lines"); continue
    # concurrency timeline from launch/done
    ev = []
    for n, t, w in dones:
        if n in launches:
            ev.append((launches[n], 1)); ev.append((t, -1))
    ev.sort()
    cur = 0; area = 0; prev = ev[0][0] if ev else 0; mx = 0
    for t, dlt in ev:
        area += cur * (t - prev); prev = t; cur += dlt; mx = max(mx, cur)
    span = (lastt - min(launches.values())) if launches else 0
    walls = [w for _, _, w in dones]
    mean = sum(walls) / len(walls)
    med = sorted(walls)[len(walls) // 2]
    avgc = area / span if span else 0
    print(f"{name}: maxpar={maxpar} minfree={minfree} runs={len(dones)} span={span/3600:.2f}h "
          f"thr={thr} max_running={mx} avg_running={avgc:.2f} mean_wall={mean:.0f}s med={med}s "
          f"sec_per_run_throughput={span/len(dones):.0f}s  wall/avg_running={mean/avgc if avgc else 0:.0f}s")
