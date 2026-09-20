"""Base-mark round Part 3: the POSITIVE CONTROL - rendered pixels of the SHIPPED
drawMap, pre (git show <rev>) vs post (working tree), with EXACT accounting.

A moved digest proves only that something changed. This accounts for every pixel
that changed, against sets derived independently of the browser's rasteriser:

  P  the banner's pixels and tones   _bm_flag_geom.banner_pixels, itself checked
                                     against the literal coordinate table of
                                     basemark_part1.txt 2.2 (_bm_part1_checks [0])
  L  the OLD label's ink             measured from the PRE renderer alone: PRE vs
                                     PRE with its fillText statement deleted
  M  later layers over the banner    unit markers, assignment lines and dots,
                                     computed from the frame payload

  A  NO STRAY   every pixel outside P is identical in POST and in PRE-without-the-
                old-label. So the ONLY differences between the two renderers are
                the banner appearing and the old label disappearing.
  B  NO SILENT  every pixel of P changed, unless PRE already had the target tone,
                or it lies in M, or it is a cloth-interior pixel whose PRE colour
                already lay on the field->white segment (happens in probability
                mode, where the depot tint over white IS on that segment).
                Every pixel of L changed.
  C  TONES      every hard-tone pixel of P outside M is exactly its tone; every
                cloth-interior pixel outside M lies on the #770099->#FFFFFF
                segment; and in a POST render with the banner's fillText removed,
                every interior pixel outside M is exactly the field colour.
  T  (trail arm) a real trail passes through P in PRE, and POST is exact there.

usage: _bm_pixelaudit.py <pre_rev> <out_json> <name>=<frame.json>[:prob] ...
"""
from __future__ import annotations
import hashlib, json, math, os, subprocess, sys

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)
sys.path.insert(0, BASE)
import _bm_proto as PR
from _bm_flag_geom import banner_pixels
from PIL import Image

F = (0x77, 0x00, 0x99)
OLD_LABEL = "ctx.fillText('BASE',dx+3,dy-3);"
NEW_TEXT = "ctx.fillText('BASE',cx+cw/2,top+ch/2+0.5,cw-6);"
TMP = os.path.join(BASE, "_bm", "p3")


def drawmap(rev: str) -> str:
    if rev == "WORKTREE":
        src = open(os.path.join(REPO, "serve_dashboard.py"), encoding="utf-8").read()
    else:
        src = subprocess.run(["git", "-C", REPO, "show", "%s:serve_dashboard.py" % rev],
                             capture_output=True, check=True).stdout.decode("utf-8")
    i = src.index("function drawMap(fr){"); j = src.index("function render(fr){", i)
    return src[i:j]


def shot(dm: str, blob: dict, prob: bool, name: str):
    path = os.path.join(TMP, "_pa_%s.png" % name)
    PR.render(PR.page(dm, blob, prob), path)
    im = Image.open(path).convert("RGB")
    return path, im.load(), hashlib.sha256(im.tobytes()).hexdigest()


def on_segment(c) -> bool:
    ts = [(c[i] - F[i]) / float(255 - F[i]) for i in range(3)]
    t = sum(ts) / 3.0
    return -0.01 <= t <= 1.01 and all(abs(c[i] - (F[i] + t * (255 - F[i]))) <= 2.0 for i in range(3))


def later_layers(frame: dict, W: int, H: int, cs: float) -> set:
    M = set()

    def box(x0, y0, w, h, pad=1.0):
        return {(u, v) for u in range(int(math.floor(x0 - pad)), int(math.ceil(x0 + w + pad)))
                for v in range(int(math.floor(y0 - pad)), int(math.ceil(y0 + h + pad)))}
    for f in frame.get("firefighters", []):
        M |= box((f["x"] + 0.15) * cs, (H - 1 - f["y"] + 0.15) * cs, cs * 0.7, cs * 0.7)
    for u in frame.get("uavs", []):
        M |= box((u["x"] + 0.1) * cs, (H - 1 - u["y"] + 0.1) * cs, cs * 0.8, cs * 0.8)
    for v in frame.get("victims", []):
        M |= box(v["x"] * cs, (H - 1 - v["y"]) * cs, cs, cs)
    for a in frame.get("assignments", []):
        ax, ay = (a["fx"] + 0.5) * cs, (H - 1 - a["fy"] + 0.5) * cs
        bx, by = (a["tx"] + 0.5) * cs, (H - 1 - a["ty"] + 0.5) * cs
        k = max(2, int(max(abs(bx - ax), abs(by - ay)) * 2))
        for i in range(k + 1):
            x, y = ax + (bx - ax) * i / k, ay + (by - ay) * i / k
            M |= box(x - 2, y - 2, 4, 4, pad=0)
        M |= box(bx - cs * 0.28, by - cs * 0.28, cs * 0.56, cs * 0.56)
    return M


def audit(name: str, blob: dict, prob: bool, pre_dm: str, post_dm: str) -> dict:
    W, H, cs = blob["width"], blob["height"], blob["cs"]
    fr = blob["frame"]
    assert pre_dm.count(OLD_LABEL) == 1 and post_dm.count(OLD_LABEL) == 0 and post_dm.count(NEW_TEXT) == 1
    _, pre, pre_sha = shot(pre_dm, blob, prob, name + "_pre")
    _, pnl, _ = shot(pre_dm.replace(OLD_LABEL, ""), blob, prob, name + "_prenolabel")
    post_png, post, post_sha = shot(post_dm, blob, prob, name + "_post")
    _, pnt, _ = shot(post_dm.replace(NEW_TEXT, ""), blob, prob, name + "_postnotext")
    nt = dict(blob); nt["frame"] = dict(fr); nt["frame"]["trails"] = []
    _, pre_nt, _ = shot(pre_dm, nt, prob, name + "_prenotrails")

    P = {}
    for d in (fr.get("depots") or []):
        P.update(banner_pixels(d, W, H, cs))
    Pset = set(P)
    size = int(W * cs)
    allpx = [(x, y) for y in range(size) for x in range(size)]
    L = {q for q in allpx if pre[q] != pnl[q]}
    M = later_layers(fr, W, H, cs)
    changed = {q for q in allpx if pre[q] != post[q]}

    # A - nothing moved except the banner appearing and the old label disappearing
    stray = {q for q in allpx if q not in Pset and post[q] != pnl[q]}
    # B - nothing silently missing
    silent_P = {q for q, tone in P.items() if q not in changed and q not in M
                and not (tone is not None and pre[q] == tone)
                and not (tone is None and on_segment(pre[q]))}
    silent_L = {q for q in L if q not in changed and q not in Pset}
    # C - tones
    hard = [q for q, t in P.items() if t is not None and q not in M]
    inter = [q for q, t in P.items() if t is None and q not in M]
    tone_bad = [q for q in hard if post[q] != P[q]]
    seg_bad = [q for q in inter if not on_segment(post[q])]
    notext_bad = [q for q in inter if pnt[q] != F]
    glyph = sum(1 for q in inter if post[q] != F)
    # residual inside M (covered by a later layer) - reported, and must be INSIDE M by construction
    covered = {q for q in Pset if q in M}
    resid_in_M = {q for q in covered if (P[q] is not None and post[q] != P[q])
                  or (P[q] is None and not on_segment(post[q])) or q not in changed}
    # T - is there a real trail through the banner's location in PRE?
    trail_in_P = sum(1 for q in Pset if pre[q] != pre_nt[q])

    ok = not stray and not silent_P and not silent_L and not tone_bad and not seg_bad and not notext_bad \
        and pre_sha != post_sha
    return {"name": name, "prob": prob, "pre_sha256": pre_sha, "post_sha256": post_sha,
            "digest_moved": pre_sha != post_sha, "canvas_px": size * size,
            "changed": len(changed), "P": len(Pset), "L": len(L), "changed_in_P": len(changed & Pset),
            "changed_in_L_only": len((changed & L) - Pset), "A_stray": len(stray),
            "B_silent_P": len(silent_P), "B_silent_L": len(silent_L),
            "C_hard_tone_px": len(hard), "C_tone_mismatch": len(tone_bad),
            "C_interior_px": len(inter), "C_interior_off_segment": len(seg_bad),
            "C_interior_glyph_inked": glyph, "C_notext_interior_not_field": len(notext_bad),
            "M_banner_px_under_later_layer": len(covered), "M_residual_inside_M": len(resid_in_M),
            "T_trail_px_through_P_in_pre": trail_in_P, "post_png": os.path.basename(post_png), "pass": ok}


def main() -> int:
    pre_rev, out_json = sys.argv[1], sys.argv[2]
    os.makedirs(TMP, exist_ok=True)
    pre_dm, post_dm = drawmap(pre_rev), drawmap("WORKTREE")
    res, bad = [], 0
    for spec in sys.argv[3:]:
        name, path = spec.split("=", 1)
        prob = path.endswith(":prob")
        path = path[:-5] if prob else path
        r = audit(name, json.load(open(path)), prob, pre_dm, post_dm)
        res.append(r); bad += (not r["pass"])
        print("%-22s %s digest %s->%s moved=%s | changed %4d = banner %4d + old label %3d | A stray %d | "
              "B silent %d/%d | C tones %d/%d bad, interior %d off-seg of %d (glyph %d), no-text!=field %d | "
              "under later layers %d (residual inside M %d) | trail px through P in pre %d | %s"
              % (name, "PROB" if prob else "map ", r["pre_sha256"][:8], r["post_sha256"][:8], r["digest_moved"],
                 r["changed"], r["changed_in_P"], r["changed_in_L_only"], r["A_stray"], r["B_silent_P"],
                 r["B_silent_L"], r["C_tone_mismatch"], r["C_hard_tone_px"], r["C_interior_off_segment"],
                 r["C_interior_px"], r["C_interior_glyph_inked"], r["C_notext_interior_not_field"],
                 r["M_banner_px_under_later_layer"], r["M_residual_inside_M"], r["T_trail_px_through_P_in_pre"],
                 "PASS" if r["pass"] else "FAIL"), flush=True)
    json.dump({"pre_rev": pre_rev, "arms": res}, open(out_json, "w"), indent=1, sort_keys=True)
    print("PIXEL AUDIT:", "PASS (%d arms)" % len(res) if not bad else "FAIL (%d of %d arms)" % (bad, len(res)))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
