"""Base-mark round Part 3: END-TO-END check of the SHIPPED dashboard page.

The pixel audit renders drawMap sliced out of the source. This loads the WHOLE
HTML constant, exactly as the server would send it, into headless Chrome and
drives the real render() / setLegend() / probability toggle on a real frame. It
is what catches a JavaScript syntax error (which no static source test can), and
it checks Item B's "fire d / r" cell against the MODEL:

  expected range per firefighter = blob["ff_truth"], read off the model's own
  attributes in the model's own order (outputs/_bm_capture2.py), NOT off the panel
  row the page itself uses. So it also tests the `assigned` proxy for
  "has a target", and that `exiting` is honoured first.

usage: _bm_page_e2e.py <rev|WORKTREE> <frame.json> [<frame.json> ...]
"""
from __future__ import annotations
import ast, base64, json, os, re, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def html_of(rev: str) -> str:
    if rev == "WORKTREE":
        src = open(os.path.join(REPO, "serve_dashboard.py"), encoding="utf-8").read()
    else:
        src = subprocess.run(["git", "-C", REPO, "show", "%s:serve_dashboard.py" % rev],
                             capture_output=True, check=True).stdout.decode("utf-8")
    for node in ast.parse(src).body:                       # the HTML constant, without importing the module
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "HTML":
            return node.value.value
    raise SystemExit("no HTML constant")


DRIVER = r"""
<script>
(function(){
  const errs=[]; window.addEventListener('error',e=>errs.push(String(e.message)));
  window.addEventListener('unhandledrejection',e=>{});          // fetch('/scenarios') fails under file://
  const B=__BLOB__;
  try{
    W=B.width;H=B.height;cs=cv.width/W;FOVR=B.fov_radius;VFR=B.victim_flee_radius;totalSteps=240;
    document.getElementById('strip').style.display='block';
    document.getElementById('layout').style.display='grid';
    curFrame=B.frame;render(curFrame);setLegend();
    const out={errors:errs,probMode0:probMode};
    out.ff_header=[...document.querySelectorAll('#ff_v th')].map(t=>t.textContent);
    out.ff_rows=[...document.querySelectorAll('#ff_v tr')].slice(1).map(tr=>[...tr.children].map(td=>td.textContent.trim()));
    out.ff_cell_html=[...document.querySelectorAll('#ff_v tr')].slice(1).map(tr=>tr.lastElementChild.innerHTML);
    out.legend_normal=document.getElementById('maplegend').innerHTML;
    document.getElementById('probtoggle').click();
    out.probMode1=probMode; out.legend_prob=document.getElementById('maplegend').innerHTML;
    out.png_prob=cv.toDataURL('image/png');
    document.getElementById('probtoggle').click();
    out.probMode2=probMode; out.legend_back=document.getElementById('maplegend').innerHTML;
    out.png_normal=cv.toDataURL('image/png');
    const r=cv.getBoundingClientRect(); out.canvas_rect=[r.left,r.top,r.width,r.height];
    document.getElementById('e2e').textContent='E2EJSON:'+btoa(unescape(encodeURIComponent(JSON.stringify(out))))+':END';
  }catch(e){document.getElementById('e2e').textContent='E2EJSON:'+btoa(JSON.stringify({fatal:String(e&&e.stack||e),errors:errs}))+':END';}
})();
</script>
"""


def run_page(html: str, blob: dict) -> dict:
    page = html.replace("</body>", "<pre id='e2e'></pre>" + DRIVER.replace("__BLOB__", json.dumps(blob)) + "</body>")
    assert "id='e2e'" in page
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "page.html")
        open(p, "w", encoding="utf-8").write(page)
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
                            "--force-device-scale-factor=1", "--window-size=1600,1400",
                            "--user-data-dir=" + os.path.join(td, "prof"), "--virtual-time-budget=4000",
                            "--dump-dom", "file:///" + p.replace("\\", "/")], capture_output=True, timeout=240)
    m = re.search(r"E2EJSON:([A-Za-z0-9+/=]+):END", r.stdout.decode("utf-8", "replace"))
    if not m:
        raise SystemExit("page produced no result - script did not run (syntax error?)\n"
                         + r.stderr.decode("utf-8", "replace")[-800:])
    return json.loads(base64.b64decode(m.group(1)).decode("utf-8"))


def expected_colour(row: dict) -> str:
    """The proximity colour must be kept in EVERY state - exiting, dead and off-grid included."""
    d = row.get("nearest_fire_dist")
    return "none" if d is None or d > 3 else ("red" if d <= 1 else "amber")


def got_colour(cell_html: str) -> str:
    head = cell_html.split("/</span>")[0]            # the distance part, before the separator
    return "red" if "var(--red)" in head else ("amber" if "var(--amber)" in head else "none")


def expected_cell(row: dict, truth: dict | None) -> str:
    d = row.get("nearest_fire_dist")
    dd = "\u2014" if d is None else str(d)
    rng = None if truth is None else truth["range"]
    return "%s/%s" % (dd, "\u2013" if rng is None else rng)


def main() -> int:
    rev = sys.argv[1]; bad = 0
    html = html_of(rev)
    for fp in sys.argv[2:]:
        blob = json.load(open(fp))
        res = run_page(html, blob)
        tag = os.path.basename(fp)
        if res.get("fatal") or res.get("errors"):
            print("%-24s JS ERROR: %s %s" % (tag, res.get("fatal"), res.get("errors"))); bad += 1; continue
        rows = blob["frame"]["panel"]["firefighter_view"]; truth = blob.get("ff_truth") or {}
        got = [r[-1] for r in res["ff_rows"]]
        exp = [expected_cell(r, truth.get(r["id"])) for r in rows] if truth else None
        chip = "outline:1px solid #000000"
        leg = {"normal": chip in res["legend_normal"], "prob": chip in res["legend_prob"], "back": chip in res["legend_back"]}
        toggled = (res["probMode0"], res["probMode1"], res["probMode2"]) == (False, True, False)
        legend_switches = res["legend_prob"] != res["legend_normal"] and res["legend_back"] == res["legend_normal"]
        cols_got = [got_colour(h) for h in res["ff_cell_html"]]
        cols_exp = [expected_colour(r) for r in rows]
        new_page = res["ff_header"][-1] == "fire d/r"
        ok = (exp is None or got == exp) and all(leg.values()) and toggled and legend_switches \
            and (cols_got == cols_exp or not new_page) and new_page
        bad += (not ok)
        print("%-24s header %-12r cells %s | model-derived %s | base chip normal/prob/back %s | toggle %s legend-follows-toggle %s -> %s"
              % (tag, res["ff_header"][-1], got, exp, list(leg.values()), toggled, legend_switches, "OK" if ok else "FAIL"))
        if new_page:
            print("%-24s proximity colour per cell %s | expected from distance alone, in EVERY state %s -> %s"
                  % ("", cols_got, cols_exp, "OK" if cols_got == cols_exp else "FAIL"))
        states = {k: v["state"] for k, v in truth.items()}
        if states:
            print("%-24s model states %s ; assigned attr == target_pos truthy for every unit: %s"
                  % ("", states, all(v["assigned_attr"] == v["target_pos_truthy"] for v in truth.values())))
    print("E2E:", "PASS" if not bad else "FAIL (%d)" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
