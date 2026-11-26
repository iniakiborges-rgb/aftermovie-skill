"""Fase 2 (opcional): análisis de un reel de referencia (cortes, beat, movimiento, destellos, SFX).
Escribe <work>/reel/reel_analysis.json y reel_shots.jpg (hoja de contacto por toma).

  python3 analyze_reel.py --project NOMBRE --reel /ruta/reel.mp4
"""
import argparse, json, os, re, subprocess
import numpy as np, cv2, librosa
from common import work_dir, ffmpeg

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True)
ap.add_argument("--reel", required=True)
a = ap.parse_args()
FF = ffmpeg()
SRC = os.path.expanduser(a.reel)
OUT = os.path.join(work_dir(a.project), "reel")
os.makedirs(OUT, exist_ok=True)
_err = subprocess.run([FF, "-hide_banner", "-i", SRC], capture_output=True, text=True).stderr
_m = re.search(r"(\d+(?:\.\d+)?) fps", _err)
FPS = float(_m.group(1)) if _m else 25.0
_r = re.search(r"Video:.*?(\d{3,5})x(\d{3,5})", _err)
vw, vh = (int(_r.group(1)), int(_r.group(2))) if _r else (1080, 1920)
W, H = (180, 320) if vh >= vw else (320, 180)

# --- frames a baja resolución, todos los cuadros ---
raw = subprocess.run([FF, "-v", "error", "-i", SRC, "-vf", f"scale={W}:{H}", "-pix_fmt", "bgr24",
                      "-f", "rawvideo", "-"], capture_output=True).stdout
frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
n = len(frames)
gray = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]

# --- cortes: diferencia de histograma HSV + diferencia de píxeles ---
def hist(f):
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1, 2], None, [16, 8, 8], [0, 180, 0, 256, 0, 256])
    return cv2.normalize(h, h).flatten()
hs = [hist(f) for f in frames]
d_hist = np.array([0] + [cv2.compareHist(hs[i - 1], hs[i], cv2.HISTCMP_BHATTACHARYYA) for i in range(1, n)])
d_pix = np.array([0] + [np.abs(gray[i].astype(int) - gray[i - 1]).mean() / 255 for i in range(1, n)])
score = d_hist + d_pix
med = np.convolve(score, np.ones(9) / 9, mode="same")
cuts = [i for i in range(1, n) if score[i] > 0.28 and score[i] > 2.5 * med[i] and score[i] == score[max(1, i - 3):i + 4].max()]

# --- flujo óptico por cuadro: traslación, zoom (divergencia), rotación ---
ys, xs = np.mgrid[0:H, 0:W]
cx, cy = xs - W / 2, ys - H / 2
r2 = cx ** 2 + cy ** 2 + 1e-6
motion = [dict(tx=0, ty=0, zoom=0, rot=0, mag=0)]
for i in range(1, n):
    fl = cv2.calcOpticalFlowFarneback(gray[i - 1], gray[i], None, 0.5, 3, 15, 3, 5, 1.2, 0)
    fx, fy = fl[..., 0], fl[..., 1]
    tx, ty = float(np.median(fx)), float(np.median(fy))
    zoom = float(np.mean(((fx - tx) * cx + (fy - ty) * cy) / r2))   # >0 = acercándose
    rot = float(np.mean(((fy - ty) * cx - (fx - tx) * cy) / r2))
    motion.append(dict(tx=tx, ty=ty, zoom=zoom, rot=rot, mag=float(np.hypot(fx, fy).mean())))

# --- audio: beats, onsets y eventos tipo SFX ---
wav = os.path.join(OUT, "reel.wav")
subprocess.run([FF, "-v", "error", "-y", "-i", SRC, "-ac", "1", "-ar", "22050", wav])
y, sr = librosa.load(wav, sr=22050)
tempo, bf = librosa.beat.beat_track(y=y, sr=sr)
beats = librosa.frames_to_time(bf, sr=sr)
tempo = float(np.atleast_1d(tempo)[0])
onset_env = librosa.onset.onset_strength(y=y, sr=sr)
onsets = librosa.frames_to_time(librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr), sr=sr)
S = np.abs(librosa.stft(y))
flat = librosa.feature.spectral_flatness(S=S)[0]
cent = librosa.feature.spectral_centroid(S=S, sr=sr)[0]
rms = librosa.feature.rms(S=S)[0]
t_feat = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
# barridos de ruido (whoosh/riser): planitud y brillo altos respecto a su entorno
noisy = (flat > np.percentile(flat, 90)) & (cent > np.percentile(cent, 75))
events, i = [], 0
while i < len(noisy):
    if noisy[i]:
        j = i
        while j < len(noisy) and noisy[j]:
            j += 1
        if t_feat[j - 1] - t_feat[i] >= 0.08:
            seg = rms[i:j]
            events.append({"start": round(float(t_feat[i]), 2), "end": round(float(t_feat[j - 1]), 2),
                           "rising": bool(seg[-1] > seg[0] * 1.3), "peak_rms": round(float(seg.max()), 4)})
        i = j
    else:
        i += 1
# golpes fuertes (impactos): picos de onset muy por encima del resto
strong = librosa.frames_to_time(np.where(onset_env > np.percentile(onset_env, 97))[0], sr=sr)

beat_period = 60 / tempo
shots = []
bounds = [0] + cuts + [n]
for a, b in zip(bounds, bounds[1:]):
    m = motion[a + 1:b] or [motion[0]]
    shots.append({
        "start": round(a / FPS, 2), "end": round(b / FPS, 2), "frames": b - a,
        "beats": round((b - a) / FPS / beat_period, 2),
        "zoom_sum": round(sum(x["zoom"] for x in m), 3),
        "pan_x": round(sum(x["tx"] for x in m), 1), "pan_y": round(sum(x["ty"] for x in m), 1),
        "rot_sum": round(sum(x["rot"] for x in m), 3),
        "mag_mean": round(float(np.mean([x["mag"] for x in m])), 2),
    })
cut_t = [c / FPS for c in cuts]
def near_beat(t):
    k = int(np.argmin(np.abs(beats - t)))
    return round(float(t - beats[k]), 3)
luma = np.array([g.mean() / 255 for g in gray])
flashes = [round(i / FPS, 2) for i in range(1, n - 1) if luma[i] > 0.6 and luma[i] > luma[max(0, i - 6):i].mean() + 0.2]
res = {"flash_frames": flashes, "fps": FPS, "src": SRC, "frames": n, "tempo": tempo, "beats": [round(float(b), 3) for b in beats],
       "cuts": [round(c, 3) for c in cut_t], "cut_offset_to_beat": [near_beat(t) for t in cut_t],
       "shots": shots, "noise_events": events, "strong_hits": [round(float(t), 2) for t in strong],
       "cut_score": [round(float(s), 3) for s in score]}
json.dump(res, open(os.path.join(OUT, "reel_analysis.json"), "w"), indent=1)

# hoja de contacto: primer, medio y último cuadro de cada toma
cells = []
for k, s in enumerate(shots):
    a, b = int(s["start"] * FPS), int(s["end"] * FPS) - 1
    trip = [frames[a], frames[(a + b) // 2], frames[b]]
    row = np.hstack([cv2.resize(f, (120, 213) if H > W else (213, 120)) for f in trip])
    c = np.zeros((row.shape[0] + 23, row.shape[1], 3), np.uint8); c[23:] = row
    cv2.putText(c, f"#{k+1} {s['start']:.2f}s {s['frames']}f {s['beats']}b", (3, 16), 0, 0.45, (255, 255, 255), 1)
    cells.append(c)
while len(cells) % 5:
    cells.append(np.zeros_like(cells[0]))
cv2.imwrite(os.path.join(OUT, "reel_shots.jpg"), np.vstack([np.hstack(cells[i:i + 5]) for i in range(0, len(cells), 5)]))
print(f"tempo {tempo:.1f} · {len(cuts)} cortes · {len(shots)} tomas · {len(events)} eventos de ruido")
