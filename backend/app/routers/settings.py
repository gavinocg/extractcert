"""Configuración admin: rutas origen/destino (settings)."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import require_admin, require_csrf, get_current_user
from ..db.database import get_db
from ..db.models import User
from ..services import repo
from ..services.email import enviar_correo_config

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {
        "raiz_origen": repo.raiz_origen(db),
        "raiz_repo": repo.raiz_repo(db),
    }


class SettingsIn(BaseModel):
    raiz_origen: str
    raiz_repo: str


class SmtpSettingsIn(BaseModel):
    host: str
    port: int
    user: str
    password: str = ""
    tls: bool = True
    from_email: str = ""


class SmtpTestIn(SmtpSettingsIn):
    recipient: str


@router.put("")
def update_settings(
    body: SettingsIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    repo.set_settings(db, {"raiz_origen": body.raiz_origen.strip(), "raiz_repo": body.raiz_repo.strip()})
    return {"ok": True, "raiz_origen": body.raiz_origen.strip(), "raiz_repo": body.raiz_repo.strip()}


@router.get("/smtp")
def get_smtp_settings(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    config = repo.smtp_settings(db)
    return {
        "host": config["host"],
        "port": config["port"],
        "user": config["user"],
        "tls": config["tls"],
        "from_email": config["from_email"],
        "password_configured": bool(config["password"]),
    }


@router.put("/smtp")
def update_smtp_settings(
    body: SmtpSettingsIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    if not body.host.strip() or not body.user.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Servidor y usuario SMTP son obligatorios.")
    if body.port < 1 or body.port > 65535:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El puerto SMTP no es válido.")
    values = {
        "smtp_host": body.host.strip(),
        "smtp_port": str(body.port),
        "smtp_user": body.user.strip(),
        "smtp_tls": str(body.tls).lower(),
        "smtp_from": body.from_email.strip(),
    }
    if body.password:
        values["smtp_pass"] = repo.encrypt_secret(body.password)
    repo.set_settings(db, values)
    return {"ok": True}


@router.post("/smtp/test")
def test_smtp_settings(
    body: SmtpTestIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    recipient = body.recipient.strip().lower()
    if not recipient or "@" not in recipient:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ingrese un correo destinatario válido.")
    saved = repo.smtp_settings(db)
    config = {
        "host": body.host.strip(),
        "port": body.port,
        "user": body.user.strip(),
        "password": body.password or saved["password"],
        "tls": body.tls,
        "from_email": body.from_email.strip(),
    }
    if not config["host"] or not config["user"] or not config["password"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Complete servidor, usuario y contraseña SMTP.")
    html = """<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden">
<div style="background:#0f172a;color:white;padding:20px 24px"><strong style="color:#fca5a5">ExtractCert</strong><h2 style="margin:6px 0 0">Prueba SMTP exitosa</h2></div>
<div style="padding:24px;color:#334155"><p>Este correo confirma que los parámetros SMTP ingresados pueden enviar notificaciones correctamente.</p><p style="font-size:12px;color:#94a3b8">Mensaje automático de verificación.</p></div></div>"""
    try:
        enviar_correo_config(config, [recipient], "ExtractCert: prueba de configuración SMTP", html, "Prueba SMTP exitosa. Los parámetros ingresados funcionan correctamente.")
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"No se pudo enviar el correo de prueba: {exc}")
    return {"ok": True, "recipient": recipient}
