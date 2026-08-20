
from decoder import load_dives
from matcher import build_unified_dives

dives=build_unified_dives(load_dives("dive_data.db"))
for d in dives:
    if d["start"].startswith("2026-08-01 11:24:18"):
        print("Dive:",d["id"],d["start"])
        for m in d["members"]:
            print(" ",m["computer"],m["serial"],"first cells:",m["samples"][0].o2_cells_mv)
        for r in d["timeline"][:5]:
            print(r["t_s"],r["o2_cells_mv_by_device"])
        break
