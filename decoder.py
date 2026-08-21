import sqlite3, gzip, struct, json
from dataclasses import dataclass, field
from datetime import datetime
from geo import parse_gps, map_url

MODELS={2:"Predator",3:"Petrel",4:"Nerd",5:"Perdix",6:"Perdix AI",7:"Nerd 2",8:"Teric",9:"Peregrine",10:"Petrel 3",11:"Perdix 2",12:"Tern"}

@dataclass
class Sample:
    t_s: float
    depth: float
    temp: float|None
    avg_ppo2: float|None
    tts_min: float|None = None
    ceiling_m: float|None = None
    ceiling_time_min: float|None = None
    gf99: float|None = None
    cns: float|None = None
    o2_cells_mv: list|None = None
    tank_pressures: dict=field(default_factory=dict)

def u16(b,o): return struct.unpack_from(">H",b,o)[0]
def u32(b,o): return struct.unpack_from(">I",b,o)[0]

def pressure(v):
    if v >= 0xFFF0:
        return None
    return (v & 0x0FFF)*2.0

def decompress_pnf(blob):
    expected=struct.unpack_from("<I",blob,0)[0]
    raw=gzip.decompress(blob[4:])
    if len(raw)!=expected or len(raw)%32:
        raise ValueError("Invalid PNF payload")
    return raw

def decode_pnf(blob):
    raw=decompress_pnf(blob)
    opening={}; closing={}; final=None
    records=[]
    for off in range(0,len(raw),32):
        rec=raw[off:off+32]; typ=rec[0]
        if rec == b"\0"*32: continue
        records.append((typ,rec))
        if 0x10<=typ<=0x19: opening[typ-0x10]=rec
        elif 0x20<=typ<=0x29: closing[typ-0x20]=rec
        elif typ==0xff: final=rec

    interval=10.0
    if 5 in opening:
        interval=u16(opening[5],23)/1000 or 10.0

    serial=u32(final,2) if final else None
    model=MODELS.get(final[13],str(final[13])) if final else "Unknown"

    samples=[]; last=None; t=0.0
    for typ,rec in records:
        if typ==0x01:
            tanks={}
            # PNF: tank index 0 is bytes 28-29, index 1 is bytes 20-21.
            p0=pressure(u16(rec,28)); p1=pressure(u16(rec,20))
            if p0 is not None: tanks[0]=p0
            if p1 is not None: tanks[1]=p1
            last=Sample(
                t_s=t,
                depth=u16(rec,1)/10.0,
                temp=struct.unpack("b",rec[14:15])[0],
                avg_ppo2=rec[7]/100.0,
                # PNF: bytes 5-6 = TTS (minutes), 24 = deco ceiling/stop depth,
                # 10 = NDL or next-stop time. A zero stop depth means there is
                # no deco ceiling; byte 10 is then NDL rather than stop time.
                tts_min=float(u16(rec,5)),
                ceiling_m=float(rec[24]) if rec[24] > 0 else None,
                ceiling_time_min=float(rec[10]) if rec[24] > 0 else None,
                # PNF: byte 23 is CNS percentage; byte 25 is GF99.
                # 0xFF means GF99 is not available while tissues are on-gassing.
                cns=float(rec[23]),
                gf99=float(rec[25]) if rec[25] != 0xFF else None,
                # PNF dive sample: O2 cells are raw mV at bytes 13, 15, 16.
                # Only Petrel (3) and Nerd 2 (7) are treated as cell-capable
                # for this project; unsupported computers stay NULL.
                o2_cells_mv=(
                    [float(rec[13]), float(rec[15]), float(rec[16])]
                    if model in ("Petrel", "Nerd 2") else None
                ),
                tank_pressures=tanks
            )
            samples.append(last)
            t+=interval
        elif typ==0xe1 and last is not None:
            # Extended sample immediately follows the preceding 0x01.
            # Tank indexes 2 and 3 are encoded here.
            for idx,off in ((2,1),(3,3)):
                v=u16(rec,off)
                p=pressure(v)
                if p is not None: last.tank_pressures[idx]=p

    firmware = None
    if final and len(final) > 10:
        # PNF final record, offset 10: firmware version in packed BCD.
        # Example: 0x12 0x34 -> "12.34".
        b = final[10]
        hi, lo = (b >> 4) & 0x0F, b & 0x0F
        if hi <= 9 and lo <= 9:
            firmware = f"{hi}{lo}"
    return {
        "model_id": final[13] if final else None,
        "firmware_version": firmware or "—",
        # PNF stores the computer serial as a 32-bit hexadecimal identifier.
        "serial": f"{serial:08X}" if serial is not None else "",
        "computer": model,
        "samples": samples,
        "interval_s": interval,
    }

def transmitter_defs(tank_json):
    result={}
    try: obj=json.loads(tank_json or "{}")
    except Exception: return result
    for item in obj.get("TankData",[]):
        tx=item.get("DiveTransmitter")
        if not tx: continue
        serial=str(tx.get("UnformattedSerialNumber") or "").strip()
        if not serial or serial=="000000" or not tx.get("IsOn"): continue
        idx=int(tx.get("TankIndex",0))
        name=(tx.get("Name") or "").strip("\x00 ") or f"T{idx+1}"
        result[idx]={"serial":serial,"name":name}
    return result


def _calculated_value(raw, key):
    try:
        obj = json.loads(raw or "{}")
        value = obj.get(key)
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

def _max_deco(raw):
    return _calculated_value(raw, "MaxDecoObligation")

def _has_column(conn, table, column):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)

def load_dives(db_path):
    conn=sqlite3.connect(db_path); conn.row_factory=sqlite3.Row
    gnss_select = (
        "GnssEntryLocation"
        if _has_column(conn, "dive_details", "GnssEntryLocation")
        else "'' AS GnssEntryLocation"
    )
    rows=conn.execute(f"""
      SELECT DiveId,SerialNumber,DiveDate,Depth,AverageDepth,EndGF99,calculated_values_from_samples,
             {gnss_select},Location,Site,TankProfileData,log_data.data_bytes_1
      FROM dive_details JOIN log_data ON log_data.log_id=dive_details.DiveId
      WHERE log_data.format='sw-pnf'
      ORDER BY DiveDate
    """).fetchall()
    result=[]
    for r in rows:
        d=decode_pnf(r["data_bytes_1"])
        defs=transmitter_defs(r["TankProfileData"])
        gps_raw=r["GnssEntryLocation"] or ""
        gps=parse_gps(gps_raw)
        result.append({
            "source_id":r["DiveId"],
            "start":r["DiveDate"],
            "start_dt":datetime.fromisoformat(r["DiveDate"]),
            "serial":d["serial"] or str(r["SerialNumber"]),
            "computer":d["computer"],
            "model_id":d.get("model_id"),
            "firmware_version":d.get("firmware_version"),
            "samples":d["samples"],
            "interval_s":d["interval_s"],
            "transmitters":defs,
            "average_depth":_calculated_value(r["calculated_values_from_samples"], "AverageDepth") if _calculated_value(r["calculated_values_from_samples"], "AverageDepth") not in (None, 0.0) else (float(r["AverageDepth"]) if r["AverageDepth"] not in (None, "") and float(r["AverageDepth"]) != 0 else None),
            "max_depth":r["Depth"],
            "end_gf99":_calculated_value(r["calculated_values_from_samples"], "EndGF99") if _calculated_value(r["calculated_values_from_samples"], "EndGF99") not in (None, 0.0) else (float(r["EndGF99"]) if r["EndGF99"] not in (None, "") and float(r["EndGF99"]) != 0 else None),
            "max_deco_obligation": _max_deco(r["calculated_values_from_samples"]),
            "gps_raw":gps_raw,
            "gps": gps,
            "map_url": (map_url(*gps) if gps else None),
            "location":r["Location"],
            "site":r["Site"],
        })
    conn.close()
    return result