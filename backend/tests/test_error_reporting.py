from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import pytest

from app.db.database import Base
from app.db.models import Lote, LoteOperador, TramiteError, User
from app.routers import errores


@pytest.mark.parametrize("role", ["supervisor", "administrador"])
def test_supervision_puede_enviar_errores_de_cualquier_lote(monkeypatch, role):
    monkeypatch.setenv("ERROR_EMAIL_ALLOWED_DOMAINS", "example.com")
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


@pytest.mark.parametrize("role", ["supervisor", "administrador"])
def test_supervision_puede_enviar_todos_los_errores(monkeypatch, role):
    monkeypatch.setenv("ERROR_EMAIL_ALLOWED_DOMAINS", "example.com")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    admin = User(username="admin", password_hash="x", rol=role, estado="activo")
    operator = User(username="operador", password_hash="x", rol="usuario", estado="activo")
    db.add_all((admin, operator))
    db.flush()
    db.add_all([
        TramiteError(original_path="/lote/a.pdf", archivo="a.pdf", observacion="Ilegible", user_id=operator.id),
        TramiteError(original_path="/lote/b.pdf", archivo="b.pdf", observacion="Incompleto", user_id=operator.id),
    ])
    db.commit()
    sent = []
    monkeypatch.setattr(errores, "enviar_correo", lambda recipients, subject, html, text: sent.append(text))

    errores.enviar(errores.EnviarIn(todos=True, emails_extra=["destino@example.com"]), admin, db, None)

    assert "a.pdf" in sent[0]
    assert "b.pdf" in sent[0]


def test_usuario_envia_todos_solo_de_sus_lotes(monkeypatch):
    monkeypatch.setenv("ERROR_EMAIL_ALLOWED_DOMAINS", "example.com")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    operator = User(username="operador", password_hash="x", rol="usuario", estado="activo")
    other = User(username="otro", password_hash="x", rol="usuario", estado="activo")
    db.add_all((operator, other))
    db.flush()
    own_lot = Lote(relative_path="propio", nombre="propio", operador_id=operator.id)
    other_lot = Lote(relative_path="otro", nombre="otro", operador_id=other.id)
    db.add_all((own_lot, other_lot))
    db.flush()
    db.add(LoteOperador(lote_id=own_lot.id, operador_id=operator.id))
    db.add_all([
        TramiteError(original_path="/propio/a.pdf", archivo="a.pdf", observacion="Propio", user_id=operator.id, lote_id=own_lot.id),
        TramiteError(original_path="/otro/b.pdf", archivo="b.pdf", observacion="Ajeno", user_id=other.id, lote_id=other_lot.id),
    ])
    db.commit()
    sent = []
    monkeypatch.setattr(errores, "enviar_correo", lambda recipients, subject, html, text: sent.append(text))

    errores.enviar(errores.EnviarIn(todos=True, emails_extra=["destino@example.com"]), operator, db, None)

    assert "a.pdf" in sent[0]
    assert "b.pdf" not in sent[0]


def test_email_extra_requiere_dominio_permitido(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    user = User(username="admin", password_hash="x", rol="administrador", estado="activo")
    db.add(user)
    db.flush()
    error = TramiteError(original_path="/lote/a.pdf", archivo="a.pdf", observacion="Error", user_id=user.id)
    db.add(error)
    db.commit()
    monkeypatch.setenv("ERROR_EMAIL_ALLOWED_DOMAINS", "empresa.test")

    with pytest.raises(Exception) as exc:
        errores.enviar(errores.EnviarIn(ids=[error.id], emails_extra=["fuera@example.com"]), user, db, None)

    assert exc.value.status_code == 400


def test_envio_aplica_cuota_y_registra_auditoria(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    user = User(username="admin", password_hash="x", rol="administrador", estado="activo")
    db.add(user)
    db.flush()
    error = TramiteError(original_path="/lote/a.pdf", archivo="a.pdf", observacion="Error", user_id=user.id)
    db.add(error)
    db.commit()
    monkeypatch.setenv("ERROR_EMAIL_ALLOWED_DOMAINS", "example.com")
    monkeypatch.setenv("ERROR_EMAIL_RATE_LIMIT", "1")
    monkeypatch.setattr(errores, "enviar_correo", lambda *args: None)

    errores.enviar(errores.EnviarIn(ids=[error.id], emails_extra=["ok@example.com"]), user, db, None)
    with pytest.raises(Exception) as exc:
        errores.enviar(errores.EnviarIn(ids=[error.id], emails_extra=["ok@example.com"]), user, db, None)

    assert exc.value.status_code == 429
