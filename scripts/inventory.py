"""Inventario de clips de video: desde un bin del Media Pool (--bin) o una carpeta (--folder).
Solo lee. Escribe <work>/clips.json.

  python3 inventory.py --project NOMBRE --bin "Master"            # clips directos de ese bin
  python3 inventory.py --project NOMBRE --bin "Master/fiesta" --recursive
  python3 inventory.py --project NOMBRE --folder "/Volumes/SD/CLIP"
"""
import argparse, os, re, subprocess
from common import resolve, walk_pool, find_folder, work_dir, jsave, ffmpeg, VIDEO_EXT

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True, help="Nombre corto del proyecto (carpeta de trabajo)")
g = ap.add_mutually_exclusive_group(required=True)
g.add_argument("--bin")
g.add_argument("--folder")
ap.add_argument("--recursive", action="store_true")
a = ap.parse_args()
W = work_dir(a.project)
FF = ffmpeg()

clips = []
if a.bin:
    _, p, mp = resolve()
    f = find_folder(mp.GetRootFolder(), a.bin)
    if f is None:
        raise SystemExit(f"No existe el bin '{a.bin}'")
    src = walk_pool(f) if a.recursive else ((f.GetName(), c) for c in f.GetClipList() or [])
    for where, c in src:
        pr = c.GetClipProperty() or {}
        t = str(pr.get("Type", ""))
        if not (t.startswith("Video") or t.startswith("Vídeo")) or not pr.get("File Path"):
            continue
        clips.append({"name": c.GetName(), "path": pr["File Path"], "bin": where, "id": c.GetUniqueId(),
                      "fps": float(str(pr.get("FPS", 25)).split()[0]), "frames": int(pr.get("Frames") or 0),
                      "res": pr.get("Resolution")})
else:
    for root, _, files in os.walk(a.folder):
        for fn in sorted(files):
            if not fn.startswith(".") and os.path.splitext(fn)[1].lower() in VIDEO_EXT:
                clips.append({"name": fn, "path": os.path.join(root, fn), "bin": None})
        if not a.recursive:
            break

# fecha de creación de cámara (para el orden cronológico)
for c in clips:
    err = subprocess.run([FF, "-hide_banner", "-i", c["path"]], capture_output=True, text=True).stderr
    m = re.search(r"creation_time\s*:\s*(\S+)", err)
    c["created"] = m.group(1) if m else ""
    d = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", err)
    c["duration"] = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)) if d else 0
jsave(clips, os.path.join(W, "clips.json"))
print(f"{len(clips)} clips · {sum(c['duration'] for c in clips) / 60:.1f} min → {W}/clips.json")
