from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.models import Setting
from app.services import repo


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
