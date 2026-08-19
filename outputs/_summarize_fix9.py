"""Parse fix9/fix8 eval logs into tables. UTF-8 only."""
from __future__ import annotations

import csv
import io
import os
import re
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCENARIOS = ("A", "B", "C", "D")
WINDS = ("north", "south", "east", "west")

MEAN_KEYS = (
    "rescued",
    "dead",
    "unreachable",
    "candidate",
    "rescue_rate",
    "firefighter_deaths",
    "burnt_cells",
    "terminal_step",
    "all_terminal",
)


def _parse_file(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    crash = "Traceback" in text or "--- EXIT" in text
    # CSV block is the last header-like line
    rows = []
    header = None
    for line in text.splitlines():
        if line.startswith("seed,rescued,"):
            header = line
            continue
        if header and re.match(r"^\d+,", line):
            rows.append(line)
        elif header and line.startswith("REPRODUCE:"):
            break
        elif header and line.startswith("---"):
            break
    parsed = []
    if header and rows:
        reader = csv.DictReader(io.StringIO(header + "\n" + "\n".join(rows)))
        parsed = list(reader)
    # summary means from "rescued: x +/- y" lines
    means = {}
    for key in (
        "rescued",
        "dead",
        "unreachable",
        "geographically_isolated",
        "never_detected",
        "candidate",
        "rescue_rate",
        "firefighter_deaths",
        "burnt_cells",
        "terminal_step",
    ):
        m = re.search(r"^  %s: ([0-9.]+) \+/- ([0-9.]+)" % key, text, re.M)
        if m:
            means[key] = (float(m.group(1)), float(m.group(2)))
    nd_causes = []
    nonterm = []
    for r in parsed:
        causes = (r.get("unreachable_causes") or "").strip()
        for part in causes.split(";"):
            part = part.strip()
            if part.endswith("never_detected") or ":never_detected" in part:
                nd_causes.append((r.get("seed"), part))
        if str(r.get("all_terminal", "")).strip() in ("False", "false", "0"):
            nonterm.append(r)
    return {
        "path": path,
        "crash": crash,
        "rows": parsed,
        "means": means,
        "nd_causes": nd_causes,
        "nonterm": nonterm,
        "text_head": text[:200],
    }


def _mean_bool_all_terminal(rows: list[dict]) -> str:
    if not rows:
        return "?"
    vals = [str(r.get("all_terminal", "")).strip() in ("True", "true", "1") for r in rows]
    if all(vals):
        return "True"
    if not any(vals):
        return "False"
    return "%d/5" % sum(vals)


def dump_matrix(prefix: str) -> None:
    print("=== %s 16-row table ===" % prefix)
    print(
        "scenario | wind | rescued | dead | unreachable | candidate | "
        "rescue_rate | firefighter_deaths | burnt_cells | terminal_step | all_terminal"
    )
    nd_by_combo = []
    nd_by_id = []
    nonterm_all = []
    crashes = []
    for s in SCENARIOS:
        for w in WINDS:
            path = os.path.join(_ROOT, "outputs", "%s_%s_%s.txt" % (prefix, s, w))
            if not os.path.isfile(path):
                print("%s | %s | MISSING %s" % (s, w, path))
                continue
            data = _parse_file(path)
            if data["crash"]:
                crashes.append(path)
            m = data["means"]
            rows = data["rows"]
            def g(k, default="?"):
                if k in m:
                    return "%.2f" % m[k][0]
                return default
            print(
                "%s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s"
                % (
                    s,
                    w,
                    g("rescued"),
                    g("dead"),
                    g("unreachable"),
                    g("candidate"),
                    g("rescue_rate"),
                    g("firefighter_deaths"),
                    g("burnt_cells"),
                    g("terminal_step"),
                    _mean_bool_all_terminal(rows),
                )
            )
            nd = m.get("never_detected", (None,))[0]
            nd_count = 0
            for seed, cause in data["nd_causes"]:
                nd_count += 1
                nd_by_id.append((s, w, seed, cause))
            nd_by_combo.append((s, w, nd if nd is not None else nd_count, nd_count))
            for r in data["nonterm"]:
                nonterm_all.append((s, w, r))
    print()
    print("=== never_detected per combo (mean, raw count of ND marks) ===")
    total_marks = 0
    for s, w, mean_nd, nmarks in nd_by_combo:
        total_marks += nmarks
        print("  %s/%s  mean=%s  marks=%d" % (s, w, mean_nd, nmarks))
    print("  TOTAL marks=%d" % total_marks)
    print()
    print("=== never_detected per victim id ===")
    if not nd_by_id:
        print("  (none)")
    for s, w, seed, cause in nd_by_id:
        print("  %s/%s seed=%s  %s" % (s, w, seed, cause))
    print()
    print("=== non-terminal seeds ===")
    if not nonterm_all:
        print("  (none)")
    for s, w, r in nonterm_all:
        print(
            "  %s/%s seed=%s rescued=%s dead=%s unreachable=%s candidate=%s "
            "nd=%s ff_deaths=%s causes=%s"
            % (
                s,
                w,
                r.get("seed"),
                r.get("rescued"),
                r.get("dead"),
                r.get("unreachable"),
                r.get("candidate"),
                r.get("never_detected"),
                r.get("firefighter_deaths"),
                r.get("unreachable_causes"),
            )
        )
    print()
    print("=== crashes ===")
    if not crashes:
        print("  (none)")
    for p in crashes:
        print("  %s" % p)


if __name__ == "__main__":
    prefix = sys.argv[1] if len(sys.argv) > 1 else "fix9"
    dump_matrix(prefix)
