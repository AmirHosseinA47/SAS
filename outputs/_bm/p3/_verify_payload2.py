import json
pre = json.load(open('E:/Projects/SAS/outputs/_bm/p3/pre/_bm_payload_bmpre.json'))
post = json.load(open('E:/Projects/SAS/outputs/_bm_payload_bmpost.json'))
print('tags', pre['tag'], post['tag'], 'steps', pre['steps'], post['steps'], 'python equal', pre['python']==post['python'])
tot = 0
for c in sorted(pre['combos']):
    a, b = pre['combos'][c], post['combos'][c]
    n = len(a['stripped'])
    same_stripped = sum(1 for x, y in zip(a['stripped'], b['stripped']) if x == y)
    diff_full = sum(1 for x, y in zip(a['full'], b['full']) if x != y)
    # in pre, is stripped==full (no key to strip)?
    pre_sf = sum(1 for x, y in zip(a['stripped'], a['full']) if x == y)
    post_sf = sum(1 for x, y in zip(b['stripped'], b['full']) if x == y)
    print(c, 'n', n, len(b['stripped']), 'stripped identical', same_stripped, 'full differs', diff_full,
          '| pre stripped==full', pre_sf, 'post stripped==full', post_sf)
    print('    ff_keys pre', a['ff_keys']); print('    ff_keys post', b['ff_keys'])
    print('    grew by', sorted(set(b['ff_keys'])-set(a['ff_keys'])), 'lost', sorted(set(a['ff_keys'])-set(b['ff_keys'])))
    print('    depots equal', a['depots']==b['depots'], a['depots'])
    tot += same_stripped
print('total identical stripped frames', tot)
import os
print('post written', post['written'], 'pre written', pre['written'])
print('serve_dashboard mtime', os.path.getmtime('E:/Projects/SAS/serve_dashboard.py'))
