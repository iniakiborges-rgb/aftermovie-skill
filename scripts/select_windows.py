"""Fase 1b: mejor tramo (2-4 s) de cada clip + hojas de contacto para revisión visual.
Escribe <work>/windows.json y <work>/sheets/sheet_NN.jpg (+ descartados.jpg).

  python3 select_windows.py --project NOMBRE
"""
import argparse, glob, os, subprocess
import numpy as np, cv2
from common import work_dir, jload, jsave, ffmpeg

SFPS = 5
ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True)
ap.add_argument("--min", type=float, default=2)
ap.add_argument("--max", type=float, default=4)
a = ap.parse_args()
W = work_dir(a.project)
FF = ffmpeg()
SHEETS = os.path.join(W, "sheets"); os.makedirs(SHEETS, exist_ok=True)
metrics = [jload(f) for f in sorted(glob.glob(f"{W}/metrics/*.json"))]

for vert in (True, False):
    grp = [m for m in metrics if (m["h"] > m["w"]) == vert]
    vals = [np.log1p(s["sharp"]) for m in grp for s in m["samples"]]
    if not vals:
        continue
    mu, sd = float(np.mean(vals)), float(np.std(vals) + 1e-6)
    for m in grp:
        for s in m["samples"]:
            s["zs"] = (np.log1p(s["sharp"]) - mu) / sd

flows = np.array([s["flow"] for m in metrics for s in m["samples"][1:]] or [1.0])
FLOW_HI, FLOW_PAN = float(np.percentile(flows, 85)), float(np.percentile(flows, 70))


def expo(s):
    l = s["luma"]
    return -(max(0, 0.12 - l) * 8 + max(0, l - 0.7) * 6 + s["hi"] * 4 + s["lo"] * 1.5)


def score(S):
    zs = np.array([s["zs"] for s in S]); ex = np.mean([expo(s) for s in S])
    fl = np.array([s["flow"] for s in S[1:]]); co = np.array([s["coher"] for s in S[1:]])
    if ((fl > FLOW_PAN) & (co > 0.65)).mean() > 0.2 or (fl > FLOW_HI * 1.6).any():
        return None                                   # barrido brusco
    lively = float(np.clip(np.median(fl * (1 - co)) / (FLOW_PAN + 1e-6), 0, 1)) * 0.3
    pen = float(np.clip((fl.mean() - FLOW_HI) / (FLOW_HI + 1e-6), 0, 2))
    return zs.mean() - 0.5 * zs.std() + 0.3 * zs.min() + ex + lively - pen


def steadiest(S, L=2):                               # rescate: tramo más quieto aunque haya movimiento
    k, best = int(L * SFPS), None
    for i in range(2, len(S) - k - 1):
        w = S[i:i + k]
        sc = np.mean([s["zs"] for s in w]) - 0.15 * np.mean([s["flow"] for s in w[1:]]) \
             - 0.3 * np.mean([s["flow"] * s["coher"] for s in w[1:]])
        if best is None or sc > best[0]:
            best = (sc, i / SFPS)
    return best


res = []
for m in metrics:
    S, best = m["samples"], None
    for L in range(int(a.max), int(a.min) - 1, -1):
        k = L * SFPS
        for i in range(SFPS // 2, len(S) - k - 1, 2):
            sc = score(S[i:i + k])
            if sc is not None and (best is None or sc + 0.08 * (L - 2) > best[0]):
                best = (sc + 0.08 * (L - 2), i / SFPS, L)
    r = {"name": m["name"], "path": m["path"], "vertical": m["h"] > m["w"], "dur": len(S) / SFPS}
    if best:
        r.update(score=round(float(best[0]), 3), **{"in": best[1], "len": best[2]})
    else:
        st = steadiest(S)
        r.update(score=None, rescue_in=st[1] if st else None)
    res.append(r)
res.sort(key=lambda r: -1e9 if r["score"] is None else -r["score"])
jsave({"flow_hi": FLOW_HI, "flow_pan": FLOW_PAN, "clips": res}, f"{W}/windows.json")


def grab(path, t, vert, h=300):
    png = subprocess.run([FF, "-v", "error", "-ss", f"{max(0, t):.2f}", "-i", path, "-frames:v", "1",
                          "-vf", f"scale=-2:{h}" if vert else f"scale={h}:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                         capture_output=True).stdout
    im = cv2.imdecode(np.frombuffer(png, np.uint8), 1) if png else None
    size = (169, 300) if vert else (300, 169)
    return cv2.resize(im, size) if im is not None else np.zeros((size[1], size[0], 3), np.uint8)


def cell(r, t0, L, label):
    fr = [grab(r["path"], t0 + q * L, r["vertical"]) for q in (0.1, 0.5, 0.9)]
    row = np.hstack(fr) if r["vertical"] else cv2.resize(
        np.vstack([np.hstack(fr[:2]), np.hstack([fr[2], np.zeros_like(fr[2])])]), (507, 300))
    c = np.zeros((330, 507, 3), np.uint8); c[30:] = row
    cv2.putText(c, label, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return c


def sheets(cells, prefix):
    for s in range(0, len(cells), 12):
        part = cells[s:s + 12]
        while len(part) % 3:
            part.append(np.zeros_like(part[0]))
        cv2.imwrite(f"{SHEETS}/{prefix}_{s // 12 + 1:02d}.jpg",
                    np.vstack([np.hstack(part[i:i + 3]) for i in range(0, len(part), 3)]), [cv2.IMWRITE_JPEG_QUALITY, 80])


short = lambda n: os.path.splitext(n)[0][-8:]
ok = [r for r in res if r["score"] is not None]
bad = [r for r in res if r["score"] is None and r.get("rescue_in") is not None]
sheets([cell(r, r["in"], r["len"], f"{short(r['name'])} s={r['score']:.2f} {r['in']:.1f}+{r['len']}") for r in ok], "sheet")
if bad:
    sheets([cell(r, r["rescue_in"], 2, f"{short(r['name'])} DESCARTE rescate {r['rescue_in']:.1f}+2") for r in bad], "descartados")
print(f"{len(ok)} candidatos · {len(bad)} descartados por barrido · hojas en {SHEETS}")
