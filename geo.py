
import json, urllib.parse, urllib.request, re

def parse_gps(raw):
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        try: raw=raw.decode("utf-8","ignore")
        except Exception: return None
    s=str(raw).strip()
    if not s: return None
    try:
        obj=json.loads(s)
        if isinstance(obj,dict):
            lat=obj.get("latitude",obj.get("lat"))
            lon=obj.get("longitude",obj.get("lon",obj.get("lng")))
            if lat is not None and lon is not None:
                return float(lat),float(lon)
    except Exception:
        pass
    nums=re.findall(r"-?\d+(?:\.\d+)?",s)
    if len(nums)>=2:
        try:
            lat,lon=float(nums[0]),float(nums[1])
            if -90<=lat<=90 and -180<=lon<=180:
                return lat,lon
        except ValueError: pass
    return None

def map_url(lat,lon):
    return f"https://www.google.com/maps/search/?api=1&query={lat:.6f},{lon:.6f}"

def reverse_city(lat,lon):
    # Nominatim is optional; failure simply leaves city unknown.
    try:
        q=urllib.parse.urlencode({"lat":lat,"lon":lon,"format":"json","zoom":10})
        req=urllib.request.Request(
            "https://nominatim.openstreetmap.org/reverse?"+q,
            headers={"User-Agent":"CCR-Dive-Web/3.6"}
        )
        with urllib.request.urlopen(req,timeout=4) as r:
            obj=json.load(r)
        a=obj.get("address",{})
        return a.get("city") or a.get("town") or a.get("village") or a.get("municipality") or a.get("county")
    except Exception:
        return None
