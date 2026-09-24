"""Servicios de filesystem: normalización, contención de rutas y listado."""
import os
import re
from pathlib import Path


def normalizar(r: str) -> str:
    return (r or "").replace("\\", "/").rstrip("/")


def like_prefix(path: str) -> str:
    """Construye un patrón LIKE literal para los descendientes de path."""
    escaped = normalizar(path).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return escaped + "/%"


def filename_key(name: str) -> str:
    """Respeta la sensibilidad a mayúsculas que usa el filesystem local."""
    return os.path.normcase(name)


def unir(base: str, parte: str) -> str:
    b = normalizar(base)
    p = normalizar(str(parte)).lstrip("/")
    return f"{b}/{p}"


def _resolver(p: str) -> str:
    p = p.replace("\\", "/").strip()
    is_unc = p.startswith("//")
    drive = ""
    m = re.match(r"^([A-Za-z]:)/", p)
    if m:
        drive = m.group(1)
        p = p[len(drive):]
    parts: list[str] = []
    for seg in p.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
            continue
        parts.append(seg)
    prefix = drive + "/" if drive else "//" if is_unc else "/"
    return prefix + "/".join(parts)


def confinar(raiz: str, ruta: str) -> str | None:
    """Valida que la ruta real esté dentro de la raíz, incluyendo enlaces simbólicos."""
    if not ruta:
        return None
    cr = _resolver(normalizar(raiz)).rstrip("/")
    ru = _resolver(normalizar(str(ruta))).rstrip("/")
    if not cr or not ru:
        return None
    real_root = os.path.normcase(os.path.realpath(cr))
    real_path = os.path.normcase(os.path.realpath(ru))
    try:
        dentro = os.path.commonpath((real_root, real_path)) == real_root
    except ValueError:
        dentro = False
    if not dentro:
        return None
    canon = os.path.realpath(ru)
    return normalizar(canon)


def _natsort(names: list[str]) -> list[str]:
    def key(s):
        return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]

    return sorted(names, key=key)


def natsort_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def listar_dirs(ruta: str) -> list[str]:
    try:
        with os.scandir(ruta) as it:
            dirs = [e.name for e in it if e.is_dir() and not e.name.startswith(".")]
    except OSError:
        return []
    return _natsort(dirs)


def listar_pdfs(ruta: str) -> list[str]:
    try:
        with os.scandir(ruta) as it:
            pdfs = [
                e.name for e in it
                if e.is_file() and e.name.lower().endswith(".pdf") and not e.name.startswith(".")
            ]
    except OSError:
        return []
    return _natsort(pdfs)
