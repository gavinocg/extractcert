"""Configuración admin: rutas origen/destino (settings)."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import require_admin, require_csrf, get_current_user
from ..db.database import get_db
from ..db.models import User
from ..services import repo

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {
        "raiz_origen": repo.raiz_origen(db),
        "raiz_repo": repo.raiz_repo(db),
    }


class SettingsIn(BaseModel):
    raiz_origen: str
    raiz_repo: str


@router.put("")
def update_settings(
    body: SettingsIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    repo.set_setting(db, "raiz_origen", body.raiz_origen.strip())
    repo.set_setting(db, "raiz_repo", body.raiz_repo.strip())
    return {"ok": True, "raiz_origen": body.raiz_origen.strip(), "raiz_repo": body.raiz_repo.strip()}