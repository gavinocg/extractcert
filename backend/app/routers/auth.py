"""Autenticación: login, logout y sesión actual."""
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core import security
from ..core.deps import get_current_user, require_csrf
from ..db.database import get_db
from ..db.models import User
from ..services.security_audit import record

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


def _set_cookies(response: Response, user: User) -> None:
    token = security.create_access_token(str(user.id), user.token_version)
    secure_cookie = security.settings.app_url.lower().startswith("https://")
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="strict",
        secure=secure_cookie,
        max_age=security.settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key="csrf_token",
        value=secrets.token_urlsafe(32),
        httponly=False,
        samesite="strict",
        secure=secure_cookie,
        path="/",
    )


@router.post("/login")
def login(form: LoginIn, response: Response, request: Request, db: Session = Depends(get_db)):
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
    if user.must_change_password:
        record(db, "login_restringido", user.id, user.id, request.client.host if request.client else None)
    return {
        "ok": True,
        "user": {"id": user.id, "username": user.username, "nombre": user.nombre, "email": user.email or "", "rol": user.rol, "must_change_password": user.must_change_password},
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
    return {"id": user.id, "username": user.username, "nombre": user.nombre, "email": user.email or "", "rol": user.rol, "must_change_password": user.must_change_password, "password_changed_at": user.password_changed_at}


class PasswordIn(BaseModel):
    actual: str
    nueva: str


@router.post("/password")
def cambiar_password(
    body: PasswordIn,
    response: Response,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    if not security.verify_password(body.actual, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual es incorrecta.",
        )
    try:
        security.validate_password(body.nueva, user.username, user.password_hash)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    user.password_hash = security.hash_password(body.nueva)
    user.must_change_password = False
    user.password_changed_at = datetime.now()
    user.token_version += 1
    db.commit()
    record(db, "cambio_password", user.id, user.id, request.client.host if request.client else None)
    _set_cookies(response, user)
    return {
        "ok": True,
        "must_change_password": False,
        "user": {
            "id": user.id,
            "username": user.username,
            "nombre": user.nombre,
            "email": user.email or "",
            "rol": user.rol,
            "must_change_password": False,
            "password_changed_at": user.password_changed_at.isoformat(),
        },
    }
