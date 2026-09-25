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
from ..db.models import AssignmentLock, Extraccion, ExtraccionVersion, Lote, LoteAsignacionHistorial, LoteDocumento, LoteOperador, Notificacion, TramiteError, User
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


def _notify_members(db: Session, lote: Lote, operators: list[User], assigner: User, total: int, reassigned: bool) -> dict:
    results = [notify_assignment(db, lote, operator, assigner, total, reassigned, settings.app_url) for operator in operators]
    return {
        "enviados": sum(item["enviados"] for item in results),
        "omitidos": sum(item["omitidos"] for item in results),
        "fallidos": [email for item in results for email in item["fallidos"]],
        "sin_correo": all(item["sin_correo"] for item in results),
        "miembros": [{"operador_id": operator.id, **result} for operator, result in zip(operators, results)],
    }


class AsignarIn(BaseModel):
    relative_path: str
    operador_id: int | None = None
    operador_ids: list[int] = []
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
    pagina: int = Query(1, ge=1),
    tam: int = Query(5, ge=1, le=20),
    user: User = Depends(require_supervisor),
    db: Session = Depends(get_db),
):
    base = raiz_origen(db)
    current = lote_service.absolute_path(db, path) if path else base
    if not os.path.isdir(current):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El directorio no existe.")
    all_dirs = fs.listar_dirs(current)
    total = len(all_dirs)
    start = (pagina - 1) * tam
    page_dirs = all_dirs[start:start + tam]
    result = []
    for name in page_dirs:
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
    return {
        "actual": lote_service.relative_path(base, current) if current != base else "",
        "items": result,
        "pagina": pagina,
        "tam": tam,
        "total": total,
    }


@router.get("")
def listar(
    scope: str = "mine",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Lote)
    if user.rol == "usuario" or scope == "mine":
        q = q.join(LoteOperador).filter(LoteOperador.operador_id == user.id, LoteOperador.activo.is_(True))
    elif scope in ("supervision", "archived") and user.rol in ("supervisor", "administrador"):
        q = q.filter(Lote.operador_id.is_not(None))
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bandeja no válida.")
    rows = q.order_by(Lote.assigned_at.desc(), Lote.nombre).all()
    result = [lote_service.serialize(db, lote) for lote in rows]
    if scope == "mine":
        result = [item for item in result if item["estado"] != "notificado"]
    elif scope == "supervision":
        result = [item for item in result if item["estado"] != "notificado"]
    elif scope == "archived":
        result = [item for item in result if item["estado"] == "notificado"]
    db.commit()
    return result


@router.get("/counts")
def counts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mine = db.query(Lote).join(LoteOperador).filter(LoteOperador.operador_id == user.id, LoteOperador.activo.is_(True)).all()
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
        operator_lots = db.query(Lote).join(LoteOperador).filter(LoteOperador.operador_id == operator.id, LoteOperador.activo.is_(True)).all()
        shared_stats = [lote_service.metricas(db, lote) for lote in operator_lots]
        realizados = db.query(LoteDocumento).filter(LoteDocumento.completed_by == operator.id, LoteDocumento.estado == "completado", LoteDocumento.presente.is_(True)).count()
        errores = db.query(LoteDocumento).filter(LoteDocumento.completed_by == operator.id, LoteDocumento.estado == "error", LoteDocumento.presente.is_(True)).count()
        totals = {"total": sum(item["total"] for item in shared_stats), "realizados": realizados, "errores": errores, "pendientes": sum(item["pendientes"] for item in shared_stats)}
        completed_lots = sum(1 for item in shared_stats if item["total"] and item["pendientes"] == 0)
        recent = db.query(ExtraccionVersion).filter(ExtraccionVersion.autor_id == operator.id, ExtraccionVersion.created_at >= since).all()
        version_count = db.query(ExtraccionVersion).filter(ExtraccionVersion.autor_id == operator.id).count()
        progress = round((totals["total"] - totals["pendientes"]) * 100 / totals["total"]) if totals["total"] else 0
        result.append({
            "id": operator.id,
            "username": operator.username,
            "nombre": operator.nombre,
            "lotes_asignados": len(operator_lots),
            "lotes_completados": completed_lots,
            **totals,
            "porcentaje": progress,
            "realizados_30_dias": len(recent),
            "versiones": version_count,
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
    operator_ids = list(dict.fromkeys(body.operador_ids or ([body.operador_id] if body.operador_id else [])))
    operators = db.query(User).filter(User.id.in_(operator_ids)).all() if operator_ids else []
    if not operator_ids or len(operators) != len(operator_ids) or any(item.rol not in ("usuario", "supervisor") or item.estado != "activo" for item in operators):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El operador no es válido o está inactivo.")
    operators_by_id = {item.id: item for item in operators}
    operator = operators_by_id[operator_ids[0]]
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
    memberships = db.query(LoteOperador).filter(LoteOperador.lote_id == lote.id).with_for_update().all()
    documents = db.query(LoteDocumento).filter(LoteDocumento.lote_id == lote.id).with_for_update().all()
    active_ids = {row.operador_id for row in memberships if row.activo}
    same_operator = active_ids == set(operator_ids)
    if same_operator:
        token = str(uuid4())
        lote.notification_token = token
        lote.notification_started_at = now
        stats = lote_service.sync_estado(db, lote)
        db.commit()
        try:
            notification = _notify_members(db, lote, [operators_by_id[item] for item in operator_ids], user, stats["total"], False)
        finally:
            locked = db.query(Lote).filter(Lote.id == lote.id).with_for_update().first()
            if locked and locked.notification_token == token:
                locked.notification_token = None
                locked.notification_started_at = None
                db.commit()
        db.expire(lote, ["miembros"])
        return {"ok": True, "lote": lote_service.serialize(db, lote), "reasignado": False, "sin_cambios": True, "notificacion": notification}
    removed_ids = active_ids - set(operator_ids)
    for document in documents:
        if document.reservado_por in removed_ids:
            lote_service.clear_lease(document)
            if document.estado == "procesando": document.estado = "pendiente"
    for membership in memberships:
        should_be_active = membership.operador_id in operator_ids
        if membership.activo and not should_be_active:
            membership.activo, membership.unassigned_at = False, now
            db.query(LoteAsignacionHistorial).filter(LoteAsignacionHistorial.lote_id == lote.id, LoteAsignacionHistorial.operador_id == membership.operador_id, LoteAsignacionHistorial.unassigned_at.is_(None)).update({LoteAsignacionHistorial.unassigned_at: now, LoteAsignacionHistorial.completed_at: lote.completed_at, LoteAsignacionHistorial.notified_at: lote.notified_at}, synchronize_session=False)
        elif should_be_active and not membership.activo:
            membership.activo, membership.unassigned_at = True, None
            membership.assigned_at, membership.asignado_por_id = now, user.id
            db.add(LoteAsignacionHistorial(lote_id=lote.id, operador_id=membership.operador_id, asignado_por_id=user.id, assigned_at=now, motivo=body.motivo.strip() or None))
    existing_ids = {row.operador_id for row in lote.miembros}
    for operator_id in operator_ids:
        if operator_id not in existing_ids:
            db.add(LoteOperador(lote_id=lote.id, operador_id=operator_id, asignado_por_id=user.id, assigned_at=now))
            db.add(LoteAsignacionHistorial(lote_id=lote.id, operador_id=operator_id, asignado_por_id=user.id, assigned_at=now, motivo=body.motivo.strip() or None))
    lote.operador_id = operator.id
    lote.asignado_por_id = user.id
    lote.assigned_at = now
    lote.notified_at = None
    lote.completed_at = None
    lote.estado = "asignado"
    token = str(uuid4())
    lote.notification_token = token
    lote.notification_started_at = now
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
        notification = _notify_members(db, lote, [operators_by_id[item] for item in operator_ids], user, stats["total"], reassigned)
    finally:
        locked = db.query(Lote).filter(Lote.id == lote.id).with_for_update().first()
        if locked and locked.notification_token == token:
            locked.notification_token = None
            locked.notification_started_at = None
            db.commit()
    db.expire(lote, ["miembros"])
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
    if not lote_service.is_member(db, lote.id, user.id) and user.rol == "usuario":
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


@router.get("/{lote_id}/archive-summary")
def archive_summary(
    lote_id: int,
    user: User = Depends(require_supervisor),
    db: Session = Depends(get_db),
):
    lote = db.get(Lote, lote_id)
    if not lote:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lote no encontrado.")
    serialized = lote_service.serialize(db, lote)
    if serialized["estado"] != "notificado":
        raise HTTPException(status.HTTP_409_CONFLICT, "El lote no está archivado.")

    extractions = db.query(Extraccion).filter(Extraccion.lote_id == lote.id).all()
    versions = db.query(ExtraccionVersion).join(LoteDocumento, ExtraccionVersion.documento_id == LoteDocumento.id).filter(LoteDocumento.lote_id == lote.id).all()
    errors = db.query(TramiteError).filter(TramiteError.lote_id == lote.id).all()
    user_ids = {item.user_id for item in extractions} | {item.autor_id for item in versions} | {item.user_id for item in errors}
    users = {item.id: item for item in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    by_user: dict[int, dict] = {}
    for extraction in extractions:
        entry = by_user.setdefault(extraction.user_id, {"realizados": 0, "versiones": 0, "paginas": 0, "paginas_versionadas": 0, "errores": 0})
        entry["realizados"] += 1
        entry["paginas"] += max(0, extraction.pagina_fin - extraction.pagina_inicio + 1)
    for version in versions:
        entry = by_user.setdefault(version.autor_id, {"realizados": 0, "versiones": 0, "paginas": 0, "paginas_versionadas": 0, "errores": 0})
        entry["versiones"] += 1
        entry["paginas_versionadas"] += max(0, version.pagina_fin - version.pagina_inicio + 1)
    for error in errors:
        by_user.setdefault(error.user_id, {"realizados": 0, "versiones": 0, "paginas": 0, "paginas_versionadas": 0, "errores": 0})["errores"] += 1

    history = (
        db.query(LoteAsignacionHistorial)
        .filter(LoteAsignacionHistorial.lote_id == lote.id)
        .order_by(LoteAsignacionHistorial.assigned_at)
        .all()
    )
    history_user_ids = {row.operador_id for row in history} | {row.asignado_por_id for row in history if row.asignado_por_id}
    history_users = {item.id: item for item in db.query(User).filter(User.id.in_(history_user_ids)).all()} if history_user_ids else {}
    notifications = (
        db.query(Notificacion)
        .filter(Notificacion.lote_id == lote.id)
        .order_by(Notificacion.created_at)
        .all()
    )
    processed_dates = [item.created_at for item in versions if item.created_at] or [item.processed_at for item in extractions if item.processed_at]
    attention_seconds = None
    if lote.assigned_at and lote.notified_at:
        attention_seconds = max(0, int((lote.notified_at - lote.assigned_at).total_seconds()))

    return {
        "lote": serialized,
        "resumen": {
            "extracciones": len(extractions),
            "versiones": len(versions),
            "reextracciones": sum(1 for item in versions if item.tipo == "rehecho"),
            "errores": serialized["metricas"]["errores"],
            "paginas_extraidas": sum(max(0, item.pagina_fin - item.pagina_inicio + 1) for item in versions),
            "primer_procesamiento": min(processed_dates).isoformat() if processed_dates else None,
            "ultimo_procesamiento": max(processed_dates).isoformat() if processed_dates else None,
            "duracion_atencion_segundos": attention_seconds,
        },
        "participantes": [
            {
                "id": user_id,
                "username": users[user_id].username if user_id in users else "usuario eliminado",
                "nombre": users[user_id].nombre if user_id in users else "",
                **stats,
            }
            for user_id, stats in sorted(by_user.items())
        ],
        "historial": [
            {
                "id": row.id,
                "operador": (history_users[row.operador_id].nombre or history_users[row.operador_id].username) if row.operador_id in history_users else "Usuario eliminado",
                "asignado_por": (history_users[row.asignado_por_id].nombre or history_users[row.asignado_por_id].username) if row.asignado_por_id in history_users else None,
                "assigned_at": row.assigned_at.isoformat(),
                "unassigned_at": row.unassigned_at.isoformat() if row.unassigned_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                "notified_at": row.notified_at.isoformat() if row.notified_at else None,
                "motivo": row.motivo,
            }
            for row in history
        ],
        "notificaciones": [
            {
                "tipo": item.tipo.split(":", 1)[0],
                "destinatario": item.destinatario,
                "estado": item.estado,
                "intentos": item.intentos,
                "sent_at": item.sent_at.isoformat() if item.sent_at else None,
            }
            for item in notifications
        ],
    }


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
    memberships = db.query(LoteOperador).filter(LoteOperador.lote_id == lote.id, LoteOperador.activo.is_(True)).with_for_update().all()
    documents = db.query(LoteDocumento).filter(LoteDocumento.lote_id == lote.id).with_for_update().all()
    if lote.operador_id is None and not memberships:
        return {"ok": True, "sin_cambios": True, "lote": lote_service.serialize(db, lote)}
    for document in documents:
        lote_service.clear_lease(document)
        if document.estado == "procesando": document.estado = "pendiente"
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
    db.query(LoteOperador).filter(LoteOperador.lote_id == lote.id, LoteOperador.activo.is_(True)).update({LoteOperador.activo: False, LoteOperador.unassigned_at: now}, synchronize_session=False)
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
    db.query(AssignmentLock).filter(AssignmentLock.clave == "global").with_for_update().one()
    lote = db.query(Lote).filter(Lote.id == lote_id).with_for_update().first()
    if not lote:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lote no encontrado.")
    if not lote_service.is_member(db, lote.id, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Lote no asignado al usuario.")
    if not lote.operador:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El lote no tiene operador asignado.")
    now = datetime.now()
    if _lease_active(lote, now):
        raise HTTPException(status.HTTP_409_CONFLICT, "El lote está enviando otra notificación. Intente en unos minutos.")
    stats = lote_service.sync_estado(db, lote)
    active_leases = db.query(LoteDocumento.id).filter(LoteDocumento.lote_id == lote.id, LoteDocumento.lease_expires_at > now).first()
    if stats["total"] == 0 or stats["pendientes"] > 0 or active_leases:
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "El lote todavía tiene archivos pendientes.")
    token = str(uuid4())
    lote.notification_token = token
    lote.notification_started_at = now
    operator = lote.operador
    assignment_at = lote.assigned_at
    member_ids = {row.operador_id for row in db.query(LoteOperador).filter(LoteOperador.lote_id == lote.id, LoteOperador.activo.is_(True)).all()}
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
        team = [row.operador for row in db.query(LoteOperador).filter(LoteOperador.lote_id == lote.id, LoteOperador.activo.is_(True)).all()]
        result = notify_completion(db, lote, team, recipients, stats, settings.app_url)
    finally:
        db.query(AssignmentLock).filter(AssignmentLock.clave == "global").with_for_update().one()
        locked = db.query(Lote).filter(Lote.id == lote_id).with_for_update().first()
        if locked and locked.notification_token == token:
            current_stats = lote_service.sync_estado(db, locked)
            current_active_leases = db.query(LoteDocumento.id).filter(LoteDocumento.lote_id == locked.id, LoteDocumento.lease_expires_at > datetime.now()).first()
            current_member_ids = {row.operador_id for row in db.query(LoteOperador).filter(LoteOperador.lote_id == locked.id, LoteOperador.activo.is_(True)).all()}
            assignment_unchanged = locked.operador_id == operator.id and locked.assigned_at == assignment_at and current_member_ids == member_ids
            if 'result' in locals() and not result["fallidos"] and assignment_unchanged and not current_active_leases and current_stats["total"] > 0 and current_stats["pendientes"] == 0:
                locked.estado = "notificado"
                locked.notified_at = datetime.now()
                db.query(LoteAsignacionHistorial).filter(LoteAsignacionHistorial.lote_id == locked.id, LoteAsignacionHistorial.unassigned_at.is_(None)).update({
                    LoteAsignacionHistorial.completed_at: locked.completed_at,
                    LoteAsignacionHistorial.notified_at: locked.notified_at,
                }, synchronize_session=False)
            locked.notification_token = None
            locked.notification_started_at = None
            db.commit()
    return {"ok": not result["fallidos"], "notificacion": result, "lote": lote_service.serialize(db, locked)}


class LeaseIn(BaseModel):
    lease_token: str = ""


@router.post("/documentos/{documento_id}/claim")
def claim(documento_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db), _: None = Depends(require_csrf)):
    documento, token = lote_service.claim_document(db, documento_id, user.id)
    db.commit()
    return {"documento_id": documento.id, "lease_token": token, "lease_expires_at": documento.lease_expires_at.isoformat()}


@router.post("/documentos/{documento_id}/heartbeat")
def heartbeat(documento_id: int, body: LeaseIn, user: User = Depends(get_current_user), db: Session = Depends(get_db), _: None = Depends(require_csrf)):
    documento = db.query(LoteDocumento).filter(LoteDocumento.id == documento_id).with_for_update().first()
    if not documento: raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado.")
    lote_service.require_member(db, documento.lote_id, user.id)
    lote_service.validate_lease(documento, user.id, body.lease_token)
    documento.lease_expires_at = datetime.now() + timedelta(minutes=10)
    db.commit()
    return {"ok": True, "lease_expires_at": documento.lease_expires_at.isoformat()}


@router.post("/documentos/{documento_id}/release")
def release(documento_id: int, body: LeaseIn, user: User = Depends(get_current_user), db: Session = Depends(get_db), _: None = Depends(require_csrf)):
    documento = db.query(LoteDocumento).filter(LoteDocumento.id == documento_id).with_for_update().first()
    if not documento: raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado.")
    lote_service.require_member(db, documento.lote_id, user.id)
    lote_service.validate_lease(documento, user.id, body.lease_token)
    lote_service.clear_lease(documento)
    if documento.estado == "procesando": documento.estado = "pendiente"
    db.commit()
    return {"ok": True}
