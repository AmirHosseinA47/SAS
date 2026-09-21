"""Ungated-firefighting round, Part 1: which tooling changes meaning SILENTLY when the
FF_FIREFIGHT_* defaults flip (EXTINGUISH 0->1, FIREBREAK 0->1, ENGAGED_RETREAT_RANGE
3->1, MISSION_GATE 1->0; DRY_RUN stays 0).

READ-ONLY. Never walks a directory tree: the universe is `git ls-files` (tracked) plus
`git ls-files --others --exclude-standard` (untracked, not ignored). git does not
descend into outputs/_firemech_rewound_20260914/ because it is listed in
.git/info/exclude, so this script cannot touch the quarantine; it also drops any path
under it defensively and counts how many it dropped (expected 0).

REACHABILITY RULE (from agents.Firefighter._firefight_prepare, read at 11c3661):
  - EXTINGUISH and FIREBREAK are read first; if both are 0 the function returns None
    and nothing else is read. So a run that sets BOTH to 0 explicitly is FF-SAFE.
  - If either is non-zero, MISSION_GATE is read, then ENGAGED_RETREAT_RANGE, then
    DRY_RUN. DRY_RUN's default does not change, so it never needs to be explicit.
  => FF-SAFE   iff E and F both set, and (E == F == 0, or RANGE and GATE both set)
     PARTIAL   some FF key set but not a reachable one whose default changes
     SILENT    no FF key set, runs the live tree -> now the ungated feature
  A --repo that is not the live checkout is OTHER-CHECKOUT if the path exists, and
  FAILS-LOUDLY if it does not (every E:/Projects/SAS_wt/* worktree is gone).

For shell and python files the scan only collects EVIDENCE (markers) for the manual
classification in outputs/ungated_part1.txt; files that existed at b853617 carry the
flip audit's class (outputs/_flip_audit_coverage.json), which said whether they launch
a simulation at all. No FF_FIREFIGHT_* switch existed before 003ed91, so no file the
flip audit saw can set one.

  .venv/Scripts/python.exe -B outputs/_ug_register_scan.py [--lines]  > outputs/_ug_register_scan.txt
"""
import collections
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUAR = "outputs/_firemech_rewound_20260914/"
LIVE = {"e:/projects/sas", ".", "", "/e/projects/sas", "e:\\projects\\sas"}
FF = {
    "E": "FF_FIREFIGHT_EXTINGUISH",
    "F": "FF_FIREFIGHT_FIREBREAK",
    "K": "FF_FIREFIGHT_ENGAGED_RETREAT_RANGE",
    "G": "FF_FIREFIGHT_MISSION_GATE",
    "D": "FF_FIREFIGHT_DRY_RUN",
}
SIM_MARKERS = [
    ("WildFireModel(", r"WildFireModel\s*\("),
    ("_run_seed", r"_run_seed"),
    ("harness", r"_ffr_harness"),
    ("fm2p", r"_fm2_probe_harness"),
    ("eval", r"evaluate_scenarios"),
    ("rbcamp", r"_rblatch_campaign2"),
    ("pytest", r"pytest"),
    ("main.py", r"\bmain\.py"),
    ("dashboard", r"serve_dashboard"),
    ("subprocess", r"subprocess|Popen|os\.system"),
    ("pool", r"_pool\.sh|QUEUE="),
]


def git_list(*args):
    out = subprocess.run(["git", "-C", ROOT, "ls-files", "-z"] + list(args),
                         capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def read_text(path):
    raw = open(os.path.join(ROOT, path), "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or raw[1:2] == b"\x00":
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8", errors="replace")


def norm_repo(r):
    return r.strip().strip("'\"").rstrip("/\\").replace("\\", "/").lower()


def classify_sets(sets, repo):
    """sets: dict short -> value string."""
    if repo is not None and norm_repo(repo) not in LIVE:
        exists = os.path.isdir(repo.strip().strip("'\""))
        return "OTHER-CHECKOUT" if exists else "FAILS-LOUDLY"
    if not sets:
        return "SILENT"
    if "E" in sets and "F" in sets:
        try:
            both_off = float(sets["E"]) == 0 and float(sets["F"]) == 0
        except ValueError:
            both_off = False
        if both_off or ("K" in sets and "G" in sets):
            return "FF-SAFE"
    return "PARTIAL"


def parse_queue_line(line):
    """Return (tag, repo, sets, n_runs) or None for a non-run line."""
    s = line.strip().replace("\r", "")
    if not s or s.startswith("#"):
        return None
    sets = {}
    for m in re.finditer(r"--set\s+([A-Za-z_0-9]+)=(\S+)", s):
        for short, name in FF.items():
            if m.group(1) == name:
                sets[short] = m.group(2)
    fm2p = sorted(set(re.findall(r"--set\s+(FM2P_[A-Z_]+)=", s)))
    if "|" in s:
        f = s.split("|")
        if f[0] in ("ff", "rb") and len(f) >= 7:
            tag, repo, seeds = f[1], f[2], f[5]
            n = len([x for x in seeds.split(",") if x.strip()])
        elif len(f) >= 5:
            tag, repo, n = f[0], f[1], 1
        else:
            return None
        return tag, repo, sets, n, fm2p
    m = re.search(r"--repo\s+(\S+)", s)
    repo = m.group(1) if m else None
    m = re.search(r"--tag\s+(\S+)", s)
    tag = m.group(1) if m else s.split()[0]
    return tag, repo, sets, 1, fm2p


def main():
    tracked = git_list("--", "outputs")
    untracked = git_list("--others", "--exclude-standard", "--", "outputs")
    dropped = [p for p in tracked + untracked if p.startswith(QUAR)]
    files = sorted(set(p for p in tracked + untracked if not p.startswith(QUAR)))
    audit = json.load(open(os.path.join(ROOT, "outputs", "_flip_audit_coverage.json")))
    flip_cls = {}
    for key in ("shell", "python"):
        for path, cls, _why in audit[key]:
            flip_cls[path] = cls
    added = set(subprocess.run(
        ["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=A", "b853617", "HEAD"],
        capture_output=True, check=True).stdout.decode().split())

    print("UNGATED REGISTER SCAN  quarantine paths seen by git listing: %d (expected 0)" % len(dropped))
    queues = [p for p in files if p.endswith(".txt") and "queue" in os.path.basename(p).lower()]
    shells = [p for p in files if p.endswith((".sh", ".ps1"))]
    pys = [p for p in files if p.endswith(".py")]

    print("\n=== QUEUE FILES (%d) ===" % len(queues))
    grand = collections.Counter()
    show_lines = "--lines" in sys.argv
    for q in queues:
        per = collections.Counter()
        arms = collections.defaultdict(collections.Counter)
        detail = []
        for line in read_text(q).splitlines():
            parsed = parse_queue_line(line)
            if parsed is None:
                continue
            tag, repo, sets, n, fm2p = parsed
            cls = classify_sets(sets, repo)
            per[cls] += n
            arms[cls][tag] += n
            if show_lines and cls == "PARTIAL":
                detail.append("      %s %s %s" % (tag, sets, fm2p))
        grand.update(per)
        tot = sum(per.values())
        print("%-44s runs=%-4d %s" % (q, tot, " / ".join(
            "%s %d (%s)" % (c, per[c], ", ".join("%s %d" % kv for kv in sorted(arms[c].items())))
            for c in ("FF-SAFE", "PARTIAL", "SILENT", "OTHER-CHECKOUT", "FAILS-LOUDLY") if per[c])))
        for d in sorted(set(detail)):
            print(d)
    print("QUEUE TOTAL runs by class: %s" % dict(grand))

    for title, group in (("SHELL / POWERSHELL", shells), ("PYTHON", pys)):
        print("\n=== %s (%d) ===" % (title, len(group)))
        cnt = collections.Counter()
        for p in group:
            t = read_text(p)
            marks = [name for name, rx in SIM_MARKERS if re.search(rx, t)]
            ffk = sorted(short for short, name in FF.items() if name in t)
            fm2p = "FM2P" if "FM2P_" in t else ""
            src = flip_cls.get(p, "NEW-SINCE-b853617" if p in added else "UNTRACKED" if p in untracked else "not-in-audit")
            cnt[src.split(" ")[0]] += 1
            print("%-52s %-22s ff=%-10s %s %s" % (p, src[:22], "".join(ffk) or "-", fm2p, ",".join(marks)))
        print("by flip-audit class: %s" % dict(cnt))


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    main()
