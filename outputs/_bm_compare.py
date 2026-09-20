"""Base-mark round Part 3: the gate comparator for the DISPLAY items.

_fov_compare.py cannot be reused: it is hard-wired to the fov tags and REQUIRES a
payload digest to differ. This one reads ONLY this round's tagged artifacts and
refuses anything older than the patch (the FOV round's gate first read FAIL
because it compared another round's committed files).

  1 SIMULATION   _sc_control bmpre vs bmpost, three combos: VALUE identity on every
                 field, plus BYTE identity of the dumped stdout files (stronger;
                 achievable here - _sc_control emits no hash-ordered dict)
  2 NEGATIVE     cellcolor identical; whole-frame payload digest with the round's
                 one added key stripped: IDENTICAL at every one of 3 x 241 steps
  3 POSITIVE     whole-frame payload digest as published: DIFFERS, and the
                 firefighter_view key set grew by exactly {'exiting'}
  4 SCOPE        AST of serve_dashboard.py, pre rev vs working tree, with the HTML
                 constant blanked: the ONLY difference is that one whitelist key
  5 TESTS        failing NAME SETS pre vs post vs the recorded d3640e3 baseline
  6 COLOUR       the banner's hex literals, extracted from the PATCHED source

usage: _bm_compare.py <pre_outputs_dir> <pre_rev>
"""
from __future__ import annotations
import ast, json, os, re, subprocess, sys

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)
PRE = sys.argv[1]; REV = sys.argv[2]
FAILS = []


def P(s=""):
    print(s)


def check(ok, msg):
    P("  [%s] %s" % ("PASS" if ok else "FAIL", msg))
    if not ok:
        FAILS.append(msg)


def patch_mtime():
    return os.path.getmtime(os.path.join(REPO, "serve_dashboard.py"))


def sim():
    P("1. SIMULATION IDENTITY - outputs/_sc_control.py, bmpre (worktree at %s) vs bmpost (patched tree)" % REV)
    a = json.load(open(os.path.join(PRE, "_sc_control_bmpre.json"), encoding="utf-8"))
    post_path = os.path.join(BASE, "_sc_control_bmpost.json")
    b = json.load(open(post_path, encoding="utf-8"))
    check(os.path.getmtime(post_path) > patch_mtime(), "post artifact is NEWER than the patch (not a stale file)")
    check(a["steps"] == b["steps"] == 240 and sorted(a["runs"]) == sorted(b["runs"]),
          "same three combos, 240 steps: %s" % sorted(a["runs"]))
    for key in sorted(a["runs"]):
        ra, rb = a["runs"][key], b["runs"][key]
        fields = sorted(set(ra) | set(rb))
        diff = [f for f in fields if ra.get(f) != rb.get(f)]
        check(not diff, "%s: value-identical on all %d fields (stdout sha, agent_positions list + sha, firemap, "
                        "scorchmap, ground_counts, eval dict, residue, leftover_pending, cellcolor)%s"
              % (key, len(fields), "" if not diff else " DIFF: %s" % diff))
        check(json.dumps(ra, sort_keys=True) == json.dumps(rb, sort_keys=True), "%s: sorted-key JSON equal" % key)
        name = "_sc_control_%%s_%s.stdout.txt" % key.replace("/", "-").replace("|", "_")
        ba = open(os.path.join(PRE, name % "bmpre"), "rb").read()
        bb = open(os.path.join(BASE, name % "bmpost"), "rb").read()
        check(ba == bb and len(ba) > 0, "%s: dumped stdout BYTE-identical (%d bytes)" % (key, len(ba)))
        P("       eval: %s" % {k: ra["eval"].get(k) for k in ("rescued", "dead", "firefighter_deaths", "burnt_cells", "steps_run")})
    P("  cellcolor_sha256 is a NEGATIVE control here (cells are built in a Fire-only loop): identical above.")


def payload():
    P("2/3. WHOLE-FRAME PAYLOAD - json.dumps(_capture_frame(model, s), sort_keys=True) at every step")
    a = json.load(open(os.path.join(PRE, "_bm_payload_bmpre.json")))
    post_path = os.path.join(BASE, "_bm_payload_bmpost.json")
    b = json.load(open(post_path))
    check(os.path.getmtime(post_path) > patch_mtime(), "post payload artifact is newer than the patch")
    for key in sorted(a["combos"]):
        ca, cb = a["combos"][key], b["combos"][key]
        n = len(ca["stripped"])
        same = sum(1 for x, y in zip(ca["stripped"], cb["stripped"]) if x == y)
        differ = sum(1 for x, y in zip(ca["full"], cb["full"]) if x != y)
        check(same == n == len(cb["stripped"]), "%s NEGATIVE: payload with the added key stripped identical on %d/%d steps"
              % (key, same, n))
        check(differ > 0, "%s POSITIVE: payload as published differs on %d/%d steps" % (key, differ, n))
        check(set(cb["ff_keys"]) - set(ca["ff_keys"]) == {"exiting"} and set(ca["ff_keys"]) <= set(cb["ff_keys"]),
              "%s: firefighter_view keys grew by exactly {'exiting'}: %s -> %s" % (key, ca["ff_keys"], cb["ff_keys"]))
        check(ca["depots"] == cb["depots"], "%s: fr.depots unchanged: %s" % (key, cb["depots"]))


def blank_html(src: str):
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "HTML":
            node.value = ast.Constant(value="<HTML>")
    return tree


def scope():
    P("4. SCOPE - serve_dashboard.py, %s vs working tree, AST with the HTML constant blanked" % REV)
    pre = subprocess.run(["git", "-C", REPO, "show", "%s:serve_dashboard.py" % REV],
                         capture_output=True, check=True).stdout.decode("utf-8")
    post = open(os.path.join(REPO, "serve_dashboard.py"), encoding="utf-8").read()
    da, db = ast.dump(blank_html(pre)), ast.dump(blank_html(post))
    check(da != db, "the AST outside the HTML constant DID change (the whitelist key) - so the instrument can see a change")
    check(da.replace("Constant(value='nearest_fire_dist')", "Constant(value='nearest_fire_dist'), Constant(value='exiting')") == db,
          "and the ONLY change is one list element: 'exiting' appended to the firefighter_view whitelist")
    names = subprocess.run(["git", "-C", REPO, "diff", "--name-only", REV], capture_output=True, check=True).stdout.decode().split()
    check(names == ["serve_dashboard.py"], "tracked files changed vs %s: %s (the new test file is untracked/added, off the harness path)"
          % (REV, names))
    for fn in ("_build_evaluation", "_capture_frame", "_cell_color"):
        fa = [ast.dump(n) for n in ast.parse(pre).body if isinstance(n, ast.FunctionDef) and n.name == fn]
        fb = [ast.dump(n) for n in ast.parse(post).body if isinstance(n, ast.FunctionDef) and n.name == fn]
        check(fa == fb and len(fa) == 1, "%s: AST identical" % fn)


def failed_names(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    names = sorted(set(re.findall(r"^FAILED (\S+)", txt, flags=re.M)))
    m = re.search(r"(\d+) failed, (\d+) passed", txt)
    return names, (int(m.group(1)), int(m.group(2))) if m else None


def tests():
    P("5. TESTS - full suite, default order; failing NAME SETS")
    base_names, base_cnt = failed_names(os.path.join(BASE, "_fm3_merge_pytest.log"))
    pre_names, pre_cnt = failed_names(os.path.join(PRE, "_bm_pytest_pre.log"))
    post_names, post_cnt = failed_names(os.path.join(BASE, "_bm_pytest_post.log"))
    P("       recorded baseline at %s: %s | pre (worktree): %s | post (patched): %s" % (REV, base_cnt, pre_cnt, post_cnt))
    check(pre_names == base_names, "pre failing set == the recorded d3640e3 baseline set (%d names)" % len(base_names))
    check(post_names == pre_names, "post failing set == pre failing set: 0 new, 0 newly passing")
    check(post_cnt is not None and pre_cnt is not None and post_cnt[0] == pre_cnt[0] == 8
          and post_cnt[1] == pre_cnt[1] + 3 == 626, "counts: pre %s, post %s (+3 new static tests)" % (pre_cnt, post_cnt))
    for n in post_names:
        P("       %s" % n)


def colour():
    P("6. COLOUR GATE - literals extracted from the PATCHED source, not from the proposal")
    html = None
    src = open(os.path.join(REPO, "serve_dashboard.py"), encoding="utf-8").read()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "HTML":
            html = node.value.value
    i = html.index("function drawMap(fr){"); j = html.index("function render(fr){", i)
    dm = html[i:j]
    k = dm.index("for(const d of _dps){\n    const bw="); blk = dm[k:dm.index("// assignment lines (A)", k)]
    tones = re.findall(r"ctx\.fillStyle='(#[0-9A-Fa-f]{6})'", blk)
    check([t.lower() for t in tones] == ["#000000", "#ffffff", "#770099", "#ffffff"],
          "banner fill order casing/keyline/field/text = %s" % tones)
    chip = html[html.index("function baseSwatch(){"):]
    chip = chip[:chip.index("}")]
    check(all(t in chip for t in ("#770099", "#FFFFFF", "#000000")), "legend chip carries the same three tones")
    sys.path.insert(0, BASE)
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        import _sc_deltae as S                         # the repo's committed CIEDE2000 (9 Sharma pairs)

    def grey(h):
        r, g, b = (S._lin(int(h[i:i + 2], 16)) for i in (1, 3, 5))
        return (116 * (lambda t: t ** (1 / 3) if t > 216 / 24389 else (841 / 108) * t + 4 / 29)(0.2126729 * r + 0.7151522 * g + 0.0721750 * b) - 16, 0.0, 0.0)

    def comp(src_, dst, a=0.22):
        s = [int(src_[i:i + 2], 16) for i in (1, 3, 5)]; d = [int(dst[i:i + 2], 16) for i in (1, 3, 5)]
        return "#%02x%02x%02x" % tuple(int(a * s[i] + (1 - a) * d[i] + 0.5) for i in range(3))
    VEG = ["#414141", "#9eff89", "#85e370", "#72d05c", "#62c14c", "#459f30", "#389023", "#2f831b", "#236f11", "#1c630b", "#175808", "#124b05"]
    FIRE = ["#d8d675", "#eae740", "#fefa01", "#fed401", "#feaa01", "#fe7001", "#fe5501", "#fe3e01", "#fe2f01", "#fe2301", "#fe0101"]
    BW = ["#ffffff", "#e6e6e6", "#c9c9c9", "#b1b1b1", "#a1a1a1", "#818181", "#636363", "#474747", "#303030", "#1a1a1a", "#000000"]
    OTHER = ["#ababab", "#2b2b2b", "#895e00", "#2f4a1a", "#00ffff", "#ff00ff", "#0066cc", "#ff8c00", "#888888", "#ffff00",
             "#ffa500", "#00aaff", "#00ffcc", "#770099", "#ffd75a", "#78aaff"]
    n50 = sorted(set(VEG + FIRE + BW + OTHER))
    grounds = VEG + FIRE + ["#ababab", "#2b2b2b", "#895e00", "#2f4a1a"] + BW
    comps = [comp("#770099", g) for g in grounds]
    grid = ["#%02x%02x%02x" % tuple(int(round(int(c[i:i + 2], 16) * 0.82)) for i in (1, 3, 5)) for c in comps]
    nplus = sorted(set(n50 + comps + grid))
    mark = sorted(set(t.lower() for t in tones))

    def score(pal, lab):
        return min(max(S.de2000(lab(t), lab(b)) for t in mark) for b in pal)
    check(len(n50) == 50, "N50 rebuilt here has %d colours" % len(n50))
    P("       N+ rebuilt here: %d effective colours (instruments A/B: 126)" % len(nplus))
    sn, sa = score(nplus, S.lab), score(nplus, grey)
    P("       shipped three-tone mark vs N+: normal %.2f, achromatic %.2f  (instruments A/B/x: 40.04 / 36.90)" % (sn, sa))
    check(abs(sn - 40.04) < 0.05 and abs(sa - 36.90) < 0.05, "reproduces the certified 40.04 / 36.90 with the SHIPPED literals")
    s50 = score(n50, grey)
    check(abs(s50 - 38.26) < 0.05, "vs the 50 nominal colours, achromatic (the binding condition): %.2f (certified 38.26)" % s50)


def main() -> int:
    sim(); P(); payload(); P(); scope(); P(); tests(); P(); colour(); P()
    P("GATE (display items): %s" % ("PASS" if not FAILS else "FAIL - %d item(s):" % len(FAILS)))
    for f in FAILS:
        P("   - " + f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
