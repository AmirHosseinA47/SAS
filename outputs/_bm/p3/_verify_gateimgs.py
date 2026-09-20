import hashlib
from PIL import Image
SP="C:/Users/ahrar/AppData/Local/Temp/claude/E--Projects-SAS/16e3ff3e-5519-4661-ab76-dd6ac8f01aec/scratchpad/"
G="E:/Projects/SAS/outputs/_bm/p3/gate/"
def h(p):
    im=Image.open(p).convert('RGB'); return im.size, hashlib.sha256(im.tobytes()).hexdigest()[:16]
for mine, theirs, g in [('v_q_x1.png','shipped_q_x1.png','g01.png'),('v_b_x1.png','shipped_b_x1.png','g02.png'),('v_s_x1.png','shipped_s_x1.png','g03.png'),('v_q_x1.25.png','shipped_q_x1.25.png','g04.png'),('v_s_x1.5.png','shipped_s_x1.5.png','g09.png')]:
    a,b,c=h(SP+mine),h(G+theirs),h(G+g)
    print(mine, a, '| gate', theirs, b, '| blind', g, c, '| rerender==shipped', a==b, '| shipped==blind img', b==c)
