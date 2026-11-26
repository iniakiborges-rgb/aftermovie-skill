"""Fase 3b: busca en el Media Pool destellos (film burn / light leak / flash) y SFX (riser, impacto, whooshes,
ambiente), mide dónde está el pico de cada uno y arma <work>/resources.json + sheets/destellos.jpg.
Prioriza los nombres "preferidos" de estilo.md si existen en el proyecto.

  python3 find_resources.py --project NOMBRE [--bins "VISUAL EFFECTS,recursos pol"]
"""
import argparse, os, re, subprocess
import numpy as np, cv2, librosa
from common import resolve, walk_pool, find_folder, work_dir, jsave, load_style, ffmpeg

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True)
ap.add_argument("--bins", default="", help="Bins donde buscar (coma). Vacío = todo el Media Pool")
a = ap.parse_args()
ST = load_style()
W = work_dir(a.project)
FF = ffmpeg()
_, project, mp = resolve()
root = mp.GetRootFolder()
roots = [find_folder(root, b.strip()) for b in a.bins.split(",") if b.strip()] or [root]
items = []
for r in roots:
    if r is None:
        continue
    for where, c in walk_pool(r, ""):
        pr = c.GetClipProperty() or {}
        items.append({"name": c.GetName(), "bin": where, "type": str(pr.get("Type", "")), "path": pr.get("File Path", ""),
                      "fps": float(str(pr.get("FPS") or 25).split()[0]), "frames": int(pr.get("Frames") or 0),
                      "res": pr.get("Resolution", "")})
K = ST["resource_keywords"]
rx = {k: re.compile(v, re.I) for k, v in K.items()}


def audio_profile(path):
    try:
        y, sr = librosa.load(path, sr=11025, mono=True, duration=40)
    except Exception:
        return None
    r = librosa.feature.rms(y=y, hop_length=256)[0]
    if r.max() <= 0:
        return None
    pk = float(np.argmax(r) * 256 / sr)
    return {"dur": len(y) / sr, "peak": pk, "peak_ratio": pk / max(len(y) / sr, 1e-3)}


def video_peak(it):
    dur = it["frames"] / it["fps"] if it["frames"] else 2
    raw = subprocess.run([FF, "-v", "error", "-t", "60", "-i", it["path"], "-vf", "fps=10,scale=32:18", "-pix_fmt", "gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    lum = np.frombuffer(raw, np.uint8).reshape(-1, 18 * 32).mean(axis=1) / 255 if raw else np.zeros(1)
    k = int(np.argmax(lum))
    return {"dur": dur, "peak": k / 10, "peak_luma": float(lum[k]), "mean_luma": float(lum.mean())}


def ok_audio(t):
    return t.startswith("Audio") or "audio" in t.lower()


res = {"flashes": [], "riser": [], "impact": [], "whoosh": [], "ambience": []}
for it in items:
    hay = f"{it['bin']}/{it['name']}"
    if not it["path"] or not os.path.exists(it["path"]):
        continue
    if it["type"].startswith(("Video", "Vídeo")) and rx["flash"].search(hay) and not rx["flash_exclude"].search(hay):
        vp = video_peak(it)
        if vp["peak_luma"] > 0.45 and vp["dur"] <= 60:
            res["flashes"].append({**it, **vp})
    elif ok_audio(it["type"]):
        for kind in ("riser", "whoosh", "impact", "ambience"):
            if rx[kind].search(hay):
                ap_ = audio_profile(it["path"])
                if not ap_:
                    break
                good = {"riser": ap_["peak_ratio"] > 0.8 and 2.5 <= ap_["dur"] <= 9,
                        "impact": ap_["peak"] < 0.25 and ap_["dur"] <= 8,
                        "whoosh": 0.15 <= ap_["peak"] <= 0.9 and ap_["dur"] <= 4.5,
                        "ambience": ap_["dur"] >= 15}[kind]
                if good:
                    res[kind].append({**it, **ap_})
                break

pref = ST.get("preferred_resources", {})
for kind, lst in res.items():
    order = pref.get(kind, [])
    def rank(x):  # coincidencia exacta o por fragmento del nombre (ej. "Cheering Crowd")
        for k, o in enumerate(order):
            if o.lower() == x["name"].lower() or o.lower() in x["name"].lower():
                return k
        return 99
    lst.sort(key=lambda x: (rank(x), x["name"]))
jsave(res, f"{W}/resources.json")
for k, v in res.items():
    print(f"{k}: {len(v)} → {[x['name'] for x in v[:6]]}")

# hoja de contacto de destellos (cuadro del pico) para validarlos a ojo
cells = []
for f in res["flashes"][:24]:
    png = subprocess.run([FF, "-v", "error", "-ss", f"{f['peak']:.2f}", "-i", f["path"], "-frames:v", "1", "-vf", "scale=240:-2",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    im = cv2.imdecode(np.frombuffer(png, np.uint8), 1) if png else None
    im = cv2.resize(im, (240, 135)) if im is not None else np.zeros((135, 240, 3), np.uint8)
    c = np.zeros((155, 240, 3), np.uint8); c[20:] = im
    cv2.putText(c, f"{f['name'][:26]} pk{f['peak']:.1f}", (3, 14), 0, 0.4, (255, 255, 255), 1); cells.append(c)
if cells:
    while len(cells) % 4:
        cells.append(np.zeros_like(cells[0]))
    os.makedirs(f"{W}/sheets", exist_ok=True)
    cv2.imwrite(f"{W}/sheets/destellos.jpg", np.vstack([np.hstack(cells[i:i + 4]) for i in range(0, len(cells), 4)]))
