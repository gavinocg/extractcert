"""Autenticación: login, logout y sesión actual."""
import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core import security
from ..core.deps import get_current_user, require_csrf
from ..db.database import get_db
from ..db.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


def _set_cookies(response: Response, user: User) -> None:
    token = security.create_access_token(str(user.id))
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="strict",
        secure=False,
        max_age=security.settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key="csrf_token",
        value=secrets.token_urlsafe(32),
        httponly=False,
        samesite="strict",
        secure=False,
        path="/",
    )


@router.post("/login")
def login(form: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not security.verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
        )
    if user.estado != "activo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo. Contacte al administrador.",
        )
    _set_cookies(response, user)
    return {
        "ok": True,
        "user": {"id": user.id, "username": user.username, "rol": user.rol},
    }


@router.post("/logout")
def logout(
    response: Response,
    user: User = Depends(get_current_user),
):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("csrf_token", path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "rol": user.rol}


class PasswordIn(BaseModel):
    actual: str
    nueva: str


@router.post("/password")
def cambiar_password(
    body: PasswordIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    if not security.verify_password(body.actual, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La contraseña actual es incorrecta.",
        )
    nueva = body.nueva.strip()
    if len(nueva) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe tener al menos 4 caracteres.",
        )
    if security.verify_password(nueva, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe ser distinta a la actual.",
        )
    user.password_hash = security.hash_password(nueva)
    db.commit()
    return {"ok": True}