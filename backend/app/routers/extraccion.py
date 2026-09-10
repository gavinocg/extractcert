"""Extracción: previsualización temporal y confirmación (guardar)."""
import os

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, require_csrf
from ..db.database import get_db
from ..db.models import Extraccion, User
from ..services import fs
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


def _validar_origen(ruta: str, db: Session) -> str:
    original = fs.confinar(raiz_origen(db), ruta)
    if original is None or not os.path.isfile(original):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El PDF original no existe.")
    if not original.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo se permiten archivos PDF.")
    return original


@router.post("/preview")
def preview(
    body: OrigIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    if body.inicio < 1 or body.fin < body.inicio:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Parámetros inválidos.")
    original = _validar_origen(body.ruta, db)

    limpiar_temporales()
    tmp = new_temp_filename()
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
    original = _validar_origen(body.ruta, db)

    destino: str | None = None
    estado = "realizado"
    reg = None

    if body.reextra:
        q = db.query(Extraccion)
        if body.extraccion_id:
            q = q.filter(Extraccion.id == body.extraccion_id, Extraccion.original_path == original)
        else:
            q = q.filter(Extraccion.original_path == original).order_by(Extraccion.created_at.desc())
        reg = q.first()
        if not reg:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe una extracción previa.")
        destino = reg.destino_path
        estado = "rehecho"
    else:
        db.query(Extraccion).filter(Extraccion.original_path == original).delete()
        repo = raiz_repo(db)
        if not os.path.isdir(repo):
            os.makedirs(repo, exist_ok=True)
        if not os.access(repo, os.W_OK):
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Destino no escribible.")
        destino = fs.unir(repo, generar_nombre_sin_colision(repo, os.path.basename(original)))

    rot2 = int(body.rotacion) % 360 if hasattr(body, 'rotacion') else 0
    extraer_paginas(original, body.inicio, body.fin, destino, rotacion=rot2)
    if not os.path.isfile(destino) or os.path.getsize(destino) == 0:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "No se pudo generar el archivo.")

    if reg is not None:
        reg.pagina_inicio = body.inicio
        reg.pagina_fin = body.fin
        reg.estado = estado
        nuevo_id = reg.id
    else:
        e = Extraccion(
            user_id=user.id,
            original_path=original,
            destino_path=destino,
            pagina_inicio=body.inicio,
            pagina_fin=body.fin,
            estado=estado,
        )
        db.add(e)
        db.flush()
        nuevo_id = e.id
    db.commit()

    return {
        "ok": True,
        "extraccion_id": nuevo_id,
        "destino": destino,
        "nombre": os.path.basename(destino),
        "estado": estado,
        "paginas": body.fin - body.inicio + 1,
    }