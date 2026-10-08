"""_dq_seedscan.py - read-only whole-token seed scanner for dispatch round 2 (fresh seed sets 7 and 8).

A copy of outputs/_mvg_seedscan.py (the movement round's 1d.4 check, on main) with these changes, each required by
the selection rule written BEFORE this scan ran (outputs/dispatch2_part1.txt section 0.6, commit 824c1de7):
  - OWN_ROUND skips only this round's files ("_dq", "dispatch2"); the movement round's files ARE scanned now (they
    hold sets 5-6, which are spent);
  - the trees are the movement round's list without the removed prereg480cur worktree;
  - RESERVED adds sets 5-6 with their margins (135941-135996, 287021-287076);
  - LISTING LINES (rule 0.6 (3)): a TEXT line naming at least two of the eight bases the 2026-10-07 scan certified
    clean (LISTED below). Every whole-token value on such a line is counted into a separate histogram H_LIST, and
    every listing line is written to the report with its file and line number. NAME and BINARY occurrences are never
    listing occurrences;
  - CLEAN(b) (rule 0.6 (4)): sum over [b - 20, b + 35] of (all occurrences - listing occurrences) == 0;
  - the rule's pick is printed: set 7 = smallest CLEAN, set 8 = smallest CLEAN >= set 7 + 100000; the git-history
    check (rule 0.6 (6)) is a separate step, recorded in outputs/_dq_seedscan_summary.txt.
It is NOT a selector to re-run: analyzers read outputs/_dq_seeds.txt and never re-scan.

Counting is unchanged from _mvg_seedscan.py: every maximal ASCII digit run of length 4..6 with a non-zero first digit
(= whole-token matches of (?<![0-9])N(?![0-9]) for 1000 <= N <= 999999). UTF-16 files are decoded (BOM, or the
NUL-parity heuristic) and re-encoded to UTF-8; every other file is scanned as bytes.
Traversal: os.walk; the quarantine directory name and .git are removed from dirs BEFORE descending.
Files > 200 MB are skipped and listed. Nothing is written except the result files in OUTDIR.
"""
import json
import os
import re
import sys
import time

import numpy as np

QUAR = "_firemech_rewound_20260914"
OWN_ROUND = ("_dq", "dispatch2")
MAXSZ = 200 * 1024 * 1024
CHUNK = 32 * 1024 * 1024
HERE = os.path.dirname(os.path.abspath(__file__))

TREES = [  # (label, root, recursive, filename filter for non-recursive)
    ("SAS/outputs", r"E:/Projects/SAS/outputs", True, None),
    ("dispatch/outputs", r"E:/Projects/SAS_wt/dispatch/outputs", True, None),
    ("zealous/outputs", r"E:/Projects/SAS/.claude/worktrees/zealous-colden-0b9fe2/outputs", True, None),
    ("urgency/outputs", r"E:/Projects/SAS_wt/urgency/outputs", True, None),
    ("SAS/docs", r"E:/Projects/SAS/docs", True, None),
    ("SAS/tests", r"E:/Projects/SAS/tests", True, None),
    ("SAS/src_extension (extra)", r"E:/Projects/SAS/src_extension", True, None),
    ("SAS root *.py/*.md/*.txt", r"E:/Projects/SAS", False, (".py", ".md", ".txt")),
    ("memory (extra)", r"C:/Users/ahrar/.claude/projects/E--Projects-SAS/memory", True, None),
]

LISTED = (135961, 287041, 474781, 575201, 662481, 674101, 741141, 819941)  # the 2026-10-07 scan's clean bases
LISTED_ARR = np.array(LISTED, dtype=np.int64)
CONTROLS = ((9601, "set1"), (9621, "set2"), (573001, "set3"), (780001, "set4"), (135961, "set5"),
            (287041, "set6"))
WATCH = sorted(set(b + i for b, _ in CONTROLS for i in range(16))
               | set(v for b in LISTED for v in range(b - 20, b + 36)))
WATCH_ARR = np.array(WATCH, dtype=np.int64)
WATCH_SET = set(WATCH)
POW = {L: (10 ** np.arange(L - 1, -1, -1)).astype(np.int64) for L in (4, 5, 6)}
NAME_RE = re.compile(r"(?<![0-9])[1-9][0-9]{3,5}(?![0-9])")
TOKEN_RE = re.compile(rb"(?<![0-9])[1-9][0-9]{3,5}(?![0-9])")
LISTED_RES = [re.compile(rb"(?<![0-9])" + str(b).encode() + rb"(?![0-9])") for b in LISTED]

H_NAME = np.zeros(1_000_000, dtype=np.int64)
H_TEXT = np.zeros(1_000_000, dtype=np.int64)
H_BIN = np.zeros(1_000_000, dtype=np.int64)
H_LIST = np.zeros(1_000_000, dtype=np.int64)   # TEXT occurrences on listing lines (a subset of H_TEXT)
F_TEXT = np.zeros(1_000_000, dtype=np.int64)
F_BIN = np.zeros(1_000_000, dtype=np.int64)
EXAMPLES = {}   # value -> list of (kind, path, count), at most 40 per value
LISTING_LINES = []   # (path, line number, text)


def runs_values(buf: bytes) -> np.ndarray:
    """Values of every maximal digit run of length 4..6 with a non-zero first digit."""
    if not buf:
        return np.zeros(0, dtype=np.int64)
    a = np.frombuffer(buf, dtype=np.uint8)
    d = ((a >= 48) & (a <= 57)).astype(np.int8)
    dd = np.diff(np.concatenate((np.zeros(1, np.int8), d, np.zeros(1, np.int8))))
    starts = np.flatnonzero(dd == 1)
    ends = np.flatnonzero(dd == -1)
    L = ends - starts
    out = []
    for n in (4, 5, 6):
        s = starts[(L == n)]
        if s.size == 0:
            continue
        s = s[a[s] != 48]
        if s.size == 0:
            continue
        idx = s[:, None] + np.arange(n)[None, :]
        dig = a[idx].astype(np.int64) - 48
        out.append(dig @ POW[n])
    if not out:
        return np.zeros(0, dtype=np.int64)
    return np.concatenate(out)


def classify(head: bytes):
    if head.startswith(b"\xff\xfe"):
        return "utf-16-le-bom"
    if head.startswith(b"\xfe\xff"):
        return "utf-16-be-bom"
    if b"\x00" not in head:
        return "bytes"
    n = len(head) - (len(head) % 2)
    if n >= 2:
        odd = head[1:n:2].count(0)
        even = head[0:n:2].count(0)
        half = n // 2
        if odd > 0.6 * half and even < 0.1 * half:
            return "utf-16-le-nobom"
        if even > 0.6 * half and odd < 0.1 * half:
            return "utf-16-be-nobom"
    return "binary"


def text_bytes(path, kind):
    """The file's text as UTF-8 bytes (UTF-16 decoded), for the listing-line pass of a TEXT file."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if kind.startswith("utf-16"):
        enc = "utf-16" if kind.endswith("-bom") else ("utf-16-le" if "le" in kind else "utf-16-be")
        return raw.decode(enc, errors="ignore").encode("utf-8", errors="ignore")
    return raw


def scan_file(path):
    """Return (kind, values array) for a file."""
    with open(path, "rb") as fh:
        head = fh.read(65536)
        kind = classify(head)
        if kind.startswith("utf-16"):
            fh.seek(0)
            raw = fh.read()
            enc = "utf-16" if kind.endswith("-bom") else ("utf-16-le" if "le" in kind else "utf-16-be")
            txt = raw.decode(enc, errors="ignore")
            return kind, runs_values(txt.encode("utf-8", errors="ignore"))
        fh.seek(0)
        parts = []
        carry = b""
        while True:
            blk = fh.read(CHUNK)
            if not blk:
                parts.append(runs_values(carry))
                break
            buf = carry + blk
            cut = len(buf)
            while cut > 0 and 48 <= buf[cut - 1] <= 57:
                cut -= 1
            parts.append(runs_values(buf[:cut]))
            carry = buf[cut:]
        vals = np.concatenate(parts) if parts else np.zeros(0, dtype=np.int64)
        return kind, vals


def listing_pass(path, kind, label_rel):
    """Rule 0.6 (3): count the whole-token values of every line naming >= 2 LISTED bases into H_LIST."""
    data = text_bytes(path, kind)
    for ln, line in enumerate(data.splitlines(), 1):
        if sum(1 for rx in LISTED_RES if rx.search(line)) < 2:
            continue
        toks = [int(m) for m in TOKEN_RE.findall(line)]
        for v in toks:
            H_LIST[v] += 1
        LISTING_LINES.append((label_rel, ln, line.decode("utf-8", errors="replace")[:400]))


def main():
    t0 = time.time()
    report = {"trees": [], "skipped_big": [], "errors": [], "kinds": {}, "listing_files": 0}
    for label, root, rec, filt in TREES:
        tr = {"label": label, "root": root, "exists": os.path.isdir(root), "files": 0, "bytes": 0,
              "text_files": 0, "binary_files": 0, "utf16_files": 0, "dirs_visited": 0, "secs": 0.0}
        if not tr["exists"]:
            report["trees"].append(tr)
            print("MISSING", label, root, flush=True)
            continue
        t1 = time.time()
        if rec:
            walker = os.walk(root)
        else:
            walker = [(root, [], [f for f in os.listdir(root)
                                  if os.path.isfile(os.path.join(root, f)) and f.lower().endswith(filt)])]
        for dp, dn, fn in walker:
            dn[:] = [d for d in dn if d not in (QUAR, ".git")]
            tr["dirs_visited"] += 1
            for f in fn:
                if f.startswith(OWN_ROUND):
                    continue
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, root)
                for m in NAME_RE.findall(rel):
                    v = int(m)
                    H_NAME[v] += 1
                    if v in WATCH_SET:
                        EXAMPLES.setdefault(v, [])
                        if len(EXAMPLES[v]) < 40:
                            EXAMPLES[v].append(("NAME", label + ":" + rel, 1))
                try:
                    sz = os.path.getsize(p)
                except OSError as e:
                    report["errors"].append((p, str(e)))
                    continue
                if sz > MAXSZ:
                    report["skipped_big"].append((p, sz))
                    continue
                try:
                    kind, vals = scan_file(p)
                except OSError as e:
                    report["errors"].append((p, str(e)))
                    continue
                tr["files"] += 1
                tr["bytes"] += sz
                report["kinds"][kind] = report["kinds"].get(kind, 0) + 1
                isbin = kind == "binary"
                if isbin:
                    tr["binary_files"] += 1
                else:
                    tr["text_files"] += 1
                if kind.startswith("utf-16"):
                    tr["utf16_files"] += 1
                if vals.size == 0:
                    continue
                H = H_BIN if isbin else H_TEXT
                F = F_BIN if isbin else F_TEXT
                u, c = np.unique(vals, return_counts=True)
                H[u] += c
                F[u] += 1
                hit = np.isin(u, WATCH_ARR)
                if hit.any():
                    for v, cc in zip(u[hit].tolist(), c[hit].tolist()):
                        EXAMPLES.setdefault(v, [])
                        if len(EXAMPLES[v]) < 40:
                            EXAMPLES[v].append(("BIN" if isbin else "TEXT", label + ":" + rel, cc))
                if not isbin and int(np.isin(LISTED_ARR, u).sum()) >= 2:
                    try:
                        listing_pass(p, kind, label + ":" + rel)
                        report["listing_files"] += 1
                    except OSError as e:
                        report["errors"].append((p, "listing pass: " + str(e)))
        tr["secs"] = round(time.time() - t1, 1)
        report["trees"].append(tr)
        print("DONE", label, tr, flush=True)
    report["secs_total"] = round(time.time() - t0, 1)
    np.savez_compressed(os.path.join(OUTDIR, "_dq_seedscan_hist.npz"), name=H_NAME, text=H_TEXT, bin=H_BIN,
                        listing=H_LIST, ftext=F_TEXT, fbin=F_BIN)
    report["examples"] = {str(k): v for k, v in sorted(EXAMPLES.items())}
    report["listing_lines"] = LISTING_LINES
    with open(os.path.join(OUTDIR, "_dq_seedscan_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    print("TOTAL secs", report["secs_total"], "skipped_big", report["skipped_big"], "errors", len(report["errors"]))
    print("kinds", report["kinds"], "listing files", report["listing_files"], "listing lines", len(LISTING_LINES))
    select(H_NAME + H_TEXT + H_BIN, H_LIST)


RESERVED = ((29000, 32000), (572981, 573036), (779981, 780036), (135941, 135996), (287021, 287076))


def in_reserved(b):
    return any(not (b + 15 < lo or b > hi) for lo, hi in RESERVED)


def clean_base(total, listing, b):
    """Rule 0.6 (1)-(4): every occurrence on [b - 20, b + 35] is a listing occurrence; block outside RESERVED."""
    if b - 20 < 0 or b + 35 >= total.size or in_reserved(b):
        return False
    return int((total[b - 20:b + 36] - listing[b - 20:b + 36]).sum()) == 0


def select(total, listing):
    assert int((listing > total).sum()) == 0, "listing histogram exceeds the total - counting defect"
    cands = [b for b in range(100001, 999962, 20) if clean_base(total, listing, b)]
    literal = [b for b in cands if int(total[b - 20:b + 36].sum()) == 0]
    print("CLEAN six-digit bases (rule 0.6 (1)-(4)): %d" % len(cands))
    print("  all:", cands[:60])
    print("  of which literal-zero (no listing occurrence either):", literal[:60])
    for b in LISTED:
        w_all = int(total[b - 20:b + 36].sum())
        w_list = int(listing[b - 20:b + 36].sum())
        print("  listed base %d: window occurrences %d, listing %d, non-listing %d, reserved %s"
              % (b, w_all, w_list, w_all - w_list, in_reserved(b)))
    s7 = cands[0] if cands else None
    s8 = next((b for b in cands if s7 is not None and b >= s7 + 100000), None)
    print("RULE: set 7 = smallest CLEAN = %s; set 8 = smallest CLEAN >= set 7 + 100000 = %s" % (s7, s8))
    print("  replacements in rule order if the git check fails: set 7 ->", [b for b in cands if b > (s7 or 0)][:5],
          "| set 8 ->", [b for b in cands if s8 is not None and b > s8][:5])
    for lo, lab in CONTROLS:
        print("  positive control %s %d-%d: %d occurrences" % (lab, lo, lo + 15, int(total[lo:lo + 16].sum())))


OUTDIR = HERE
if __name__ == "__main__":
    if len(sys.argv) > 1:
        OUTDIR = sys.argv[1]
    main()
