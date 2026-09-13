"""FOV-frame round: render one captured dashboard frame through the REAL drawMap.

Two jobs, one mechanism:
  * Layer C of the positive control - a rendered-pixel digest that CAN move when
    an overlay changes, unlike the cell-colour digest (`cells` is built inside a
    Fire-only loop, so no UAV can contribute a byte to it).
  * the before/after image.

drawMap is sliced straight out of serve_dashboard.py rather than reimplemented,
so what is measured is the shipped renderer and not a model of it. The four
globals it reads are declared adjacently and are supplied here. No HTTP server
and no second model run are needed.

usage: _fov_render.py <frame.json> <out_prefix> [pre_commit]
       with pre_commit, also renders that commit's drawMap for the before panel.
"""
from __future__ import annotations
import hashlib, json, os, subprocess, sys

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)
CHROME = "/opt/pw-browsers/chromium"   # playwright's pinned revision is absent here


def slice_drawmap(src: str) -> str:
    i = src.index("function drawMap(fr){")
    j = src.index("function render(fr){", i)
    return src[i:j]


def page_html(drawmap: str, frame: dict, w: int, h: int, cs: float,
              fovr: int, vfr: int, prob: bool) -> str:
    # BW mirrors serve_dashboard.py's own const; only probMode reads it.
    return (
        "<!DOCTYPE html><html><body style='margin:0'>"
        "<canvas id='cv' width=%d height=%d></canvas><script>\n"
        "const BW=[\"#ffffff\",\"#e6e6e6\",\"#c9c9c9\",\"#b1b1b1\",\"#a1a1a1\",\"#818181\","
        "\"#636363\",\"#474747\",\"#303030\",\"#1a1a1a\",\"#000000\"];\n"
        "let W=%d,H=%d,cs=%r,probMode=%s;\n"
        "let FOVR=%d,VFR=%d;\n"
        "const cv=document.getElementById('cv'),ctx=cv.getContext('2d');\n"
        "%s\n"
        "drawMap(%s);\n"
        "</script></body></html>"
        % (int(w * cs), int(h * cs), w, h, cs, "true" if prob else "false",
           fovr, vfr, drawmap, json.dumps(frame))
    )


def render(html: str, out_png: str) -> bytes:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME)
        pg = b.new_page()
        pg.set_content(html)
        pg.wait_for_timeout(120)
        raw = pg.locator("#cv").screenshot(path=out_png)
        b.close()
    return raw


def pixels(png_path: str):
    from PIL import Image
    im = Image.open(png_path).convert("RGB")
    return im, list(im.getdata())


def main() -> int:
    frame_path, prefix = sys.argv[1], sys.argv[2]
    pre_commit = sys.argv[3] if len(sys.argv) > 3 else None
    blob = json.load(open(frame_path))
    frame = blob["frame"]
    W, H = blob.get("width", 50), blob.get("height", 50)
    CS = blob.get("cs", 11.2)
    FOVR, VFR = blob.get("fov_radius", 8), blob.get("victim_flee_radius", 0)

    post_src = open(os.path.join(REPO, "serve_dashboard.py")).read()
    arms = [("post", slice_drawmap(post_src), FOVR, VFR)]
    if pre_commit:
        pre_src = subprocess.run(
            ["git", "-C", REPO, "show", "%s:serve_dashboard.py" % pre_commit],
            capture_output=True, text=True, check=True).stdout
        # the pre renderer has no overlay at all; radii are inert there
        arms.insert(0, ("pre", slice_drawmap(pre_src), FOVR, VFR))

    out = {}
    for tag, dm, fr_, vf_ in arms:
        png = "%s_%s.png" % (prefix, tag)
        render(page_html(dm, frame, W, H, CS, fr_, vf_, False), png)
        im, px = pixels(png)
        out[tag] = {
            "png": png,
            "size": list(im.size),
            "sha256": hashlib.sha256(bytes(bytearray(
                b for p in px for b in p))).hexdigest(),
            "n_pixels": len(px),
        }
        print("%-5s %s  %s  %d px" % (tag, os.path.basename(png),
                                      out[tag]["sha256"][:16], len(px)))

    if "pre" in out and "post" in out:
        _, a = pixels(out["pre"]["png"])
        _, b = pixels(out["post"]["png"])
        diff = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        im, _ = pixels(out["post"]["png"])
        wpx = im.size[0]
        gained = {}
        for i in diff:
            gained[b[i]] = gained.get(b[i], 0) + 1
        out["diff"] = {
            "changed": len(diff),
            "total": len(a),
            "pct": round(100.0 * len(diff) / len(a), 4),
            "identical": len(diff) == 0,
            "gained_colours": {("#%02x%02x%02x" % k): v for k, v in
                               sorted(gained.items(), key=lambda kv: -kv[1])},
            "bbox": ([min(i % wpx for i in diff), min(i // wpx for i in diff),
                      max(i % wpx for i in diff), max(i // wpx for i in diff)]
                     if diff else None),
        }
        print("changed %d / %d = %.4f%%" % (len(diff), len(a), out["diff"]["pct"]))
        print("gained:", out["diff"]["gained_colours"])

    json.dump(out, open("%s_render.json" % prefix, "w"), indent=2, sort_keys=True)
    print("wrote %s_render.json" % prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
