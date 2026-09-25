import collections, importlib.util, sys
spec = importlib.util.spec_from_file_location("cov", "coverage.py")
# reuse helpers without re-running prints: exec the top half
src = open("coverage.py").read().split("PAIRS = ")[0]
ns = {}
exec(src, ns)
runs, legs, load = ns["runs"], ns["legs"], ns["load"]
for tag in ("uhD", "ugKD", "uhC", "ugKC", "sfON"):
    exc_hist = collections.Counter()
    for thr in (1, 5):
        tot = after = rd = 0
        for t, n in sorted(runs[tag].items()):
            L = legs(load(n))
            items = sorted(L.items(), key=lambda kv: kv[0][2])
            if thr == 1:
                for k, (dur, exc, c) in items:
                    exc_hist[exc if exc is None or exc < 8 else '8+'] += 1
            first = next((c for k, (dur, exc, c) in items if exc is not None and exc > thr), None)
            tot += len(items)
            if first is not None:
                rd += 1
                after += sum(1 for k, v in items if k[2] > first)
        print(f"{tag} thr excess>{thr}: runs-with {rd}/{len(runs[tag])}, legs picked up after first such completion {after}/{tot} ({after/tot:.2f})")
    print("  excess histogram", sorted(exc_hist.items(), key=lambda kv: str(kv[0])))
