
from statistics import median
from decoder import at_deco_stop

def best_shift(anchor, other, max_shift=30):
    # Compare depth profiles in sample-index space.
    n=min(len(anchor["samples"]),len(other["samples"]))
    if n<20: return 0
    a=anchor["samples"]; b=other["samples"]
    best=(float("inf"),0)
    for shift in range(-max_shift,max_shift+1):
        vals=[]
        for i in range(10,n-10,4):
            j=i+shift
            if 0<=j<n:
                vals.append(abs(a[i].depth-b[j].depth))
        if len(vals)>=10:
            score=sum(vals)/len(vals)
            if score<best[0]: best=(score,shift)
    return best[1]

def build_groups(dives):
    groups=[]; used=set()
    for d in dives:
        if d["source_id"] in used: continue
        group=[d]; used.add(d["source_id"])
        for x in dives:
            if x["source_id"] in used: continue
            dt=abs((x["start_dt"]-d["start_dt"]).total_seconds())
            if dt<=180:
                # Depth-profile check prevents unrelated nearby dives from joining.
                sh=best_shift(d,x)
                a=d["samples"]; b=x["samples"]
                checks=[]
                for i in range(20,min(len(a),len(b),300),10):
                    j=i+sh
                    if 0<=j<len(b): checks.append(abs(a[i].depth-b[j].depth))
                if checks and median(checks)<3.0:
                    group.append(x); used.add(x["source_id"])
        groups.append(group)
    return groups

def consolidate(group,gid):
    anchor=max(group,key=lambda d:len(d["samples"]))
    offsets={d["source_id"]: (0 if d is anchor else best_shift(anchor,d)) for d in group}
    maxn=max(len(d["samples"])+offsets[d["source_id"]] for d in group)
    timeline=[]
    for ai in range(maxn):
        device={}
        for d in group:
            j=ai-offsets[d["source_id"]]
            if 0<=j<len(d["samples"]):
                device[d["serial"]]=d["samples"][j]
        if not device: continue
        depths=[s.depth for s in device.values()]
        temps=[s.temp for s in device.values() if s.temp is not None]
        ppo2={serial:s.avg_ppo2 for serial,s in device.items()}
        o2_cells={serial:s.o2_cells_mv for serial,s in device.items()}
        tts={serial:s.tts_min for serial,s in device.items()}
        ceiling={serial:s.ceiling_m for serial,s in device.items()}
        ceiling_time={serial:s.ceiling_time_min for serial,s in device.items()}
        next_stop={serial:s.next_stop_m for serial,s in device.items()}
        gf99={serial:s.gf99 for serial,s in device.items()}
        cns={serial:s.cns for serial,s in device.items()}
        # Computers without cell capability deliberately remain None.
        tanks={}
        for d in group:
            j=ai-offsets[d["source_id"]]
            if not (0<=j<len(d["samples"])): continue
            s=d["samples"][j]
            # CRITICAL: only readings originating from THIS computer are added.
            for tank_idx,p in s.tank_pressures.items():
                tx=d["transmitters"].get(tank_idx)
                if tx:
                    tanks.setdefault(tx["serial"],{})[d["serial"]]=p
        timeline.append({
            "t_s":round(ai*anchor["interval_s"],1),
            "depth_m":round(median(depths),2) if depths else None,
            "temp_c":round(median(temps),1) if temps else None,
            "ppo2_by_device":ppo2,
            "tts_by_device":tts,
            "ceiling_by_device":ceiling,
            "ceiling_time_by_device":ceiling_time,
            "next_stop_by_device":next_stop,
            "gf99_by_device":gf99,
            "cns_by_device":cns,
            "o2_cells_mv_by_device":o2_cells,
            "tanks_by_serial":tanks
        })
    deco_samples=0
    prev_depth=None
    prev_t=None
    for r in timeline:
        dt=(r["t_s"]-prev_t) if prev_t is not None else None
        depth=r.get("depth_m")
        if depth is not None and any(
            at_deco_stop(depth, stop, prev_depth, dt)
            for stop in r["next_stop_by_device"].values()
        ):
            deco_samples+=1
        prev_depth=depth
        prev_t=r.get("t_s")
    tankmap={}
    for d in group:
        for idx,tx in d["transmitters"].items():
            e=tankmap.setdefault(tx["serial"],{"serial":tx["serial"],"aliases":[]})
            alias={"computer":d["computer"],"computer_serial":d["serial"],"name":tx["name"]}
            if alias not in e["aliases"]: e["aliases"].append(alias)
    return {
        "id":gid,"start":anchor["start"],"members":group,
        "computers":[d["computer"] for d in group],
        "max_depth":max(float(d["max_depth"]) for d in group if d["max_depth"] not in (None, "")),
        "average_depth":next((float(d["average_depth"]) for d in group if d["average_depth"] not in (None, "") and float(d["average_depth"]) > 0),None),
        "duration_min": round(max((len(d["samples"])-1)*d["interval_s"]/60.0 for d in group if d["samples"]),1),
        "end_gf99":next((float(d["end_gf99"]) for d in group if d["end_gf99"] not in (None, "") and float(d["end_gf99"]) != 0),None),
        "max_deco_obligation":next((d.get("max_deco_obligation") for d in group if d.get("max_deco_obligation") is not None),None),
        "dive_mode":anchor.get("dive_mode") or "other",
        "effective_deco_min":round(deco_samples*anchor["interval_s"]/60.0,2),
        "gps":next((d.get("gps") for d in group if d.get("gps")),None),
        "map_url":next((d.get("map_url") for d in group if d.get("map_url")),None),
        "location":next((d.get("location") for d in group if d.get("location")),None),
        "site":next((d.get("site") for d in group if d.get("site")),None),
        "tanks":sorted(tankmap.values(),key=lambda x:x["serial"]),
        "tanks_by_computer":{d["serial"]:sorted([
            {"serial":t["serial"], "name":next((a["name"] for a in t.get("aliases",[]) if a.get("computer_serial")==d["serial"]),t["serial"])}
            for t in tankmap.values()
            if any(a.get("computer_serial")==d["serial"] for a in t.get("aliases",[]))
        ],key=lambda x:x["serial"]) for d in group},
        "timeline":timeline
    }

def build_unified_dives(raw):
    groups=build_groups(raw)
    return [consolidate(g,f"D{i:04d}") for i,g in enumerate(groups,1)]
