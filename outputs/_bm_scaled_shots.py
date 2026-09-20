"""Base-mark round Part 3: what the SHIPPED page looks like on a SCALED display.

The canvas has no devicePixelRatio handling, so at Windows 125% / 150% display
scaling the browser RESAMPLES the 560x560 bitmap: a 1 px keyline or a 9 px glyph
is softened. The pixel audit reads the backing store and cannot see that. This
loads the whole shipped HTML (CSS included - so the canvas border and its rounded
corner are real too), renders a real frame through the page's own render(), takes
a page SCREENSHOT at --force-device-scale-factor, and crops the canvas.

usage: _bm_scaled_shots.py <rev|WORKTREE> <scale> <out.png> <frame.json>
"""
from __future__ import annotations
import json, os, re, subprocess, sys, tempfile, base64

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from _bm_page_e2e import html_of, CHROME
from PIL import Image

DRIVER = r"""
<script>
(function(){
  window.addEventListener('unhandledrejection',e=>{});
  const B=__BLOB__;
  W=B.width;H=B.height;cs=cv.width/W;FOVR=B.fov_radius;VFR=B.victim_flee_radius;totalSteps=240;
  document.getElementById('strip').style.display='block';
  document.getElementById('layout').style.display='grid';
  curFrame=B.frame;render(curFrame);setLegend();
  window.scrollTo(0,0);
  const r=cv.getBoundingClientRect();
  document.getElementById('e2e').textContent='RECT:'+[r.left,r.top,r.width,r.height].join(',')+':END';
})();
</script>
"""


def main() -> int:
    rev, scale, out, fp = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4]
    blob = json.load(open(fp))
    page = html_of(rev).replace("</body>", "<pre id='e2e' style='display:none'></pre>"
                                + DRIVER.replace("__BLOB__", json.dumps(blob)) + "</body>")
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "page.html"); open(p, "w", encoding="utf-8").write(page)
        url = "file:///" + p.replace("\\", "/")
        common = [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                  "--force-device-scale-factor=%g" % scale, "--window-size=1600,1500",
                  "--user-data-dir=" + os.path.join(td, "prof"), "--virtual-time-budget=4000"]
        dom = subprocess.run(common + ["--dump-dom", url], capture_output=True, timeout=240).stdout.decode("utf-8", "replace")
        m = re.search(r"RECT:([-0-9.,]+):END", dom)
        if not m:
            raise SystemExit("no canvas rect - page script did not run")
        left, top, w, h = (float(v) for v in m.group(1).split(","))
        shot = os.path.join(td, "shot.png")
        subprocess.run(common + ["--screenshot=" + shot, url], capture_output=True, timeout=240)
        im = Image.open(shot).convert("RGB")
        box = tuple(int(round(v * scale)) for v in (left, top, left + w, top + h))
        im.crop(box).save(out)
    print("%s scale %g canvas rect %s -> crop %s -> %s" % (os.path.basename(fp), scale, (left, top, w, h), box, out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
