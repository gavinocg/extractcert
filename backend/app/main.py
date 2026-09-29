"""Aplicación FastAPI ExtractCert."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
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

# En producción, servir assets y aplicar fallback SPA para rutas de React.
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.is_dir():
    for directory in ("assets", "pdfjs-wasm"):
        path = _DIST / directory
        if path.is_dir():
            app.mount(f"/{directory}", StaticFiles(directory=str(path)), name=f"spa-{directory}")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Endpoint no encontrado.")
        candidate = (_DIST / full_path).resolve()
        if candidate.is_file() and _DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
