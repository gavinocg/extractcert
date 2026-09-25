"""Extracción: previsualización temporal y confirmación (guardar)."""
import os
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..core.deps import get_current_user, require_csrf
from ..db.database import get_db
from ..db.models import AssignmentLock, Extraccion, ExtraccionVersion, Lote, LoteDocumento, TramiteError, User
from ..services import fs
from ..services import lotes as lote_service
from ..services.pdf import extraer_paginas
from ..services.repo import (
    generar_nombre_sin_colision,
    limpiar_temporales,
    new_temp_filename,
    raiz_origen,
    raiz_repo,
)

router = APIRouter(prefix="/api/extracciones", tags=["extraccion"])


class OrigIn(BaseModel):
    ruta: str
    documento_id: int
    lease_token: str
    inicio: int
    fin: int
    rotacion: int = 0


class GuardarIn(OrigIn):
    reextra: int = 0
    extraccion_id: int = 0
    nombre: str = ""
    idempotency_key: str


def _validar_origen(ruta: str, documento_id: int, db: Session, user: User) -> tuple[str, LoteDocumento]:
    original = fs.confinar(raiz_origen(db), ruta)
    if original is None or not os.path.isfile(original):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El PDF original no existe.")
    if not original.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo se permiten archivos PDF.")
    documento = db.get(LoteDocumento, documento_id)
    if not documento or not documento.presente:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado en el inventario.")
    lote_service.require_member(db, documento.lote_id, user.id)
    if lote_service.document_key(documento.lote_id, original) != documento.document_key:
        raise HTTPException(status.HTTP_409_CONFLICT, "La ruta no corresponde al documento indicado.")
    return original, documento


@router.post("/preview")
def preview(
    body: OrigIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    if body.inicio < 1 or body.fin < body.inicio:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Parámetros inválidos.")
    original, documento = _validar_origen(body.ruta, body.documento_id, db, user)
    lote_service.validate_lease(documento, user.id, body.lease_token)

    limpiar_temporales()
    tmp = new_temp_filename(user.id)
    rot = int(body.rotacion) % 360 if hasattr(body, 'rotacion') else 0
    extraer_paginas(original, body.inicio, body.fin, str(tmp), rotacion=rot)
    if not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "No se generó la vista previa.")

    return {
        "ok": True,
        "nombre": os.path.basename(original),
        "paginas": body.fin - body.inicio + 1,
        "url": f"/api/pdf/temp?ruta={fs.normalizar(str(tmp))}",
    }


@router.post("/guardar")
def guardar(
    body: GuardarIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    if body.inicio < 1 or body.fin < body.inicio:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Parámetros inválidos.")
    if not body.idempotency_key.strip() or len(body.idempotency_key) > 100:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Idempotency key obligatoria o demasiado larga.")
    documento = db.get(LoteDocumento, body.documento_id)
    if not documento:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado en el inventario.")
    lote_service.require_member(db, documento.lote_id, user.id)
    previous_version = db.query(ExtraccionVersion).filter(ExtraccionVersion.idempotency_key == body.idempotency_key).first()
    if previous_version:
        if previous_version.documento_id != documento.id or previous_version.autor_id != user.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "La idempotency key pertenece a otra operación.")
        return _version_response(previous_version)
    original, _ = _validar_origen(body.ruta, body.documento_id, db, user)
    db.query(AssignmentLock).filter(AssignmentLock.clave == "global").with_for_update().one()
    db.query(Lote).filter(Lote.id == documento.lote_id).with_for_update().one()
    documento = db.query(LoteDocumento).filter(LoteDocumento.id == body.documento_id).with_for_update().one()
    lote_service.require_member(db, documento.lote_id, user.id)
    previous_version = db.query(ExtraccionVersion).filter(ExtraccionVersion.idempotency_key == body.idempotency_key).first()
    if previous_version:
        if previous_version.documento_id != documento.id or previous_version.autor_id != user.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "La idempotency key pertenece a otra operación.")
        return _version_response(previous_version)
    lote_service.validate_lease(documento, user.id, body.lease_token)
    lote_id = documento.lote_id
    original_key = documento.document_key

    destino: str | None = None
    estado = "realizado"
    reg = None

    reg = db.query(Extraccion).filter(Extraccion.documento_id == documento.id).with_for_update().first()
    if body.reextra and not reg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe una extracción previa.")
    estado = "rehecho" if reg else "realizado"
    version = documento.version + 1
    pedido = os.path.basename(body.nombre.strip()) if body.nombre else os.path.basename(original)
    if not pedido.lower().endswith(".pdf"): pedido += ".pdf"
    if len(pedido) > 255: raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nombre demasiado largo.")
    version_dir = fs.unir(raiz_repo(db), f"lote-{lote_id}", f"documento-{documento.id}", f"v{version}")
    os.makedirs(version_dir, exist_ok=True)
    destino = fs.unir(version_dir, pedido)
    if os.path.exists(destino):
        confirmed = db.query(ExtraccionVersion.id).filter(ExtraccionVersion.documento_id == documento.id, ExtraccionVersion.version == version).first()
        if confirmed:
            raise HTTPException(status.HTTP_409_CONFLICT, "La versión ya está confirmada.")
        os.remove(destino)

    rot2 = int(body.rotacion) % 360 if hasattr(body, 'rotacion') else 0
    temp_output = f"{destino}.tmp-{uuid4().hex}"
    installed = False
    committed = False
    try:
        extraer_paginas(original, body.inicio, body.fin, temp_output, rotacion=rot2)
        if not os.path.isfile(temp_output) or os.path.getsize(temp_output) == 0:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "No se pudo generar el archivo.")
        os.replace(temp_output, destino)
        installed = True

        if reg is not None:
            reg.pagina_inicio = body.inicio
            reg.pagina_fin = body.fin
            reg.estado = estado
            reg.user_id = user.id
            reg.lote_id = lote_id
            reg.processed_at = datetime.now()
            reg.destino_path = destino
            nuevo_id = reg.id
        else:
            db.query(Extraccion).filter(Extraccion.original_key == original_key).delete()
            e = Extraccion(
                user_id=user.id,
                lote_id=lote_id,
                documento_id=documento.id,
                idempotency_key=body.idempotency_key,
                original_path=original,
                original_key=original_key,
                destino_path=destino,
                pagina_inicio=body.inicio,
                pagina_fin=body.fin,
                estado=estado,
                processed_at=datetime.now(),
            )
            db.add(e)
            db.flush()
            nuevo_id = e.id
            reg = e
        documento.version = version
        documento.estado, documento.completed_by, documento.completed_at = "completado", user.id, datetime.now()
        lote_service.clear_lease(documento)
        db.query(TramiteError).filter(TramiteError.documento_id == documento.id).delete()
        saved_version = ExtraccionVersion(extraccion_id=nuevo_id, documento_id=documento.id, version=version, autor_id=user.id, pagina_inicio=body.inicio, pagina_fin=body.fin, destino_path=destino, tipo=estado, idempotency_key=body.idempotency_key)
        db.add(saved_version)
        lote_service.require_member(db, lote_id, user.id)
        db.commit()
        committed = True
    except IntegrityError:
        db.rollback()
        existing = db.query(ExtraccionVersion).filter(ExtraccionVersion.idempotency_key == body.idempotency_key).first()
        if installed and os.path.exists(destino) and (not existing or fs.normalizar(existing.destino_path) != fs.normalizar(destino)):
            os.remove(destino)
        if existing and existing.documento_id == body.documento_id and existing.autor_id == user.id:
            return _version_response(existing)
        raise HTTPException(status.HTTP_409_CONFLICT, "La idempotency key pertenece a otra operación.")
    except Exception:
        if committed:
            raise
        db.rollback()
        if os.path.exists(temp_output):
            os.remove(temp_output)
        if installed and os.path.exists(destino):
            os.remove(destino)
        raise

    # El archivo y la fila ya son definitivos. Un fallo de limpieza no debe
    # compensar una transacción confirmada ni convertir el éxito en error.
    return _version_response(saved_version)


def _response(reg: Extraccion) -> dict:
    return {
        "ok": True,
        "extraccion_id": reg.id,
        "documento_id": reg.documento_id,
        "destino": reg.destino_path,
        "nombre": os.path.basename(reg.destino_path),
        "estado": reg.estado,
        "paginas": reg.pagina_fin - reg.pagina_inicio + 1,
    }


def _version_response(version: ExtraccionVersion) -> dict:
    return {"ok": True, "extraccion_id": version.extraccion_id, "documento_id": version.documento_id, "version": version.version, "destino": version.destino_path, "nombre": os.path.basename(version.destino_path), "estado": version.tipo, "paginas": version.pagina_fin - version.pagina_inicio + 1}
