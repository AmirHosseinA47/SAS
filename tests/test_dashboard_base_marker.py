"""Base-mark round: pin the base-station banner into the dashboard source.

Before this round NO test read the dashboard HTML, drawMap or setLegend, so
nothing could catch a rendering regression. These three are static source-text
checks. They cannot catch a JavaScript syntax error - the round's headless
render does that (outputs/_bm_pixelaudit.py); what they pin is the DESIGN:

  * the old 'BASE' text label stays gone (it painted 0 px for the NW depot -
    drawn above the canvas - and 111 px at 1.10:1 for SE);
  * the banner lives inside the span outputs/_fov_render.py slices as drawMap,
    in its z-order slot: after the sensing overlays and the trails, before the
    assignment lines and every unit marker;
  * the base-station legend chip is three-tone and is in BOTH legend branches,
    and the probability toggle refreshes the legend.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import serve_dashboard as sd


def _drawmap() -> str:
    html = sd.HTML
    i = html.index("function drawMap(fr){")
    j = html.index("function render(fr){", i)
    return html[i:j]


def test_old_base_text_label_is_gone():
    dm = _drawmap()
    assert "fillText('BASE',dx+3,dy-3)" not in sd.HTML
    # exactly one text draw remains in drawMap: the banner's, and it is clipped
    assert dm.count("fillText(") == 1
    assert "ctx.clip();" in dm
    # the depot loop still closes: fill + outline, then the brace
    assert "ctx.strokeRect(dx+1,dy+1,dw-2,dh-2);}" in dm


def test_banner_block_is_inside_drawmap_in_its_z_order_slot():
    dm = _drawmap()
    banner = dm.index("// ---- base-station banner")
    text = dm.index("ctx.fillText('BASE',cx+cw/2,top+ch/2+0.5,cw-6)")
    # after the sensing overlays (and their const helpers - a temporal-dead-zone
    # trap if the banner ever moves above them) and after the trails ...
    assert dm.index("const twoTone=") < banner
    assert dm.index("// walked trails (B)") < banner
    # ... and before assignment lines and every unit marker
    assert banner < text < dm.index("// assignment lines (A)")
    assert text < dm.index("for(const f of fr.firefighters)")
    assert text < dm.index("for(const v of fr.victims)")
    assert text < dm.index("for(const u of fr.uavs)")
    # the three tones, and nothing else, between the banner comment and the text
    block = dm[banner:text]
    for tone in ("'#000000'", "'#FFFFFF'", "'#770099'"):
        assert "ctx.fillStyle=" + tone in block


def test_base_legend_chip_is_three_tone_and_in_both_branches():
    html = sd.HTML
    i = html.index("function baseSwatch(){")
    chip = html[i:html.index("}", html.index("return", i))]
    for part in ("background:#770099", "border:1px solid #FFFFFF", "outline:1px solid #000000"):
        assert part in chip
    j = html.index("function setLegend(){")
    legend = html[j:html.index("function showEval(", j)]
    prob_branch, normal_branch = legend.split("\n  :'", 1)
    assert "+BASESW+FOVSW" in prob_branch          # probability-mode legend
    assert "'+BASESW+'" in normal_branch           # normal legend
    assert "background:#770099\"></i>base station" not in legend   # the flat chip is gone
    # toggling probability mode refreshes the legend instead of leaving it stale
    k = html.index("document.getElementById('probtoggle').onclick")
    assert "setLegend();" in html[k:html.index("};", k)]
