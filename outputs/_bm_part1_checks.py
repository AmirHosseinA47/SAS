"""Base-mark round, Part 1: every measurement quoted in basemark_part1.txt that
is not already produced by _bm_trace_analyze.py / _bm_flag_interact.py, in one
re-runnable place. Reads the recorded traces and captured frames only; the two
render-based checks need the installed headless Chrome (see _bm_proto.py).

usage: _bm_part1_checks.py            (writes outputs/_bm/part1_checks.txt)
"""
from __future__ import annotations
import glob, json, math, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from _bm_flag_geom import banner_pixels
from _bm_flag_interact import stroke_px, diamond_segs

W = H = 50; CS = 11.2
OUT = []
FINAL_SLOT = "  // assignment lines (A): firefighter -> its assigned victim's cell"
OLD_LABEL = "ctx.fillText('BASE',dx+3,dy-3);"


def P(s=""):
    OUT.append(s); print(s)


def traces():
    return [json.load(open(p)) for p in sorted(glob.glob(os.path.join(BASE, "_bm", "trace_*.json")))]


def ranked(ox, oy, size=5):
    cells = [(ox + i, oy + j) for i in range(size) for j in range(size)]
    return sorted(cells, key=lambda c: (-min(c[0], c[1], H - 1 - c[0], W - 1 - c[1]), c[0], c[1]))


def check_berths():
    P("[1] BERTH INDICES UNDER EACH BANNER (ranking key = wildfire_model.py:647-651)")
    for name, d in (("NW", {"x": 0, "y": 45, "size": 5}), ("SE", {"x": 45, "y": 0, "size": 5})):
        rk = ranked(d["x"], d["y"]); px = banner_pixels(d, W, H, CS)
        cells = {}
        for (x, y) in px:
            c = (int(x // CS), H - 1 - int(y // CS)); cells[c] = cells.get(c, 0) + 1
        rows = []
        for c, n in sorted(cells.items(), key=lambda kv: rk.index(kv[0])):
            x0, y0, side = (c[0] + 0.1) * CS, (H - 1 - c[1] + 0.1) * CS, CS * 0.8
            mk = {(a, b) for a in range(int(x0), int(x0 + side) + 1) for b in range(int(y0), int(y0 + side) + 1)}
            rows.append("idx %2d %s ink %3d marker-overlap %3d" % (rk.index(c), c, n, len(mk & set(px))))
        P("  %s banner: ink %d px (hard-tone %d, interior %d); %s"
          % (name, len(px), sum(v is not None for v in px.values()),
             sum(v is None for v in px.values()), "; ".join(rows)))


def literal_banner(which):
    """Section 2.2's table, typed in as numbers. Inclusive pixel ranges."""
    T = {"NW": dict(pole=(4, 6, 3, 32), cloth=(6, 33, 3, 17)),
         "SE": dict(pole=(553, 555, 507, 536), cloth=(526, 553, 507, 521))}[which]
    K, Wt = (0, 0, 0), (255, 255, 255)
    out = {}

    def fill(x0, x1, y0, y1, tone):
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                out[(x, y)] = tone
    px0, px1, py0, py1 = T["pole"]; cx0, cx1, cy0, cy1 = T["cloth"]
    fill(px0, px1, py0, py1, K); fill(cx0, cx1, cy0, cy1, K)                       # casings
    fill(px0 + 1, px1 - 1, py0 + 1, py1 - 1, Wt); fill(cx0 + 1, cx1 - 1, cy0 + 1, cy1 - 1, Wt)   # core, keyline
    fill(cx0 + 2, cx1 - 2, cy0 + 2, cy1 - 2, None)                                 # 24 x 11 field
    return out


def check_literal():
    P("[0] THE PREDICTOR AGAINST THE DESIGN'S LITERAL COORDINATE TABLE (section 2.2)")
    for name, d in (("NW", {"x": 0, "y": 45, "size": 5}), ("SE", {"x": 45, "y": 0, "size": 5})):
        a = banner_pixels(d, W, H, CS); b = literal_banner(name)
        P("  %s: banner_pixels %d px, literal table %d px, identical pixel sets AND tones: %s"
          % (name, len(a), len(b), a == b))


def check_idle_diamonds(ts):
    P("[2] OPTION (a)/(b): IDLE r=3 DIAMONDS AGAINST THE DEPOT BLOCKS")
    tot = any_ = stacked = 0; ink_px = []
    for t in ts:
        blocks = []
        for d in t["depots"]:
            x0 = math.floor(d["x"] * CS + 0.5); y0 = math.floor((H - d["y"] - d["size"]) * CS + 0.5)
            blocks.append({(x, y) for x in range(x0, x0 + 56) for y in range(y0, y0 + 56)})
        allb = set().union(*blocks); n = a = b2 = 0
        for r in t["rows"]:
            n += 1
            idle = [f for f in r["ffs"] if f["state"] == "idle" and f["pos"] is not None]
            ink = stroke_px([s for f in idle for s in diamond_segs({"x": f["pos"][0], "y": f["pos"][1]}, 3)]) & allb
            if ink:
                a += 1; ink_px.append(len(ink))
            per_block = [sum(1 for f in idle if (int((f["pos"][0] + 0.5) * CS), int((H - 1 - f["pos"][1] + 0.5) * CS)) in bl)
                         for bl in blocks]
            b2 += any(k >= 2 for k in per_block)
        P("  %s/%d: stroke inside a depot block %d/%d (%.1f%%); >=2 idle units in one block %d (%.1f%%)"
          % (t["wind"], t["seed"], a, n, 100.0 * a / n, b2, 100.0 * b2 / n))
        tot += n; any_ += a; stacked += b2
    P("  POOLED: stroke inside a block %.1f%% of steps; stacked %.1f%%; median stroke ink inside the blocks %d px"
      % (100.0 * any_ / tot, 100.0 * stacked / tot, sorted(ink_px)[len(ink_px) // 2]))
    blk = {(x, y) for x in range(5) for y in range(45, 50)}
    u = set()
    for c in ((4, 46), (2, 45), (2, 46)):
        u |= {(c[0] + dx, c[1] + dy) for dx in range(-3, 4) for dy in range(-3, 4) if abs(dx) + abs(dy) <= 3}
    P("  three idle diamonds on the default FF berths cover %d of the NW block's 25 cells" % len(u & blk))


def check_fire_d(ts):
    P("[3] THE EXISTING 'fire d' COLOUR THRESHOLDS (<=1 red, <=3 amber) AGAINST EACH UNIT'S OWN STATE")
    T = dict(assigned=0, amber=0, exiting=0, coloured=0, idle=0, idle_col=0)
    for t in ts:
        c = dict.fromkeys(T, 0)
        for r in t["rows"]:
            for f in r["ffs"]:
                d = f["nearest_fire"]
                if f["state"] == "assigned":
                    c["assigned"] += 1; c["amber"] += (d is not None and 2 <= d <= 3)
                elif f["state"] == "exiting":
                    c["exiting"] += 1; c["coloured"] += (d is not None and d <= 3)
                elif f["state"] == "idle":
                    c["idle"] += 1; c["idle_col"] += (d is not None and d <= 3)
        P("  %s/%d: assigned %d, amber at d=2-3 %d | exiting %d, coloured %d"
          % (t["wind"], t["seed"], c["assigned"], c["amber"], c["exiting"], c["coloured"]))
        for k in T:
            T[k] += c[k]
    P("  POOLED: assigned %d, wrongly amber %d (%.1f%%) | exiting %d, coloured %d (%.1f%%) | idle %d, amber/red %d (%.1f%%, correct)"
      % (T["assigned"], T["amber"], 100.0 * T["amber"] / T["assigned"], T["exiting"], T["coloured"],
         100.0 * T["coloured"] / T["exiting"], T["idle"], T["idle_col"], 100.0 * T["idle_col"] / T["idle"]))


def check_transitions(ts):
    P("[4] RANGE-SELECTING STATE: OCCUPANCY AND TRANSITIONS")
    from collections import Counter
    st = Counter(); tr = Counter(); us = 0
    for t in ts:
        prev = {}
        for r in t["rows"]:
            for f in r["ffs"]:
                st[f["state"]] += 1; us += 1
                p = prev.get(f["id"])
                if p is not None and p != f["state"]:
                    tr["%s->%s" % (p, f["state"])] += 1
                prev[f["id"]] = f["state"]
    P("  unit-steps %d: %s" % (us, {k: "%d (%.1f%%)" % (v, 100.0 * v / us) for k, v in st.most_common()}))
    P("  transitions %d = %.2f per unit per 100 steps: %s" % (sum(tr.values()), 100.0 * sum(tr.values()) / us, dict(tr.most_common())))
    d = sorted(x["manhattan"] for t in ts for x in t["dispatches"])
    P("  dispatches n=%d min=%d max=%d: %s" % (len(d), d[0], d[-1], d))


def check_lines(ts):
    P("[5] LATER LAYERS OVER THE BANNER: WALKED TRAILS AND ASSIGNMENT LINES")
    tot = th = ah = 0; mx = 0; per = []
    for t in ts:
        ink = set()
        for d in t["depots"]:
            ink |= set(banner_pixels(d, W, H, CS))
        hist = {}; n = h = 0
        for r in t["rows"]:
            units = [("U" + u["id"], (u["x"], u["y"])) for u in r["uavs"]] + \
                    [("F" + f["id"], tuple(f["pos"])) for f in r["ffs"] if f["pos"] is not None]
            for k, pos in units:
                hh = hist.setdefault(k, [])
                if not hh or hh[-1] != pos:
                    hh.append(pos)
                    if len(hh) > 60:
                        del hh[0]
            cov = set()
            for hh in hist.values():
                for a, b in zip(hh, hh[1:]):
                    ax, ay = (a[0] + 0.5) * CS, (H - 1 - a[1] + 0.5) * CS
                    bx, by = (b[0] + 0.5) * CS, (H - 1 - b[1] + 0.5) * CS
                    k = max(2, int(max(abs(bx - ax), abs(by - ay)) * 2))
                    for i in range(k + 1):
                        x, y = ax + (bx - ax) * i / k, ay + (by - ay) * i / k
                        for ox in (-0.8, 0, 0.8):
                            for oy in (-0.8, 0, 0.8):
                                q = (int(x + ox), int(y + oy))
                                if q in ink:
                                    cov.add(q)
            hit_a = False
            for f in r["ffs"]:
                if f["state"] == "assigned" and f["pos"] and f["target"]:
                    ax, ay = (f["pos"][0] + 0.5) * CS, (H - 1 - f["pos"][1] + 0.5) * CS
                    bx, by = (f["target"][0] + 0.5) * CS, (H - 1 - f["target"][1] + 0.5) * CS
                    k = max(2, int(max(abs(bx - ax), abs(by - ay)) * 2))
                    if any((int(ax + (bx - ax) * i / k + o), int(ay + (by - ay) * i / k + q)) in ink
                           for i in range(k + 1) for o in (-1, 0, 1) for q in (-1, 0, 1)):
                        hit_a = True
            n += 1; h += bool(cov); ah += hit_a; mx = max(mx, len(cov))
        per.append("%s/%d %.1f%%" % (t["wind"], t["seed"], 100.0 * h / n)); tot += n; th += h
    P("  a walked trail crosses banner ink: %s" % "; ".join(per))
    P("  POOLED %.1f%% of %d steps, at most %d of 990 px; an assignment line crosses it on %d steps"
      % (100.0 * th / tot, tot, mx, ah))


def check_render():
    P("[6] RENDER CHECKS (headless Chrome, HEAD's drawMap sliced as text)")
    import _bm_proto as PR
    from PIL import Image
    tmp = os.path.join(BASE, "_bm", "proto")
    dm = PR.drawmap_head(); assert dm.count(OLD_LABEL) == 1 and dm.count(FINAL_SLOT) == 1
    dm2 = dm.replace(OLD_LABEL, "")
    post = dm2.replace(FINAL_SLOT, PR.BANNER_JS + "  for(const d of _dps)_banner(d,'#770099');\n" + FINAL_SLOT)
    F = (0x77, 0, 0x99)

    def on_segment(c):
        """c = F + t*(white - F) for ONE t in [0,1], every channel within 2 levels."""
        ts_ = [(c[i] - F[i]) / float(255 - F[i]) for i in range(3)]
        t = sum(ts_) / 3.0
        return -0.01 <= t <= 1.01 and all(abs(c[i] - (F[i] + t * (255 - F[i]))) <= 2.0 for i in range(3))

    def px(path):
        return Image.open(path).convert("RGB").load()

    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def Y(rgb):
        return 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2])

    frames = sorted(glob.glob(os.path.join(BASE, "_bm", "frame_*.json")))
    for fp in frames:
        blob = json.load(open(fp)); tag = os.path.basename(fp)[6:-5]
        a_png, b_png, c_png = (os.path.join(tmp, "_chk_%s.png" % k) for k in "abc")
        PR.render(PR.page(dm, blob, False), a_png)      # as shipped
        PR.render(PR.page(dm2, blob, False), b_png)     # label statement deleted
        PR.render(PR.page(post, blob, False), c_png)    # banner at the final slot
        a, b, c = px(a_png), px(b_png), px(c_png)
        lab = [(x, y) for y in range(560) for x in range(560) if a[x, y] != b[x, y]]
        nw = [q for q in lab if q[0] < 280 and q[1] < 280]
        solid = [q for q in lab if a[q] == F]
        cr = sorted((max(Y(F), Y(b[q])) + 0.05) / (min(Y(F), Y(b[q])) + 0.05) for q in solid)
        pred = {}
        for d in blob["frame"]["depots"]:
            pred.update(banner_pixels(d, W, H, CS))
        changed = {(x, y) for y in range(560) for x in range(560) if b[x, y] != c[x, y]}
        resid = set()
        for q, tone in pred.items():
            if tone is not None and c[q] != tone:
                resid.add(q)
            if tone is None and not on_segment(c[q]):
                resid.add(q)
            if b[q] == c[q] and not (tone is not None and b[q] == tone):
                resid.add(q)
        M = set()

        def box(x0, y0, w, h):
            return {(u, v) for u in range(int(math.floor(x0)), int(math.ceil(x0 + w)))
                    for v in range(int(math.floor(y0)), int(math.ceil(y0 + h)))}
        for f in blob["frame"]["firefighters"]:
            M |= box((f["x"] + 0.15) * CS, (H - 1 - f["y"] + 0.15) * CS, CS * 0.7, CS * 0.7)
        for u in blob["frame"]["uavs"]:
            M |= box((u["x"] + 0.1) * CS - 0.5, (H - 1 - u["y"] + 0.1) * CS - 0.5, CS * 0.8 + 1, CS * 0.8 + 1)
        for v in blob["frame"]["victims"]:
            M |= box(v["x"] * CS, (H - 1 - v["y"]) * CS, CS, CS)
        glyph = sum(1 for q, tone in pred.items() if tone is None and c[q] != F)
        bb = (min(q[0] for q in lab), min(q[1] for q in lab), max(q[0] for q in lab), max(q[1] for q in lab)) if lab else None
        P("  %-16s old label: ink %3d px (NW half %d), bbox %s, fully inked %d, #770099-vs-ground WCAG %s"
          % (tag, len(lab), len(nw), bb, len(solid), ("%.2f" % cr[len(cr) // 2]) if cr else "n/a"))
        P("  %-16s banner   : changed %3d predicted %3d stray %d | interior glyph-inked %3d | residual %2d "
          "(inside a unit-marker footprint %2d, outside %d)"
          % ("", len(changed), len(pred), len(changed - set(pred)), glyph, len(resid), len(resid & M), len(resid - M)))


def main() -> int:
    ts = traces()
    P("basemark Part 1 checks - %d traces, %d rendered steps" % (len(ts), sum(len(t["rows"]) for t in ts)))
    check_literal(); check_berths(); check_transitions(ts); check_idle_diamonds(ts); check_fire_d(ts); check_lines(ts)
    if "--no-render" not in sys.argv:
        check_render()
    open(os.path.join(BASE, "_bm", "part1_checks.txt"), "w", encoding="utf-8").write("\n".join(OUT) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
