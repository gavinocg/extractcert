from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.models import Setting
from app.services import repo
from app.services import email


def test_smtp_settings_persistidos_tienen_prioridad(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    monkeypatch.setattr(repo.settings, "smtp_host", "smtp.env.local")
    monkeypatch.setattr(repo.settings, "smtp_port", 25)

    repo.set_setting(db, "smtp_host", "smtp.database.local")
    repo.set_setting(db, "smtp_port", "587")
    repo.set_setting(db, "smtp_tls", "true")
    repo.set_setting(db, "smtp_pass", "secret")
    config = repo.smtp_settings(db)

    assert config["host"] == "smtp.database.local"
    assert config["port"] == 587
    assert config["tls"] is True
    assert config["password"] == "secret"
    assert db.get(Setting, "smtp_pass").valor.startswith("enc:")


def test_validar_host_smtp_bloquea_destinos_internos(monkeypatch):
    monkeypatch.setattr(email.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("169.254.169.254", 0))])

    import pytest
    with pytest.raises(ValueError):
        email.validar_host_smtp("metadata.example")


def test_validar_host_smtp_permite_host_guardado_interno(monkeypatch):
    monkeypatch.setattr(email.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("127.0.0.1", 0))])

    assert email.validar_host_smtp("smtp.internal", permitir_red_interna=True) == "smtp.internal"
