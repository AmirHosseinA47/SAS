"""Base-mark round, Part 1: PROTOTYPE renders. No source file is modified.

The shipped drawMap is sliced out of serve_dashboard.py at HEAD and a candidate
mark is injected as text at the exact z-order slot the implementation would use
(after the sensing overlays, before trails / assignment lines / unit markers),
then rendered by an installed headless Chrome. So a prototype is judged in the
real renderer, on real captured frames, at the real 560x560 canvas - not in a
mock-up. Chrome's --dump-dom returns cv.toDataURL() losslessly; no playwright.

usage: _bm_proto.py <frame.json> <out.png> <variant> [field_hex] [prob]
variants: none | flag | flagtext | sign | ffa | ffb
"""
from __future__ import annotations
import base64, hashlib, json, os, re, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
FLAG_K = 1.0   # size multiplier; set by callers exploring sizes
SLOT = "  const px=(gx)=>(gx+0.5)*cs, py=(gy)=>(H-1-gy+0.5)*cs;"

# The flag. Pixel-art on integer coordinates (fillRect only): every painted pixel
# is exactly one of three tones, so nothing is anti-aliased and the pixel audit
# can be exact. s scales the glyph with the block (s = 1 at the shipped 56px block).
FLAG_JS = r"""
  const _flag=(d,FIELD,withText,K)=>{
    const bw=d.size*cs, s=(K||1)*Math.min(1.5,Math.max(0.6,bw/56)), q=(v)=>Math.max(1,Math.round(v*s));
    const bx=Math.round(d.x*cs), by=Math.round((H-d.y-d.size)*cs), bR=Math.round((d.x+d.size)*cs);
    const east=(d.x>0)&&(d.x+d.size>=W);           // pole stands on the map-edge side
    const pw=q(3), poleL=east?(bR-q(4)-pw):(bx+q(4)), top=by+q(3), ph=q(30);
    const rows=q(11), lmin=q(2), lmax=q(17);
    const run=(j)=>rows<2?lmax:Math.round(lmin+(lmax-lmin)*(1-Math.abs(2*j-(rows-1))/(rows-1)));
    const rect=(x,y,w,h)=>ctx.fillRect(x,y,w,h);
    const pen=(grow,col)=>{ctx.fillStyle=col;
      for(let j=0;j<rows;j++){const len=run(j), y=top+q(2)+j;
        if(east)rect(poleL-len-grow,y-grow,len+grow,1+2*grow);
        else rect(poleL+pw,y-grow,len+grow,1+2*grow);}};
    pen(2,'#000000');
    ctx.fillStyle='#000000';rect(poleL,top,pw,ph);
    ctx.fillStyle='#FFFFFF';rect(poleL+1,top+1,Math.max(1,pw-2),ph-2);
    pen(1,'#FFFFFF');pen(0,FIELD);
    if(withText){ctx.font='bold 9px ui-monospace,monospace';ctx.textBaseline='alphabetic';
      const tw=ctx.measureText('BASE').width, tx=east?(bR-q(4)-tw):(bx+q(4)), ty=by+bw-q(5);
      ctx.lineJoin='round';ctx.lineWidth=3;ctx.strokeStyle='#000000';ctx.strokeText('BASE',tx,ty);
      ctx.fillStyle='#FFFFFF';ctx.fillText('BASE',tx,ty);}
  };
"""

# The banner flag: a flag in FORM (pole on the map-edge side, cloth flying inward)
# and a sign in CONTENT (the word BASE). Everything is fillRect on integer pixels
# except the glyphs, and those are CLIPPED to the cloth interior - so which
# pixels may change is an exact, font-independent set even though the glyph
# shapes themselves depend on the platform's monospace font.
BANNER_JS = r"""
  const _banner=(d,FIELD)=>{
    const bw=d.size*cs, s=Math.min(1.5,Math.max(0.6,bw/56)), q=(v)=>Math.max(1,Math.round(v*s));
    const bx=Math.round(d.x*cs), by=Math.round((H-d.y-d.size)*cs), bR=Math.round((d.x+d.size)*cs);
    const east=(d.x>0)&&(d.x+d.size>=W);           // pole stands on the map-edge side
    const pw=q(3), poleL=east?(bR-q(4)-pw):(bx+q(4)), top=by+q(3), ph=q(30);
    const cw=q(28), ch=q(15), cx=east?(poleL-cw+1):(poleL+pw-1);
    ctx.fillStyle='#000000';ctx.fillRect(poleL,top,pw,ph);ctx.fillRect(cx,top,cw,ch);
    ctx.fillStyle='#FFFFFF';ctx.fillRect(poleL+1,top+1,Math.max(1,pw-2),ph-2);ctx.fillRect(cx+1,top+1,cw-2,ch-2);
    ctx.fillStyle=FIELD;ctx.fillRect(cx+2,top+2,cw-4,ch-4);
    ctx.save();ctx.beginPath();ctx.rect(cx+2,top+2,cw-4,ch-4);ctx.clip();
    ctx.fillStyle='#FFFFFF';ctx.font='bold '+q(9)+'px ui-monospace,monospace';ctx.textAlign='center';ctx.textBaseline='middle';
    ctx.fillText('BASE',cx+cw/2,top+ch/2+0.5,cw-6);ctx.restore();
  };
"""

SIGN_JS = r"""
  const _sign=(d,FIELD)=>{
    const bw=d.size*cs, bx=Math.round(d.x*cs), by=Math.round((H-d.y-d.size)*cs), bR=Math.round((d.x+d.size)*cs);
    const east=(d.x>0)&&(d.x+d.size>=W);
    ctx.font='bold 9px ui-monospace,monospace';const tw=Math.ceil(ctx.measureText('BASE').width);
    const w=tw+8,h=13,x=east?(bR-4-w):(bx+4),y=by+4;
    ctx.fillStyle='#000000';ctx.fillRect(x,y,w,h);ctx.fillStyle='#FFFFFF';ctx.fillRect(x+1,y+1,w-2,h-2);
    ctx.fillStyle=FIELD;ctx.fillRect(x+2,y+2,w-4,h-4);
    ctx.fillStyle='#FFFFFF';ctx.textBaseline='alphabetic';ctx.fillText('BASE',x+4,y+10);
    ctx.fillStyle='#000000';ctx.fillRect(x+Math.floor(w/2)-1,y+h,3,8);ctx.fillStyle='#FFFFFF';ctx.fillRect(x+Math.floor(w/2),y+h,1,7);
  };
"""

# Item B prototypes: the survival-retreat tripwire as a staircase diamond.
FF_JS = r"""
  const _ffdiamond=(f,r)=>{
    const inSet=(x,y)=>x>=0&&x<W&&y>=0&&y<H&&(Math.abs(x-f.x)+Math.abs(y-f.y))<=r;const segs=[];
    for(let dy=-r;dy<=r;dy++)for(let dx=-r;dx<=r;dx++){const x=f.x+dx,y=f.y+dy;if(!inSet(x,y))continue;
      const x0=x*cs,x1=(x+1)*cs,yT=(H-1-y)*cs,yB=(H-y)*cs;
      if(!inSet(x-1,y))segs.push([x0,yT,x0,yB]);if(!inSet(x+1,y))segs.push([x1,yT,x1,yB]);
      if(!inSet(x,y+1))segs.push([x0,yT,x1,yT]);if(!inSet(x,y-1))segs.push([x0,yB,x1,yB]);}
    twoTone(()=>{ctx.beginPath();for(const s of segs){ctx.moveTo(snap(s[0]),snap(s[1]));ctx.lineTo(snap(s[2]),snap(s[3]));}ctx.stroke();});
  };
"""


def drawmap_head() -> str:
    src = subprocess.run(["git", "-C", REPO, "show", "HEAD:serve_dashboard.py"],
                         capture_output=True, check=True).stdout.decode("utf-8")
    i = src.index("function drawMap(fr){"); j = src.index("function render(fr){", i)
    return src[i:j]


def inject(dm: str, variant: str, field: str, ffstate: dict) -> str:
    if variant == "none":
        return dm
    assert dm.count(SLOT) == 1, "slot anchor not unique"
    if variant in ("flag", "flagtext"):
        body = FLAG_JS + "  for(const d of _dps)_flag(d,'%s',%s,%r);\n" % (
            field, "true" if variant == "flagtext" else "false", FLAG_K)
    elif variant == "banner":
        body = BANNER_JS + "  for(const d of _dps)_banner(d,'%s');\n" % field
    elif variant == "sign":
        body = SIGN_JS + "  for(const d of _dps)_sign(d,'%s');\n" % field
    elif variant in ("ffa", "ffb"):
        rng = {"idle": 3, "assigned": 1} if variant == "ffb" else {"idle": 3}
        body = FF_JS + "  const _ffs=%s,_rng=%s;\n  for(const f of (fr.firefighters||[])){const r=_rng[_ffs[f.id]];if(r)_ffdiamond(f,r);}\n" % (
            json.dumps(ffstate), json.dumps(rng))
    else:
        raise SystemExit("unknown variant " + variant)
    return dm.replace(SLOT, body + SLOT)


def page(dm: str, blob: dict, prob: bool) -> str:
    W, H, cs = blob["width"], blob["height"], blob["cs"]
    return ("<!DOCTYPE html><html><body style='margin:0'><canvas id='cv' width=%d height=%d></canvas>"
            "<pre id='out'></pre><script>\n"
            "const BW=[\"#ffffff\",\"#e6e6e6\",\"#c9c9c9\",\"#b1b1b1\",\"#a1a1a1\",\"#818181\","
            "\"#636363\",\"#474747\",\"#303030\",\"#1a1a1a\",\"#000000\"];\n"
            "let W=%d,H=%d,cs=%r,probMode=%s;\nlet FOVR=%d,VFR=%d;\n"
            "const cv=document.getElementById('cv'),ctx=cv.getContext('2d');\n%s\ndrawMap(%s);\n"
            "document.getElementById('out').textContent='PNGDATA:'+cv.toDataURL('image/png')+':END';\n"
            "</script></body></html>"
            % (int(W * cs), int(H * cs), W, H, cs, "true" if prob else "false",
               blob.get("fov_radius", 8), blob.get("victim_flee_radius", 0), dm, json.dumps(blob["frame"])))


def render(html: str, out_png: str) -> str:
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "page.html")
        open(p, "w", encoding="utf-8").write(html)
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
                            "--force-device-scale-factor=1", "--user-data-dir=" + os.path.join(td, "prof"),
                            "--dump-dom", "file:///" + p.replace("\\", "/")],
                           capture_output=True, timeout=180)
        dom = r.stdout.decode("utf-8", "replace")
    m = re.search(r"PNGDATA:data:image/png;base64,([A-Za-z0-9+/=]+):END", dom)
    if not m:
        raise SystemExit("no PNG in DOM: " + r.stderr.decode("utf-8", "replace")[-400:])
    open(out_png, "wb").write(base64.b64decode(m.group(1)))
    from PIL import Image
    return hashlib.sha256(Image.open(out_png).convert("RGBA").tobytes()).hexdigest()


def main() -> int:
    blob = json.load(open(sys.argv[1])); out = sys.argv[2]; variant = sys.argv[3]
    field = sys.argv[4] if len(sys.argv) > 4 else "#770099"
    prob = len(sys.argv) > 5 and sys.argv[5] == "prob"
    sha = render(page(inject(drawmap_head(), variant, field, blob.get("ff_state", {})), blob, prob), out)
    print("%s %s %s %s" % (os.path.basename(out), variant, field, sha[:16]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
