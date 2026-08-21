from flask import Flask,render_template,abort,request
from decoder import load_dives
from matcher import build_unified_dives
from stats import build_stats_grid

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

def filtered_raw(selected=None):
    raw=raw_data()
    if selected:
        raw=[d for d in raw if d["serial"] in selected]
    return raw

def data(selected=None):
    return build_unified_dives(filtered_raw(selected))

@app.route("/")
def index():
    raw_all=raw_data()
    computers=available_computers(raw_all)
    selected=selected_serials()
    raw=raw_all if not selected else [d for d in raw_all if d["serial"] in selected]
    dives=build_unified_dives(raw)
    deco_only=request.args.get("deco","0")=="1"
    if deco_only:
        dives=[d for d in dives if (d.get("max_deco_obligation") or 0)>0]
        raw=[d for d in raw if (d.get("max_deco_obligation") or 0)>0]
    stats_grid=build_stats_grid(dives, raw)
    return render_template("index.html",dives=dives,stats_grid=stats_grid,computers=computers,
                           selected_serials=selected, deco_only=deco_only)

@app.route("/dive/<dive_id>")
def dive_detail(dive_id):
    selected=selected_serials()
    dive=next((d for d in data(selected) if d["id"]==dive_id),None)
    if not dive: abort(404)
    return render_template("dive.html",dive=dive)

if __name__=="__main__":
    app.run(debug=True)
