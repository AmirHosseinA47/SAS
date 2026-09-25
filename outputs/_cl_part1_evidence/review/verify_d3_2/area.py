import json, sys
def load(p):
    raw = open(p, 'rb').read()
    for enc in ('utf-8', 'utf-16', 'utf-8-sig'):
        try:
            return json.loads(raw.decode(enc))
        except Exception:
            pass
    raise SystemExit('cannot decode ' + p)
p = sys.argv[1]
x0, x1, y0, y1, s0, s1 = map(int, sys.argv[2:8])
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
for step in range(s0, s1 + 1):
    print('step', step, '(rows y from', y1, 'down to', y0, '; cols x', x0, '..', x1, ')')
    for y in range(y1, y0 - 1, -1):
        row = ''
        for x in range(x0, x1 + 1):
            row += '#' if burning((x, y), step) else '.'
        print('  y=%2d %s' % (y, row))
