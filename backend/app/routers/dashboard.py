"""Dashboard de una carpeta: pendientes y realizados."""
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..db.database import get_db
from ..db.models import Extraccion, TramiteError, User
from ..services import fs
from ..services.repo import raiz_origen, raiz_repo

router = APIRouter(prefix="/api", tags=["dashboard"])

MAX_TAM = 100


def _natsort_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


@router.get("/dashboard")
def dashboard(
    path: str | None = None,
    pagina: int = Query(1, ge=1),
    tam: int = Query(20, ge=1, le=MAX_TAM),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base = raiz_origen(db)
    ruta = path or base
    conf = fs.confinar(base, ruta)
    if conf is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ruta no permitida.")
    if not os.path.isdir(conf):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El directorio no existe.")

    pref = fs.normalizar(conf) + "/%"

    rows_all = db.query(Extraccion).filter(Extraccion.original_path.like(pref)).all()
    extraidos_map: dict[str, Extraccion] = {fs.normalizar(r.original_path): r for r in rows_all}
    errores_all = db.query(TramiteError).filter(TramiteError.original_path.like(pref)).all()
    errores_map: dict[str, TramiteError] = {fs.normalizar(r.original_path): r for r in errores_all}

    pdfs = fs.listar_pdfs(conf)

    items_all: list[dict] = []
    for f in pdfs:
        ruta_completa = fs.normalizar(os.path.abspath(os.path.join(conf, f)))
        reg = extraidos_map.get(ruta_completa)
        err = errores_map.get(ruta_completa)
        base_item = {
            "nombre": f,
            "ruta": ruta_completa,
            "username": None,
            "fecha": None,
            "error": None,
        }
        if err:
            base_item["error"] = {"id": err.id, "observacion": err.observacion, "username": None}
        if reg:
            base_item.update({"estado": reg.estado, "extraccion_id": reg.id, "destino_path": reg.destino_path, "pagina_inicio": reg.pagina_inicio, "pagina_fin": reg.pagina_fin, "fecha": reg.created_at.isoformat() if reg.created_at else None})
        else:
            base_item.update({"estado": "pendiente", "extraccion_id": None, "destino_path": None, "pagina_inicio": None, "pagina_fin": None, "fecha": err.updated_at.isoformat() if err and err.updated_at else None})
        items_all.append(base_item)

    user_map = {u.id: u.username for u in db.query(User).all()}
    for it in items_all:
        if it["extraccion_id"] is not None:
            reg = extraidos_map.get(it["ruta"])
            if reg:
                it["username"] = user_map.get(reg.user_id)
        if it.get("error"):
            er = errores_map.get(it["ruta"])
            if er:
                it["error"]["username"] = user_map.get(er.user_id)

    items_all.sort(key=lambda it: _natsort_key(it["nombre"]))

    total = len(items_all)
    pendientes_count = sum(1 for it in items_all if it["estado"] == "pendiente")

    first_pendiente = next((i for i, it in enumerate(items_all) if it["estado"] == "pendiente"), None)
    pagina_sugerida = (first_pendiente // tam + 1) if first_pendiente is not None else 1

    start = (pagina - 1) * tam
    items = items_all[start : start + tam]

    pendientes = [it["nombre"] for it in items_all if it["estado"] == "pendiente"]

    rows_q = (
        db.query(Extraccion, User.username)
        .join(User, Extraccion.user_id == User.id)
        .filter(Extraccion.original_path.like(pref))
    )
    total_realizados = rows_q.count()
    rows = (
        rows_q.order_by(Extraccion.created_at.desc(), Extraccion.id.desc())
        .offset((pagina - 1) * tam)
        .limit(tam)
        .all()
    )

    realizados = [
        {
            "id": e.id,
            "archivo": os.path.basename(e.original_path),
            "original_path": e.original_path,
            "destino_path": e.destino_path,
            "destino": os.path.basename(e.destino_path),
            "pagina_inicio": e.pagina_inicio,
            "pagina_fin": e.pagina_fin,
            "estado": e.estado,
            "username": username,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e, username in rows
    ]

    return {
        "origen": conf,
        "repo": raiz_repo(db),
        "pendientes": pendientes,
        "realizados": realizados,
        "total_realizados": total_realizados,
        "pagina": pagina,
        "tam": tam,
        "items": items,
        "total": total,
        "pendientes_count": pendientes_count,
        "pagina_sugerida": pagina_sugerida,
    }
