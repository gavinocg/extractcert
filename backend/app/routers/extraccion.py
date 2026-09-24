"""Extracción: previsualización temporal y confirmación (guardar)."""
import os
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, require_csrf
from ..db.database import get_db
from ..db.models import AssignmentLock, Extraccion, TramiteError, User
from ..services import fs
from ..services.lotes import document_key, require_path_access
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
    inicio: int
    fin: int
    rotacion: int = 0


class GuardarIn(OrigIn):
    reextra: int = 0
    extraccion_id: int = 0
    nombre: str = ""


def _validar_origen(ruta: str, db: Session, user: User) -> tuple[str, int | None]:
    original = fs.confinar(raiz_origen(db), ruta)
    if original is None or not os.path.isfile(original):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El PDF original no existe.")
    if not original.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo se permiten archivos PDF.")
    lote = require_path_access(db, user, original)
    return original, lote.id if lote else None


@router.post("/preview")
def preview(
    body: OrigIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    if body.inicio < 1 or body.fin < body.inicio:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Parámetros inválidos.")
    original, _ = _validar_origen(body.ruta, db, user)

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
    original, lote_id = _validar_origen(body.ruta, db, user)

    # La misma fila serializa extracción con reasignación/liberación. Es estable
    # entre procesos y evita que un trabajo autorizado continúe tras un cambio.
    db.query(AssignmentLock).filter(AssignmentLock.clave == "global").with_for_update().one()
    original, locked_lote_id = _validar_origen(body.ruta, db, user)
    if locked_lote_id != lote_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "La asignación del lote cambió durante la extracción.")
    lote_id = locked_lote_id
    original_key = document_key(lote_id, original)

    destino: str | None = None
    estado = "realizado"
    reg = None

    if body.reextra:
        q = db.query(Extraccion)
        if body.extraccion_id:
            q = q.filter(Extraccion.id == body.extraccion_id)
        else:
            q = q.filter(Extraccion.original_key == original_key).order_by(Extraccion.created_at.desc())
        reg = q.with_for_update().first()
        if not reg:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe una extracción previa.")
        if document_key(reg.lote_id, reg.original_path) != original_key:
            raise HTTPException(status.HTTP_409_CONFLICT, "La extracción previa no pertenece al documento actual.")
        destino = reg.destino_path
        estado = "rehecho"
    else:
        db.query(Extraccion).filter(Extraccion.original_key == original_key).with_for_update().all()
        repo = raiz_repo(db)
        if not os.path.isdir(repo):
            os.makedirs(repo, exist_ok=True)
        if not os.access(repo, os.W_OK):
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Destino no escribible.")
        pedido = os.path.basename(body.nombre.strip()) if body.nombre else ""
        if pedido and not pedido.lower().endswith(".pdf"):
            pedido += ".pdf"
        if len(pedido) > 255:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nombre demasiado largo.")
        base = pedido or os.path.basename(original)
        while True:
            destino = fs.unir(repo, generar_nombre_sin_colision(repo, base))
            try:
                fd = os.open(destino, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                break
            except FileExistsError:
                continue

    rot2 = int(body.rotacion) % 360 if hasattr(body, 'rotacion') else 0
    temp_output = f"{destino}.tmp-{uuid4().hex}"
    backup = None
    installed = False
    committed = False
    try:
        extraer_paginas(original, body.inicio, body.fin, temp_output, rotacion=rot2)
        if not os.path.isfile(temp_output) or os.path.getsize(temp_output) == 0:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "No se pudo generar el archivo.")
        if reg is not None and os.path.isfile(destino):
            backup = f"{destino}.bak-{uuid4().hex}"
            os.replace(destino, backup)
        os.replace(temp_output, destino)
        installed = True

        if reg is not None:
            reg.pagina_inicio = body.inicio
            reg.pagina_fin = body.fin
            reg.estado = estado
            reg.user_id = user.id
            reg.lote_id = lote_id
            reg.processed_at = datetime.now()
            nuevo_id = reg.id
        else:
            db.query(Extraccion).filter(Extraccion.original_key == original_key).delete()
            e = Extraccion(
                user_id=user.id,
                lote_id=lote_id,
                original_path=original,
                original_key=original_key,
                destino_path=destino,
                pagina_inicio=body.inicio,
                pagina_fin=body.fin,
                estado=estado,
            )
            db.add(e)
            db.flush()
            nuevo_id = e.id
        db.query(TramiteError).filter(TramiteError.original_path == original).delete()
        # Revalida bajo el lock inmediatamente antes del commit.
        _, current_lote_id = _validar_origen(body.ruta, db, user)
        if current_lote_id != lote_id:
            raise HTTPException(status.HTTP_409_CONFLICT, "La asignación del lote cambió durante la extracción.")
        db.commit()
        committed = True
    except Exception:
        if committed:
            raise
        db.rollback()
        if os.path.exists(temp_output):
            os.remove(temp_output)
        if backup and os.path.exists(backup):
            if installed and os.path.exists(destino):
                os.remove(destino)
            os.replace(backup, destino)
        elif installed and os.path.exists(destino):
            os.remove(destino)
        elif reg is None and os.path.exists(destino):
            os.remove(destino)
        raise

    # El archivo y la fila ya son definitivos. Un fallo de limpieza no debe
    # compensar una transacción confirmada ni convertir el éxito en error.
    if backup and os.path.exists(backup):
        try:
            os.remove(backup)
        except OSError:
            pass

    return {
        "ok": True,
        "extraccion_id": nuevo_id,
        "destino": destino,
        "nombre": os.path.basename(destino),
        "estado": estado,
        "paginas": body.fin - body.inicio + 1,
    }
