"""CRUD de usuarios (solo administrador)."""
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core import security
from ..core.deps import require_admin, require_csrf
from ..db.database import get_db
from ..db.models import Extraccion, Lote, LoteAsignacionHistorial, TramiteError, User

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])


class UsuarioIn(BaseModel):
    username: str
    nombre: str = ""
    email: str = ""
    rol: str = "usuario"
    estado: str = "activo"
    password: str = ""


def _rol_valido(rol: str) -> str:
    if rol not in ("usuario", "supervisor", "administrador"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Rol no válido.")
    return rol


def _estado_valido(estado: str) -> str:
    if estado not in ("activo", "inactivo"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Estado no válido.")
    return estado


def _email_valido(email: str) -> str | None:
    value = email.strip().lower()
    if not value:
        return None
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El correo electrónico no es válido.")
    return value


@router.get("")
def listar(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    filas = (
        db.query(User, func.count(Extraccion.id))
        .outerjoin(Extraccion, Extraccion.user_id == User.id)
        .group_by(User.id)
        .order_by(User.username)
        .all()
    )
    return [
        {
            "id": u.id,
            "username": u.username,
            "nombre": u.nombre,
            "email": u.email or "",
            "rol": u.rol,
            "estado": u.estado,
            "extracciones": cuenta,
        }
        for u, cuenta in filas
    ]


@router.post("")
def crear(
    body: UsuarioIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    if not body.username.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El usuario es obligatorio.")
    if not body.password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña es obligatoria.")
    username = body.username.strip()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El usuario ya existe.")
    email = _email_valido(body.email)
    if email and db.query(User).filter(User.email == email).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El correo ya está registrado.")

    u = User(
        username=username,
        nombre=body.nombre.strip(),
        email=email,
        password_hash=security.hash_password(body.password),
        rol=_rol_valido(body.rol),
        estado=_estado_valido(body.estado),
    )
    db.add(u)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "El usuario o correo ya está registrado.")
    return {"ok": True, "id": u.id}


@router.put("/{user_id}")
def actualizar(
    user_id: int,
    body: UsuarioIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no existe.")
    if not body.username.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El usuario es obligatorio.")
    if user_id == user.id and _estado_valido(body.estado) == "inactivo":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puede desactivar su propio usuario.")
    email = _email_valido(body.email)
    if email and db.query(User).filter(User.email == email, User.id != user_id).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El correo ya está registrado.")
    new_role = _rol_valido(body.rol)
    new_status = _estado_valido(body.estado)
    active_lots = db.query(Lote).filter(
        Lote.operador_id == user_id,
        Lote.estado.in_(("asignado", "en_progreso")),
    ).count()
    if active_lots and (new_role not in ("usuario", "supervisor") or new_status != "activo"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Reasigne los lotes activos antes de cambiar el rol o desactivar al operador.")
    username = body.username.strip()
    if db.query(User).filter(User.username == username, User.id != user_id).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "El usuario ya existe.")
    u.username = username
    u.nombre = body.nombre.strip()
    u.email = email
    u.rol = new_role
    u.estado = new_status
    if body.password:
        u.password_hash = security.hash_password(body.password)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "El usuario o correo ya está registrado.")
    return {"ok": True}


@router.delete("/{user_id}")
def eliminar(
    user_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    if user_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puede eliminar su propio usuario.")
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no existe.")
    has_activity = (
        db.query(Extraccion).filter(Extraccion.user_id == user_id).first()
        or db.query(TramiteError).filter(TramiteError.user_id == user_id).first()
        or db.query(Lote).filter((Lote.operador_id == user_id) | (Lote.asignado_por_id == user_id)).first()
        or db.query(LoteAsignacionHistorial).filter(
            (LoteAsignacionHistorial.operador_id == user_id) | (LoteAsignacionHistorial.asignado_por_id == user_id)
        ).first()
    )
    if has_activity:
        raise HTTPException(status.HTTP_409_CONFLICT, "El usuario tiene actividad registrada; desactívelo en lugar de eliminarlo.")
    db.delete(u)
    db.commit()
    return {"ok": True}
