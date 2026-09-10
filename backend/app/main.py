"""Aplicación FastAPI ExtractCert."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .db.database import SessionLocal, init_db
from .core import security
from .db.models import Observacion, Setting, User
from .routers import (
    auth,
    contactos,
    dashboard,
    errores,
    extraccion,
    historial,
    observaciones,
    pdf,
    settings as settings_router,
    tree,
    usuarios,
)


def _seed() -> None:
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "admin").first():
            db.add(
                User(
                    username="admin",
                    nombre="Administrador",
                    password_hash=security.hash_password("Admin123"),
                    rol="administrador",
                    estado="activo",
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
app.include_router(tree.router)
app.include_router(dashboard.router)
app.include_router(pdf.router)
app.include_router(extraccion.router)
app.include_router(historial.router)
app.include_router(usuarios.router)
app.include_router(settings_router.router)
app.include_router(errores.router)
app.include_router(contactos.router)
app.include_router(observaciones.router)

# En producción, servir el build de Vite (frontend/dist).
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="spa")