import json
P3='E:/Projects/SAS/outputs/_bm/p3/'
for fn in ['f_west_101_s200.json','f_west_101_s60.json','f_north_101_s192.json','f_south_202_s160.json']:
    b=json.load(open(P3+fn))
    print(fn)
    for r in b['frame']['panel']['firefighter_view']:
        print('   ', r, '| truth', b['ff_truth'].get(r['id']))
