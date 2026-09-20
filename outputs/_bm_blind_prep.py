"""Base-mark round: regenerate EVERY blind-panel image from committed code, and
check each against the PNG the readers actually saw (sha256 of the RGBA store).

Rounds 1-2 were rendered with the candidate at the pre-trail slot (_bm_proto.SLOT);
round 3 and the final design use the post-trail slot. For the banner the two are
pixel-identical on these frames (no trail touches its ink), which this script
also proves. In every candidate variant the old `fillText('BASE',...)` label is
removed, so the candidate is tested alone; the status-quo variant keeps it.

usage: _bm_blind_prep.py [--write]     default: verify only
"""
from __future__ import annotations
import hashlib, json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import _bm_proto as PR
from PIL import Image

R = os.path.join(BASE, "_bm")
OLD_LABEL = "ctx.fillText('BASE',dx+3,dy-3);"
FINAL_SLOT = "  // assignment lines (A): firefighter -> its assigned victim's cell"
FRAMES = {"q": "frame_east_101_s0.json", "b": "frame_west_101_s105.json", "s": "frame_south_202_s99.json",
          "w0": "frame_west_101_s0.json", "w30": "frame_west_101_s30.json", "s72": "frame_south_202_s72.json"}
FFB = r"""
  const _tt=(path)=>{ctx.setLineDash([]);ctx.lineWidth=3;ctx.strokeStyle='#000000';path();ctx.lineWidth=1;ctx.strokeStyle='#00FFCC';path();};
  const _ffd=(f,r)=>{const inSet=(x,y)=>x>=0&&x<W&&y>=0&&y<H&&(Math.abs(x-f.x)+Math.abs(y-f.y))<=r;const segs=[];
    for(let dy=-r;dy<=r;dy++)for(let dx=-r;dx<=r;dx++){const x=f.x+dx,y=f.y+dy;if(!inSet(x,y))continue;
      const x0=x*cs,x1=(x+1)*cs,yT=(H-1-y)*cs,yB=(H-y)*cs;
      if(!inSet(x-1,y))segs.push([x0,yT,x0,yB]);if(!inSet(x+1,y))segs.push([x1,yT,x1,yB]);
      if(!inSet(x,y+1))segs.push([x0,yT,x1,yT]);if(!inSet(x,y-1))segs.push([x0,yB,x1,yB]);}
    _tt(()=>{ctx.beginPath();for(const s of segs){ctx.moveTo(snap(s[0]),snap(s[1]));ctx.lineTo(snap(s[2]),snap(s[3]));}ctx.stroke();});};
"""


def source(variant: str, blob: dict) -> str:
    dm = PR.drawmap_head()
    if variant == "none":
        return dm
    dm2 = dm.replace(OLD_LABEL, "")
    if variant in ("flag", "flagL", "sign"):
        PR.FLAG_K = 1.4 if variant == "flagL" else 1.0
        return PR.inject(dm2, "flag" if variant != "sign" else "sign", "#770099", {})
    banner = PR.BANNER_JS + "  for(const d of _dps)_banner(d,'#770099');\n"
    src = dm2.replace(FINAL_SLOT, banner + FINAL_SLOT)
    if variant == "bannerB":
        ffb = FFB + "  const _ffs=%s,_rng={\"idle\":3,\"assigned\":1};\n  for(const f of (fr.firefighters||[])){const r=_rng[_ffs[f.id]];if(r)_ffd(f,r);}\n" \
              % json.dumps(blob.get("ff_state", {}))
        src = src.replace(PR.SLOT, ffb + PR.SLOT)
    return src


def sha(path: str) -> str:
    return hashlib.sha256(Image.open(path).convert("RGBA").tobytes()).hexdigest()


def main() -> int:
    write = "--write" in sys.argv
    jobs = []
    for name in ("_mapping.txt", "_mapping2.txt", "_mapping3.txt"):
        for line in open(os.path.join(R, "blind", name)):
            neutral, real = line.split()
            stem = real.replace("img3_", "").replace("img_", "").replace(".png", "")
            fk, variant = stem.rsplit("_", 1)
            jobs.append((neutral, fk, variant))
    bad = 0
    for neutral, fk, variant in jobs:
        blob = json.load(open(os.path.join(R, FRAMES[fk])))
        tmp = os.path.join(R, "proto", "_blind_regen.png")
        PR.render(PR.page(source(variant, blob), blob, False), tmp)
        seen = os.path.join(R, "blind", neutral)
        same = sha(tmp) == sha(seen)
        bad += (not same)
        print("%-8s frame %-4s variant %-8s regenerated == image the reader saw: %s" % (neutral, fk, variant, same))
        if write and not same:
            os.replace(tmp, seen)
    print("ALL %d BLIND IMAGES REPRODUCE" % len(jobs) if not bad else "%d of %d DO NOT REPRODUCE" % (bad, len(jobs)))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
