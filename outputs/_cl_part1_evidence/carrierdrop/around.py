"""Read-only: per-step fire around each drop cell and the ex-carrier, from recorded burn_intervals."""
import json
import os
import sys

OUT_DIR = r"E:\Projects\SAS\outputs"
HERE = os.path.dirname(os.path.abspath(__file__))
W = H = 50


def burning_at(bi, cell, s):
    for st, en in bi.get("%d,%d" % cell, []):
        if st <= s and (en is None or s < en):
            return True
    return False


def nbrs(c):
    out = []
    for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (c[0] + ox, c[1] + oy)
        if 0 <= n[0] < W and 0 <= n[1] < H:
            out.append(n)
    return out


def adj_fire(bi, c, s):
    return any(burning_at(bi, n, s) for n in nbrs(c))


def main():
    with open(os.path.join(HERE, "drops.json"), encoding="utf-8") as f:
        rows = json.load(f)
    seen = set()
    for r in rows:
        if r["kind"] in ("HORIZON",):
            continue
        key = (r["file"], r["ff"], r["s0"])
        if key in seen:
            continue
        seen.add(key)
        with open(os.path.join(OUT_DIR, r["file"]), encoding="utf-8") as f:
            d = json.load(f)
        bi = d.get("burn_intervals") or {}
        ff, vid, end = r["ff"], r["vid"], r["end"]
        ex = tuple(json.loads(r["exit"].replace("(", "[").replace(")", "]"))) if isinstance(r["exit"], str) else tuple(r["exit"])
        drop = r["cell_prev"]
        drop = tuple(json.loads(drop.replace("(", "[").replace(")", "]"))) if isinstance(drop, str) else tuple(drop)
        print("=" * 90)
        print(r["tag"], r["file"], ff, vid, "kind", r["kind"], "drop", end, "cell", drop, "exit", ex)
        last = min(len(d["ff_steps"]), (r["ff_death"] or end + 12) + 1, end + 25)
        for s in range(end - 2, last + 1):
            if s < 1 or s > len(d["ff_steps"]):
                continue
            fr = next(x for x in d["ff_steps"][s - 1] if x[0] == ff)
            vr = next(x for x in d["victim_steps"][s - 1] if x[0] == vid)
            c = tuple(fr[1]) if fr[1] else None
            free = [n for n in nbrs(c) if not burning_at(bi, n, s)] if c else []
            freed = [n for n in nbrs(drop) if not burning_at(bi, n, s)]
            print("  s=%d ff@%s %s own_burn=%s free_nbrs=%s | dropcell own_burn=%s free_nbrs=%s | victim %s %s | on_bnd=%s dist_exit=%s" % (
                s, c, fr[2] + ("/DEAD" if fr[5] else ""), burning_at(bi, c, s) if c else None,
                [(n, "adjF" if adj_fire(bi, n, s) else "clean") for n in free],
                burning_at(bi, drop, s), freed, vr[1], vr[2],
                c is not None and (c[0] in (0, W - 1) or c[1] in (0, H - 1)),
                (abs(c[0] - ex[0]) + abs(c[1] - ex[1])) if c else None))


if __name__ == "__main__":
    main()
