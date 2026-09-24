import os
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, require_csrf
from ..db.database import get_db
from ..db.models import AssignmentLock, Contacto, Lote, TramiteError, User
from ..services import fs
from ..services.email import enviar_correo
from ..services.lotes import require_path_access
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


def _validar_ruta(ruta: str, db: Session, user: User) -> tuple[str, int | None]:
    real = fs.confinar(raiz_origen(db), ruta)
    if real is None or not os.path.isfile(real):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF no encontrado.")
    if not real.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo PDF.")
    lote = require_path_access(db, user, real)
    return real, lote.id if lote else None


@router.post("")
def crear(body: ErrorIn, user: User = Depends(get_current_user), db: Session = Depends(get_db), _: None = Depends(require_csrf)):
    if not body.observacion.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Observación requerida.")
    real, lote_id = _validar_ruta(body.ruta, db, user)
    db.query(AssignmentLock).filter(AssignmentLock.clave == "global").with_for_update().one()
    real, locked_lote_id = _validar_ruta(body.ruta, db, user)
    if locked_lote_id != lote_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "La asignación del lote cambió.")
    lote_id = locked_lote_id
    canon = fs.normalizar(real)
    existente = db.query(TramiteError).filter(TramiteError.original_path == canon).first()
    if existente:
        existente.observacion = body.observacion.strip()
        existente.user_id = user.id
        existente.lote_id = lote_id
        db.commit()
        return {"ok": True, "id": existente.id}
    e = TramiteError(original_path=canon, archivo=os.path.basename(canon), observacion=body.observacion.strip(), user_id=user.id, lote_id=lote_id)
    db.add(e)
    db.commit()
    return {"ok": True, "id": e.id}


@router.get("")
def listar(path: str | None = None, pagina: int = Query(1, ge=1), tam: int = Query(20, ge=1, le=100), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(TramiteError, User.username).join(User, TramiteError.user_id == User.id)
    if user.rol == "usuario":
        assigned = db.query(Lote.id).filter(Lote.operador_id == user.id)
        q = q.filter(TramiteError.lote_id.in_(assigned))
    if path:
        base = raiz_origen(db)
        conf = fs.confinar(base, path)
        if conf is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ruta no permitida.")
        pref = fs.like_prefix(conf)
        q = q.filter(TramiteError.original_path.like(pref, escape="\\"))
    total = q.count()
    rows = q.order_by(TramiteError.created_at.desc()).offset((pagina - 1) * tam).limit(tam).all()
    datos = [{"id": e.id, "original_path": e.original_path, "archivo": e.archivo, "observacion": e.observacion, "username": u, "created_at": e.created_at.isoformat() if e.created_at else None} for e, u in rows]
    return {"registros": datos, "total": total, "pagina": pagina, "tam": tam}


@router.delete("/{eid}")
def eliminar(eid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db), _: None = Depends(require_csrf)):
    db.query(AssignmentLock).filter(AssignmentLock.clave == "global").with_for_update().one()
    e = db.get(TramiteError, eid)
    if not e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe.")
    require_path_access(db, user, e.original_path)
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
    for item in errores:
        require_path_access(db, user, item.original_path)
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
    filas = "".join([f"<tr><td>{escape(e.archivo)}</td><td>{escape(e.observacion)}</td><td>{escape(e.original_path)}</td></tr>" for e in errores])
    html = f"<p>{escape(cuerpo_extra)}</p>" if cuerpo_extra else ""
    html += f"<table border='1' cellpadding='6' cellspacing='0'><tr><th>Trámite (archivo)</th><th>Observación</th><th>Ruta</th></tr>{filas}</table>"
    txt = cuerpo_extra + "\n" + "\n".join([f"{e.archivo} | {e.observacion} | {e.original_path}" for e in errores])
    try:
        enviar_correo(destinatarios, asunto, html, txt)
    except Exception as ex:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Error enviando correo: {ex}")
    return {"ok": True, "enviados": len(destinatarios)}
