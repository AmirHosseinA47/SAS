import hashlib
from PIL import Image
SP="C:/Users/ahrar/AppData/Local/Temp/claude/E--Projects-SAS/16e3ff3e-5519-4661-ab76-dd6ac8f01aec/scratchpad/"
G="E:/Projects/SAS/outputs/_bm/p3/gate/"
def h(p):
    im=Image.open(p).convert('RGB'); return im.size, hashlib.sha256(im.tobytes()).hexdigest()[:16]
print(h(SP+'v_sq_s_x1.png'), h(G+'statusquo_s_x1.png'), h(G+'g12.png'))
