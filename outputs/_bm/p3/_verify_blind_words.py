import json,re
B='E:/Projects/SAS/outputs/_bm/blind/'
r1=json.load(open(B+'_results.json',encoding='utf-8')); r2=json.load(open(B+'_results2.json',encoding='utf-8')); r3=json.load(open(B+'_results3.json',encoding='utf-8'))
def alltext(r): return ' '.join(str(v) for v in r.values() if isinstance(v,(str,list)))
print('== round 1: flag_word field and text mention, by variant')
for r in r1:
    t=alltext(r).lower()
    print(r['variant'].ljust(9), 'flag_word=',r['flag_word'], '| "flag" in text:', 'flag' in t, '| pennant:', 'pennant' in t, '| pole:', 'pole' in t, '| text_read=',repr(r['text_read'])[:60])
print('== round 2')
for r in r2:
    t=alltext(r).lower()
    print(r['variant'].ljust(9), '| flag:', 'flag' in t, '| pole:', 'pole' in t, '| label:', 'label' in t, '| text_read=',repr(r['text_read'])[:60])
    for m in re.finditer(r'[^.;]*\b(pole|flag)\b[^.;]*', alltext(r), flags=re.I):
        print('      >>', m.group(0).strip()[:200])
print('== round 3')
for r in r3:
    t=alltext(r).lower()
    print(r['variant'].ljust(11), '| flag:', 'flag' in t, '| pole:', 'pole' in t, '| text_read=',repr(r['text_read'])[:70])
    for m in re.finditer(r'[^.;]*\b(pole|flag|flagpole|flag-pole)\b[^.;]*', alltext(r), flags=re.I):
        print('      >>', m.group(0).strip()[:220])
