"""CRUD de usuarios (solo administrador)."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core import security
from ..core.deps import require_admin, require_csrf
from ..db.database import get_db
from ..db.models import Extraccion, User

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])


class UsuarioIn(BaseModel):
    username: str
    nombre: str = ""
    rol: str = "usuario"
    estado: str = "activo"
    password: str = ""


def _rol_valido(rol: str) -> str:
    return rol if rol in ("usuario", "administrador") else "usuario"


def _estado_valido(estado: str) -> str:
    return estado if estado in ("activo", "inactivo") else "activo"


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
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El usuario ya existe.")

    u = User(
        username=body.username.strip(),
        nombre=body.nombre.strip(),
        password_hash=security.hash_password(body.password),
        rol=_rol_valido(body.rol),
        estado=_estado_valido(body.estado),
    )
    db.add(u)
    db.commit()
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
    u.username = body.username.strip()
    u.nombre = body.nombre.strip()
    u.rol = _rol_valido(body.rol)
    u.estado = _estado_valido(body.estado)
    if body.password:
        u.password_hash = security.hash_password(body.password)
    db.commit()
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
    db.delete(u)
    db.commit()
    return {"ok": True}
