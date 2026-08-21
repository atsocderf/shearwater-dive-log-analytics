from collections import Counter

COLUMNS=(
    ("all","Todos os modos de mergulho"),
    ("oc_rec","OC Rec"),
    ("oc_tec","OC Tec"),
    ("cc_bo","CC/BO"),
)

EMPTY={"text":"—","meters":None}
NA={"text":"N/A","meters":None}

def _in_mode(dive, mode):
    if mode=="all":
        return True
    return dive.get("dive_mode")==mode

def _duration(dive):
    value=dive.get("duration_min")
    if value is None:
        return 0.0
    return float(value)

def _max_depth(dive):
    value=dive.get("max_depth")
    if value in (None,""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _place(dive, key):
    value=dive.get(key)
    if value is None:
        return None
    text=str(value).strip()
    return text or None

def _cell(text, meters=None):
    return {"text":text,"meters":meters}

def format_dhmin(minutes):
    total=int(round(max(float(minutes),0)))
    days, rem=divmod(total,1440)
    hours, mins=divmod(rem,60)
    parts=[]
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{mins}min")
    return " ".join(parts)

def format_hmin(minutes):
    total=int(round(max(float(minutes),0)))
    hours, mins=divmod(total,60)
    if hours:
        return f"{hours}h {mins}min"
    return f"{mins}min"

def format_mins_secs(minutes):
    total_s=int(round(max(float(minutes),0)*60))
    mins, secs=divmod(total_s,60)
    return f"{mins}min {secs:02d}s"

def _sum_duration(dives):
    if not dives:
        return EMPTY
    return _cell(format_dhmin(sum(_duration(d) for d in dives)))

def _deepest(dives):
    depths=[m for m in (_max_depth(d) for d in dives) if m is not None]
    if not depths:
        return EMPTY
    value=max(depths)
    return _cell(f"{value:.1f}m", value)

def _avg_max_depth(dives):
    depths=[m for m in (_max_depth(d) for d in dives) if m is not None]
    if not depths:
        return EMPTY
    value=sum(depths)/len(depths)
    return _cell(f"{value:.1f}m", value)

def _longest(dives):
    if not dives:
        return EMPTY
    return _cell(format_hmin(max(_duration(d) for d in dives)))

def _avg_duration(dives):
    if not dives:
        return EMPTY
    return _cell(format_mins_secs(sum(_duration(d) for d in dives)/len(dives)))

def _effective_deco(dives):
    if not dives:
        return EMPTY
    total=sum(float(d.get("effective_deco_min") or 0) for d in dives)
    return _cell(format_dhmin(total))

def _most_visited(dives, key):
    values=[_place(d,key) for d in dives]
    values=[v for v in values if v]
    if not values:
        return NA
    return _cell(Counter(values).most_common(1)[0][0])

def _distinct(dives, key):
    values={_place(d,key) for d in dives}
    values={v for v in values if v}
    return _cell(str(len(values)))

METRICS=(
    ("total_time","Tempo total embaixo d'água",_sum_duration),
    ("deepest","Mergulho mais profundo",_deepest),
    ("avg_max_depth","Prof. máxima do mergulho",_avg_max_depth),
    ("longest","Mergulho mais longo",_longest),
    ("avg_duration","Tempo médio do mergulho",_avg_duration),
    ("effective_deco","Tempo de descompressão efetivo",_effective_deco),
    ("top_location","Localidade mais visitada",lambda dives: _most_visited(dives,"location")),
    ("distinct_locations","Localidades distintas",lambda dives: _distinct(dives,"location")),
    ("top_site","Ponto mais visitado",lambda dives: _most_visited(dives,"site")),
    ("distinct_sites","Pontos distintos",lambda dives: _distinct(dives,"site")),
)

def _computers(raw):
    seen={}
    for d in raw:
        serial=d.get("serial")
        if not serial or serial in seen:
            continue
        seen[serial]={"serial":serial,"name":d.get("computer") or serial}
    return sorted(seen.values(), key=lambda c: (c["name"], c["serial"]))

def build_stats_grid(unified, raw):
    computers=_computers(raw)
    rows=[]
    for metric_id, label, fn in METRICS:
        total={}
        by_computer={c["serial"]:{ } for c in computers}
        for mode,_ in COLUMNS:
            total[mode]=fn([d for d in unified if _in_mode(d, mode)])
            for computer in computers:
                subset=[
                    d for d in raw
                    if d.get("serial")==computer["serial"] and _in_mode(d, mode)
                ]
                by_computer[computer["serial"]][mode]=fn(subset)
        rows.append({
            "id":metric_id,
            "label":label,
            "total":total,
            "by_computer":by_computer,
        })
    return {
        "columns":[{"id":mode,"label":label} for mode,label in COLUMNS],
        "computers":computers,
        "rows":rows,
    }
