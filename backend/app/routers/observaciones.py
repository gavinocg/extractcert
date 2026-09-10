"""Catálogo de observaciones para errores en PDF (lectura global, gestión admin)."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, require_admin, require_csrf
from ..db.database import get_db
from ..db.models import Observacion, User

router = APIRouter(prefix="/api/observaciones", tags=["observaciones"])


class ObservacionIn(BaseModel):
    descripcion: str
    orden: int = 0


def _validar(descripcion: str) -> str:
    texto = descripcion.strip()
    if not texto:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Descripción requerida.")
    if len(texto) > 500:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Máximo 500 caracteres.")
    return texto


@router.get("")
def listar(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [
        {"id": o.id, "descripcion": o.descripcion, "orden": o.orden}
        for o in db.query(Observacion).order_by(Observacion.orden, Observacion.descripcion).all()
    ]


@router.post("")
def crear(body: ObservacionIn, user: User = Depends(require_admin), db: Session = Depends(get_db), _: None = Depends(require_csrf)):
    texto = _validar(body.descripcion)
    if db.query(Observacion).filter(Observacion.descripcion == texto).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Observación ya existe.")
    o = Observacion(descripcion=texto, orden=body.orden or 0)
    db.add(o)
    db.commit()
    return {"ok": True, "id": o.id}


@router.put("/{oid}")
def actualizar(oid: int, body: ObservacionIn, user: User = Depends(require_admin), db: Session = Depends(get_db), _: None = Depends(require_csrf)):
    o = db.get(Observacion, oid)
    if not o:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Observación no existe.")
    texto = _validar(body.descripcion)
    if db.query(Observacion).filter(Observacion.descripcion == texto, Observacion.id != oid).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Observación ya existe.")
    o.descripcion = texto
    o.orden = body.orden or 0
    db.commit()
    return {"ok": True}


@router.delete("/{oid}")
def eliminar(oid: int, user: User = Depends(require_admin), db: Session = Depends(get_db), _: None = Depends(require_csrf)):
    o = db.get(Observacion, oid)
    if not o:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Observación no existe.")
    db.delete(o)
    db.commit()
    return {"ok": True}
