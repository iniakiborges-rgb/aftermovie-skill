"""Fase 1c: bin "Filtrados" (In/Out marcados) + timeline "Selects" en orden cronológico.
NO mueve ni borra nada: reimporta los archivos elegidos en un bin nuevo; si el nombre existe usa "v2", "v3"...

Entrada <work>/selection.json (la escribe Claude tras mirar las hojas de contacto):
  [{"name": "C0012.MP4", "type": "DJ|público|banda|general|marca|detalle",
    "in": 3.2, "len": 3,            # opcionales: por defecto, el tramo de windows.json
    "rotate": "cw|ccw",             # opcional: toma grabada de costado
    "note": "brindis"}]

  python3 build_selects.py --project NOMBRE [--format vertical|horizontal] [--parent-bin Master]
"""
import argparse, os, sys
from common import resolve, work_dir, jload, jsave, find_folder, timeline_names, free_name

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True)
ap.add_argument("--format", choices=["vertical", "horizontal"], default="vertical")
ap.add_argument("--parent-bin", default="Master")
ap.add_argument("--bin-name", default="Filtrados")
ap.add_argument("--timeline", default="Selects")
a = ap.parse_args()
W = work_dir(a.project)

win = {r["name"]: r for r in jload(f"{W}/windows.json")["clips"]}
clips = {c["name"]: c for c in jload(f"{W}/clips.json")}
sel = []
for s in jload(f"{W}/selection.json"):
    r = win[s["name"]]
    t_in = s.get("in", r.get("in", r.get("rescue_in")))
    L = s.get("len", r.get("len", 2))
    if t_in is None:
        sys.exit(f"{s['name']}: sin tramo; indicá 'in' y 'len' en selection.json")
    sel.append({**s, "in": float(t_in), "len": float(L), "path": r["path"], "vertical": r["vertical"],
                "created": clips.get(s["name"], {}).get("created", "")})
sel.sort(key=lambda s: (s["created"], s["name"]))

_, project, mp = resolve()
root = mp.GetRootFolder()
parent = find_folder(root, a.parent_bin) or root
bin_name = free_name([f.GetName() for f in parent.GetSubFolderList() or []], a.bin_name)
tl_name = free_name(timeline_names(project), a.timeline)

folder = mp.AddSubFolder(parent, bin_name)
mp.SetCurrentFolder(folder)
imported = mp.ImportMedia([s["path"] for s in sel]) or []
by_path = {it.GetClipProperty("File Path"): it for it in imported}

infos, fps_seen = [], None
for s in sel:
    it = by_path.get(s["path"])
    if it is None:
        print("  ! no se importó", s["name"]); continue
    fps = float(str(it.GetClipProperty("FPS")).split()[0]); fps_seen = fps_seen or fps
    a0, n = int(round(s["in"] * fps)), int(round(s["len"] * fps))
    s["src"], s["frames"], s["fps"] = a0, n, fps
    it.SetMarkInOut(a0, a0 + n - 1, "all")                 # Media Pool: Out inclusivo
    it.SetClipColor("Green")
    infos.append({"mediaPoolItem": it, "startFrame": a0, "endFrame": a0 + n})   # API: endFrame exclusivo

tl = mp.CreateTimelineFromClips(tl_name, infos)
if not tl:
    sys.exit("No pude crear el timeline de selects.")
project.SetCurrentTimeline(tl)
tw, th = (2160, 3840) if a.format == "vertical" else (3840, 2160)
tl.SetSetting("useCustomSettings", "1")
tl.SetSetting("timelineResolutionWidth", str(tw)); tl.SetSetting("timelineResolutionHeight", str(th))

for ti, s in zip(tl.GetItemListInTrack("video", 1), [s for s in sel if "src" in s]):
    if s.get("rotate"):
        ti.SetProperty("RotationAngle", -90.0 if s["rotate"] == "cw" else 90.0)
        z = max(tw, th) / min(tw, th)
        ti.SetProperty("ZoomX", z); ti.SetProperty("ZoomY", z)
jsave({"bin": f"{a.parent_bin}/{bin_name}", "timeline": tl_name, "format": a.format, "clips": sel}, f"{W}/selects.json")
durs = [ti.GetDuration() for ti in tl.GetItemListInTrack("video", 1)]
print(f"Bin '{bin_name}' · timeline '{tl_name}' · {len(durs)} tramos · {sum(durs) / (fps_seen or 25):.1f} s")
