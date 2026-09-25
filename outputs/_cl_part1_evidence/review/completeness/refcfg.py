import json, os
O = "E:/Projects/SAS/outputs/"
names = [
    "_ffr_ugD_east_half_101.json", "_ffr_ugD_south_half_505.json", "_ffr_ugD_east_def_303.json",
    "_ffr_uhD_east_half_2070841104.json", "_ffr_ugD_east_half_2070841104.json",
    "_ffr_ugKD_east_half_2070841104.json", "_ffr_ugKC_east_half_2070841104.json",
    "_ffr_ugmD_east_half_101.json", "_ffr_uhC_east_half_2070841104.json",
    "_ffr_ugC_east_half_101.json",
]
for n in names:
    p = O + n
    if not os.path.isfile(p):
        print(n, "MISSING"); continue
    d = json.load(open(p, encoding="utf-8"))
    ua = d.get("uav_actions")
    print(n, "| repo", d.get("repo"), "| steps", d.get("steps"), "| extra", d.get("extra_params"),
          "| uav_actions", None if ua is None else len(ua), "| fm2p", "fm2p" in d,
          "| fm2p cfg", (d.get("fm2p") or {}).get("config"))
    pr = d.get("params") or {}
    print("    params keys subset:", {k: pr.get(k) for k in ("BATCH_SIZE", "FF_FIREFIGHT_GATE", "FF_FIREFIGHT_EXTINGUISH", "FF_FIREFIGHT_FIREBREAK") if k in pr})
