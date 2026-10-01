"""Autenticación: login, logout y sesión actual."""
import logging
import secrets
import threading
import time
from collections import OrderedDict, deque
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core import security
from ..core.deps import get_current_user, require_csrf, require_trusted_origin
from ..db.database import get_db
from ..db.models import User
from ..services.security_audit import record

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


class LoginRateLimiter:
    """Sliding-window limiter with an LRU cap to bound process memory."""

    def __init__(self, limit: int = 5, window_seconds: int = 300, max_keys: int = 10_000):
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._attempts: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def check(self, key: tuple[str, str]) -> bool:
        now = time.monotonic()
        with self._lock:
            attempts = self._attempts.get(key)
            if attempts is None:
                while len(self._attempts) >= self.max_keys:
                    self._attempts.popitem(last=False)
                attempts = deque()
                self._attempts[key] = attempts
            else:
                self._attempts.move_to_end(key)
            cutoff = now - self.window_seconds
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            return len(attempts) < self.limit

    def failure(self, key: tuple[str, str]) -> None:
        with self._lock:
            attempts = self._attempts.get(key)
            if attempts is not None:
                attempts.append(time.monotonic())

    def success(self, key: tuple[str, str]) -> None:
        with self._lock:
            self._attempts.pop(key, None)


login_limiter = LoginRateLimiter()
login_ip_limiter = LoginRateLimiter(limit=20)
login_account_limiter = LoginRateLimiter(limit=10)
INVALID_LOGIN = "Usuario o contraseña incorrectos."
DUMMY_PASSWORD_HASH = security.hash_password(secrets.token_urlsafe(32))


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
    require_trusted_origin(request)
    peer_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    ip = forwarded if peer_ip in {"127.0.0.1", "::1"} and forwarded else peer_ip
    rate_key = (ip, form.username.casefold()[:128])
    ip_key = (ip, "*")
    account_key = ("*", form.username.casefold()[:128])
    if not login_limiter.check(rate_key) or not login_ip_limiter.check(ip_key) or not login_account_limiter.check(account_key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos. Intente más tarde.", headers={"Retry-After": "300"})
    user = db.query(User).filter(User.username == form.username).first()
    password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
    if not security.verify_password(form.password, password_hash) or not user:
        login_limiter.failure(rate_key)
        login_ip_limiter.failure(ip_key)
        login_account_limiter.failure(account_key)
        if user:
            record(db, "login_fallido", user.id, user.id, ip)
        else:
            logger.warning("Login fallido para usuario inexistente", extra={"client_ip": ip})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_LOGIN)
    if user.estado != "activo":
        login_limiter.failure(rate_key)
        login_ip_limiter.failure(ip_key)
        login_account_limiter.failure(account_key)
        record(db, "login_fallido", user.id, user.id, ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_LOGIN)
    login_limiter.success(rate_key)
    login_account_limiter.success(account_key)
    _set_cookies(response, user)
    record(db, "login_exitoso", user.id, user.id, ip)
    if user.must_change_password:
        record(db, "login_restringido", user.id, user.id, request.client.host if request.client else None)
    return {
        "ok": True,
        "user": {"id": user.id, "username": user.username, "nombre": user.nombre, "email": user.email or "", "rol": user.rol, "must_change_password": user.must_change_password},
    }


@router.post("/logout")
def logout(
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    user.token_version += 1
    db.commit()
    record(db, "logout", user.id, user.id, request.client.host if request.client else None)
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
