"""Registro tolerante a fallos de eventos de seguridad."""
from sqlalchemy.orm import Session

from ..db.models import SecurityAudit


def record(db: Session, evento: str, usuario_id: int | None, actor_id: int | None = None, ip: str | None = None) -> None:
    try:
        db.add(SecurityAudit(usuario_id=usuario_id, actor_id=actor_id, evento=evento, ip=ip))
        db.commit()
    except Exception:
        # La auditoria nunca debe impedir una operacion de seguridad.
        db.rollback()
