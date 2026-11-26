"""Fase 1a: métricas por clip (5 muestras/s a 1/8 de resolución).
sharp = varianza del Laplaciano · luma/lo/hi = exposición · flow/coher = flujo óptico (coher≈1 → barrido).
Lee <work>/clips.json, escribe <work>/metrics/*.json (con caché).

  python3 analyze_clips.py --project NOMBRE [--workers 5]
"""
import argparse, os, subprocess
from multiprocessing import Pool
import numpy as np, cv2
from common import work_dir, jload, jsave, ffmpeg

SFPS = 5


def probe_size(path, FF):
    png = subprocess.run([FF, "-v", "error", "-i", path, "-frames:v", "1", "-vf", "scale=iw/8:ih/8",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
    return img.shape[1], img.shape[0]


def analyze(job):
    clip, out_dir, FF = job
    dst = os.path.join(out_dir, clip["name"] + ".json")
    if os.path.exists(dst):
        return clip["name"], "caché"
    try:
        w, h = probe_size(clip["path"], FF)
        proc = subprocess.Popen([FF, "-v", "error", "-threads", "2", "-i", clip["path"],
                                 "-vf", f"fps={SFPS},scale=iw/8:ih/8", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
                                stdout=subprocess.PIPE)
        rows, prev, i = [], None, 0
        while True:
            buf = proc.stdout.read(w * h)
            if len(buf) < w * h:
                break
            g = np.frombuffer(buf, np.uint8).reshape(h, w)
            r = {"t": i / SFPS, "sharp": float(cv2.Laplacian(g, cv2.CV_64F).var()), "luma": float(g.mean() / 255),
                 "lo": float((g < 10).mean()), "hi": float((g > 245).mean()), "flow": 0.0, "coher": 0.0}
            if prev is not None:
                fl = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                mag = np.linalg.norm(fl, axis=2)
                r["flow"] = float(mag.mean())
                r["coher"] = float(np.linalg.norm(fl.reshape(-1, 2).mean(axis=0)) / (r["flow"] + 1e-6))
            rows.append(r)
            prev, i = g, i + 1
        proc.wait()
        jsave({"name": clip["name"], "path": clip["path"], "w": w, "h": h, "samples": rows}, dst)
        return clip["name"], len(rows)
    except Exception as e:  # noqa
        return clip["name"], f"ERROR {e}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--workers", type=int, default=5)
    a = ap.parse_args()
    W = work_dir(a.project)
    out = os.path.join(W, "metrics"); os.makedirs(out, exist_ok=True)
    FF = ffmpeg()
    clips = jload(os.path.join(W, "clips.json"))
    with Pool(a.workers) as p:
        for n, (name, res) in enumerate(p.imap_unordered(analyze, [(c, out, FF) for c in clips]), 1):
            print(f"[{n}/{len(clips)}] {name}: {res}", flush=True)
