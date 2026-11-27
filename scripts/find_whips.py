"""Barridos propios del editor: busca en cada clip los picos de movimiento coherente (paneo rápido = barrido).
Escribe <work>/whips.json: {"<clip>": [{"t": 6.56, "score": 3.1}, ...]} (t = segundos del clip, ordenados por tiempo).
Los barridos NO se descartan: build_montage (modo fiesta) los usa como transición entre planos del mismo tipo,
con el punto más rápido del barrido justo en el corte/beat.

  python3 find_whips.py --project NOMBRE --clips ALEJO_back1312.MP4,ALEJO_back1328.MP4 [--min-score 3]
  (sin --clips: los clips de party_plan.json marcados con "whip")
Rápido: decodifica a 48 px de ancho y 12,5 fps, 8 clips en paralelo.
"""
import argparse, os, subprocess
from concurrent.futures import ThreadPoolExecutor
import numpy as np, cv2
from common import work_dir, jload, jsave, ffmpeg

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True)
ap.add_argument("--clips", help="Nombres separados por coma (default: los de party_plan.json con 'whip')")
ap.add_argument("--min-score", type=float, default=3.0)
ap.add_argument("--workers", type=int, default=8)
a = ap.parse_args()
W = work_dir(a.project)
CL = {c["name"]: c for c in jload(f"{W}/clips.json")}
if a.clips:
    names = [x.strip() for x in a.clips.split(",") if x.strip()]
else:
    pp = jload(f"{W}/party_plan.json")
    names = sorted({s["clip"] for s in pp["shots"] if s.get("whip") is True})
FF = ffmpeg()
SFPS, WD, HT = 12.5, 48, 86


def run(name):
    c = CL[name]
    raw = subprocess.run([FF, "-v", "error", "-threads", "2", "-i", c["path"], "-vf", f"fps={SFPS},scale={WD}:{HT}",
                          "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, HT, WD)
    rows = []
    for k in range(1, len(fr)):
        fl = cv2.calcOpticalFlowFarneback(fr[k - 1], fr[k], None, 0.5, 2, 9, 2, 5, 1.1, 0)
        m = float(np.linalg.norm(fl, axis=2).mean())
        coh = float(np.linalg.norm(fl.reshape(-1, 2).mean(0)) / (m + 1e-6))
        rows.append((k / SFPS, m * (coh > 0.6)))
    peaks = []
    for j in np.argsort([-s for _, s in rows]):
        t, s = rows[j]
        if s < a.min_score:
            break
        if all(abs(t - p["t"]) > 1 for p in peaks):
            peaks.append({"t": round(t, 2), "score": round(s, 1)})
        if len(peaks) >= 4:
            break
    return name, sorted(peaks, key=lambda p: p["t"])


out = jload(f"{W}/whips.json") if os.path.exists(f"{W}/whips.json") else {}
with ThreadPoolExecutor(a.workers) as ex:
    for name, peaks in ex.map(run, names):
        out[name] = peaks
        print(f"  {name}: " + (", ".join(f"{p['t']:.2f}s ({p['score']})" for p in peaks) or "sin barrido claro"))
jsave(out, f"{W}/whips.json")
print(f"→ {W}/whips.json")
