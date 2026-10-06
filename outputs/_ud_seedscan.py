"""_ud_seedscan.py - read-only whole-token seed scanner (agent seedstools, urgency round Part 1;
outputs/urgency_part1.txt 16.2). RECORD of the freshness check behind outputs/_ud_seeds.txt, run once on
2026-10-06 BEFORE any file of this round existed. It is NOT a selector: analyzers read _ud_seeds.txt and never
re-run this. Changes from the copy that ran: the result-file names (_ud_ prefix) and OWN_ROUND, which skips this
round's own files (it matched nothing when the check ran) so that a re-run cannot find the chosen seeds in the
round's own records (seed-selector self-reference rule).

Counts whole-token occurrences of integers, i.e. matches of (?<![0-9])N(?![0-9]), which is exactly
"a MAXIMAL run of ASCII digits whose text equals str(N)" (so a run with a leading zero never equals N).

For every scanned file it extracts every maximal digit run of length 4..6 with a non-zero first digit
and adds it to three global histograms (values 0..999999):
    NAME   - runs in the file's path relative to its tree root (directory components + basename)
    TEXT   - runs in the content of files classified as text
    BIN    - runs in the content of files classified as binary (NUL bytes, not UTF-16)
plus per-value FILE counts and up to 8 example paths for every value in the WATCH list.

Decoding: UTF-16 by BOM (FF FE / FE FF) or, without a BOM, by a NUL-parity heuristic on the first
64 KiB; the decoded text is re-encoded to UTF-8. Every other file is scanned as raw bytes: ASCII digits
0x30-0x39 never occur inside a UTF-8 multi-byte sequence, so a byte-level scan is identical to scanning
the UTF-8 (errors=ignore) or latin-1 decoding of the same file.

Traversal: os.walk; the quarantine directory name and .git are removed from dirs BEFORE descending.
Files > 200 MB are skipped and listed. Nothing is written except the result files in this folder.
"""
import json
import os
import re
import sys
import time

import numpy as np

QUAR = "_firemech_rewound_20260914"
OWN_ROUND = ("_ud", "urgency_", "_sd_ud", "_ffr_ud", "_ffr_rb_ud", "_rblatch_camp2_ud")
MAXSZ = 200 * 1024 * 1024
CHUNK = 32 * 1024 * 1024
HERE = os.path.dirname(os.path.abspath(__file__))

TREES = [  # (label, root, recursive, filename filter for non-recursive)
    ("SAS/outputs", r"E:/Projects/SAS/outputs", True, None),
    ("dispatch/outputs", r"E:/Projects/SAS_wt/dispatch/outputs", True, None),
    ("prereg480cur/outputs", r"E:/Projects/SAS_wt/prereg480cur/outputs", True, None),
    ("zealous/outputs", r"E:/Projects/SAS/.claude/worktrees/zealous-colden-0b9fe2/outputs", True, None),
    ("urgency/outputs (extra)", r"E:/Projects/SAS_wt/urgency/outputs", True, None),
    ("SAS/docs", r"E:/Projects/SAS/docs", True, None),
    ("SAS/tests", r"E:/Projects/SAS/tests", True, None),
    ("SAS/src_extension (extra)", r"E:/Projects/SAS/src_extension", True, None),
    ("SAS root *.py/*.md/*.txt", r"E:/Projects/SAS", False, (".py", ".md", ".txt")),
    ("memory (extra)", r"C:/Users/ahrar/.claude/projects/E--Projects-SAS/memory", True, None),
]

BASES = [9601, 9621,  # positive controls (the dispatch round's sets 1 and 2)
         9641, 9661, 9681, 9701, 9721, 9741, 9761, 9781, 9801, 9821, 9841, 9861, 9881, 9901, 9921, 9941,
         9961, 9981,
         40001, 40021, 40041, 41001, 41021, 42001, 43001, 44001, 45001, 46001, 47001, 48001, 49001,
         50001, 50021, 51001, 52001, 53001, 54001, 55001, 56001, 57001, 58001, 59001,
         61001, 61021, 62001, 63001, 64001, 65001, 66001, 67001, 68001, 69001,
         70001, 71001, 72001, 73001, 74001, 75001, 76001, 77001, 78001, 79001,
         81001, 82001, 83001, 84001, 85001, 86001, 87001, 88001, 89001,
         91001, 92001, 93001, 94001, 95001, 96001, 97001, 98001, 99001]
WATCH = sorted(set(b + i for b in BASES for i in range(16)) | set(range(30001, 30257)))
WATCH_ARR = np.array(WATCH, dtype=np.int64)
POW = {L: (10 ** np.arange(L - 1, -1, -1)).astype(np.int64) for L in (4, 5, 6)}
NAME_RE = re.compile(r"(?<![0-9])[1-9][0-9]{3,5}(?![0-9])")

H_NAME = np.zeros(1_000_000, dtype=np.int64)
H_TEXT = np.zeros(1_000_000, dtype=np.int64)
H_BIN = np.zeros(1_000_000, dtype=np.int64)
F_TEXT = np.zeros(1_000_000, dtype=np.int64)   # files (text) containing the value at least once
F_BIN = np.zeros(1_000_000, dtype=np.int64)
EXAMPLES = {}   # value -> list of (kind, path, count)


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
            # cut after the last non-digit byte so no digit run straddles the cut
            cut = len(buf)
            while cut > 0 and 48 <= buf[cut - 1] <= 57:
                cut -= 1
            parts.append(runs_values(buf[:cut]))
            carry = buf[cut:]
        vals = np.concatenate(parts) if parts else np.zeros(0, dtype=np.int64)
        return kind, vals


def main():
    t0 = time.time()
    report = {"trees": [], "skipped_big": [], "errors": [], "kinds": {}}
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
                    H_NAME[int(m)] += 1
                    v = int(m)
                    if v in WATCH_SET:
                        EXAMPLES.setdefault(v, [])
                        if len(EXAMPLES[v]) < 8:
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
                        if len(EXAMPLES[v]) < 8:
                            EXAMPLES[v].append(("BIN" if isbin else "TEXT", label + ":" + rel, cc))
        tr["secs"] = round(time.time() - t1, 1)
        report["trees"].append(tr)
        print("DONE", label, tr, flush=True)
    report["secs_total"] = round(time.time() - t0, 1)
    np.savez_compressed(os.path.join(HERE, "_ud_seedscan_hist.npz"), name=H_NAME, text=H_TEXT, bin=H_BIN,
                        ftext=F_TEXT, fbin=F_BIN)
    report["examples"] = {str(k): v for k, v in sorted(EXAMPLES.items())}
    with open(os.path.join(HERE, "_ud_seedscan_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    print("TOTAL secs", report["secs_total"], "skipped_big", report["skipped_big"], "errors", len(report["errors"]))
    print("kinds", report["kinds"])


WATCH_SET = set(WATCH)
if __name__ == "__main__":
    main()
