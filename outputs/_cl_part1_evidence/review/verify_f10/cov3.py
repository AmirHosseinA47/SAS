src = open("coverage.py").read().split("PAIRS = ")[0]
ns = {}
exec(src, ns)
runs, legs, load = ns["runs"], ns["legs"], ns["load"]
print("legs picked up at/after the PICKUP of the first leg with excess>1 or broken (upper bound on legs a MODE arm could leave unmatched)")
for tag in ("uhD", "ugKD", "uhC", "ugKC", "sfON", "fmEFS", "f2cEFS", "dfD", "flhD"):
    if tag not in runs: continue
    tot = aff = rd = 0
    for t, n in sorted(runs[tag].items()):
        items = sorted(legs(load(n)).items(), key=lambda kv: kv[0][2])
        first = next((k[2] for k, (dur, exc, c) in items if exc is None or exc > 1), None)
        tot += len(items)
        if first is not None:
            rd += 1
            aff += sum(1 for k, v in items if k[2] > first)
    print(f"  {tag:6s} runs {len(runs[tag]):3d} legs {tot:4d} runs-with {rd:3d}  later legs {aff:3d} ({aff/tot:.2f})")
