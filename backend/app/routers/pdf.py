"""Servir PDF (original, extraído, temporal) confinado a su raíz."""
import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.deps import get_current_user
from ..db.database import get_db
from ..db.models import User
from ..services import fs
from ..services.pdf import pdf_response
from ..services.repo import raiz_origen, raiz_repo

router = APIRouter(prefix="/api/pdf", tags=["pdf"])


@router.get("/{tipo}")
def get_pdf(
    tipo: str,
    ruta: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    roots = {
        "original": raiz_origen(db),
        "extraido": raiz_repo(db),
        "temp": fs.normalizar(str(settings.temp_dir)),
    }
    root = roots.get(tipo)
    if root is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tipo de PDF no válido.")

    real = fs.confinar(root, ruta)
    if real is None or not os.path.isfile(real):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF no encontrado.")
    if not real.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo se permiten archivos PDF.")

    return pdf_response(real)