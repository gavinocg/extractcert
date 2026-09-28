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
    claims = security.decode_access_token(access_token)
    if claims is None:
        raise FORBIDDEN
    try:
        user = db.get(User, int(claims["sub"]))
    except (TypeError, ValueError):
        raise FORBIDDEN
    if not user:
        raise FORBIDDEN
    if user.estado != "activo":
        raise FORBIDDEN
    if claims["ver"] != user.token_version:
        raise FORBIDDEN
    return user


def require_full_access(user: User = Depends(get_current_user)) -> User:
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debe cambiar su contraseña antes de continuar.",
        )
    return user


def require_admin(user: User = Depends(require_full_access)) -> User:
    if user.rol != "administrador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren privilegios de administrador.",
        )
    return user


def require_supervisor(user: User = Depends(require_full_access)) -> User:
    if user.rol not in ("supervisor", "administrador"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren privilegios de supervisor.",
        )
    return user


def require_csrf(
    request: Request,
    csrf_token: str | None = Cookie(default=None),
    x_csrf_token: str | None = Header(default=None),
) -> None:
    if not csrf_token or not x_csrf_token or csrf_token != x_csrf_token:
        raise FORBIDDEN
