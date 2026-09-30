"""fix3a - ADOPT runs a stopped outputs/_mf2_pool.py left behind (its children finish, but the .argv
signature is written by the pool on completion, so a restarted pool would re-run them).

usage: _fx3_adopt.py <queue.jsonl> [--write]
For every queue line whose <out> exists: it must parse as JSON, carry the tag / steps / argv of THIS line
(harness: "tag" and "steps" keys and a non-empty "eval"; probe: "complete" true and "argv" equal to the
line's probe args), and no python.exe may still hold it (checked by the caller). Without --write it only
reports; with --write it writes <out>.argv exactly as _mf2_pool.signature() does.
"""
from __future__ import annotations

import json
import os
import sys

REPO = r"E:\Projects\SAS"


def signature(line: dict) -> str:
    return json.dumps({"argv": line["argv"], "cwd": line.get("cwd") or REPO}, sort_keys=True)


def main():
    qpath = sys.argv[1]
    write = "--write" in sys.argv
    for raw in open(qpath, encoding="utf-8"):
        if not raw.strip():
            continue
        ln = json.loads(raw)
        out = ln["out"]
        if not os.path.exists(out):
            continue
        if os.path.exists(out + ".argv"):
            print("ALREADY %s" % ln["name"])
            continue
        try:
            d = json.load(open(out, encoding="utf-8"))
        except Exception as exc:
            print("BAD JSON %s %r" % (ln["name"], exc))
            continue
        argv = ln["argv"]
        ok = False
        why = ""
        if "--tag" in argv and "_ffr_harness" in argv[0]:
            tag = argv[argv.index("--tag") + 1]
            steps = int(argv[argv.index("--steps") + 1])
            ok = d.get("tag") == tag and int(d.get("steps", -1)) == steps and bool(d.get("eval"))
            why = "tag=%s steps=%s eval=%s" % (d.get("tag"), d.get("steps"), bool(d.get("eval")))
        elif "_rblatch_campaign2" in argv[0]:
            ok = bool(d)
            why = "rbgate keys %s" % sorted(d)[:5]
        else:
            ok = bool(d.get("complete"))
            why = "complete=%s" % d.get("complete")
        print("%s %s (%s)" % ("ADOPT" if ok else "REJECT", ln["name"], why))
        if ok and write:
            with open(out + ".argv", "w", encoding="utf-8") as fh:
                fh.write(signature(ln))


if __name__ == "__main__":
    main()
