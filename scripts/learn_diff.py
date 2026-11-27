"""Fase 4: aprender de las correcciones. Solo LEE el timeline (no modifica nada).
Compara el timeline corregido a mano contra <work>/montage_plan.json y escribe <work>/learn_report.json.

  python3 learn_diff.py --project NOMBRE [--timeline "Nombre del timeline"]
"""
import argparse, statistics as stt
from collections import Counter
from common import resolve, work_dir, jload, jsave, get_timeline

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True)
ap.add_argument("--timeline")
a = ap.parse_args()
W = work_dir(a.project)
plan = jload(f"{W}/montage_plan.json")
r, project, mp = resolve()
tl = get_timeline(project, a.timeline or plan["timeline"])
if tl is None:
    raise SystemExit("No encuentro el timeline.")
FPS = plan["fps"]; st = tl.GetStartFrame()
_ORDER = ("Normal Add Subtract Diff Multiply Screen Overlay Hardlight Softlight Darken Lighten ColorDodge ColorBurn "
          "Exclusion Hue Saturate Colorize LumaMask Divide LinearDodge LinearBurn LinearLight VividLight PinLight HardMix "
          "LighterColor DarkerColor Foreground Alpha InvertedAlpha Lum InvertedLum").split()
MODES = dict(enumerate(_ORDER))              # orden de COMPOSITE_* en el README de la API

snap = {}
for kind in ("video", "audio"):
    for k in range(1, tl.GetTrackCount(kind) + 1):
        rows = []
        for it in tl.GetItemListInTrack(kind, k) or []:
            d = {"name": it.GetName(), "start": it.GetStart() - st, "dur": it.GetDuration(), "left": it.GetLeftOffset()}
            if kind == "video":
                for p in ("ZoomX", "RotationAngle", "Pan", "Tilt", "CompositeMode", "Opacity", "CropLeft", "CropRight"):
                    d[p] = it.GetProperty(p)
            rows.append(d)
        snap[f"{kind}{k}:{tl.GetTrackName(kind, k)}"] = {"enabled": tl.GetIsTrackEnabled(kind, k), "items": rows}
snap["markers"] = {str(k): v for k, v in tl.GetMarkers().items()}
jsave(snap, f"{W}/timeline_corrected.json")

R = {"shots": [], "flashes": [], "audio": [], "tracks": [], "summary": []}
v1 = snap.get("video1:Tomas", list(snap.values())[0])["items"]
built = plan["shots"]
names_b = [s["name"] for s in built]; names_n = [s["name"] for s in v1]
removed = [n for n in names_b if n not in names_n]
added = [n for n in names_n if n not in names_b]
if removed: R["summary"].append(f"Tomas sacadas: {removed}")
if added: R["summary"].append(f"Tomas agregadas: {added}")
# emparejar en orden por nombre
j = 0; dur_ratio = Counter(); shifts = []
for b in built:
    while j < len(v1) and v1[j]["name"] != b["name"] and v1[j]["name"] in added:
        j += 1
    if j >= len(v1) or v1[j]["name"] != b["name"]:
        continue
    n = v1[j]; j += 1; ch = []
    if n["dur"] != b["len"]:
        ch.append(f"duración {b['len']}→{n['dur']} cuadros ({(n['dur'] - b['len']) / FPS:+.2f} s)")
        dur_ratio[b["kind"]] += 1
    if n["start"] != b["rec"]:
        shifts.append(n["start"] - b["rec"])
    if n["left"] != b["src"]:
        ch.append(f"parte del clip {b['src']}→{n['left']} ({(n['left'] - b['src']) / b['clip_fps']:+.2f} s)")
    if abs((n["ZoomX"] or 1) - b["zoom_applied"]) > 0.01:
        ch.append(f"zoom {b['zoom_applied']}→{round(n['ZoomX'], 3)}")
    exp_rot = -90.0 if b.get("rotate") == "cw" else 90.0 if b.get("rotate") == "ccw" else 0.0
    if abs((n["RotationAngle"] or 0) - exp_rot) > 0.1:
        ch.append(f"rotación {exp_rot}→{n['RotationAngle']}")
    for p in ("Pan", "Tilt", "CropLeft", "CropRight"):
        if n.get(p):
            ch.append(f"{p}={round(n[p], 1)}")
    if n.get("Opacity") not in (None, 100, 100.0):
        ch.append(f"opacidad {n['Opacity']}")
    if ch:
        R["shots"].append({"kind": b["kind"], "type": b["type"], "name": b["name"], "at_s": round(b["rec"] / FPS, 2), "changes": ch})
if shifts:
    R["summary"].append(f"Cortes corridos (ripple): {len(shifts)} tomas, mediana {stt.median(shifts) / FPS:+.2f} s"
                        " — probablemente ripple sin querer (estilo: los cortes quedan en la grilla); preguntar")
if v1:
    end_v = v1[-1]["start"] + v1[-1]["dur"]
    end_b = built[-1]["rec"] + built[-1]["len"]
    if end_v != end_b:
        R["summary"].append(f"V1 termina {(end_v - end_b) / FPS:+.2f} s respecto del tema — el video debe terminar con el tema")

# efectos/generadores agregados a mano (Fusion, p. ej. Brightness Flash): no son clips del plan
plan_names = {s["name"] for s in built} | {x["name"] for x in plan.get("flashes", [])}
for key, val in snap.items():
    if key.startswith("video"):
        for x in val["items"]:
            if x["name"] not in plan_names and not x["name"].lower().endswith((".mp4", ".mov", ".mxf", ".braw", ".m4v")):
                R["summary"].append(f"Efecto agregado a mano: {x['name']} en {x['start'] / FPS:.2f} s ({x['dur']} cuadros, {key})")
# largo del tema (modo fiesta: tramo del editor + cola de audio)
if plan.get("mode") == "party":
    a1 = snap.get("audio1:Tema", {"items": []})["items"]
    if a1:
        exp = plan["song"]["len_f"] + plan.get("audio_tail", 0)
        if a1[0]["dur"] != exp:
            R["summary"].append(f"Tema: {exp}→{a1[0]['dur']} cuadros ({(a1[0]['dur'] - exp) / FPS:+.2f} s de cola respecto del plan)")
    pm = {int(float(k)) for k in snap["markers"]}
    lost = [m for m in plan.get("markers", []) if m[0] not in pm]
    if lost:
        R["summary"].append("Marcadores sacados: " + ", ".join(f"{m[2]} @{m[0]}" for m in lost))
v2 = snap.get("video2:Destellos", {"items": []})["items"]
modes = Counter(MODES.get(x["CompositeMode"], x["CompositeMode"]) for x in v2)
if v2:
    R["flashes"] = [{"name": x["name"], "at_s": round(x["start"] / FPS, 2), "len_s": round(x["dur"] / FPS, 2),
                     "mode": MODES.get(x["CompositeMode"], x["CompositeMode"]), "zoom": round(x["ZoomX"] or 1, 2)} for x in v2]
    R["summary"].append(f"Destellos: modos {dict(modes)} · zoom mediano {stt.median([x['ZoomX'] or 1 for x in v2]):.2f}"
                        f" · duración mediana {stt.median([x['dur'] for x in v2]) / FPS:.2f} s (armé {len(plan['flashes'])})")
for key, val in snap.items():
    if key.startswith("audio"):
        tname = key.split(":", 1)[1]
        mine = [x for x in plan["audio"] if x["track"] == tname]
        if not val["items"] and mine:
            R["summary"].append(f"Pista {tname}: vaciada (sacaste {len(mine)} clip/s)")
        elif not val["enabled"]:
            R["summary"].append(f"Pista {tname}: desactivada")
        elif mine and len(val["items"]) != len(mine):
            R["summary"].append(f"Pista {tname}: {len(mine)}→{len(val['items'])} clips")
        R["audio"].append({"track": tname, "items": [(x["name"], round(x["start"] / FPS, 2), round(x["dur"] / FPS, 2)) for x in val["items"]]})
if dur_ratio:
    R["summary"].append(f"Duraciones cambiadas por tipo de toma: {dict(dur_ratio)}")
jsave(R, f"{W}/learn_report.json")
print("\n".join(R["summary"]) or "Sin cambios detectables por API.")
for s in R["shots"]:
    print(f"  {s['at_s']:6.2f}s {s['kind']:6} {s['type']:8} {s['name']}: " + "; ".join(s["changes"]))
print("\nNo visible por API (preguntar): volúmenes, fundidos, efectos/Fusion, keyframes de zoom, color.")
