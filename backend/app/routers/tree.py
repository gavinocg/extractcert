"""Árbol de archivos del directorio de origen."""
import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..db.database import get_db
from ..db.models import Extraccion, TramiteError, User
from ..services import fs
from ..services.repo import raiz_origen

router = APIRouter(prefix="/api", tags=["tree"])


@router.get("/tree")
def tree(
    path: str | None = None,
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

    dirs = fs.listar_dirs(conf)
    dirs_stats = []
    for d in dirs:
        dir_path = fs.unir(conf, d)
        real_dir = fs.confinar(base, dir_path)
        if real_dir is None or not os.path.isdir(real_dir):
            continue
        pdfs_in = fs.listar_pdfs(real_dir)
        total = len(pdfs_in)
        if total == 0:
            dirs_stats.append({"nombre": d, "total": 0, "realizados": 0, "errores": 0, "pendientes": 0, "pctRealizado": 0, "pctError": 0, "pctPendiente": 0})
            continue
        pref = fs.normalizar(real_dir) + "/%"
        realizados = db.query(Extraccion).filter(Extraccion.original_path.like(pref)).count()
        errores = db.query(TramiteError).filter(TramiteError.original_path.like(pref)).count()
        realizados = min(realizados, total)
        errores = min(errores, total)
        pendientes = max(0, total - realizados - errores)
        # Si un PDF está a la vez realizado y con error, no doble conteo: el error ya implica no realizado, pero mantenemos suma <= total
        if realizados + errores > total:
            # prioriza realizados, ajusta errores
            errores = max(0, total - realizados)
            pendientes = 0
        pctRealizado = round(realizados * 100 / total) if total else 0
        pctError = round(errores * 100 / total) if total else 0
        pctPendiente = max(0, 100 - pctRealizado - pctError)
        dirs_stats.append({"nombre": d, "total": total, "realizados": realizados, "errores": errores, "pendientes": pendientes, "pctRealizado": pctRealizado, "pctError": pctError, "pctPendiente": pctPendiente})

    return {
        "base": base,
        "actual": conf,
        "dirs": dirs,
        "dirs_stats": dirs_stats,
        "pdfs": fs.listar_pdfs(conf),
    }