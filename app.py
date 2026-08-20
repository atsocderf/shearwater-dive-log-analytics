from flask import Flask,render_template,abort,request
import statistics
from decoder import load_dives
from matcher import build_unified_dives

app=Flask(__name__)
DB_PATH="dive_data.db"

def raw_data():
    return load_dives(DB_PATH)

def available_computers(raw=None):
    raw = raw if raw is not None else raw_data()
    result={}
    for d in raw:
        serial=d["serial"]
        if serial not in result:
            result[serial]={
                "serial":serial,
                "name":d["computer"],
                "model_id":d.get("model_id"),
                "firmware_version":d.get("firmware_version") or "—",
            }
        elif result[serial]["firmware_version"]=="—" and d.get("firmware_version"):
            result[serial]["firmware_version"]=d["firmware_version"]
    return [result[s] for s in sorted(result)]

def selected_serials():
    # Multiple checkboxes use the same query parameter name.
    # get() returns only the first value; getlist() preserves all selected computers.
    values=request.args.getlist("computers")
    if not values:
        return None
    return {x.strip() for x in values if x.strip()}

def data(selected=None):
    raw=raw_data()
    if selected:
        raw=[d for d in raw if d["serial"] in selected]
    return build_unified_dives(raw)

@app.route("/")
def index():
    raw=raw_data()
    computers=available_computers(raw)
    selected=selected_serials()
    dives=data(selected)
    deco_only=request.args.get("deco","0")=="1"
    if deco_only:
        dives=[d for d in dives if (d.get("max_deco_obligation") or 0)>0]
    source_dives=data(selected)
    durations=[float(d["duration_min"]) for d in source_dives if d.get("duration_min") is not None]
    depths=[float(d["average_depth"]) for d in source_dives if d.get("average_depth") not in (None,0)]
    stats={
        "dives":len(dives),
        "deco_dives":sum(1 for d in source_dives if (d.get("max_deco_obligation") or 0)>0),
        "median_average_depth":statistics.median(depths) if depths else None,
        "median_duration":statistics.median(durations) if durations else None,
    }
    return render_template("index.html",dives=dives,stats=stats,computers=computers,
                           selected_serials=selected, deco_only=deco_only)

@app.route("/dive/<dive_id>")
def dive_detail(dive_id):
    selected=selected_serials()
    dive=next((d for d in data(selected) if d["id"]==dive_id),None)
    if not dive: abort(404)
    return render_template("dive.html",dive=dive)

if __name__=="__main__":
    app.run(debug=True)
