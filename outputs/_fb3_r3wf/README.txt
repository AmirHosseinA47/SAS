fix3b R-3 analysis workflow (2026-10-01): read-only scripts and outputs behind fix3b_rescreen_report.txt
section 15. Three analysts (a1 = code, a2 = recorded data, top level = options), each followed by an
adversarial verifier (v1 = code, verify_data = data, adv = options). Full structured results with verdicts:
outputs/fix3b_r3_analysis.json. Every script reads recorded run JSON through outputs/_fb3_analyze.load or
reads source; none runs the simulator. Paths inside the scripts point at the session scratchpad where they ran.
