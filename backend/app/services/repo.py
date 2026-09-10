"""Repositorio: settings persistentes, raíces y naming anti-colisión."""
import os
import time
from pathlib import Path

from sqlalchemy.orm import Session

from ..core.config import settings
from ..db.models import Setting
from . import fs


def _get_setting(db: Session, clave: str, default: str) -> str:
    row = db.get(Setting, clave)
    return row.valor if row else default


def raiz_origen(db: Session) -> str:
    return fs.normalizar(_get_setting(db, "raiz_origen", settings.default_raiz_origen))


def raiz_repo(db: Session) -> str:
    return fs.normalizar(_get_setting(db, "raiz_repo", settings.default_raiz_repo))


def set_setting(db: Session, clave: str, valor: str) -> None:
    row = db.get(Setting, clave)
    if row:
        row.valor = valor
    else:
        db.add(Setting(clave=clave, valor=valor))
    db.commit()


def generar_nombre_sin_colision(dir_: str, archivo: str) -> str:
    """4426.pdf -> 4426.pdf, 4426c.pdf, 4426cc.pdf ..."""
    base, ext = os.path.splitext(os.path.basename(archivo))
    ext = ext.lower() or ".pdf"
    intento = f"{base}{ext}"
    sufijo = ""
    while os.path.exists(fs.unir(dir_, intento)):
        sufijo += "c"
        intento = f"{base}{sufijo}{ext}"
    return intento


def new_temp_filename(prefix: str = "prev") -> Path:
    import uuid

    return settings.temp_dir / f"{prefix}_{uuid.uuid4().hex[:12]}.pdf"


def limpiar_temporales(max_mins: int = 90) -> None:
    now = time.time()
    for f in settings.temp_dir.glob("prev_*.pdf"):
        try:
            if (now - f.stat().st_mtime) > max_mins * 60:
                f.unlink(missing_ok=True)
        except OSError:
            pass