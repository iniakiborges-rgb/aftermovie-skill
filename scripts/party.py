"""Modo fiesta (bandas + DJs) de build_montage.py: estructura por bloques de estilo.md ("party_block_order").
Se activa solo cuando existe <work>/party_plan.json (o con --party). Lo escribe Claude después de mirar las hojas:

{
  "song": {"timeline": "Timeline 1"},          # tramo del tema que dejó el editor (A1 de ese timeline), tal cual
          # o {"path": "/ruta/tema.mp3", "in": 53.52, "len": 23.8}   (segundos del tema)
  "flashes": ["16mm Film Burn (4).mov", ...],   # opcional: un destello por entrada de bloque (desde el 2º), en orden
  "shots": [
    {"block": "Apertura DJs", "clip": "C0012.MP4", "in": 27.4, "beats": 1},
    {"block": "Bandas", "clip": "C0020.MP4", "whip": true, "beats": 5},     # termina en su barrido (whips.json)
    {"block": "Bandas", "clip": "C0021.MP4", "whip": 2.56, "beats": 4},     # ...o el segundo exacto del pico del barrido
    {"block": "DJs", "clip": "C0030.MP4", "in": 26.8, "beats": 3, "punch_in": true},  # general → detalle con punch-in
    ...                                              # la última toma llega hasta el final del tema
  ]
}
- "beats": cuántos beats dura la toma. Los cortes caen en la grilla de beats del tramo: [0, beat1, beat2, ..., fin].
  Si falta, se usa party_default_beats[bloque] de estilo.md.
- "whip": la toma SALE con el barrido: termina en el punto más rápido, justo en el corte. Solo hacia una toma del mismo
  bloque (banda↔banda, DJ↔DJ, cabina↔cabina); si no, avisa. Lleva whoosh con el pico en el corte.
- "punch_in": parte la toma; el último beat sigue el mismo clip con zoom party_punch_in.zoom (general → detalle).
- "type": opcional (default: el tipo del bloque).
"""
import os, sys
import numpy as np
from common import walk_pool, jload, jsave, timeline_names, free_name, get_timeline

BLOCK_TYPE = {"Apertura DJs": "DJ", "Bandas": "banda", "DJs": "DJ", "Cabina": "cabina", "Público": "público"}
BLOCK_COLOR = {"Apertura DJs": "Pink", "Bandas": "Yellow", "DJs": "Purple", "Cabina": "Cyan", "Público": "Green"}


def song_segment(PP, W, project, FPS):
    """Tramo del tema elegido por el editor + grilla de beats (con caché en song_party.json)."""
    sp = PP["song"]
    cache = f"{W}/song_party.json"
    c = jload(cache) if os.path.exists(cache) else None
    if project is None:                                      # sin Resolve (dry-run): tramo desde la caché
        if c and c.get("timeline") == sp.get("timeline", c.get("timeline")):
            return c
        sys.exit("Sin Resolve y sin caché del tramo (song_party.json): abrí Resolve una vez.")
    if "timeline" in sp:
        t = get_timeline(project, sp["timeline"])
        if t is None:
            sys.exit(f"No encuentro el timeline del tema '{sp['timeline']}'.")
        its = t.GetItemListInTrack("audio", 1) or []
        if not its:
            sys.exit(f"'{sp['timeline']}' no tiene audio en A1.")
        it = its[0]
        seg = {"path": it.GetMediaPoolItem().GetClipProperty("File Path"), "in_f": it.GetLeftOffset(),
               "len_f": it.GetDuration(), "timeline": sp["timeline"], "fps": FPS,
               "res": [t.GetSetting("timelineResolutionWidth"), t.GetSetting("timelineResolutionHeight")]}
    else:
        seg = {"path": sp["path"], "in_f": int(round(sp["in"] * FPS)), "len_f": int(round(sp["len"] * FPS)), "res": None, "fps": FPS}
    if c and (c["path"], c["in_f"], c["len_f"]) == (seg["path"], seg["in_f"], seg["len_f"]) and "beats" in c:
        return {**c, **seg}
    import librosa
    y, sr = librosa.load(seg["path"], sr=22050, offset=seg["in_f"] / FPS, duration=seg["len_f"] / FPS)
    tempo, b = librosa.beat.beat_track(y=y, sr=sr, units="time")
    on = librosa.onset.onset_strength(y=y, sr=sr); ot = librosa.times_like(on, sr=sr)
    seg["tempo"] = float(np.atleast_1d(tempo)[0])
    seg["beats"] = [float(x) for x in b]
    seg["strength"] = [float(on[np.argmin(abs(ot - x))]) for x in b]
    jsave(seg, cache)
    return seg


def run(a, ST, W, r, project, mp, RS):
    PP = jload(f"{W}/party_plan.json")
    if project is not None:
        FPS = float(str(project.GetSetting("timelineFrameRate")).split()[0])
    else:
        sc = f"{W}/song_party.json"
        FPS = float(jload(sc)["fps"]) if os.path.exists(sc) else 25.0
    f = lambda t: int(round(t * FPS))
    CL = {c["name"]: c for c in jload(f"{W}/clips.json")}
    WH = jload(f"{W}/whips.json") if os.path.exists(f"{W}/whips.json") else {}
    order = ST.get("party_block_order", list(BLOCK_TYPE))
    dbeats = ST.get("party_default_beats", {})
    PI = ST.get("party_punch_in", {"zoom": 1.5, "beats": 1})
    FX = ST.get("party_effect_markers", {})
    seg = song_segment(PP, W, project, FPS)
    TOTAL = seg["len_f"]                                     # V1 dura exactamente el tramo elegido
    tail = f(ST.get("audio_tail_seconds", 0))
    grid = [0.0] + [b for b in seg["beats"] if 0.1 < b < TOTAL / FPS - 0.1] + [TOTAL / FPS]
    warn = []

    # ---------- 1) tomas sobre la grilla ----------
    shots, pos = [], 0
    S = PP["shots"]
    for i, s in enumerate(S):
        blk = s["block"]
        last = i == len(S) - 1
        nb = s.get("beats") or dbeats.get(blk, 2)
        end = len(grid) - 1 if last else min(pos + nb, len(grid) - 1)
        if end <= pos:
            warn.append(f"no hay más beats para {s['clip']} (se corta el plan acá)"); break
        rec, rec_end = f(grid[pos]), (TOTAL if end == len(grid) - 1 else f(grid[end]))
        c = CL.get(s["clip"])
        if c is None:
            sys.exit(f"{s['clip']} no está en clips.json")
        cf = float(c["fps"]); L = rec_end - rec; n_src = int(round(L * cf / FPS))
        whip_t = None
        if s.get("whip") is True:
            fits = [p["t"] for p in WH.get(s["clip"], []) if p["t"] * cf >= n_src]
            if fits:
                whip_t = fits[0]
            else:
                warn.append(f"{s['clip']}: sin barrido detectado que entre (corré find_whips.py); uso 'in'")
        elif isinstance(s.get("whip"), (int, float)) and not isinstance(s.get("whip"), bool):
            whip_t = float(s["whip"])
        src = int(round(whip_t * cf)) - n_src if whip_t is not None else int(round(s.get("in", 0) * cf))
        if src < 0 or src + n_src > c["frames"]:
            warn.append(f"{s['clip']}: tramo fuera del clip ({src}..{src + n_src} de {c['frames']})"); src = max(0, min(src, c["frames"] - n_src))
        base = {"kind": blk, "type": s.get("type", BLOCK_TYPE.get(blk, blk)), "name": s["clip"], "path": c["path"],
                "clip_fps": cf, "rotate": s.get("rotate"), "whip_out": whip_t is not None, "marker": None, "note": s.get("note")}
        pb = PI.get("beats", 1)
        if s.get("punch_in") and end - pos > pb:
            cut = f(grid[end - pb]); L1 = cut - rec; n1 = int(round(L1 * cf / FPS))
            shots.append({**base, "rec": rec, "len": L1, "src": src, "zoom_applied": 1.0, "whip_out": False})
            shots.append({**base, "rec": cut, "len": rec_end - cut, "src": src + n1, "zoom_applied": PI["zoom"],
                          "marker": ("punch-in", f"punch-in {PI['zoom']} · ajustar encuadre (tilt/pan) al detalle")})
        else:
            shots.append({**base, "rec": rec, "len": L, "src": src, "zoom_applied": 1.0})
        pos = end
    shots[-1]["marker"] = shots[-1]["marker"] or ("zoom out", "zoom out · cierre")

    # validaciones
    seen = [s["block"] for s in S]
    blocks_in = list(dict.fromkeys(seen))
    if [b for b in blocks_in if b in order] != [b for b in order if b in blocks_in]:
        warn.append(f"orden de bloques {blocks_in} ≠ estándar {order}")
    for x, y in zip(shots, shots[1:]):
        if x["whip_out"] and x["kind"] != y["kind"]:
            warn.append(f"barrido de {x['name']} entra a otro bloque ({x['kind']}→{y['kind']}): usarlo solo entre planos del mismo tipo")
    v1_end = shots[-1]["rec"] + shots[-1]["len"]
    if v1_end != TOTAL:
        warn.append(f"V1 termina en {v1_end} y el tramo dura {TOTAL}")

    # ---------- 2) destellos, SFX y marcadores (plan) ----------
    starts = []                                              # (frame, bloque) de cada entrada de bloque
    for s in shots:
        if not starts or starts[-1][1] != s["kind"]:
            starts.append((s["rec"], s["kind"]))
    FL = ST["flashes"]
    fl_by = {x["name"]: x for x in RS.get("flashes", [])}
    fl_names = PP.get("flashes") or [x["name"] for x in RS.get("flashes", [])]
    flashes = []
    entries = [(cut, blk) for cut, blk in starts[1:] if blk not in FL.get("party_no_flash_blocks", ["Cabina"])]
    for k, (cut, blk) in enumerate(entries):
        if not fl_names:
            break
        x = fl_by.get(fl_names[k % len(fl_names)])
        if not x:
            warn.append(f"destello {fl_names[k % len(fl_names)]} no está en resources.json"); continue
        big = k == len(entries) - 1                          # entrada al último bloque (público) = el "drop"
        Lf = f(FL.get("party_big_len", 1.0) if big else FL["len"])
        s0 = max(0, int(x["peak"] * x["fps"]) - Lf // 2)
        flashes.append({"name": x["name"], "path": x["path"], "rec": cut - Lf // 2, "len": Lf, "src": s0,
                        "mode": FL.get("party_composite", "Add"), "fit": FL.get("party_fit", "rotate")})
    audio = []
    wh = RS.get("whoosh", [])
    for k, s in enumerate([s for s in shots if s["whip_out"]]):
        if not wh:
            break
        w = wh[k % len(wh)]; cut = s["rec"] + s["len"]
        pk = f(w["peak"]); s0 = max(0, pk - f(0.6))
        audio.append({"track": "Whooshes", "ti": 2, "name": w["name"], "path": w["path"], "rec": cut - (pk - s0), "src": s0, "len": pk + f(0.5) - s0})
    if RS.get("impact") and len(starts) > 1:
        w = RS["impact"][0]; cut = starts[-1][0]; pk = f(w["peak"]); s0 = max(0, pk - 2)
        audio.append({"track": "Impacto", "ti": 4, "name": w["name"], "path": w["path"], "rec": cut - (pk - s0), "src": s0, "len": pk + f(1.5) - s0})
    if ST.get("ambience", {}).get("enabled") and RS.get("ambience"):
        w = RS["ambience"][0]; s0 = f(ST["ambience"].get("in_seconds", 5.0))
        audio.append({"track": "Ambiente", "ti": 5, "name": w["name"], "path": w["path"], "rec": 0, "src": s0, "len": TOTAL})

    markers = []
    for k, (a_, blk) in enumerate(starts):
        b_ = starts[k + 1][0] if k + 1 < len(starts) else TOTAL
        markers.append((a_, BLOCK_COLOR.get(blk, "Sand"), blk, f"Bloque {blk}", b_ - a_))
    for blk, fx in FX.items():                                # efectos que la API no pone (p. ej. Brightness Flash)
        inner = [s for s in shots if s["kind"] == blk][1:]
        for s in inner:
            markers.append((s["rec"], "Fuchsia", fx, f"{fx}: poner a mano, centrado en el corte (~4 cuadros antes, 1–3 después)", 1))
    for s in shots:
        if s["marker"]:
            markers.append((s["rec"], "Blue", s["marker"][0], s["marker"][1], 1))
    vol = " · ".join(f"{k} {v}" for k, v in ST.get("volumes_db", {}).items())
    markers.append((1, "Red", "Mezcla (a mano)", f"Volúmenes: {vol}", 1))
    fo = f(ST.get("fade_out_seconds", 0))
    if fo:
        markers.append((TOTAL + tail - fo, "Red", "Fade out", f"Fade out de {ST['fade_out_seconds']} s (Tema y Ambiente) hasta el final del audio", fo))
    used = set(); mk = []
    for m in sorted(markers, key=lambda m: m[0]):            # Resolve no admite dos marcadores en el mismo cuadro
        fr = m[0]
        while fr in used:
            fr += 1
        used.add(fr); mk.append((fr,) + m[1:])

    # ---------- 3) mostrar ----------
    print(f"Tema: {os.path.basename(seg['path'])} · tramo {seg['in_f']}+{TOTAL} cuadros ({TOTAL / FPS:.2f} s) · "
          f"{seg['tempo']:.0f} BPM · cola de audio {tail} cuadros")
    for s in shots:
        extra = (" barrido→" if s["whip_out"] else "") + (f" zoom {s['zoom_applied']}" if s["zoom_applied"] != 1 else "")
        print(f"  {s['rec'] / FPS:6.2f}s {s['rec']:4d}-{s['rec'] + s['len']:4d} {s['len']:3d}f {s['kind']:13} {s['name']:20} src {s['src']}{extra}")
    print("  destellos: " + ", ".join(f"{x['name']} @{x['rec']} ({x['len']}f, {x['mode']}, {x['fit']})" for x in flashes))
    print("  audio: " + ", ".join(f"{x['track']} {x['name']} @{x['rec']}" for x in audio))
    print("  marcadores: " + ", ".join(f"{m[0]} {m[1]} {m[2]}" for m in mk))
    for w_ in warn:
        print("  ! " + w_)

    plan = {"mode": "party", "timeline": None, "fps": FPS, "song": {k: seg[k] for k in ("path", "in_f", "len_f", "tempo")},
            "audio_tail": tail, "shots": [{k: v for k, v in s.items() if k != "path"} for s in shots],
            "flashes": [{k: v for k, v in x.items() if k != "path"} for x in flashes],
            "audio": [{k: v for k, v in x.items() if k not in ("path", "ti")} for x in audio],
            "markers": mk, "warnings": warn}
    if a.dry_run:
        plan["timeline"] = a.name
        jsave(plan, f"{W}/montage_plan_dryrun.json")
        print(f"{len(shots)} tomas · {TOTAL / FPS:.2f} s (dry-run: no se creó nada) → {W}/montage_plan_dryrun.json")
        return

    # ---------- 4) Resolve ----------
    items = {}
    for _, c in walk_pool(mp.GetRootFolder()):
        p_ = c.GetClipProperty("File Path")
        if p_:
            items.setdefault(p_, c)
    name = free_name(timeline_names(project), a.name)
    mp.SetCurrentFolder(mp.GetRootFolder())
    tl = mp.CreateEmptyTimeline(name); project.SetCurrentTimeline(tl)
    if a.format:
        tw, th = (2160, 3840) if a.format == "vertical" else (3840, 2160)
    elif seg.get("res"):
        tw, th = (int(x) for x in seg["res"])
    else:
        tw, th = 2160, 3840
    tl.SetSetting("useCustomSettings", "1")
    tl.SetSetting("timelineResolutionWidth", str(tw)); tl.SetSetting("timelineResolutionHeight", str(th))
    st = tl.GetStartFrame()
    while tl.GetTrackCount("video") < 2:
        tl.AddTrack("video")
    while tl.GetTrackCount("audio") < 5:
        tl.AddTrack("audio", "stereo")
    for i, n_ in enumerate(["Tomas", "Destellos"], 1):
        tl.SetTrackName("video", i, n_)
    for i, n_ in enumerate(["Tema", "Whooshes", "Riser", "Impacto", "Ambiente"], 1):
        tl.SetTrackName("audio", i, n_)

    def put(path, s0, n, media, track, rec):
        it = items.get(path)
        if it is None:
            print(f"  ! {os.path.basename(path)} no está en el Media Pool"); return None
        res = mp.AppendToTimeline([{"mediaPoolItem": it, "startFrame": int(s0), "endFrame": int(s0 + n),
                                    "mediaType": media, "trackIndex": track, "recordFrame": st + int(rec)}])
        if not res:
            print(f"  ! no entró {os.path.basename(path)} @{rec}")
        return res[0] if res else None

    COMP = {"Add": getattr(r, "COMPOSITE_ADD", 1), "Screen": getattr(r, "COMPOSITE_SCREEN", 5),
            "LinearDodge": getattr(r, "COMPOSITE_LINEAR_DODGE", 19)}
    for s in shots:
        t_ = put(CL[s["name"]]["path"], s["src"], int(round(s["len"] * s["clip_fps"] / FPS)), 1, 1, s["rec"])
        if t_ is None:
            continue
        z = s["zoom_applied"]
        if s["rotate"]:
            t_.SetProperty("RotationAngle", -90.0 if s["rotate"] == "cw" else 90.0); z = max(z, max(tw, th) / min(tw, th))
        if z != 1.0:
            t_.SetProperty("ZoomX", z); t_.SetProperty("ZoomY", z)
    put(seg["path"], seg["in_f"], TOTAL + tail, 2, 1, 0)
    for x in flashes:
        t_ = put(x["path"], x["src"], x["len"], 1, 2, x["rec"])
        if t_:
            t_.SetProperty("CompositeMode", COMP.get(x["mode"], COMP["Add"]))
            z = FL.get("party_rotated_zoom", 2.71) if x["fit"] == "rotate" else FL["zoom"]
            if x["fit"] == "rotate" and th > tw:
                t_.SetProperty("RotationAngle", -90.0)
            t_.SetProperty("ZoomX", z); t_.SetProperty("ZoomY", z)
    for x in audio:
        put(x["path"], x["src"], x["len"], 2, x["ti"], x["rec"])
    for m in mk:
        tl.AddMarker(m[0], m[1], m[2], m[3], max(1, m[4]))
    plan["timeline"] = name
    plan["resolution"] = [tw, th]
    jsave(plan, f"{W}/montage_plan.json")
    v1 = tl.GetItemListInTrack("video", 1)
    print(f"Timeline '{name}': {len(v1)} tomas · {len(flashes)} destellos · {len(audio)} SFX → {W}/montage_plan.json")
    print("A mano (la API no llega; quedaron como marcadores): volúmenes, fade out, " + ", ".join(sorted(set(FX.values()))) + ", encuadre de los punch-in.")
