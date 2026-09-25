import json, sys
def load(p):
    raw = open(p, 'rb').read()
    for enc in ('utf-8', 'utf-16', 'utf-8-sig'):
        try:
            return json.loads(raw.decode(enc))
        except Exception:
            pass
    raise SystemExit('cannot decode ' + p)

p, vid, ffid, s0, s1 = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
d = load(p)
bi = d['burn_intervals']
def burning(cell, step):
    iv = bi.get('%d,%d' % cell)
    if not iv:
        return False
    for a, b in iv:
        if a <= step and (b is None or step < b):
            return True
    return False
def nb(cell):
    x, y = cell
    out = []
    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx, ny = x+dx, y+dy
        if 0 <= nx < 50 and 0 <= ny < 50:
            out.append((nx, ny))
    return out
def stat(cell, step):
    own = burning(cell, step)
    nbs = [burning(n, step) for n in nb(cell)]
    return 'own=%d nb=%d/%d' % (own, sum(nbs), len(nbs))
print('eval', d['eval'])
for k in ('exit_starts','completions','assigns','unassigns','unreachable_marks','unreachable_escape_log','retargets'):
    for r in d.get(k, []):
        print(k, r)
fl = [r for r in d.get('victim_flee_log', []) if r['victim_id'] == vid]
for r in fl:
    if s0 <= r['step'] <= s1:
        print('flee', r)
print('leash anchor', d.get('victim_leash_anchors', {}).get(vid), 'reanchors', d.get('victim_leash_reanchors', {}).get(vid))
for i in range(s0 - 1, min(s1, len(d['ff_steps']))):
    step = i + 1
    ff = [r for r in d['ff_steps'][i] if r[0] == ffid]
    vv = [r for r in d['victim_steps'][i] if r[0] == vid]
    bind = [r for r in d['ff_bind_steps'][i] if r[0] == ffid] if d.get('ff_bind_steps') else []
    fpos = tuple(ff[0][1]) if ff and ff[0][1] else None
    vpos = tuple(vv[0][1]) if vv and vv[0][1] else None
    print(step, 'FF', ff, bind, stat(fpos, step) if fpos else '', '| V', vv, stat(vpos, step) if vpos else '')
