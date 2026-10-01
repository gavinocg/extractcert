"""Aplicación FastAPI ExtractCert."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

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
            if settings.admin_bootstrap_password:
                security.validate_password(settings.admin_bootstrap_password, "admin")
                db.add(
                    User(
                        username="admin",
                        nombre="Administrador",
                        password_hash=security.hash_password(settings.admin_bootstrap_password),
                        rol="administrador",
                        estado="activo",
                        must_change_password=True,
                    )
                )
            elif settings.is_production:
                raise RuntimeError("No existe un administrador y ADMIN_BOOTSTRAP_PASSWORD no está configurada.")
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


app = FastAPI(
    title="ExtractCert",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

allowed_hosts = {"127.0.0.1", "localhost"}
if settings.app_url:
    from urllib.parse import urlsplit
    if hostname := urlsplit(settings.app_url).hostname:
        allowed_hosts.add(hostname)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=sorted(allowed_hosts))


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
        "script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; connect-src 'self'; worker-src 'self' blob:; font-src 'self'"
    )
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "private, no-store"
    elif request.url.path == "/" or not request.url.path.rsplit("/", 1)[-1].count("."):
        response.headers["Cache-Control"] = "no-cache"
    elif request.url.path.startswith(("/assets/", "/pdfjs-wasm/")):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


if settings.is_production:
    @app.get("/docs", include_in_schema=False)
    @app.get("/redoc", include_in_schema=False)
    @app.get("/openapi.json", include_in_schema=False)
    def disabled_documentation():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Endpoint no encontrado.")


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}

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
