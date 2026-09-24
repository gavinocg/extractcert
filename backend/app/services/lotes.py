"""Reglas de lotes, métricas dinámicas y acceso por asignación."""
import os
from hashlib import sha256
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db.models import Extraccion, Lote, TramiteError, User
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
    if user.rol in ("supervisor", "administrador"):
        return lote_for_document(db, path)
    lote = lote_for_document(db, path)
    if lote is None or lote.operador_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El PDF no pertenece a un lote asignado.")
    return lote


def require_directory_access(db: Session, user: User, path: str) -> Lote | None:
    if user.rol in ("supervisor", "administrador"):
        return lote_for_directory(db, path)
    lote = lote_for_directory(db, path)
    if lote is None or lote.operador_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El lote no está asignado al usuario.")
    return lote


def metricas(db: Session, lote: Lote) -> dict:
    directory = absolute_path(db, lote.relative_path)
    pdf_names = fs.listar_pdfs(directory) if os.path.isdir(directory) else []
    pdf_keys = {fs.filename_key(name) for name in pdf_names}
    current_paths = {fs.normalizar(os.path.abspath(os.path.join(directory, name))) for name in pdf_names}
    configured_directory = fs.unir(raiz_origen(db), lote.relative_path)
    configured_paths = {fs.normalizar(os.path.abspath(os.path.join(configured_directory, name))) for name in pdf_names}
    path_aliases = current_paths | configured_paths
    if path_aliases:
        extraction_filter = Extraccion.original_path.in_(path_aliases)
        error_filter = TramiteError.original_path.in_(path_aliases)
        if lote.id is not None:
            extraction_filter = or_(Extraccion.lote_id == lote.id, extraction_filter)
            error_filter = or_(TramiteError.lote_id == lote.id, error_filter)
        extracted = {
            fs.filename_key(os.path.basename(fs.normalizar(path)))
            for (path,) in db.query(Extraccion.original_path).filter(extraction_filter).all()
        }
        errors = {
            fs.filename_key(os.path.basename(fs.normalizar(path)))
            for (path,) in db.query(TramiteError.original_path).filter(error_filter).all()
        } - extracted
        extracted &= pdf_keys
        errors &= pdf_keys
    else:
        extracted = set()
        errors = set()
    total = len(pdf_keys)
    realizados = len(extracted)
    errores = len(errors)
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
    if lote is None:
        lote = Lote(relative_path=relative, nombre=nombre or os.path.basename(relative))
    return metricas(db, lote)


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
        "asignado_por": ({"id": lote.asignado_por.id, "username": lote.asignado_por.username, "nombre": lote.asignado_por.nombre} if lote.asignado_por else None),
        "estado": lote.estado,
        "assigned_at": lote.assigned_at.isoformat() if lote.assigned_at else None,
        "completed_at": lote.completed_at.isoformat() if lote.completed_at else None,
        "notified_at": lote.notified_at.isoformat() if lote.notified_at else None,
        "metricas": stats,
    }
