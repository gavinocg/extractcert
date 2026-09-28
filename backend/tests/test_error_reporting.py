from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import pytest

from app.db.database import Base
from app.db.models import TramiteError, User
from app.routers import errores


@pytest.mark.parametrize("role", ["supervisor", "administrador"])
def test_supervision_puede_enviar_errores_de_cualquier_lote(monkeypatch, role):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    admin = User(username="admin", password_hash="x", rol=role, estado="activo")
    operator = User(username="operador", password_hash="x", rol="usuario", estado="activo")
    db.add_all((admin, operator))
    db.flush()
    error = TramiteError(original_path="/otro/lote/documento.pdf", archivo="documento.pdf", observacion="Ilegible", user_id=operator.id)
    db.add(error)
    db.commit()
    sent = []
    monkeypatch.setattr(errores, "enviar_correo", lambda recipients, subject, html, text: sent.append((recipients, subject)))

    result = errores.enviar(
        errores.EnviarIn(ids=[error.id], emails_extra=["destino@example.com"]),
        admin,
        db,
        None,
    )

    assert result == {"ok": True, "enviados": 1}
    assert sent[0][0] == ["destino@example.com"]
