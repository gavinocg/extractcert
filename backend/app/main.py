"""Aplicación FastAPI ExtractCert."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .db.database import SessionLocal, init_db
from .core import security
from .core.deps import require_full_access
from .db.models import Observacion, Setting, User
from .routers import (
    auth,
    contactos,
    dashboard,
    errores,
    extraccion,
    historial,
    lotes,
    observaciones,
    pdf,
    settings as settings_router,
    tree,
    usuarios,
)


def _seed() -> None:
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.rol == "administrador").first():
            db.add(
                User(
                    username="admin",
                    nombre="Administrador",
                    password_hash=security.hash_password("Temporal-2026!"),
                    rol="administrador",
                    estado="activo",
                    must_change_password=True,
                )
            )
        for clave, valor in (
            ("raiz_origen", settings.default_raiz_origen),
            ("raiz_repo", settings.default_raiz_repo),
        ):
            if not db.get(Setting, clave):
                db.add(Setting(clave=clave, valor=valor))
        if not db.query(Observacion).first():
            for orden, texto in (
                (10, "Faltan páginas"),
                (20, "Documento ilegible"),
                (30, "Trámite duplicado"),
                (40, "Certificado incompleto"),
                (50, "Firma faltante"),
            ):
                db.add(Observacion(descripcion=texto, orden=orden))
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed()
    yield


app = FastAPI(title="ExtractCert", lifespan=lifespan)

app.include_router(auth.router)
full_access = [Depends(require_full_access)]
app.include_router(tree.router, dependencies=full_access)
app.include_router(dashboard.router, dependencies=full_access)
app.include_router(pdf.router, dependencies=full_access)
app.include_router(extraccion.router, dependencies=full_access)
app.include_router(historial.router, dependencies=full_access)
app.include_router(lotes.router, dependencies=full_access)
app.include_router(usuarios.router, dependencies=full_access)
app.include_router(settings_router.router, dependencies=full_access)
app.include_router(errores.router, dependencies=full_access)
app.include_router(contactos.router, dependencies=full_access)
app.include_router(observaciones.router, dependencies=full_access)

# En producción, servir el build de Vite (frontend/dist).
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="spa")
