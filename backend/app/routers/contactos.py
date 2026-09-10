import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, require_csrf
from ..db.database import get_db
from ..db.models import Contacto, User

router = APIRouter(prefix="/api/contactos", tags=["contactos"])
_email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ContactoIn(BaseModel):
    nombre: str
    email: str


@router.get("")
def listar(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [{"id": c.id, "nombre": c.nombre, "email": c.email} for c in db.query(Contacto).order_by(Contacto.nombre).all()]


@router.post("")
def crear(body: ContactoIn, user: User = Depends(get_current_user), db: Session = Depends(get_db), _: None = Depends(require_csrf)):
    if not body.nombre.strip() or not body.email.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nombre y email requeridos.")
    if not _email_re.match(body.email.strip()):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email inválido.")
    if db.query(Contacto).filter(Contacto.email == body.email.strip().lower()).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email ya existe.")
    c = Contacto(nombre=body.nombre.strip(), email=body.email.strip().lower())
    db.add(c)
    db.commit()
    return {"ok": True, "id": c.id}


@router.put("/{cid}")
def actualizar(cid: int, body: ContactoIn, user: User = Depends(get_current_user), db: Session = Depends(get_db), _: None = Depends(require_csrf)):
    c = db.get(Contacto, cid)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contacto no existe.")
    if not body.nombre.strip() or not body.email.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nombre y email requeridos.")
    if not _email_re.match(body.email.strip()):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email inválido.")
    c.nombre = body.nombre.strip()
    c.email = body.email.strip().lower()
    db.commit()
    return {"ok": True}


@router.delete("/{cid}")
def eliminar(cid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db), _: None = Depends(require_csrf)):
    c = db.get(Contacto, cid)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contacto no existe.")
    db.delete(c)
    db.commit()
    return {"ok": True}
