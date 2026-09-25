import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from streak import burning_at, bfs
d = json.load(open(sys.argv[1])); other = sys.argv[2]; s0, s1 = int(sys.argv[3]), int(sys.argv[4])
bi = d["burn_intervals"]
for s in range(s0, s1+1):
    o = {r[0]: r for r in d["ff_steps"][s-1]}[other]
    b = burning_at(bi, s)
    reach = bfs([tuple(o[1])] if o[1] is not None and not o[5] and not o[4] and o[2] != "dead" else [], b)
    grid = []
    for y in range(11, 3, -1):
        line = ""
        for x in range(43, 50):
            c = (x, y)
            line += "#" if c in b else ("R" if c in reach else ".")
        grid.append("y%2d %s" % (y, line))
    print("step", s, "x43..49"); print("\n".join(grid))
