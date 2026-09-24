"""Repositorio: settings persistentes, raíces y naming anti-colisión."""
import os
import time
import base64
import hashlib
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
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
    set_settings(db, {clave: valor})


def set_settings(db: Session, values: dict[str, str]) -> None:
    for clave, valor in values.items():
        row = db.get(Setting, clave)
        if row:
            row.valor = valor
        else:
            db.add(Setting(clave=clave, valor=valor))
    db.commit()


def encrypt_secret(value: str) -> str:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode("utf-8")).digest())
    return "enc:" + Fernet(key).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    if not value.startswith("enc:"):
        return value
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode("utf-8")).digest())
    try:
        return Fernet(key).decrypt(value[4:].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("No se pudo descifrar la contraseña SMTP; revise SECRET_KEY.") from exc


def smtp_settings(db: Session) -> dict:
    password_row = db.get(Setting, "smtp_pass")
    stored_password = password_row.valor if password_row else settings.smtp_pass
    if password_row and stored_password and not stored_password.startswith("enc:"):
        password_row.valor = encrypt_secret(stored_password)
        db.commit()
        stored_password = password_row.valor
    return {
        "host": _get_setting(db, "smtp_host", settings.smtp_host),
        "port": int(_get_setting(db, "smtp_port", str(settings.smtp_port))),
        "user": _get_setting(db, "smtp_user", settings.smtp_user),
        "password": decrypt_secret(stored_password),
        "tls": _get_setting(db, "smtp_tls", str(settings.smtp_tls)).lower() in ("1", "true", "yes", "si"),
        "from_email": _get_setting(db, "smtp_from", settings.smtp_from),
    }


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


def new_temp_filename(user_id: int, prefix: str = "prev") -> Path:
    import uuid

    return settings.temp_dir / f"{prefix}_u{user_id}_{uuid.uuid4().hex[:12]}.pdf"


def limpiar_temporales(max_mins: int = 90) -> None:
    now = time.time()
    for f in settings.temp_dir.glob("prev_*.pdf"):
        try:
            if (now - f.stat().st_mtime) > max_mins * 60:
                f.unlink(missing_ok=True)
        except OSError:
            pass
