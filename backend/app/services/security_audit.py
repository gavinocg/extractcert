"""Registro tolerante a fallos de eventos de seguridad."""
import logging

from sqlalchemy.orm import Session

from ..db.models import SecurityAudit

logger = logging.getLogger(__name__)


def record(db: Session, evento: str, usuario_id: int | None, actor_id: int | None = None, ip: str | None = None) -> None:
    try:
        db.add(SecurityAudit(usuario_id=usuario_id, actor_id=actor_id, evento=evento, ip=ip))
        db.commit()
    except Exception:
        # La auditoria nunca debe impedir una operacion de seguridad.
        db.rollback()
        logger.exception("No se pudo registrar el evento de seguridad", extra={"security_event": evento})
