"""Reglas de lotes, métricas dinámicas y acceso por asignación."""
import os
import secrets
from hashlib import sha256
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db.models import Extraccion, ExtraccionVersion, Lote, LoteDocumento, LoteOperador, TramiteError, User
from . import fs
from .repo import raiz_origen


def relative_path(base: str, path: str) -> str:
    return fs.normalizar(os.path.relpath(os.path.realpath(path), os.path.realpath(base)))


def document_key(lote_id: int | None, path: str) -> str:
    filename = fs.filename_key(os.path.basename(fs.normalizar(path)))
    return sha256(f"{lote_id or 0}:{filename}".encode("utf-8")).hexdigest()


def absolute_path(db: Session, relative: str) -> str:
    base = raiz_origen(db)
    # Acepta rutas relativas actuales y rutas absolutas conservadas por pestañas antiguas.
    path = fs.confinar(base, relative)
    if path is None:
        path = fs.confinar(base, fs.unir(base, relative))
    if path is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ruta de lote no permitida.")
    return path


def lote_for_directory(db: Session, path: str) -> Lote | None:
    base = raiz_origen(db)
    confined = fs.confinar(base, path)
    if confined is None:
        return None
    return db.query(Lote).filter(Lote.relative_path == relative_path(base, confined)).first()


def lote_for_document(db: Session, path: str) -> Lote | None:
    return lote_for_directory(db, os.path.dirname(path))


def require_path_access(db: Session, user: User, path: str) -> Lote | None:
    lote = lote_for_document(db, path)
    if lote is None:
        if user.rol in ("supervisor", "administrador"):
            return None
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El PDF no pertenece a un lote asignado.")
    if not is_member(db, lote.id, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El PDF no pertenece a un lote asignado.")
    return lote


def require_directory_access(db: Session, user: User, path: str) -> Lote | None:
    lote = lote_for_directory(db, path)
    if lote is None:
        if user.rol in ("supervisor", "administrador"):
            return None
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El lote no está asignado al usuario.")
    if not is_member(db, lote.id, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El lote no está asignado al usuario.")
    return lote


def is_member(db: Session, lote_id: int, user_id: int) -> bool:
    return db.query(LoteOperador.id).filter(LoteOperador.lote_id == lote_id, LoteOperador.operador_id == user_id, LoteOperador.activo.is_(True)).first() is not None


def require_member(db: Session, lote_id: int, user_id: int) -> None:
    if not is_member(db, lote_id, user_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El usuario no es miembro activo del lote.")


def sync_documentos(db: Session, lote: Lote) -> list[LoteDocumento]:
    if lote.id is None:
        raise ValueError("sync_documentos requiere un lote persistido")
    # Las métricas y el dashboard pueden sincronizar el mismo lote en paralelo.
    # El índice único + savepoint protegen la creación sin bloquear lotes en
    # distinto orden, evitando deadlocks entre Supervisión y Productividad.
    lote = db.query(Lote).filter(Lote.id == lote.id).one()
    directory = absolute_path(db, lote.relative_path)
    names = fs.listar_pdfs(directory) if os.path.isdir(directory) else []
    rows = {row.document_key: row for row in db.query(LoteDocumento).filter(LoteDocumento.lote_id == lote.id).all()}
    extraction_by_key = {
        document_key(lote.id, item.original_path): item
        for item in db.query(Extraccion).filter(Extraccion.lote_id == lote.id).order_by(Extraccion.processed_at).all()
    }
    error_by_key = {
        document_key(lote.id, item.original_path): item
        for item in db.query(TramiteError).filter(TramiteError.lote_id == lote.id).order_by(TramiteError.updated_at).all()
    }
    current = set()
    for name in names:
        path = fs.normalizar(os.path.abspath(os.path.join(directory, name)))
        key = document_key(lote.id, path)
        current.add(key)
        row = rows.get(key)
        if row is None:
            try:
                with db.begin_nested():
                    row = LoteDocumento(lote_id=lote.id, document_key=key, relative_path=name, nombre=name)
                    db.add(row)
                    db.flush()
            except IntegrityError:
                row = db.query(LoteDocumento).filter(LoteDocumento.lote_id == lote.id, LoteDocumento.document_key == key).with_for_update().one()
            rows[key] = row
        row.relative_path, row.nombre, row.presente = name, name, True
        stat = os.stat(path)
        replaced = row.source_size is not None and (row.source_size != stat.st_size or row.source_mtime_ns != stat.st_mtime_ns)
        row.source_size, row.source_mtime_ns = stat.st_size, stat.st_mtime_ns
        extraction = db.query(Extraccion).filter(Extraccion.documento_id == row.id).order_by(Extraccion.processed_at.desc()).first() or extraction_by_key.get(key)
        error = db.query(TramiteError).filter(TramiteError.documento_id == row.id).first() or error_by_key.get(key)
        source_mtime = datetime.fromtimestamp(stat.st_mtime)
        if replaced:
            clear_lease(row)
            row.estado, row.completed_by, row.completed_at = "pendiente", None, None
        if extraction and extraction.processed_at and extraction.processed_at < source_mtime:
            extraction = None
        if error and error.updated_at and error.updated_at < source_mtime:
            error = None
        if extraction:
            extraction.documento_id = row.id
            legacy_key = f"legacy:{extraction.id}"
            if not db.query(ExtraccionVersion.id).filter(ExtraccionVersion.extraccion_id == extraction.id, ExtraccionVersion.version == 1).first():
                db.add(ExtraccionVersion(
                    extraccion_id=extraction.id,
                    documento_id=row.id,
                    version=1,
                    autor_id=extraction.user_id,
                    pagina_inicio=extraction.pagina_inicio,
                    pagina_fin=extraction.pagina_fin,
                    destino_path=extraction.destino_path,
                    tipo=extraction.estado,
                    idempotency_key=legacy_key,
                    created_at=extraction.processed_at,
                ))
            row.estado, row.completed_by, row.completed_at = "completado", extraction.user_id, extraction.processed_at
            row.version = max(row.version, 1)
        elif error:
            error.documento_id = row.id
            row.estado, row.completed_by, row.completed_at = "error", error.user_id, error.updated_at
        elif row.estado in ("completado", "error"):
            row.estado, row.completed_by, row.completed_at = "pendiente", None, None
    for key, row in rows.items():
        if key not in current:
            row.presente = False
            if row.estado in ("pendiente", "procesando"):
                row.estado = "ausente"
            clear_lease(row)
    db.flush()
    return list(rows.values())


def clear_lease(documento: LoteDocumento) -> None:
    documento.reservado_por = None
    documento.lease_token = None
    documento.reservado_at = None
    documento.lease_expires_at = None


def validate_lease(documento: LoteDocumento, user_id: int, token: str) -> None:
    if not token or documento.reservado_por != user_id or documento.lease_token != token or not documento.lease_expires_at or documento.lease_expires_at <= datetime.now():
        raise HTTPException(status.HTTP_409_CONFLICT, "El lease no existe, venció o pertenece a otro operador.")


def claim_document(db: Session, documento_id: int, user_id: int) -> tuple[LoteDocumento, str]:
    documento = db.query(LoteDocumento).filter(LoteDocumento.id == documento_id).with_for_update().first()
    if not documento or not documento.presente:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado.")
    require_member(db, documento.lote_id, user_id)
    now = datetime.now()
    if documento.lease_expires_at and documento.lease_expires_at > now:
        if documento.reservado_por == user_id:
            detail = "Este archivo ya está siendo procesado en otra ventana de su usuario. Cierre esa ventana o seleccione otro archivo."
        else:
            owner = db.get(User, documento.reservado_por) if documento.reservado_por else None
            name = (owner.nombre or owner.username) if owner else "otro usuario"
            detail = f"Este archivo está siendo procesado por {name}. Seleccione otro archivo."
        raise HTTPException(status.HTTP_409_CONFLICT, detail)
    token = secrets.token_urlsafe(32)
    documento.reservado_por, documento.lease_token = user_id, token
    documento.reservado_at, documento.lease_expires_at = now, now + timedelta(minutes=10)
    if documento.estado == "pendiente": documento.estado = "procesando"
    return documento, token


def metricas(db: Session, lote: Lote) -> dict:
    documents = [row for row in sync_documentos(db, lote) if row.presente]
    total = len(documents)
    realizados = sum(row.estado == "completado" for row in documents)
    errores = sum(row.estado == "error" for row in documents)
    pendientes = max(0, total - realizados - errores)
    porcentaje = round((realizados + errores) * 100 / total) if total else 0
    return {
        "total": total,
        "realizados": realizados,
        "errores": errores,
        "pendientes": pendientes,
        "porcentaje": porcentaje,
    }


def metricas_directorio(db: Session, relative: str, nombre: str = "") -> dict:
    lote = db.query(Lote).filter(Lote.relative_path == relative).first()
    if lote is not None:
        return metricas(db, lote)
    directory = absolute_path(db, relative)
    names = fs.listar_pdfs(directory) if os.path.isdir(directory) else []
    keys = {fs.filename_key(name) for name in names}
    prefix = fs.like_prefix(directory)
    extracted = {fs.filename_key(os.path.basename(fs.normalizar(path))) for (path,) in db.query(Extraccion.original_path).filter(Extraccion.original_path.like(prefix, escape="\\")).all()} & keys
    errors = {fs.filename_key(os.path.basename(fs.normalizar(path))) for (path,) in db.query(TramiteError.original_path).filter(TramiteError.original_path.like(prefix, escape="\\")).all()} & keys
    errors -= extracted
    total = len(keys)
    realizados, errores = len(extracted), len(errors)
    pendientes = max(0, total - realizados - errores)
    return {"total": total, "realizados": realizados, "errores": errores, "pendientes": pendientes, "porcentaje": round((realizados + errores) * 100 / total) if total else 0}


def sync_estado(db: Session, lote: Lote, stats: dict | None = None) -> dict:
    stats = stats or metricas(db, lote)
    now = datetime.now()
    if stats["total"] > 0 and stats["pendientes"] == 0:
        if lote.estado not in ("completado", "notificado"):
            lote.estado = "completado"
            lote.completed_at = now
    elif lote.operador_id:
        if lote.estado in ("completado", "notificado"):
            lote.notified_at = None
        lote.estado = "en_progreso" if stats["realizados"] + stats["errores"] else "asignado"
        lote.completed_at = None
    else:
        lote.estado = "sin_asignar"
    return stats


def serialize(db: Session, lote: Lote) -> dict:
    stats = sync_estado(db, lote)
    return {
        "id": lote.id,
        "nombre": lote.nombre,
        "relative_path": lote.relative_path,
        "operador": ({"id": lote.operador.id, "username": lote.operador.username, "nombre": lote.operador.nombre} if lote.operador else None),
        "operadores": [{"id": m.operador.id, "username": m.operador.username, "nombre": m.operador.nombre} for m in lote.miembros if m.activo],
        "asignado_por": ({"id": lote.asignado_por.id, "username": lote.asignado_por.username, "nombre": lote.asignado_por.nombre} if lote.asignado_por else None),
        "estado": lote.estado,
        "assigned_at": lote.assigned_at.isoformat() if lote.assigned_at else None,
        "completed_at": lote.completed_at.isoformat() if lote.completed_at else None,
        "notified_at": lote.notified_at.isoformat() if lote.notified_at else None,
        "metricas": stats,
    }
