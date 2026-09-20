"""Is the final burnt/scorched/burning split of the depot cells recoverable offline? Reads JSON only."""
import glob, json, os, statistics
BASE = "E:/Projects/SAS/outputs"
files = sorted(glob.glob(os.path.join(BASE, "_ffr_f3OFF_*.json")))
DEP = {(x, y) for x in range(0, 5) for y in range(45, 50)} | {(x, y) for x in range(45, 50) for y in range(0, 5)}
tot = [0, 0, 0, 0]
allok = True
digest_lens = set()
for fp in files:
    d = json.load(open(fp))
    name = os.path.basename(fp)[len("_ffr_f3OFF_"):-5]
    g = d.get("fire_ground_final")
    if not g:
        print(name, "NO fire_ground_final"); allok = False; continue
    burnt_all = sum(1 for v in g.values() if v[1])
    ev = d["eval"]["burnt_cells"]
    nb = ns = nf = nu = 0
    for k, v in g.items():
        x, y = map(int, k.split(","))
        if (x, y) not in DEP:
            continue
        hb, bt, bg = v
        if bt: nb += 1
        elif bg: nf += 1
        elif hb: ns += 1
        else: nu += 1
    bi = d["burn_intervals"]
    ever = sum(1 for k, iv in bi.items() if iv and tuple(map(int, k.split(","))) in DEP)
    ok = (burnt_all == ev) and (nb + ns + nf == ever)
    allok &= ok
    tot[0] += nb; tot[1] += ns; tot[2] += nf; tot[3] += nu
    digest_lens.add(len(d.get("fire_digests") or []))
    print("%-18s ncells %d | depot final: burnt %2d scorched %2d burning %2d untouched %2d | ever(burn_intervals) %2d | sum burnt==eval %s (%d vs %d)"
          % (name, len(g), nb, ns, nf, nu, ever, burnt_all == ev, burnt_all, ev))
print("totals over 27: burnt %d scorched %d burning %d untouched %d ; all consistent: %s" % (tot[0], tot[1], tot[2], tot[3], allok))
print("fire_digests lengths:", digest_lens)
print("mean burnt %.2f scorched %.2f burning %.2f" % (tot[0] / 27.0, tot[1] / 27.0, tot[2] / 27.0))
