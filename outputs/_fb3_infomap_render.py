"""Render outputs/fix3b_information_map.json (the read-only information-map workflow: M1 current searcher,
M2 fix3b strategies + shared pipeline, C cross-check + paper table) as outputs/fix3b_information_map.txt.

usage (repo root): .venv/Scripts/python.exe -B outputs/_fb3_infomap_render.py
"""
import json
import os
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "fix3b_information_map.json")
DST = os.path.join(HERE, "fix3b_information_map.txt")

CLASSES = ("B = briefing (known before launch) | S = sensed (own sensors, detection events, own state) | "
           "A3 = true fire state as an assumed perfect fire perimeter feed (assumption A3) | "
           "P = privileged (simulator ground truth no operator has) | D = design constant (set by hand)")


def wrap(s, ind):
    return "\n".join(textwrap.fill(p, 112, initial_indent=ind, subsequent_indent=ind) for p in str(s).split("\n"))


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    o = []
    o.append("fix3b INFORMATION MAP - exactly what each searcher strategy reads (paper finding (b), ruling 16.7)")
    o.append("Read-only mapping at branch fix3b 0e457b92 (source identical at 3e0973d9). Three agents: M1 = the current")
    o.append("searcher (SEARCHER_TARGETING 0); M2 = LO / BD / BF / RW and the shared pipeline; C = cross-check of both")
    o.append("(22 spot-checks against source, corrections C1-C5, omissions O1-O8) and the paper table.")
    o.append("Classes: " + CLASSES)
    o.append("")
    for key, title in (("table", "C - CROSS-CHECK, CORRECTIONS, OMISSIONS AND THE PAPER TABLE (governs where M1/M2 differ)"),
                       ("cur", "M1 - THE CURRENT SEARCHER"), ("fb", "M2 - THE fix3b STRATEGIES AND THE SHARED PIPELINE")):
        sec = d[key]
        o.append("=" * 112)
        o.append(title)
        o.append("=" * 112)
        o.append(sec["summary"])
        o.append("")
        o.append("-- items (%d) --" % len(sec["strategy_items"]))
        for i, it in enumerate(sec["strategy_items"], 1):
            o.append("[%s-%02d] %s | %s | %s | %s" % (key.upper(), i, it["strategy"], it["klass"], it["status"], it["item"]))
            o.append(wrap(it["how_used"], "    "))
            o.append(wrap("evidence: " + it["evidence"], "    "))
        o.append("")
        o.append("quarantine contact: " + sec["quarantine_contact"])
        o.append("")
    open(DST, "w", encoding="utf-8", newline="\n").write("\n".join(o) + "\n")
    print("wrote", DST)


if __name__ == "__main__":
    main()
