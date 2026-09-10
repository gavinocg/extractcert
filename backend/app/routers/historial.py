"""Historial de extracciones (admin: todos + filtro por usuario)."""
import os

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..db.database import get_db
from ..db.models import Extraccion, User

router = APIRouter(prefix="/api", tags=["historial"])

MAX_TAM = 200


@router.get("/historial")
def historial(
    usuario: int = 0,
    pagina: int = Query(1, ge=1),
    tam: int = Query(20, ge=1, le=MAX_TAM),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    es_admin = user.rol == "administrador"
    q = db.query(Extraccion, User.username).join(User, Extraccion.user_id == User.id)
    if not es_admin:
        q = q.filter(Extraccion.user_id == user.id)
    elif usuario:
        q = q.filter(Extraccion.user_id == usuario)

    total = q.count()
    filas = (
        q.order_by(Extraccion.created_at.desc(), Extraccion.id.desc())
        .offset((pagina - 1) * tam)
        .limit(tam)
        .all()
    )
    datos = [
        {
            "id": e.id,
            "original_path": e.original_path,
            "destino_path": e.destino_path,
            "archivo": os.path.basename(e.original_path),
            "destino": os.path.basename(e.destino_path),
            "pagina_inicio": e.pagina_inicio,
            "pagina_fin": e.pagina_fin,
            "estado": e.estado,
            "username": username,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e, username in filas
    ]

    usuarios = []
    if es_admin:
        usuarios = [
            {"id": u.id, "username": u.username}
            for u in db.query(User).order_by(User.username)
        ]

    return {
        "registros": datos,
        "total": total,
        "pagina": pagina,
        "tam": tam,
        "usuarios": usuarios,
    }