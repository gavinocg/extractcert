from datetime import datetime
import importlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import Settings
from app.core.deps import get_current_user, require_csrf, require_full_access, require_trusted_origin
from app.db.database import Base
from app.db.models import SecurityAudit, User
from app.routers import auth, usuarios


def database() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def request(ip="127.0.0.1", origin=None):
    headers = {"origin": origin} if origin else {}
    return SimpleNamespace(client=SimpleNamespace(host=ip), headers=headers)


def response():
    result = SimpleNamespace(cookies={}, deleted=[])
    result.set_cookie = lambda **kwargs: result.cookies.update({kwargs["key"]: kwargs["value"]})
    result.delete_cookie = lambda key, **kwargs: result.deleted.append(key)
    return result


def user(db, username="persona", password="Clave-segura-2026", **values):
    row = User(username=username, password_hash=security.hash_password(password), **values)
    db.add(row)
    db.commit()
    return row


def test_token_version_y_token_legacy_se_invalidan():
    db = database()
    row = user(db)
    token = security.create_access_token(str(row.id), row.token_version)
    assert get_current_user(token, None, db).id == row.id
    row.token_version += 1
    db.commit()
    with pytest.raises(HTTPException) as stale:
        get_current_user(token, None, db)
    assert stale.value.status_code == 403
    legacy = security.jwt.encode({"sub": str(row.id)}, security.settings.secret_key, algorithm=security.ALGORITHM)
    with pytest.raises(HTTPException):
        get_current_user(legacy, None, db)


def test_acceso_restringido_solo_falla_en_dependencia_completa():
    db = database()
    row = user(db, must_change_password=True)
    token = security.create_access_token(str(row.id), row.token_version)
    authenticated = get_current_user(token, None, db)
    assert authenticated.must_change_password
    with pytest.raises(HTTPException) as forbidden:
        require_full_access(authenticated)
    assert forbidden.value.status_code == 403


@pytest.mark.parametrize("password", ["corta", "password123", "PERSONA-extra-2026", "a" * 73])
def test_politica_rechaza_passwords_invalidas(password):
    with pytest.raises(ValueError):
        security.validate_password(password, "persona")


def test_politica_cuenta_bytes_y_rechaza_password_actual():
    current = security.hash_password("Otra-clave-2026")
    security.validate_password("Nueva-clave-2026", "persona", current)
    with pytest.raises(ValueError):
        security.validate_password("Otra-clave-2026", "persona", current)
    with pytest.raises(ValueError):
        security.validate_password("ñ" * 40, "persona")


def test_politica_acepta_exactamente_seis_caracteres():
    security.validate_password("Ab1!xy", "persona")


def test_cambio_password_incrementa_version_y_reemite_cookie():
    db = database()
    row = user(db, must_change_password=True)
    response = SimpleNamespace(cookies={}, set_cookie=lambda **kwargs: response.cookies.update({kwargs["key"]: kwargs["value"]}))
    result = auth.cambiar_password(auth.PasswordIn(actual="Clave-segura-2026", nueva="Nueva-clave-2026"), response, request(), row, db, None)
    assert result["ok"] is True and result["must_change_password"] is False
    assert result["user"]["id"] == row.id
    assert result["user"]["must_change_password"] is False
    assert row.token_version == 2 and not row.must_change_password
    assert isinstance(row.password_changed_at, datetime)
    assert "access_token" in response.cookies
    assert db.query(SecurityAudit).filter_by(evento="cambio_password").count() == 1


def test_login_responde_igual_para_usuario_inexistente_e_inactivo(monkeypatch):
    db = database()
    user(db, "inactivo", estado="inactivo")
    monkeypatch.setattr(auth, "login_limiter", auth.LoginRateLimiter())
    errors = []
    for username in ("ausente", "inactivo"):
        with pytest.raises(HTTPException) as exc:
            auth.login(auth.LoginIn(username=username, password="incorrecta"), response(), request(), db)
        errors.append((exc.value.status_code, exc.value.detail))
    assert errors == [(401, auth.INVALID_LOGIN), (401, auth.INVALID_LOGIN)]


def test_rate_limit_es_por_ip_usuario_y_tiene_memoria_acotada():
    limiter = auth.LoginRateLimiter(limit=2, window_seconds=300, max_keys=2)
    key = ("127.0.0.1", "persona")
    assert limiter.check(key)
    limiter.failure(key)
    assert limiter.check(key)
    limiter.failure(key)
    assert not limiter.check(key)
    assert limiter.check(("127.0.0.2", "persona"))
    assert limiter.check(("127.0.0.1", "otra"))
    assert len(limiter._attempts) == 2


def test_logout_exige_csrf_y_revoca_token():
    db = database()
    row = user(db)
    result = response()
    auth.logout(result, request(), db, row, None)
    assert row.token_version == 2
    assert result.deleted == ["access_token", "csrf_token"]
    route = next(route for route in auth.router.routes if route.path == "/api/auth/logout")
    assert any(dependency.call is require_csrf for dependency in route.dependant.dependencies)


def test_origin_y_csrf_se_validan_con_comparacion_segura(monkeypatch):
    require_trusted_origin(request(origin=security.settings.app_url))
    with pytest.raises(HTTPException):
        require_trusted_origin(request(origin="https://evil.example"))
    called = False
    original = __import__("secrets").compare_digest

    def compared(left, right):
        nonlocal called
        called = True
        return original(left, right)

    monkeypatch.setattr("app.core.deps.secrets.compare_digest", compared)
    require_csrf(request(), "token", "token")
    assert called


def test_defaults_y_validacion_de_produccion():
    development = Settings(_env_file=None)
    assert development.access_token_expire_minutes == 60
    with pytest.raises(ValueError):
        Settings(environment="production", app_url="http://example.com", _env_file=None)
    with pytest.raises(ValueError):
        Settings(environment="production", app_url="https://example.com", secret_key="x" * 32, _env_file=None)
    production = Settings(
        environment="production",
        app_url="https://example.com",
        secret_key="0123456789abcdef0123456789abcdef",
        _env_file=None,
    )
    assert production.is_production


def test_admin_reset_y_forzado_expulsan_sesiones():
    db = database()
    admin = user(db, "admin", "Clave-admin-2026", rol="administrador")
    target = user(db, "target", "Clave-target-2026")
    body = usuarios.UsuarioIn(username="target", password="Reset-seguro-2026", must_change_password=True)
    usuarios.actualizar(target.id, body, request(), admin, db, None)
    assert target.token_version == 2 and target.must_change_password
    assert db.query(SecurityAudit).filter_by(evento="reset_password").count() == 1
    body.password = ""
    body.must_change_password = False
    usuarios.actualizar(target.id, body, request(), admin, db, None)
    body.must_change_password = True
    usuarios.actualizar(target.id, body, request(), admin, db, None)
    assert target.token_version == 4 and target.must_change_password


def test_admin_puede_solicitar_cambio_repetidamente():
    db = database()
    admin = user(db, "admin", "Clave-admin-2026", rol="administrador")
    target = user(db, "target", "Clave-target-2026", must_change_password=True)
    body = usuarios.UsuarioIn(username="target", must_change_password=True)

    usuarios.actualizar(target.id, body, request(), admin, db, None)
    usuarios.actualizar(target.id, body, request(), admin, db, None)

    assert target.must_change_password
    assert target.token_version == 3
    assert db.query(SecurityAudit).filter_by(evento="force_password_change").count() == 2


@pytest.mark.parametrize("password", ["1", "password123", "x" * 100])
def test_admin_puede_establecer_password_sin_politica_de_complejidad(password):
    db = database()
    admin = user(db, "admin", "Clave-admin-2026", rol="administrador")
    target = user(db, "target", "Clave-target-2026")
    body = usuarios.UsuarioIn(username="target", password=password, must_change_password=True)

    usuarios.actualizar(target.id, body, request(), admin, db, None)

    assert security.verify_password(password, target.password_hash)
    assert target.must_change_password


def test_modelos_contienen_campos_y_auditoria():
    db = database()
    columns = {column["name"] for column in inspect(db.bind).get_columns("users")}
    assert {"must_change_password", "password_changed_at", "token_version"} <= columns
    assert "security_audit" in inspect(db.bind).get_table_names()


def test_migracion_12_es_posterior_y_reintentable(monkeypatch):
    migration = importlib.import_module("migrations.versions.20260928_12_password_security")
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        migration.upgrade()
        columns = {column["name"] for column in inspect(connection).get_columns("users")}
        assert migration.down_revision == "20260928_11"
        assert {"must_change_password", "password_changed_at", "token_version"} <= columns
        assert "security_audit" in inspect(connection).get_table_names()


def test_todas_las_apis_no_auth_exigen_acceso_completo():
    from app.core.deps import require_full_access
    from app.main import app

    exemptions = {("GET", "/api/auth/me"), ("POST", "/api/auth/password"), ("POST", "/api/auth/logout")}
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/") or route.path.startswith("/api/auth/"):
            continue
        for method in route.methods:
            if (method, route.path) not in exemptions:
                assert any(dependency.call is require_full_access for dependency in route.dependant.dependencies), route.path
