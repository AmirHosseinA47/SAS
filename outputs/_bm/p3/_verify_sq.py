import json
tot = 0
for fn in ['_results.json','_results2.json','_results3.json']:
    rows = json.load(open('E:/Projects/SAS/outputs/_bm/blind/'+fn))
    tot += len(rows)
    kinds = {}
    for x in rows:
        k = x.get('variant')
        kinds.setdefault(k, []).append((x.get('img'), x.get('tl_conf'), x.get('br_conf')))
    print(fn, len(rows))
    for k, v in kinds.items():
        tl = [a[1] for a in v if isinstance(a[1], (int, float))]; br = [a[2] for a in v if isinstance(a[2], (int, float))]
        print('   ', k, 'n', len(v), 'TL mean %.1f' % (sum(tl)/max(1,len(tl))), 'BR mean %.1f' % (sum(br)/max(1,len(br))), v)
print('total part1 responses', tot)
