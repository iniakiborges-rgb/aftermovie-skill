"""Fase 3a: estructura del tema → tramo a usar (subida + hueco + drop), grilla de beats y unidad de corte.
Sirve para cualquier BPM/género: el drop es el beat con mayor salto de graves+energía (8 beats después vs. 8 antes).

  python3 analyze_song.py --project NOMBRE --song /ruta/tema.mp3 --max 35 [--drop 112.5] [--candidate 2]
Escribe <work>/song_plan.json. Imprime los 3 mejores candidatos a drop.
"""
import argparse
import numpy as np, librosa
from common import work_dir, jsave, load_style

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True)
ap.add_argument("--song", required=True)
ap.add_argument("--max", type=float, default=35)
ap.add_argument("--drop", type=float, help="Forzar el drop (segundos del tema)")
ap.add_argument("--candidate", type=int, default=1, help="Usar el 2º/3º candidato a drop")
ap.add_argument("--allow-intro", action="store_true", help="Permitir drops en la intro (primer 15%% / 20 s)")
a = ap.parse_args()
ST = load_style()
W = work_dir(a.project)

y, sr = librosa.load(a.song, sr=22050)
dur = len(y) / sr
tempo, bf = librosa.beat.beat_track(y=y, sr=sr)
tempo = float(np.atleast_1d(tempo)[0])
beats = librosa.frames_to_time(bf, sr=sr)
period = float(np.median(np.diff(beats)))

S = np.abs(librosa.stft(y, hop_length=512))
freqs = librosa.fft_frequencies(sr=sr)
t_fr = librosa.frames_to_time(np.arange(S.shape[1]), sr=sr, hop_length=512)
low = S[freqs < 150].mean(axis=0)
rms = librosa.feature.rms(S=S)[0]
def per_beat(x):
    out = []
    for i, b in enumerate(beats):
        e = beats[i + 1] if i + 1 < len(beats) else dur
        m = (t_fr >= b) & (t_fr < e)
        out.append(float(x[m].mean()) if m.any() else 0.0)
    return np.array(out)
lb, rb = per_beat(low), per_beat(rms)
# ataque de graves: primeros 150 ms de cada beat (distingue el golpe del drop de un "pickup" previo)
att = np.array([float(low[(t_fr >= b) & (t_fr < b + 0.15)].mean()) if ((t_fr >= b) & (t_fr < b + 0.15)).any() else 0.0
                for b in beats])
lb, rb = lb / (lb.max() + 1e-9), rb / (rb.max() + 1e-9)

cands = []
for i in range(8, len(beats) - 16):
    if beats[i] < (10 if a.allow_intro else max(20, 0.15 * dur)):
        continue
    jump = (lb[i:i + 8].mean() - lb[i - 8:i].mean()) + 0.5 * (rb[i:i + 8].mean() - rb[i - 8:i].mean())
    cands.append((jump, i))
cands.sort(reverse=True)
def refine(i):                                         # el beat exacto donde salta el bajo
    rng = range(max(1, i - 1), min(len(lb) - 1, i + 3))
    return max(rng, key=lambda k: att[k] - att[k - 1])
cands = [(j, refine(i)) for j, i in cands]
picked = []
for j, i in cands:                                      # candidatos separados al menos 8 s
    if all(abs(beats[i] - beats[k]) > 8 for _, k in picked):
        picked.append((j, i))
    if len(picked) == 3:
        break
print(f"Tempo {tempo:.1f} BPM · beat {period:.3f} s · {dur:.1f} s")
for n, (j, i) in enumerate(picked, 1):
    print(f"  candidato {n}: drop en {beats[i]:.2f} s (salto {j:.2f})")
di = int(np.argmin(np.abs(beats - a.drop))) if a.drop else picked[a.candidate - 1][1]

# unidad de corte: múltiplo de beat más cercano a la duración base del estilo
base = ST["shot_unit_seconds"]
unit = min([0.5, 1, 2, 4], key=lambda u: abs(u * period - base))
gap_beats = min([0.5, 1, 2], key=lambda g: abs(g * period - ST["gap_seconds"]))
build_beats = int(round(ST["build_seconds"] / period))
build_beats = max(4, min(build_beats, int(a.max * 0.3 / period)))
i0 = max(0, di - build_beats)
song_in, drop = float(beats[i0]), float(beats[di])
gap_start = drop - gap_beats * period
budget_end = song_in + a.max
# fin: múltiplo de frase (8 beats) desde el drop si no pierde más de 3 s; si no, último beat dentro del límite
ends = [b for b in beats if drop < b <= budget_end]
phr = [beats[k] for k in range(di, len(beats), 8) if beats[k] <= budget_end]
song_out = float(phr[-1]) if phr and ends and ends[-1] - phr[-1] <= 3 else float(ends[-1] if ends else min(dur, budget_end))
grid = [float(b - song_in) for b in beats if song_in - 1e-3 <= b <= song_out + 1e-3]
plan = {"song": a.song, "tempo": tempo, "beat": period, "unit_beats": unit, "gap_beats": gap_beats,
        "song_in": song_in, "gap_start": gap_start, "drop": drop, "song_out": song_out,
        "length": song_out - song_in, "drop_tl": drop - song_in, "gap_tl": gap_start - song_in,
        "beats_tl": grid, "build_beats": di - i0}
jsave(plan, f"{W}/song_plan.json")
print(f"Tramo {song_in:.2f}→{song_out:.2f} s ({plan['length']:.1f} s) · drop en {plan['drop_tl']:.2f} s del timeline"
      f" · hueco {gap_beats} beat · unidad {unit} beat ({unit * period:.2f} s)")
