"""Asignación, bandeja y seguimiento de lotes."""
import os
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, require_csrf, require_supervisor
from ..core.config import settings
from ..db.database import get_db
from ..db.models import AssignmentLock, Extraccion, Lote, LoteAsignacionHistorial, TramiteError, User
from ..services import fs, lotes as lote_service
from ..services.notificaciones import notify_assignment, notify_completion
from ..services.repo import raiz_origen

router = APIRouter(prefix="/api/lotes", tags=["lotes"])
LEASE_MINUTES = 5


def _lease_active(lote: Lote, now: datetime) -> bool:
    return bool(
        lote.notification_token
        and lote.notification_started_at
        and lote.notification_started_at > now - timedelta(minutes=LEASE_MINUTES)
    )


class AsignarIn(BaseModel):
    relative_path: str
    operador_id: int
    motivo: str = ""


@router.get("/operadores")
def operadores(
    search: str = "",
    user: User = Depends(require_supervisor),
    db: Session = Depends(get_db),
):
    q = db.query(User).filter(User.rol.in_(("usuario", "supervisor")), User.estado == "activo")
    if search.strip():
        term = f"%{search.strip()}%"
        q = q.filter((User.username.like(term)) | (User.nombre.like(term)))
    return [
        {"id": item.id, "username": item.username, "nombre": item.nombre, "email": item.email or ""}
        for item in q.order_by(User.nombre, User.username).all()
    ]


@router.get("/arbol")
def arbol(
    path: str = "",
    user: User = Depends(require_supervisor),
    db: Session = Depends(get_db),
):
    base = raiz_origen(db)
    current = lote_service.absolute_path(db, path) if path else base
    if not os.path.isdir(current):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El directorio no existe.")
    result = []
    for name in fs.listar_dirs(current):
        directory = fs.unir(current, name)
        relative = lote_service.relative_path(base, directory)
        child_dirs = fs.listar_dirs(directory)
        pdfs = fs.listar_pdfs(directory)
        lote = db.query(Lote).filter(Lote.relative_path == relative).first()
        is_final = bool(pdfs) and not child_dirs
        result.append({
            "nombre": name,
            "relative_path": relative,
            "es_lote": is_final,
            "tiene_hijos": bool(child_dirs),
            "total": len(pdfs),
            "lote": lote_service.serialize(db, lote) if lote else None,
            "metricas": lote_service.metricas_directorio(db, relative, name) if is_final else None,
        })
    db.commit()
    return {"actual": lote_service.relative_path(base, current) if current != base else "", "items": result}


@router.get("")
def listar(
    scope: str = "mine",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Lote)
    if user.rol == "usuario" or scope == "mine":
        q = q.filter(Lote.operador_id == user.id)
    elif scope == "supervision" and user.rol in ("supervisor", "administrador"):
        q = q.filter(Lote.operador_id.is_not(None))
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bandeja no válida.")
    rows = q.order_by(Lote.assigned_at.desc(), Lote.nombre).all()
    result = [lote_service.serialize(db, lote) for lote in rows]
    if scope == "mine":
        result = [item for item in result if item["estado"] != "notificado"]
    db.commit()
    return result


@router.get("/counts")
def counts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mine = db.query(Lote).filter(Lote.operador_id == user.id).all()
    pending = 0
    for lote in mine:
        lote_service.sync_estado(db, lote)
        if lote.estado != "notificado":
            pending += 1
    supervision = 0
    if user.rol in ("supervisor", "administrador"):
        assigned = db.query(Lote).filter(Lote.operador_id.is_not(None)).all()
        supervision = sum(1 for lote in assigned if lote_service.metricas(db, lote)["porcentaje"] < 100)
    db.commit()
    return {"pending": pending, "supervision": supervision}


@router.get("/operator-stats")
def operator_stats(
    user: User = Depends(require_supervisor),
    db: Session = Depends(get_db),
):
    since = datetime.now() - timedelta(days=30)
    operators = db.query(User).filter(
        User.rol.in_(("usuario", "supervisor")),
        User.estado == "activo",
    ).order_by(User.nombre, User.username).all()
    result = []
    for operator in operators:
        operator_lots = db.query(Lote).filter(Lote.operador_id == operator.id).all()
        totals = {"total": 0, "realizados": 0, "errores": 0, "pendientes": 0}
        completed_lots = 0
        for lote in operator_lots:
            stats = lote_service.metricas(db, lote)
            for key in totals:
                totals[key] += stats[key]
            if stats["total"] > 0 and stats["pendientes"] == 0:
                completed_lots += 1
        completed_lots += db.query(LoteAsignacionHistorial).filter(
            LoteAsignacionHistorial.operador_id == operator.id,
            LoteAsignacionHistorial.unassigned_at.is_not(None),
            LoteAsignacionHistorial.completed_at.is_not(None),
        ).count()
        recent = db.query(Extraccion).filter(
            Extraccion.user_id == operator.id,
            Extraccion.processed_at >= since,
        ).all()
        progress = round((totals["realizados"] + totals["errores"]) * 100 / totals["total"]) if totals["total"] else 0
        result.append({
            "id": operator.id,
            "username": operator.username,
            "nombre": operator.nombre,
            "lotes_asignados": len(operator_lots),
            "lotes_completados": completed_lots,
            **totals,
            "porcentaje": progress,
            "realizados_30_dias": len(recent),
            "promedio_diario_30_dias": round(len(recent) / 30, 1),
        })
    return result


@router.post("/asignar")
def asignar(
    body: AsignarIn,
    user: User = Depends(require_supervisor),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    operator = db.get(User, body.operador_id)
    if not operator or operator.rol not in ("usuario", "supervisor") or operator.estado != "activo":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El operador no es válido o está inactivo.")
    path = lote_service.absolute_path(db, body.relative_path)
    child_dirs = fs.listar_dirs(path)
    pdfs = fs.listar_pdfs(path)
    if child_dirs or not pdfs:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Solo puede asignar una carpeta final que contenga PDFs.")
    relative = lote_service.relative_path(raiz_origen(db), path)
    db.query(AssignmentLock).filter(AssignmentLock.clave == "global").with_for_update().one()
    lote = db.query(Lote).filter(Lote.relative_path == relative).with_for_update().first()
    now = datetime.now()
    if lote and _lease_active(lote, now):
        raise HTTPException(status.HTTP_409_CONFLICT, "El lote está enviando una notificación. Intente en unos minutos.")
    reassigned = lote is not None and lote.operador_id is not None
    if lote is None:
        lote = Lote(relative_path=relative, nombre=os.path.basename(path))
        db.add(lote)
        db.flush()
    same_operator = lote is not None and lote.operador_id == operator.id
    if same_operator:
        token = str(uuid4())
        lote.notification_token = token
        lote.notification_started_at = now
        stats = lote_service.sync_estado(db, lote)
        db.commit()
        try:
            notification = notify_assignment(db, lote, operator, user, stats["total"], False, settings.app_url)
        finally:
            locked = db.query(Lote).filter(Lote.id == lote.id).with_for_update().first()
            if locked and locked.notification_token == token:
                locked.notification_token = None
                locked.notification_started_at = None
                db.commit()
        return {"ok": True, "lote": lote_service.serialize(db, lote), "reasignado": False, "sin_cambios": True, "notificacion": notification}
    elif lote.operador_id:
        db.query(LoteAsignacionHistorial).filter(
            LoteAsignacionHistorial.lote_id == lote.id,
            LoteAsignacionHistorial.unassigned_at.is_(None),
        ).update({
            LoteAsignacionHistorial.unassigned_at: now,
            LoteAsignacionHistorial.completed_at: lote.completed_at,
            LoteAsignacionHistorial.notified_at: lote.notified_at,
        }, synchronize_session=False)
    lote.operador_id = operator.id
    lote.asignado_por_id = user.id
    lote.assigned_at = now
    lote.notified_at = None
    lote.completed_at = None
    lote.estado = "asignado"
    token = str(uuid4())
    lote.notification_token = token
    lote.notification_started_at = now
    db.add(LoteAsignacionHistorial(
        lote_id=lote.id,
        operador_id=operator.id,
        asignado_por_id=user.id,
        assigned_at=now,
        motivo=body.motivo.strip() or None,
    ))
    document_paths = {
        fs.normalizar(os.path.abspath(os.path.join(path, filename)))
        for filename in pdfs
    }
    if document_paths:
        db.query(Extraccion).filter(Extraccion.original_path.in_(document_paths)).update(
            {Extraccion.lote_id: lote.id}, synchronize_session=False
        )
        db.query(TramiteError).filter(TramiteError.original_path.in_(document_paths)).update(
            {TramiteError.lote_id: lote.id}, synchronize_session=False
        )
    stats = lote_service.sync_estado(db, lote)
    db.commit()
    db.refresh(lote)
    try:
        notification = notify_assignment(db, lote, operator, user, stats["total"], reassigned, settings.app_url)
    finally:
        locked = db.query(Lote).filter(Lote.id == lote.id).with_for_update().first()
        if locked and locked.notification_token == token:
            locked.notification_token = None
            locked.notification_started_at = None
            db.commit()
    return {"ok": True, "lote": lote_service.serialize(db, lote), "reasignado": reassigned, "notificacion": notification}


@router.get("/{lote_id}")
def detalle(
    lote_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lote = db.get(Lote, lote_id)
    if not lote:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lote no encontrado.")
    if user.rol == "usuario" and lote.operador_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Lote no asignado al usuario.")
    result = lote_service.serialize(db, lote)
    db.commit()
    return result


@router.get("/{lote_id}/historial")
def historial(
    lote_id: int,
    user: User = Depends(require_supervisor),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(LoteAsignacionHistorial)
        .filter(LoteAsignacionHistorial.lote_id == lote_id)
        .order_by(LoteAsignacionHistorial.assigned_at.desc())
        .all()
    )
    users = {item.id: item for item in db.query(User).filter(User.id.in_({row.operador_id for row in rows} | {row.asignado_por_id for row in rows if row.asignado_por_id})).all()} if rows else {}
    return [{
        "id": row.id,
        "operador": users[row.operador_id].nombre or users[row.operador_id].username,
        "asignado_por": (users[row.asignado_por_id].nombre or users[row.asignado_por_id].username) if row.asignado_por_id in users else None,
        "assigned_at": row.assigned_at.isoformat(),
        "unassigned_at": row.unassigned_at.isoformat() if row.unassigned_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "notified_at": row.notified_at.isoformat() if row.notified_at else None,
        "motivo": row.motivo,
    } for row in rows]


@router.post("/{lote_id}/liberar")
def liberar(
    lote_id: int,
    user: User = Depends(require_supervisor),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    db.query(AssignmentLock).filter(AssignmentLock.clave == "global").with_for_update().one()
    lote = db.query(Lote).filter(Lote.id == lote_id).with_for_update().first()
    if not lote:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lote no encontrado.")
    now = datetime.now()
    if _lease_active(lote, now):
        raise HTTPException(status.HTTP_409_CONFLICT, "El lote está enviando una notificación. Intente en unos minutos.")
    if lote.operador_id is None:
        return {"ok": True, "sin_cambios": True, "lote": lote_service.serialize(db, lote)}
    db.query(LoteAsignacionHistorial).filter(
        LoteAsignacionHistorial.lote_id == lote.id,
        LoteAsignacionHistorial.unassigned_at.is_(None),
    ).update({
        LoteAsignacionHistorial.unassigned_at: now,
        LoteAsignacionHistorial.completed_at: lote.completed_at,
        LoteAsignacionHistorial.notified_at: lote.notified_at,
        LoteAsignacionHistorial.motivo: f"Liberado por {user.username}",
    }, synchronize_session=False)
    lote.operador_id = None
    lote.asignado_por_id = None
    lote.assigned_at = None
    lote.completed_at = None
    lote.notified_at = None
    lote.estado = "sin_asignar"
    db.commit()
    db.refresh(lote)
    return {"ok": True, "sin_cambios": False, "lote": lote_service.serialize(db, lote)}


@router.post("/{lote_id}/notificar-finalizacion")
def notificar_finalizacion(
    lote_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    lote = db.query(Lote).filter(Lote.id == lote_id).with_for_update().first()
    if not lote:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lote no encontrado.")
    if user.rol == "usuario" and lote.operador_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Lote no asignado al usuario.")
    if not lote.operador:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El lote no tiene operador asignado.")
    now = datetime.now()
    if _lease_active(lote, now):
        raise HTTPException(status.HTTP_409_CONFLICT, "El lote está enviando otra notificación. Intente en unos minutos.")
    stats = lote_service.sync_estado(db, lote)
    if stats["total"] == 0 or stats["pendientes"] > 0:
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "El lote todavía tiene archivos pendientes.")
    token = str(uuid4())
    lote.notification_token = token
    lote.notification_started_at = now
    operator = lote.operador
    assignment_at = lote.assigned_at
    db.commit()
    recipients = []
    if lote.asignado_por and lote.asignado_por.email:
        recipients.append(lote.asignado_por.email)
    recipients.extend(
        email for (email,) in db.query(User.email).filter(
            User.rol == "administrador", User.estado == "activo", User.email.is_not(None)
        ).all() if email
    )
    if not recipients:
        locked = db.query(Lote).filter(Lote.id == lote_id).with_for_update().first()
        if locked and locked.notification_token == token:
            locked.notification_token = None
            locked.notification_started_at = None
            db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "No hay correos configurados para supervisor o administradores.")
    try:
        result = notify_completion(db, lote, operator, recipients, stats, settings.app_url)
    finally:
        locked = db.query(Lote).filter(Lote.id == lote_id).with_for_update().first()
        if locked and locked.notification_token == token:
            current_stats = lote_service.sync_estado(db, locked)
            assignment_unchanged = locked.operador_id == operator.id and locked.assigned_at == assignment_at
            if 'result' in locals() and not result["fallidos"] and assignment_unchanged and current_stats["total"] > 0 and current_stats["pendientes"] == 0:
                locked.estado = "notificado"
                locked.notified_at = datetime.now()
                db.query(LoteAsignacionHistorial).filter(
                    LoteAsignacionHistorial.lote_id == locked.id,
                    LoteAsignacionHistorial.operador_id == operator.id,
                    LoteAsignacionHistorial.unassigned_at.is_(None),
                ).update({
                    LoteAsignacionHistorial.completed_at: locked.completed_at,
                    LoteAsignacionHistorial.notified_at: locked.notified_at,
                }, synchronize_session=False)
            locked.notification_token = None
            locked.notification_started_at = None
            db.commit()
    return {"ok": not result["fallidos"], "notificacion": result, "lote": lote_service.serialize(db, locked)}
