"""Fase 3c: arma el timeline del aftermovie con el estilo de estilo.md.
V1 tomas · V2 destellos · A1 tema (con hueco antes del drop) · A2 whooshes · A3 riser · A4 impacto · A5 ambiente (si estilo lo pide)
Nunca pisa timelines: si el nombre existe crea "v2", "v3"...  Guarda <work>/montage_plan.json para aprender después
(en --dry-run: montage_plan_dryrun.json).
MODO FIESTA (bandas + DJs): si existe <work>/party_plan.json (o con --party) arma la estructura por bloques de estilo.md
(party_block_order) sobre el tramo del tema que dejó el editor, con barridos propios, punch-in y cola de audio: ver party.py.

  python3 build_montage.py --project NOMBRE --name "Fiesta Aftermovie" [--format vertical|horizontal]
"""
import argparse, os, sys
from collections import defaultdict
from common import resolve, walk_pool, work_dir, jload, jsave, load_style, timeline_names, free_name, timecode

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True)
ap.add_argument("--name", required=True)
ap.add_argument("--format", choices=["vertical", "horizontal"])
ap.add_argument("--dry-run", action="store_true", help="Calcula y muestra el plan sin crear nada en Resolve")
ap.add_argument("--party", action="store_true", help="Forzar el modo fiesta por bloques (party_plan.json)")
ap.add_argument("--classic", action="store_true", help="Ignorar party_plan.json y usar subida/hueco/drop")
a = ap.parse_args()
ST = load_style()
W = work_dir(a.project)
if not a.classic and (a.party or os.path.exists(f"{W}/party_plan.json")):
    import party
    try:
        r, project, mp = resolve()
    except SystemExit as e:
        if not a.dry_run:
            raise
        print(f"(sin Resolve: {e}; dry-run con cachés)"); r = project = mp = None
    party.run(a, ST, W, r, project, mp, jload(f"{W}/resources.json") if os.path.exists(f"{W}/resources.json") else {})
    sys.exit(0)
SEL = jload(f"{W}/selects.json")
SP = jload(f"{W}/song_plan.json")
RS = jload(f"{W}/resources.json") if os.path.exists(f"{W}/resources.json") else {}
FMT = a.format or SEL.get("format", "vertical")

r, project, mp = resolve()
FPS = float(str(project.GetSetting("timelineFrameRate")).split()[0])
f = lambda t: int(round(t * FPS))
grid = SP["beats_tl"]; u = SP["unit_beats"]


def bt(x):                                   # tiempo de timeline para x beats (admite fracciones)
    i = int(x); fr = x - i
    if i >= len(grid) - 1:
        return grid[-1]
    return grid[i] + fr * (grid[i + 1] - grid[i])


# ---------- 1) duraciones (en beats) ----------
drop_b = SP["build_beats"]; total_b = len(grid) - 1
P = ST["pattern"]
open_b = min(P["open_units"] * u, drop_b / 3)
build = [x * u for x in P["build_units"]]
room = drop_b - open_b
while sum(build) > room and len(build) > 1:
    build.pop(0)
while sum(build) + 2 * u <= room:
    build.insert(0, 2 * u)
if sum(build) < room:
    build[0] += room - sum(build)
close_b = P["close_units"] * u
seq = [("open", open_b)] + [("build", b) for b in build]
seq += [("burst", P["burst_len_units"] * u)] * P["burst_count"]
left = total_b - drop_b - P["burst_count"] * P["burst_len_units"] * u - close_b
blocks, k = [], 0
while True:
    blk = P["drop_blocks"][k % len(P["drop_blocks"])]
    items = [("hold", blk["hold"] * u)] if "hold" in blk else [("run", x * u) for x in blk["run"]]
    if sum(x for _, x in items) > left:
        for kind, x in items:                # completar con lo que entre
            if x <= left:
                blocks.append((kind, x)); left -= x
        break
    blocks += items; left -= sum(x for _, x in items); k += 1
if left > 0:
    kind, x = blocks[-1] if blocks else ("run", 0)
    if blocks:
        blocks[-1] = (kind, x + left)
    else:
        blocks.append(("run", left))
seq += blocks + [("close", close_b)]

# ---------- 2) tipos de plano y clips ----------
clips = [c for c in SEL["clips"] if "src" in c]
by_type = defaultdict(list)
for c in clips:
    by_type[c["type"]].append(c)
cycle = [t for t in ST["type_cycle"] if by_type.get(t)]
brand = by_type.get("marca") or by_type.get("detalle") or by_type.get(cycle[-1])
open_c = [c for c in clips if c.get("role") == "open"] or brand[:1]
close_c = [c for c in clips if c.get("role") == "close"] or brand[1:] or brand
used = defaultdict(float)                     # segundos ya usados de cada tramo
import re as _re
_win = {r["name"]: r for r in jload(f"{W}/windows.json")["clips"]} if os.path.exists(f"{W}/windows.json") else {}
score = lambda c: _win.get(c["name"], {}).get("score") or -1.0
num = lambda c: int((_re.findall(r"\d+", os.path.splitext(c["name"])[0]) or ["-999"])[-1])
recent = []                                   # clips recientes: evitar misma escena (numeración consecutiva)


def near(c):
    return any(abs(num(c) - num(x)) <= 2 and c["name"] != x["name"] for x in recent[-10:])


def take(cands, need, prefer_long=False):
    pool = sorted(cands, key=lambda c: (used[c["name"]] > 0, near(c),
                                        -(c["len"] - used[c["name"]]) if prefer_long else -score(c)))
    for c in pool:
        if c["len"] - used[c["name"]] >= need - 1e-3:
            s = c["in"] + used[c["name"]]; used[c["name"]] += need
            return c, s
    c = max(cands, key=lambda c: c["len"])
    print(f"  ! reuso {c['name']} (no hay tramo libre de {need:.2f} s)")
    return c, c["in"] + max(0, c["len"] - need)


shots, cursor, ti = [], 0.0, 0
for n, (kind, nb) in enumerate(seq):
    a_t = bt(cursor); b_t = bt(cursor + nb)
    if kind in ("open", "close"):
        typ, cands = "marca", (open_c if kind == "open" else close_c)
    else:
        typ = cycle[ti % len(cycle)]; ti += 1
        if shots and shots[-1]["type"] == typ:
            typ = cycle[ti % len(cycle)]; ti += 1
        cands = by_type[typ]
    c, s_in = take(cands, b_t - a_t, prefer_long=kind in ("hold", "open", "close"))
    recent.append(c)
    zoom = 1.0
    if kind == "burst" and (n % 2):
        zoom = P["burst_zoom"]
    marker = {"open": "zoom in", "close": "zoom out", "hold": "zoom in" if len([s for s in shots if s["kind"] == "hold"]) % 2 == 0 else "zoom out"}.get(kind)
    if kind == "build" and n == len(build):
        marker = "zoom in"                    # toma que cruza el hueco
    shots.append({"kind": kind, "type": c["type"] if typ == "marca" else typ, "name": c["name"], "rec": f(a_t),
                  "len": f(b_t) - f(a_t), "src_s": s_in, "clip_fps": c["fps"], "rotate": c.get("rotate"),
                  "zoom": zoom, "marker": marker})
    cursor += nb
for x, y in zip(shots, shots[1:]):
    if x["type"] == y["type"]:
        print(f"  ! dos '{x['type']}' seguidas en {y['rec'] / FPS:.2f} s")

if a.dry_run:
    for sh in shots:
        print(f"  {sh['rec'] / FPS:6.2f}s {sh['len']:3d}f {sh['kind']:6} {sh['type']:8} {sh['name']}"
              f"{'  zoom ' + str(sh['zoom']) if sh['zoom'] != 1 else ''}{'  [' + sh['marker'] + ']' if sh['marker'] else ''}")
    jsave({"mode": "classic", "timeline": a.name, "fps": FPS, "shots": shots}, f"{W}/montage_plan_dryrun.json")
    print(f"{len(shots)} tomas · {sum(s['len'] for s in shots) / FPS:.2f} s · drop {SP['drop_tl']:.2f} s (dry-run: no se creó nada)")
    sys.exit(0)

# ---------- 3) Resolve ----------
root = mp.GetRootFolder()
pool = list(walk_pool(root))
by_path = {}
for where, c in pool:
    p_ = c.GetClipProperty("File Path")
    if p_:
        by_path.setdefault(p_, []).append((where, c))
sel_bin = SEL["bin"].split("/")[-1]


def item_for(path, prefer_bin=None):
    lst = by_path.get(path, [])
    for where, c in lst:
        if prefer_bin and where.endswith("/" + prefer_bin):
            return c
    return lst[0][1] if lst else None


song_item = item_for(SP["song"])
if song_item is None:                          # importar el tema en un bin NUEVO (no toca nada existente)
    b = mp.AddSubFolder(root, free_name([x.GetName() for x in root.GetSubFolderList()], f"{a.name} audio"))
    mp.SetCurrentFolder(b); song_item = (mp.ImportMedia([SP["song"]]) or [None])[0]
    if song_item is None:
        sys.exit("No pude importar el tema.")

name = free_name(timeline_names(project), a.name)
mp.SetCurrentFolder(root)
tl = mp.CreateEmptyTimeline(name)
project.SetCurrentTimeline(tl)
tw, th = (2160, 3840) if FMT == "vertical" else (3840, 2160)
tl.SetSetting("useCustomSettings", "1")
tl.SetSetting("timelineResolutionWidth", str(tw)); tl.SetSetting("timelineResolutionHeight", str(th))
start = tl.GetStartFrame()
while tl.GetTrackCount("video") < 2:
    tl.AddTrack("video")
while tl.GetTrackCount("audio") < 5:
    tl.AddTrack("audio", "stereo")
for i, n_ in enumerate(["Tomas", "Destellos"], 1):
    tl.SetTrackName("video", i, n_)
for i, n_ in enumerate(["Tema", "Whooshes", "Riser", "Impacto", "Ambiente"], 1):
    tl.SetTrackName("audio", i, n_)


def put(item, src_frames, len_frames, track, rec, media):
    res = mp.AppendToTimeline([{"mediaPoolItem": item, "startFrame": src_frames, "endFrame": src_frames + len_frames,
                                "mediaType": media, "trackIndex": track, "recordFrame": start + rec}])
    return res[0] if res else None


built = {"timeline": name, "fps": FPS, "shots": [], "flashes": [], "audio": []}
COMP = {"Screen": r.COMPOSITE_SCREEN, "Add": r.COMPOSITE_ADD, "LinearDodge": r.COMPOSITE_LINEAR_DODGE,
        "Lighten": r.COMPOSITE_LIGHTEN, "Overlay": r.COMPOSITE_OVERLAY}
sel_paths = {c["name"]: c["path"] for c in clips}
for sh in shots:
    it = item_for(sel_paths[sh["name"]], sel_bin)
    src = int(round(sh["src_s"] * sh["clip_fps"])); n_src = int(round(sh["len"] * sh["clip_fps"] / FPS))
    t_ = put(it, src, n_src, 1, sh["rec"], 1)
    if not t_:
        print("  ! no entró", sh["name"]); continue
    z = sh["zoom"]
    if sh["rotate"]:
        t_.SetProperty("RotationAngle", -90.0 if sh["rotate"] == "cw" else 90.0); z = max(tw, th) / min(tw, th)
    if z != 1.0:
        t_.SetProperty("ZoomX", z); t_.SetProperty("ZoomY", z)
    if sh["marker"]:
        tl.AddMarker(sh["rec"], "Blue", sh["marker"], f"{sh['marker']} · {sh['type']} {sh['name']}", max(1, sh["len"]))
    built["shots"].append({**sh, "src": src, "zoom_applied": z})

# tema con hueco antes del drop
gap_rec, drop_rec = f(SP["gap_tl"]), f(SP["drop_tl"])
put(song_item, f(SP["song_in"]), gap_rec, 1, 0, 2)
put(song_item, f(SP["drop"]), f(SP["song_out"] - SP["drop"]), 1, drop_rec, 2)
tl.AddMarker(gap_rec, "Red", "Hueco", "Silencio antes del drop", max(1, drop_rec - gap_rec))
tl.AddMarker(drop_rec, "Red", "DROP", "Impacto + ráfaga", 1)

# destellos y whooshes: drop + inicio de cada toma larga + cierre
FL = ST["flashes"]
cuts = [drop_rec] + [s["rec"] for s in built["shots"] if s["kind"] in ("hold", "close")]
flashes = RS.get("flashes", [])
big = [x for x in flashes if x["dur"] >= 1.5] or flashes
small = [x for x in flashes if x["dur"] < 1.5] or flashes
whoosh = RS.get("whoosh", [])
for k, cut in enumerate(cuts):
    if flashes:
        fx = big[0] if k == 0 else small[(k - 1) % len(small)]
        dur = FL["drop_len"] if k == 0 else FL["len"]
        pre = min(fx["peak"], dur * FL["peak_position"])
        src_s = max(0.0, fx["peak"] - pre)
        dur = min(dur, fx["dur"] - src_s)
        it = item_for(fx["path"])
        t_ = put(it, int(round(src_s * fx["fps"])), int(round(dur * fx["fps"])), 2, cut - f(pre), 1) if it else None
        if t_:
            mode = FL["composite_cycle"][k % len(FL["composite_cycle"])]
            t_.SetProperty("CompositeMode", COMP.get(mode, r.COMPOSITE_ADD))
            t_.SetProperty("ZoomX", FL["zoom"]); t_.SetProperty("ZoomY", FL["zoom"])
            built["flashes"].append({"name": fx["name"], "rec": cut - f(pre), "len": f(dur), "src_s": src_s, "mode": mode})
    if whoosh and k > 0:
        w = whoosh[(k - 1) % len(whoosh)]
        it = item_for(w["path"])
        if it and put(it, 0, f(min(w["dur"], 1.5)), 2, cut - f(w["peak"]), 2):
            built["audio"].append({"track": "Whooshes", "name": w["name"], "rec": cut - f(w["peak"])})
if RS.get("riser"):
    w = RS["riser"][0]; d = min(w["dur"], SP["gap_tl"])
    it = item_for(w["path"])
    if it and put(it, f(w["dur"] - d), f(d), 3, gap_rec - f(d), 2):
        built["audio"].append({"track": "Riser", "name": w["name"], "rec": gap_rec - f(d)})
if RS.get("impact"):
    w = RS["impact"][0]; it = item_for(w["path"])
    if it and put(it, 0, f(min(3.0, w["dur"])), 4, drop_rec - f(w["peak"]), 2):
        built["audio"].append({"track": "Impacto", "name": w["name"], "rec": drop_rec - f(w["peak"])})
if ST.get("ambience", {}).get("enabled") and RS.get("ambience"):
    w = RS["ambience"][0]; it = item_for(w["path"])
    if it and put(it, 0, f(min(w["dur"], SP["length"])), 5, 0, 2):
        built["audio"].append({"track": "Ambiente", "name": w["name"], "rec": 0})

built["song_plan"] = {k: SP[k] for k in ("song_in", "gap_start", "drop", "song_out", "tempo", "unit_beats")}
jsave(built, f"{W}/montage_plan.json")
v1 = tl.GetItemListInTrack("video", 1)
print(f"Timeline '{name}': {len(v1)} tomas · {len(built['flashes'])} destellos · {len(built['audio'])} SFX · "
      f"{(tl.GetEndFrame() - start) / FPS:.2f} s · drop en {SP['drop_tl']:.2f} s")
print("Volúmenes a ajustar a mano (la API no los expone):")
for k, v in ST["volumes_db"].items():
    print(f"  - {k}: {v}")
