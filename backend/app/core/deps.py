"""Dependencias FastAPI: usuario actual, roles y CSRF."""
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..core import security
from ..db.database import get_db
from ..db.models import User

UNAUTH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No autenticado",
)
FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Sesión expirada o token inválido.",
)


def get_current_user(
    access_token: str | None = Cookie(default=None),
    csrf_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not access_token:
        raise UNAUTH
    user_id = security.decode_access_token(access_token)
    if user_id is None:
        raise FORBIDDEN
    user = db.get(User, int(user_id))
    if not user:
        raise FORBIDDEN
    if user.estado != "activo":
        raise FORBIDDEN
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.rol != "administrador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren privilegios de administrador.",
        )
    return user


def require_csrf(
    request: Request,
    csrf_token: str | None = Cookie(default=None),
    x_csrf_token: str | None = Header(default=None),
) -> None:
    if not csrf_token or not x_csrf_token or csrf_token != x_csrf_token:
        raise FORBIDDEN