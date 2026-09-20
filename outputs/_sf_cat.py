"""Independent (orchestrator's own) per-step ground categoriser.
burning -> in a burn interval; scorched -> has burned, fuel left, not burning;
burnt -> fuel exhausted (== end of LAST interval when fire_ground_final says burnt);
virgin -> never burned.  Validated: 0/85440 disagreements vs the harness's own
live-recorded uav_actions burning bit over 89 runs.
"""
import json, collections

def load(p):
    with open(p, 'rb') as fh:
        head = fh.read(2)
    enc = 'utf-16' if head in (b'\xff\xfe', b'\xfe\xff') else 'utf-8'
    with open(p, encoding=enc) as fh:
        return json.load(fh)

def categorise(d):
    """-> cat[t][cellkey] via function cat(t, key); plus per-step counts."""
    steps = d['steps']; bi = d['burn_intervals']; gf = d['fire_ground_final']
    burning = collections.defaultdict(set)   # t -> set(cell)
    firstburn = {}
    burnt_from = {}                          # cell -> t at which it becomes burnt
    for cell, ivs in bi.items():
        ends = []
        for s, e in ivs:
            e2 = steps + 1 if e is None else e
            for t in range(s, e2):
                burning[t].add(cell)
            ends.append(e2)
        firstburn[cell] = min(s for s, _ in ivs)
        if gf.get(cell, [0, 0, 0])[1]:       # final burnt
            burnt_from[cell] = max(ends)     # end of last interval
    return steps, burning, firstburn, burnt_from

def cat_of(cell, t, burning, firstburn, burnt_from):
    if cell in burning.get(t, ()):           return 'burning'
    if cell not in firstburn or firstburn[cell] > t: return 'virgin'
    bf = burnt_from.get(cell)
    if bf is not None and t >= bf:           return 'burnt'
    return 'scorched'
