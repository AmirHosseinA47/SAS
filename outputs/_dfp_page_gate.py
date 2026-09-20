# -*- coding: utf-8 -*-
"""Non-burnable-depot round: the FULL-PAGE layout gate the base-mark round lacked.

The base-mark round recorded that its own validation was pixel-exact INSIDE the
map and blind to everything outside it: outputs/_bm_scaled_shots.py takes a
full-viewport screenshot and then crops it to the canvas rectangle before saving
(:55-57), and the only DOM measurement anywhere in outputs/ is the canvas
bounding box (outputs/_bm_page_e2e.py:58). A table cell wrapped and no test, no
payload digest and no pixel audit saw it - only a human looking at a full-page
screenshot did. This round adds a legend chip, so it has to close that gap.

WHAT THIS DOES, at display scales 1, 1.25 and 1.5:
  * saves the WHOLE PAGE as a PNG - uncropped - for PRE and POST, so the pair
    can be looked at;
  * measures, in the page, with real layout: every table's per-row offsetHeight,
    every panel's scrollWidth vs clientWidth, the document's own scrollWidth vs
    clientWidth, the legend strip's height and chip count, and the bounding box
    of every card. These are NUMERIC ASSERTIONS, not an eyeball;
  * diffs PRE against POST per scale and reports where on the page the pixels
    moved, by named region.

THREE ARMS, and the third is the point:
  A  PRE html  + PRE frame   what 6281542 would have drawn for this model state
  B  POST html + POST frame  what the change draws for the same state
  C  POST html + PRE frame   the SAME payload through the new page - isolates the
                             layout delta (one more legend chip) from the colour
                             delta, which outputs/_dfp_payload.py already proves
                             exactly at the payload level

usage: _dfp_page_gate.py [scale ...]     (default 1 1.25 1.5)
  -> outputs/_dfp_page/<arm>_x<scale>.png, outputs/_dfp_page_gate.json/.txt
"""
from __future__ import annotations

import ast
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)
OUTDIR = os.path.join(BASE, "_dfp_page")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PRE_REV = "6281542"
NEW_HEX = "#193cff"
OUT = []


def hex2rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb2hex(r, g, b):
    return "#%02x%02x%02x" % (int(r), int(g), int(b))


def over_pct(src, pct, dst):
    return tuple((pct * s + (100 - pct) * d + 50) // 100 for s, d in zip(src, dst))


DEPOT = hex2rgb("#770099")


def P(s=""):
    OUT.append(str(s))
    print(s)
    sys.stdout.flush()


def html_of(rev):
    if rev == "WORKTREE":
        src = open(os.path.join(REPO, "serve_dashboard.py"), encoding="utf-8").read()
    else:
        src = subprocess.run(["git", "-C", REPO, "show", "%s:serve_dashboard.py" % rev],
                             capture_output=True, check=True).stdout.decode("utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "HTML":
            return node.value.value
    raise SystemExit("no HTML constant in %s" % rev)


# The measurement driver. Everything it reports is layout, read after a real
# render at a real device scale factor - the thing no existing tool looked at.
DRIVER = r"""
<script>
(function(){
  const errs=[]; window.addEventListener('error',e=>errs.push(String(e.message)));
  window.addEventListener('unhandledrejection',e=>{});
  const B=__BLOB__;
  const R=el=>{const r=el.getBoundingClientRect();
               return [Math.round(r.left*100)/100,Math.round(r.top*100)/100,
                       Math.round(r.width*100)/100,Math.round(r.height*100)/100];};
  const OV=el=>({tag:el.tagName.toLowerCase(),id:el.id||null,cls:el.className||null,
                 scrollW:el.scrollWidth,clientW:el.clientWidth,
                 scrollH:el.scrollHeight,clientH:el.clientHeight,rect:R(el)});
  try{
    W=B.width;H=B.height;cs=cv.width/W;FOVR=B.fov_radius;VFR=B.victim_flee_radius;totalSteps=240;
    document.getElementById('strip').style.display='block';
    document.getElementById('layout').style.display='grid';
    curFrame=B.frame;render(curFrame);setLegend();
    const out={errors:errs};
    out.dpr=window.devicePixelRatio;
    out.doc={scrollW:document.documentElement.scrollWidth,
             clientW:document.documentElement.clientWidth,
             scrollH:document.documentElement.scrollHeight,
             bodyScrollW:document.body.scrollWidth,bodyClientW:document.body.clientWidth};
    // every table, its rows, and whether the rows are the same height
    out.tables=[...document.querySelectorAll('table')].map(t=>{
      const rows=[...t.querySelectorAll('tr')];
      const hs=rows.map(r=>Math.round(r.getBoundingClientRect().height*100)/100);
      const body=hs.slice(1);
      return {panel:(t.closest('.card')||{}).id||(t.parentElement||{}).id||null,
              rows:hs.length,heights:hs,body_heights:body,
              body_uniform:body.length?body.every(h=>h===body[0]):true,
              cells_per_row:rows.map(r=>r.children.length),
              overflow:OV(t)};
    });
    // every panel that can clip, plus the two legend strips
    const sel=['.card','.legend','.mission-strip','.setup','#layout','.center','.col','.eval'];
    out.panels=[];
    for(const s of sel) for(const el of document.querySelectorAll(s)) out.panels.push(OV(el));
    out.legend_normal_html=document.getElementById('maplegend').innerHTML;
    out.legend_normal_chips=document.querySelectorAll('#maplegend span').length;
    out.legend_normal_rect=R(document.getElementById('maplegend'));
    out.canvas_rect=R(cv);
    out.png_normal=cv.toDataURL('image/png');
    document.getElementById('probtoggle').click();
    out.legend_prob_html=document.getElementById('maplegend').innerHTML;
    out.legend_prob_chips=document.querySelectorAll('#maplegend span').length;
    out.legend_prob_rect=R(document.getElementById('maplegend'));
    out.png_prob=cv.toDataURL('image/png');
    document.getElementById('probtoggle').click();
    out.legend_back_html=document.getElementById('maplegend').innerHTML;
    document.getElementById('dfp').textContent='DFPJSON:'+btoa(unescape(encodeURIComponent(JSON.stringify(out))))+':END';
  }catch(e){document.getElementById('dfp').textContent='DFPJSON:'+btoa(JSON.stringify({fatal:String(e&&e.stack||e),errors:errs}))+':END';}
})();
</script>
"""


def page_of(html, blob):
    page = html.replace("</body>", "<pre id='dfp'></pre>"
                        + DRIVER.replace("__BLOB__", json.dumps(blob)) + "</body>")
    assert "id='dfp'" in page
    return page


COMMON = ["--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
          "--no-sandbox", "--window-size=1600,1600", "--virtual-time-budget=6000"]


def run(html, blob, scale, png_path):
    """One Chrome run for the DOM measurements, one for the FULL-PAGE screenshot."""
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "page.html")
        open(p, "w", encoding="utf-8").write(page_of(html, blob))
        url = "file:///" + p.replace("\\", "/")
        prof = "--user-data-dir=" + os.path.join(td, "prof")
        sf = "--force-device-scale-factor=%g" % scale
        r = subprocess.run([CHROME] + COMMON + [sf, prof, "--dump-dom", url],
                           capture_output=True, timeout=300)
        m = re.search(r"DFPJSON:([A-Za-z0-9+/=]+):END", r.stdout.decode("utf-8", "replace"))
        if not m:
            raise SystemExit("no driver result at scale %s (JS syntax error?)\n%s"
                             % (scale, r.stderr.decode("utf-8", "replace")[-900:]))
        res = json.loads(base64.b64decode(m.group(1)).decode("utf-8"))
        shot = os.path.join(td, "shot.png")
        subprocess.run([CHROME] + COMMON + [sf, "--user-data-dir=" + os.path.join(td, "prof2"),
                                            "--screenshot=" + shot, url],
                       capture_output=True, timeout=300)
        if os.path.exists(shot):
            shutil.copyfile(shot, png_path)          # the WHOLE page, never cropped
    return res


def _prob_png(res):
    import base64 as _b64
    import io as _io
    from PIL import Image
    png = res.get("png_prob") or ""
    if not png.startswith("data:image/png;base64,"):
        return None
    return Image.open(_io.BytesIO(_b64.b64decode(png.split(",", 1)[1]))).convert("RGB")


def prob_mode_check(res, blob, ref=None):
    """Does PROBABILITY mode actually paint the cleared ground?

    The legend carries the chip in BOTH branches, so the probability surface has
    to draw the colour or the chip names something that is not on screen. Nothing
    else in this round renders that path: the payload proof is map-mode only, and
    the base-mark pixel audit varies drawMap with the payload held FIXED, which
    cannot see a colour that arrives IN the payload.

    TWO THINGS THE FIRST VERSION OF THIS CHECK GOT WRONG, both found by running it:

     1. LATER LAYERS. Sampling a cell centre and demanding the ground colour
        ignores everything drawn after the ground - the BASE banner (opaque), UAV
        and firefighter trails and the FOV frame (semi-transparent). 18 of the 50
        cleared cells are under one of those. That is the same `later_layers`
        problem outputs/_bm_pixelaudit.py solves by predicting the covered set.
        Here the reference arm does it without a geometry model: C_layout is the
        SAME page with the OLD payload, so a cell whose pixel DIFFERS between the
        two arms has the new ground showing through (tinted or not), and a cell
        whose pixel is IDENTICAL is fully occluded by an opaque later layer. Both
        are correct outcomes; only "identical AND not the ground colour AND the
        canvas shows no change anywhere in this depot" would be a real miss.

     2. THE COMPOSITE IS OFF BY ONE. This round's arithmetic composites
        rgba(119,0,153,0.22) over #193cff with round-half-up in byte space and
        gets #2e2fe9; Chrome paints #2d2ee9. One unit on one channel, about 0.1
        dE - far below the ~2.3 dE JND and below any threshold in this round - but
        an exact equality test fails on it. Tolerance is +-1 per channel, and the
        discrepancy is recorded rather than hidden, because every composite entry
        in the colour instrument's palette is built with the same arithmetic.

    The canvas backing store is 560x560 whatever the device scale factor, because
    the <canvas> width/height attributes are fixed - so this is scale-independent.
    """
    cells = (blob.get("frame") or {}).get("nofuel") or []
    out = {"expected": len(cells), "ground": 0, "showing_through": 0, "occluded": 0,
           "colour": None, "fail": None, "misses": [], "diff_px": None,
           "diff_outside_depots": None}
    if not cells:
        return out
    im = _prob_png(res)
    if im is None:
        out["fail"] = "no probability-mode canvas captured"
        return out
    W, H = int(blob["width"]), int(blob["height"])
    cs = im.size[0] / float(W)
    want = over_pct(DEPOT, 22, hex2rgb(NEW_HEX))
    out["colour"] = rgb2hex(*want)
    px = im.load()
    rim = _prob_png(ref) if ref is not None else None
    rpx = rim.load() if rim is not None else None
    for k in cells:
        x, y = (int(v) for v in k.split(","))
        cx, cy = int(x * cs + cs / 2), int((H - 1 - y) * cs + cs / 2)
        got = px[cx, cy]
        if all(abs(a - b) <= 1 for a, b in zip(got, want)):
            out["ground"] += 1
        elif rpx is not None and rpx[cx, cy] != got:
            out["showing_through"] += 1
        elif rpx is not None:
            out["occluded"] += 1
            out["misses"].append([k, rgb2hex(*got)])
        else:
            out["misses"].append([k, rgb2hex(*got)])
    # THE STRONG CHECK: with the page held fixed and only the payload changed,
    # every pixel of the probability canvas that moved must be inside a depot.
    if rim is not None and rim.size == im.size:
        import numpy as np
        A = np.asarray(im, dtype=np.uint8)
        B = np.asarray(rim, dtype=np.uint8)
        diff = np.any(A != B, axis=2)
        mask = np.zeros_like(diff)
        # The mask has to be the JS rect, not a nominal cell. drawMap fills
        # ctx.fillRect(x*cs, (H-1-y)*cs, Math.ceil(cs), Math.ceil(cs)) from a
        # FRACTIONAL origin (cs = 560/50 = 11.2) with an integer ceil(cs) = 12
        # extent, so a painted rect overhangs the nominal cell by up to a pixel
        # on each side. A nominal-cell mask leaves a one-pixel sliver around the
        # outside of each depot block - about 109 px - and reads as a leak.
        import math as _math
        ext = int(_math.ceil(cs))
        for k in cells:
            x, y = (int(v) for v in k.split(","))
            x0, y0 = int(_math.floor(x * cs)), int(_math.floor((H - 1 - y) * cs))
            mask[max(0, y0):y0 + ext + 1, max(0, x0):x0 + ext + 1] = True
        out["diff_px"] = int(np.count_nonzero(diff))
        out["diff_outside_depots"] = int(np.count_nonzero(diff & ~mask))
        if out["diff_px"] == 0:
            out["fail"] = "probability mode is IDENTICAL with and without the cleared ground"
        elif out["diff_outside_depots"]:
            out["fail"] = ("%d probability-mode pixels changed OUTSIDE a cleared cell"
                           % out["diff_outside_depots"])
    if out["ground"] == 0:
        out["fail"] = "not one cleared cell shows the cleared colour in probability mode"
    return out


def measure(res):
    """Everything numeric the page reports, as a flat comparable dict."""
    d = res["doc"]
    m = {"doc_scrollW": d["scrollW"], "doc_clientW": d["clientW"],
         "doc_scrollH": d["scrollH"],
         "body_scrollW": d["bodyScrollW"], "body_clientW": d["bodyClientW"],
         "legend_normal_rect": res["legend_normal_rect"],
         "legend_prob_rect": res["legend_prob_rect"],
         "canvas_rect": res["canvas_rect"],
         "n_tables": len(res["tables"])}
    for i, t in enumerate(res["tables"]):
        k = "table%d_%s" % (i, t["panel"])
        m[k + "_heights"] = t["heights"]
        m[k + "_cells_per_row"] = t["cells_per_row"]
        m[k + "_scrollW"] = t["overflow"]["scrollW"]
        m[k + "_clientW"] = t["overflow"]["clientW"]
        m[k + "_rect"] = t["overflow"]["rect"]
    for pn in res["panels"]:
        k = "panel_%s_%s" % (pn["tag"], (pn["id"] or pn["cls"] or "").replace(" ", "."))
        n, base = 0, k
        while k in m:
            n += 1
            k = "%s#%d" % (base, n)
        m[k] = [pn["scrollW"], pn["clientW"], pn["rect"]]
    return m


def absolute(res):
    """What must hold in ANY arm, this change or not. Returns a list of failures."""
    bad = []
    if res.get("fatal"):
        return ["FATAL in page: %s" % res["fatal"][:300]]
    if res.get("errors"):
        bad.append("javascript errors: %s" % res["errors"][:3])
    d = res["doc"]
    if d["scrollW"] > d["clientW"]:
        bad.append("DOCUMENT scrolls horizontally: scrollW %s > clientW %s"
                   % (d["scrollW"], d["clientW"]))
    if d["bodyScrollW"] > d["bodyClientW"] + 1:
        bad.append("BODY scrolls horizontally: %s > %s" % (d["bodyScrollW"], d["bodyClientW"]))
    if res["legend_normal_html"] != res["legend_back_html"]:
        bad.append("legend not restored after toggling probability mode twice")
    return bad


def shape(res):
    """Layout facts that are PROPERTIES OF THE PAGE, not of this change.

    REPORTED, NEVER FAILED ON - and that is a maintainer ruling, not an
    oversight. The brief asked for an absolute assertion that table row heights
    are equal and no panel overflows. At 6281542, BEFORE this change touches
    anything, the UAV panel already mixes 4-cell rows with 2-cell continuation
    rows (body row heights 22 and 43) and its table's scrollWidth exceeds its
    clientWidth by 13 px. So the absolute form is a pre-existing condition of the
    page, not a gate on this round; the base-mark lesson was about a CHANGE (a
    cell wrapped and nothing saw it), not about absolute compliance.

    THE GATE IS THEREFORE THE DELTA: this list must be IDENTICAL between the two
    arms, and every one of the 41 measured quantities must be unchanged except
    the legend strip's own geometry. If this change had made the UAV panel worse,
    or started an overflow anywhere else, that catches it.

    The absolute measurement is printed at every scale so the pre-existing
    condition stays visible and can be decided on separately. See section 9.3 of
    outputs/depotfireproof_report.txt."""
    out = []
    for t in res["tables"]:
        if not t["body_uniform"]:
            out.append("table in %s: body row heights %s"
                       % (t["panel"], sorted(set(t["body_heights"]))))
        if len(set(t["cells_per_row"][1:])) > 1:
            out.append("table in %s: ragged cell counts %s" % (t["panel"], t["cells_per_row"]))
        o = t["overflow"]
        if o["scrollW"] > o["clientW"] + 1:
            out.append("table in %s: scrollW %s > clientW %s"
                       % (t["panel"], o["scrollW"], o["clientW"]))
    for pn in res["panels"]:
        if pn["scrollW"] > pn["clientW"] + 1:
            out.append("panel %s#%s: scrollW %s > clientW %s"
                       % (pn["tag"], pn["id"] or pn["cls"], pn["scrollW"], pn["clientW"]))
    return out


def sha(path):
    import hashlib
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def region_diff(a_png, b_png, regions):
    """Where the two FULL pages differ, counted in NAMED regions.

    Exact: two pixels are equal or they are not, no tolerance - the same rule
    outputs/_bm_pixelaudit.py uses. Vectorised, because a 2400x2400 page at
    scale 1.5 is 5.8M pixels and the per-pixel Python loop the earlier audits
    used would dominate the run.
    """
    import numpy as np
    from PIL import Image
    a = Image.open(a_png).convert("RGB")
    b = Image.open(b_png).convert("RGB")
    if a.size != b.size:
        return {"size_mismatch": [list(a.size), list(b.size)]}
    A = np.asarray(a, dtype=np.uint8)
    B = np.asarray(b, dtype=np.uint8)
    diff = np.any(A != B, axis=2)
    h, w = diff.shape
    out = {}
    claimed = np.zeros_like(diff)
    for k, (x0, y0, x1, y1) in regions.items():
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(w, x1), min(h, y1)
        m = np.zeros_like(diff)
        if x1 > x0 and y1 > y0:
            m[y0:y1, x0:x1] = True
        out[k] = int(np.count_nonzero(diff & m & ~claimed))
        claimed |= m
    out["_outside_all_named_regions"] = int(np.count_nonzero(diff & ~claimed))
    out["_total_changed_px"] = int(np.count_nonzero(diff))
    out["_page_px"] = int(w * h)
    ys, xs = np.nonzero(diff)
    out["_changed_bbox"] = ([int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
                            if xs.size else None)
    return out


def main():
    scales = [float(s) for s in sys.argv[1:]] or [1.0, 1.25, 1.5]
    os.makedirs(OUTDIR, exist_ok=True)
    pre_blob = json.load(open(os.path.join(BASE, "_dfp_frame_pre.json")))
    post_blob = json.load(open(os.path.join(BASE, "_dfp_frame_post.json")))
    pre_html, post_html = html_of(PRE_REV), html_of("WORKTREE")
    ARMS = [("A_pre", pre_html, pre_blob, "6281542 page + 6281542 payload"),
            ("B_post", post_html, post_blob, "the change: new page + new payload"),
            ("C_layout", post_html, pre_blob, "new page + OLD payload - isolates the layout delta")]

    P("=" * 96)
    P("FULL-PAGE LAYOUT GATE  -  outputs/_dfp_page_gate.py")
    P("=" * 96)
    P("  scales %s | window 1600x1600 | full page saved UNCROPPED to %s" % (scales, OUTDIR))
    P("  Chrome %s" % (CHROME if os.path.exists(CHROME) else "NOT FOUND - " + CHROME))
    P("  frame: seed %s wind %s step %s ; cleared cells in the payload: %d"
      % (post_blob["seed"], post_blob["wind"], post_blob["steps"],
         len(post_blob["frame"].get("nofuel") or [])))
    results, allok = {}, True
    for scale in scales:
        P("")
        P("-" * 96)
        P("DISPLAY SCALE %g" % scale)
        P("-" * 96)
        raw = {}
        for name, html, blob, what in ARMS:
            png = os.path.join(OUTDIR, "%s_x%g.png" % (name, scale))
            res = run(html, blob, scale, png)
            raw[name] = res
            bad = absolute(res)
            allok &= not bad
            results["%s_x%g" % (name, scale)] = {
                "absolute_failures": bad, "shape": shape(res), "measure": measure(res),
                "legend_normal_chips": res.get("legend_normal_chips"),
                "legend_prob_chips": res.get("legend_prob_chips"),
                "png": png, "png_sha": sha(png) if os.path.exists(png) else None}
            nt = len(res.get("tables") or [])
            rows = sum(t["rows"] for t in (res.get("tables") or []))
            P("  %-9s %-46s absolute checks: %s" % (name, what, "PASS" if not bad else "FAIL"))
            P("              doc scrollW/clientW %s/%s  body %s/%s | tables %d (%d rows)"
              % (res["doc"]["scrollW"], res["doc"]["clientW"],
                 res["doc"]["bodyScrollW"], res["doc"]["bodyClientW"], nt, rows))
            P("              legend chips normal %s prob %s | legend strip rect %s | canvas rect %s"
              % (res.get("legend_normal_chips"), res.get("legend_prob_chips"),
                 res.get("legend_normal_rect"), res.get("canvas_rect")))
            for b in bad:
                P("              !! %s" % b)
        # PROBABILITY MODE, after all three arms exist: B_post against C_layout,
        # which is the SAME page with the OLD payload.
        prob = prob_mode_check(raw["B_post"], post_blob, ref=raw["C_layout"])
        results["prob_x%g" % scale] = prob
        if prob["expected"]:
            P("  PROBABILITY MODE (B_post vs C_layout, same page, old payload):")
            P("     %d of %d cleared cells show %s at their centre; %d show it through a"
              % (prob["ground"], prob["expected"], prob["colour"], prob["showing_through"]))
            P("     semi-transparent overlay; %d are fully occluded by an opaque later layer"
              % prob["occluded"])
            P("     (the BASE banner). canvas pixels that moved: %s, of which OUTSIDE a"
              % prob["diff_px"])
            P("     cleared cell: %s" % prob["diff_outside_depots"])
        if prob.get("fail"):
            allok = False
            P("     !! %s" % prob["fail"])
        # THE GATE: nothing about the layout may move except the legend chip count.
        ma, mb = measure(raw["A_pre"]), measure(raw["B_post"])
        # The legend strip's OWN geometry is the thing being changed, so it is
        # allowed to move and is reported in full instead. Everything else on the
        # page must be untouched - that is the check the base-mark round lacked.
        ALLOWED = ("legend_normal_rect", "legend_prob_rect")
        every = sorted(k for k in set(ma) | set(mb) if ma.get(k) != mb.get(k))
        moved = [k for k in every if k not in ALLOWED]
        P("  DELTA A_pre -> B_post over %d measured layout quantities:" % len(set(ma) | set(mb)))
        for k in every:
            P("      %-22s %s  ->  %s%s"
              % (k, ma.get(k), mb.get(k), "   (the legend strip itself)" if k in ALLOWED else ""))
        P("      quantities moved OUTSIDE the legend strip: %s" % (moved if moved else "NONE"))
        chips = (raw["B_post"]["legend_normal_chips"] - raw["A_pre"]["legend_normal_chips"],
                 raw["B_post"]["legend_prob_chips"] - raw["A_pre"]["legend_prob_chips"])
        P("  legend chips: normal %+d, probability %+d (exactly one new chip in each branch)" % chips)
        if moved:
            allok = False
            P("  !! GATE FAIL: a layout quantity outside the legend strip moved")
        if chips != (1, 1):
            allok = False
            P("  !! GATE FAIL: expected exactly one new chip in each legend branch")
        sa, sb = shape(raw["A_pre"]), shape(raw["B_post"])
        P("  PRE-EXISTING page shape - reported, not failed on (identical in both arms: %s);"
          % (sa == sb))
        P("  the absolute row-height / overflow assertion is a property of the page at 6281542:")
        for s in sb:
            P("      - %s" % s)
        if sa != sb:
            allok = False
            P("  !! GATE FAIL: the page's pre-existing shape changed: %s"
              % sorted(set(sb) ^ set(sa)))
        results["delta_x%g" % scale] = {"moved": moved, "moved_any": every,
                                        "legend_rect_pre": [ma.get(k) for k in ALLOWED],
                                        "legend_rect_post": [mb.get(k) for k in ALLOWED],
                                        "chip_delta": list(chips),
                                        "shape_pre": sa, "shape_post": sb,
                                        "shape_identical": sa == sb}
        # named-region diff, A vs B and C vs B
        a = results["A_pre_x%g" % scale]
        b = results["B_post_x%g" % scale]
        c = results["C_layout_x%g" % scale]
        lr = raw["B_post"]["legend_normal_rect"]
        cr = raw["B_post"]["canvas_rect"]
        # The canvas region is inflated by 10 CSS px: the element carries a 1px
        # border, a 10px border-radius and a 24px-blur box-shadow, and the two
        # depot blocks sit in the TOP-LEFT and BOTTOM-RIGHT corners - exactly
        # where the rounded corner composites - so changing the ground under them
        # moves a few pixels just outside the content box.
        def box(r, pad):
            return (int((r[0] - pad) * scale), int((r[1] - pad) * scale),
                    int((r[0] + r[2] + pad) * scale) + 1, int((r[1] + r[3] + pad) * scale) + 1)
        regions = {"map canvas (+border/shadow)": box(cr, 10),
                   "map legend strip": box(lr, 3)}
        for label, x, y in (("A_pre vs B_post", a, b), ("C_layout vs B_post", c, b)):
            if not (os.path.exists(x["png"]) and os.path.exists(y["png"])):
                P("  %s: screenshot missing, skipped" % label)
                continue
            d = region_diff(x["png"], y["png"], regions)
            P("  DIFF %-20s %s" % (label, json.dumps(d, sort_keys=True)))
            results["diff_%s_x%g" % (label.split()[0], scale)] = d
    P("")
    P("  OVERALL %s" % ("PASS" if allok else "FAIL"))
    json.dump({"scales": scales, "results": results, "pass": bool(allok)},
              open(os.path.join(BASE, "_dfp_page_gate.json"), "w"), indent=1, sort_keys=True)
    with open(os.path.join(BASE, "_dfp_page_gate.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(OUT) + "\n")
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
