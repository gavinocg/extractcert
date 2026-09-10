import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, require_csrf
from ..db.database import get_db
from ..db.models import Contacto, TramiteError, User
from ..services import fs
from ..services.email import enviar_correo
from ..services.repo import raiz_origen

router = APIRouter(prefix="/api/errores", tags=["errores"])


class ErrorIn(BaseModel):
    ruta: str
    observacion: str


class EnviarIn(BaseModel):
    ids: list[int] = []
    contactos_ids: list[int] = []
    emails_extra: list[str] = []
    asunto: str = ""
    cuerpo: str = ""


def _validar_ruta(ruta: str, db: Session) -> str:
    real = fs.confinar(raiz_origen(db), ruta)
    if real is None or not os.path.isfile(real):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF no encontrado.")
    if not real.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo PDF.")
    return real


@router.post("")
def crear(body: ErrorIn, user: User = Depends(get_current_user), db: Session = Depends(get_db), _: None = Depends(require_csrf)):
    if not body.observacion.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Observación requerida.")
    real = _validar_ruta(body.ruta, db)
    canon = fs.normalizar(real)
    existente = db.query(TramiteError).filter(TramiteError.original_path == canon).first()
    if existente:
        existente.observacion = body.observacion.strip()
        existente.user_id = user.id
        db.commit()
        return {"ok": True, "id": existente.id}
    e = TramiteError(original_path=canon, archivo=os.path.basename(canon), observacion=body.observacion.strip(), user_id=user.id)
    db.add(e)
    db.commit()
    return {"ok": True, "id": e.id}


@router.get("")
def listar(path: str | None = None, pagina: int = Query(1, ge=1), tam: int = Query(20, ge=1, le=100), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(TramiteError, User.username).join(User, TramiteError.user_id == User.id)
    if path:
        base = raiz_origen(db)
        conf = fs.confinar(base, path)
        if conf is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ruta no permitida.")
        pref = fs.normalizar(conf) + "/%"
        q = q.filter(TramiteError.original_path.like(pref))
    total = q.count()
    rows = q.order_by(TramiteError.created_at.desc()).offset((pagina - 1) * tam).limit(tam).all()
    datos = [{"id": e.id, "original_path": e.original_path, "archivo": e.archivo, "observacion": e.observacion, "username": u, "created_at": e.created_at.isoformat() if e.created_at else None} for e, u in rows]
    return {"registros": datos, "total": total, "pagina": pagina, "tam": tam}


@router.delete("/{eid}")
def eliminar(eid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db), _: None = Depends(require_csrf)):
    e = db.get(TramiteError, eid)
    if not e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe.")
    db.delete(e)
    db.commit()
    return {"ok": True}


@router.post("/enviar")
def enviar(body: EnviarIn, user: User = Depends(get_current_user), db: Session = Depends(get_db), _: None = Depends(require_csrf)):
    if not body.ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Seleccione al menos un trámite.")
    errores = db.query(TramiteError).filter(TramiteError.id.in_(body.ids)).all()
    if not errores:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trámites no encontrados.")
    destinatarios: list[str] = []
    if body.contactos_ids:
        contactos = db.query(Contacto).filter(Contacto.id.in_(body.contactos_ids)).all()
        destinatarios.extend([c.email for c in contactos])
    for em in body.emails_extra:
        em = em.strip()
        if em and "@" in em:
            destinatarios.append(em)
    destinatarios = list(dict.fromkeys(destinatarios))
    if not destinatarios:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Indique destinatarios.")
    asunto = body.asunto.strip() or "Trámites con error en digital"
    cuerpo_extra = body.cuerpo.strip()
    filas = "".join([f"<tr><td>{e.archivo}</td><td>{e.observacion}</td><td>{e.original_path}</td></tr>" for e in errores])
    html = f"<p>{cuerpo_extra}</p>" if cuerpo_extra else ""
    html += f"<table border='1' cellpadding='6' cellspacing='0'><tr><th>Trámite (archivo)</th><th>Observación</th><th>Ruta</th></tr>{filas}</table>"
    txt = cuerpo_extra + "\n" + "\n".join([f"{e.archivo} | {e.observacion} | {e.original_path}" for e in errores])
    try:
        enviar_correo(destinatarios, asunto, html, txt)
    except Exception as ex:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Error enviando correo: {ex}")
    return {"ok": True, "enviados": len(destinatarios)}
