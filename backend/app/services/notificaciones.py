"""Plantillas y registro de notificaciones de lotes."""
from datetime import datetime, timedelta
from html import escape

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db.models import Lote, Notificacion, User
from .email import enviar_correo


def _layout(title: str, intro: str, rows: list[tuple[str, str]], action_url: str = "") -> tuple[str, str]:
    detail_rows = "".join(
        f"<tr><td style='padding:8px 12px;color:#64748b'>{escape(label)}</td>"
        f"<td style='padding:8px 12px;font-weight:600;color:#0f172a'>{escape(value)}</td></tr>"
        for label, value in rows
    )
    button = (
        f"<p style='margin:24px 0 0'><a href='{escape(action_url)}' style='display:inline-block;background:#dc2626;color:#fff;text-decoration:none;padding:11px 18px;border-radius:8px;font-weight:700'>Abrir ExtractCert</a></p>"
        if action_url else ""
    )
    html = f"""<!doctype html><html><body style="margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 8px 28px rgba(15,23,42,.10)">
<tr><td style="background:#0f172a;padding:22px 28px;color:#fff"><div style="font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#fca5a5">ExtractCert</div><h1 style="font-size:22px;margin:6px 0 0">{escape(title)}</h1></td></tr>
<tr><td style="padding:28px"><p style="margin:0 0 20px;line-height:1.6;color:#475569">{escape(intro)}</p><table role="presentation" width="100%" style="border-collapse:collapse;background:#f8fafc;border-radius:8px">{detail_rows}</table>{button}<p style="margin:24px 0 0;font-size:12px;color:#94a3b8">Mensaje automático. No responda a este correo.</p></td></tr>
</table></td></tr></table></body></html>"""
    text = title + "\n\n" + intro + "\n\n" + "\n".join(f"{label}: {value}" for label, value in rows)
    if action_url:
        text += f"\n\nAbrir ExtractCert: {action_url}"
    return html, text


def send_recorded(
    db: Session,
    lote: Lote,
    notification_type: str,
    recipients: list[str],
    subject: str,
    html: str,
    text: str,
) -> dict:
    unique = list(dict.fromkeys(email.strip().lower() for email in recipients if email and email.strip()))
    sent = 0
    omitted = 0
    failed: list[str] = []
    for email in unique:
        record = db.query(Notificacion).filter(
            Notificacion.lote_id == lote.id,
            Notificacion.tipo == notification_type,
            Notificacion.destinatario == email,
        ).first()
        if record and record.estado == "enviado":
            omitted += 1
            continue
        if record:
            stale_before = datetime.now() - timedelta(minutes=5)
            claimed = db.query(Notificacion).filter(
                Notificacion.id == record.id,
                (
                    (Notificacion.estado == "fallido")
                    | ((Notificacion.estado == "enviando") & (Notificacion.updated_at < stale_before))
                ),
            ).update({
                Notificacion.estado: "enviando",
                Notificacion.intentos: Notificacion.intentos + 1,
                Notificacion.error: None,
                Notificacion.updated_at: datetime.now(),
            }, synchronize_session=False)
            db.commit()
            if not claimed:
                omitted += 1
                continue
            db.refresh(record)
        else:
            record = Notificacion(
                lote_id=lote.id,
                tipo=notification_type[:100],
                destinatario=email,
                estado="enviando",
                intentos=1,
                updated_at=datetime.now(),
            )
            db.add(record)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                omitted += 1
                continue
        try:
            enviar_correo([email], subject, html, text)
            record.estado = "enviado"
            record.sent_at = datetime.now()
            record.updated_at = datetime.now()
            sent += 1
        except Exception as exc:
            record.estado = "fallido"
            record.error = str(exc)[:2000]
            record.updated_at = datetime.now()
            failed.append(email)
        try:
            db.commit()
        except Exception:
            db.rollback()
    return {"enviados": sent, "omitidos": omitted, "fallidos": failed, "sin_correo": not unique}


def notify_assignment(db: Session, lote: Lote, operator: User, assigner: User, total: int, reassigned: bool, app_url: str) -> dict:
    title = "Lote reasignado" if reassigned else "Nueva asignación"
    intro = "Tiene pendiente la extracción de certificados del siguiente lote."
    rows = [
        ("Carpeta", lote.nombre),
        ("Ruta", lote.relative_path),
        ("Archivos PDF", str(total)),
        ("Asignado por", assigner.nombre or assigner.username),
        ("Fecha y hora", datetime.now().strftime("%d/%m/%Y %H:%M")),
    ]
    html, text = _layout(title, intro, rows, app_url)
    return send_recorded(db, lote, f"{'reasignacion' if reassigned else 'asignacion'}:{lote.assigned_at.isoformat()}", [operator.email or ""], f"ExtractCert: {title} - {lote.nombre}", html, text)


def notify_completion(db: Session, lote: Lote, operator: User, recipients: list[str], stats: dict, app_url: str) -> dict:
    rows = [
        ("Operador", operator.nombre or operator.username),
        ("Carpeta", lote.nombre),
        ("Total de archivos", str(stats["total"])),
        ("Realizados", str(stats["realizados"])),
        ("Con error", str(stats["errores"])),
        ("Fecha y hora", datetime.now().strftime("%d/%m/%Y %H:%M")),
    ]
    html, text = _layout("Lote finalizado", "El operador reportó la finalización del lote.", rows, app_url)
    event = lote.completed_at.isoformat() if lote.completed_at else "actual"
    return send_recorded(db, lote, f"finalizacion:{event}", recipients, f"ExtractCert: lote finalizado - {lote.nombre}", html, text)
