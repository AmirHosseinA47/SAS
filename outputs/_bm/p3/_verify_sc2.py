import json, hashlib, os
pre = json.load(open('E:/Projects/SAS/outputs/_bm/p3/pre/_sc_control_bmpre.json'))
post = json.load(open('E:/Projects/SAS/outputs/_sc_control_bmpost.json'))
print('tags', pre['tag'], post['tag'], 'steps', pre['steps'], post['steps'])
print('combos', sorted(pre['runs']), sorted(post['runs']))
for c in sorted(pre['runs']):
    a, b = pre['runs'][c], post['runs'][c]
    print(c, 'nfields', len(a), len(b), 'keys equal', sorted(a)==sorted(b))
    diffs = [k for k in a if a[k] != b.get(k)]
    print('   differing fields:', diffs)
    print('   sorted json equal:', json.dumps(a, sort_keys=True)==json.dumps(b, sort_keys=True))
    fn = c.split('|')[0].replace('/', '-') + '_' + c.split('|')[1]
    pa = 'E:/Projects/SAS/outputs/_bm/p3/pre/_sc_control_bmpre_%s.stdout.txt' % fn
    pb = 'E:/Projects/SAS/outputs/_sc_control_bmpost_%s.stdout.txt' % fn
    da, db = open(pa,'rb').read(), open(pb,'rb').read()
    print('   stdout bytes', len(da), len(db), 'identical', da==db, 'sha', hashlib.sha256(da).hexdigest()[:12])
    e = a['eval']
    print('   eval', e['rescued'], e['dead'], e['firefighter_deaths'], e['burnt_cells'], e['steps_run'], e['terminal_step'])
print('whole json equal modulo tag:', {k:v for k,v in pre.items() if k!='tag'}=={k:v for k,v in post.items() if k!='tag'})
