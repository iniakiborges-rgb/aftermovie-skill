"""Utilidades compartidas: conexión a Resolve, Media Pool, ffmpeg, estilo y rutas de trabajo."""
import json, os, re, sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STYLE_MD = os.path.join(SKILL_DIR, "estilo.md")

RESOLVE_API = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
RESOLVE_LIB = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mxf", ".braw", ".avi", ".mts", ".mkv", ".insv"}


def ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("Falta ffmpeg. Instalá:  pip3 install --user imageio-ffmpeg opencv-python-headless librosa")


def work_dir(project_name):
    d = os.path.expanduser(f"~/Movies/aftermovie_work/{safe(project_name)}")
    os.makedirs(d, exist_ok=True)
    return d


def safe(s):
    return re.sub(r"[^\w\-]+", "_", str(s)).strip("_") or "proyecto"


def jload(path):
    return json.load(open(path, encoding="utf-8"))


def jsave(obj, path):
    json.dump(obj, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


# ---------- Resolve ----------
def resolve():
    os.environ.setdefault("RESOLVE_SCRIPT_API", os.path.dirname(RESOLVE_API))
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", RESOLVE_LIB)
    if RESOLVE_API not in sys.path:
        sys.path.append(RESOLVE_API)
    try:
        import DaVinciResolveScript as dvr
    except ImportError:
        sys.exit("No encuentro el scripting de Resolve (¿Resolve Studio instalado?).")
    r = dvr.scriptapp("Resolve")
    if r is None:
        sys.exit("No me conecto a Resolve: abrilo y activá Preferences > System > General > External scripting = Local.")
    p = r.GetProjectManager().GetCurrentProject()
    if p is None:
        sys.exit("Abrí un proyecto en Resolve.")
    return r, p, p.GetMediaPool()


def walk_pool(folder, path=""):
    here = f"{path}/{folder.GetName()}"
    for c in folder.GetClipList() or []:
        yield here, c
    for s in folder.GetSubFolderList() or []:
        yield from walk_pool(s, here)


def find_folder(root, bin_path):
    """bin_path tipo 'Master' o 'Master/fiesta'. Devuelve el Folder o None."""
    parts = [x for x in bin_path.strip("/").split("/") if x]
    if parts and parts[0] == root.GetName():
        parts = parts[1:]
    f = root
    for name in parts:
        nxt = [s for s in f.GetSubFolderList() or [] if s.GetName() == name]
        if not nxt:
            return None
        f = nxt[0]
    return f


def timeline_names(project):
    return [project.GetTimelineByIndex(i).GetName() for i in range(1, project.GetTimelineCount() + 1)]


def get_timeline(project, name):
    for i in range(1, project.GetTimelineCount() + 1):
        t = project.GetTimelineByIndex(i)
        if t.GetName() == name:
            return t
    return None


def free_name(existing, base):
    """Nunca pisa nada: si 'base' existe devuelve 'base v2', 'base v3'..."""
    if base not in existing:
        return base
    stem = re.sub(r"\s+v\d+$", "", base)
    k = 2
    while f"{stem} v{k}" in existing:
        k += 1
    return f"{stem} v{k}"


def timecode(frame, fps):
    fps_i = int(round(fps))
    return f"{frame // (3600 * fps_i):02d}:{(frame // (60 * fps_i)) % 60:02d}:{(frame // fps_i) % 60:02d}:{frame % fps_i:02d}"


# ---------- estilo ----------
def load_style():
    """Lee el bloque ```json de estilo.md (parámetros que usan los scripts)."""
    txt = open(STYLE_MD, encoding="utf-8").read()
    m = re.search(r"```json\s*(\{.*?\})\s*```", txt, re.S)
    if not m:
        sys.exit("estilo.md no tiene bloque ```json de parámetros.")
    return json.loads(m.group(1))
