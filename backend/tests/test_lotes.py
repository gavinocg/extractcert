from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.models import Extraccion, Lote, LoteOperador, TramiteError, User
from app.routers import lotes as lotes_router
from app.services import lotes as lote_service
from app.services import notificaciones


def _database() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_metricas_deduplica_error_y_extraccion(tmp_path: Path, monkeypatch):
    folder = tmp_path / "2026" / "09-24-2026"
    folder.mkdir(parents=True)
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        (folder / name).write_bytes(b"pdf")

    db = _database()
    monkeypatch.setattr(lote_service, "raiz_origen", lambda _: str(tmp_path))
    user = User(username="operador", password_hash="hash", rol="usuario", estado="activo")
    db.add(user)
    db.flush()
    lote = Lote(relative_path="2026/09-24-2026", nombre="09-24-2026", operador_id=user.id)
    db.add(lote)
    db.flush()
    path_a = str(folder / "a.pdf").replace("\\", "/")
    path_b = str(folder / "b.pdf").replace("\\", "/")
    db.add(Extraccion(user_id=user.id, lote_id=lote.id, original_path=path_a, destino_path="out/a.pdf", pagina_inicio=1, pagina_fin=1))
    db.add(TramiteError(user_id=user.id, lote_id=lote.id, original_path=path_a, archivo="a.pdf", observacion="duplicado"))
    db.add(TramiteError(user_id=user.id, lote_id=lote.id, original_path=path_b, archivo="b.pdf", observacion="ilegible"))
    db.commit()

    assert lote_service.metricas(db, lote) == {
        "total": 3,
        "realizados": 1,
        "errores": 1,
        "pendientes": 1,
        "porcentaje": 67,
    }


def test_lote_dinamico_reabre_al_agregar_pdf(tmp_path: Path, monkeypatch):
    folder = tmp_path / "lote"
    folder.mkdir()
    first = folder / "uno.pdf"
    first.write_bytes(b"pdf")

    db = _database()
    monkeypatch.setattr(lote_service, "raiz_origen", lambda _: str(tmp_path))
    user = User(username="operador", password_hash="hash", rol="usuario", estado="activo")
    db.add(user)
    db.flush()
    lote = Lote(relative_path="lote", nombre="lote", operador_id=user.id, estado="notificado")
    db.add(lote)
    db.flush()
    db.add(Extraccion(user_id=user.id, lote_id=lote.id, original_path=str(first).replace("\\", "/"), destino_path="out/uno.pdf", pagina_inicio=1, pagina_fin=1))
    db.commit()

    assert lote_service.sync_estado(db, lote)["porcentaje"] == 100
    (folder / "dos.pdf").write_bytes(b"pdf")
    stats = lote_service.sync_estado(db, lote)

    assert stats["porcentaje"] == 50
    assert lote.estado == "en_progreso"
    assert lote.notified_at is None


def test_notificacion_no_repite_destinatario_enviado(monkeypatch):
    db = _database()
    lote = Lote(relative_path="lote", nombre="lote")
    db.add(lote)
    db.commit()
    calls: list[list[str]] = []
    monkeypatch.setattr(notificaciones, "enviar_correo", lambda recipients, *_: calls.append(recipients))

    first = notificaciones.send_recorded(db, lote, "asignacion:evento", ["user@example.com"], "Asunto", "<p>Mensaje</p>", "Mensaje")
    second = notificaciones.send_recorded(db, lote, "asignacion:evento", ["user@example.com"], "Asunto", "<p>Mensaje</p>", "Mensaje")

    assert first["enviados"] == 1
    assert second["omitidos"] == 1
    assert calls == [["user@example.com"]]


def test_metricas_no_colapsa_nombres_que_el_filesystem_distingue(tmp_path: Path, monkeypatch):
    folder = tmp_path / "lote"
    folder.mkdir()
    (folder / "A.pdf").write_bytes(b"pdf")
    (folder / "a.pdf").write_bytes(b"pdf")
    if len(list(folder.glob("*.pdf"))) != 2:
        return  # Windows normalmente no permite representar este caso.

    db = _database()
    monkeypatch.setattr(lote_service, "raiz_origen", lambda _: str(tmp_path))
    user = User(username="case", password_hash="hash", rol="usuario", estado="activo")
    db.add(user)
    db.flush()
    lote = Lote(relative_path="lote", nombre="lote", operador_id=user.id)
    db.add(lote)
    db.flush()
    db.add(Extraccion(user_id=user.id, lote_id=lote.id, original_path=str(folder / "A.pdf"), destino_path="out/A.pdf", pagina_inicio=1, pagina_fin=1))
    db.commit()

    assert lote_service.metricas(db, lote)["total"] == 2
    assert lote_service.metricas(db, lote)["realizados"] == 1


def test_metricas_conserva_avance_de_ruta_historica(tmp_path: Path, monkeypatch):
    folder = tmp_path / "lote"
    folder.mkdir()
    (folder / "uno.pdf").write_bytes(b"pdf")
    db = _database()
    monkeypatch.setattr(lote_service, "raiz_origen", lambda _: str(tmp_path))
    user = User(username="historico", password_hash="hash", rol="usuario", estado="activo")
    db.add(user)
    db.flush()
    lote = Lote(relative_path="lote", nombre="lote", operador_id=user.id)
    db.add(lote)
    db.flush()
    db.add(Extraccion(user_id=user.id, lote_id=lote.id, original_path="//servidor/raiz-antigua/lote/uno.pdf", destino_path="out/uno.pdf", pagina_inicio=1, pagina_fin=1))
    db.commit()

    assert lote_service.metricas(db, lote)["realizados"] == 1


def test_document_key_no_depende_de_unidad_o_unc():
    mapped = lote_service.document_key(17, "X:/2026/lote/Certificado.pdf")
    unc = lote_service.document_key(17, "//servidor/entrega/2026/lote/Certificado.pdf")

    assert mapped == unc


def test_sync_estado_recupera_operador_desde_miembros_activos(tmp_path: Path, monkeypatch):
    folder = tmp_path / "lote"
    folder.mkdir()
    (folder / "uno.pdf").write_bytes(b"pdf")

    db = _database()
    monkeypatch.setattr(lote_service, "raiz_origen", lambda _: str(tmp_path))
    user = User(username="fantasma", password_hash="hash", rol="usuario", estado="activo")
    db.add(user)
    db.flush()
    lote = Lote(relative_path="lote", nombre="lote", operador_id=None, estado="notificado", notified_at=datetime.now())
    db.add(lote)
    db.flush()
    db.add(LoteOperador(lote_id=lote.id, operador_id=user.id, activo=True))
    db.commit()

    stats = lote_service.sync_estado(db, lote)

    assert stats["pendientes"] == 1
    assert lote.operador_id == user.id
    assert lote.estado == "asignado"
    assert lote.notified_at is None


def test_sync_estado_sin_miembros_marca_sin_asignar(tmp_path: Path, monkeypatch):
    folder = tmp_path / "lote"
    folder.mkdir()
    (folder / "uno.pdf").write_bytes(b"pdf")

    db = _database()
    monkeypatch.setattr(lote_service, "raiz_origen", lambda _: str(tmp_path))
    lote = Lote(relative_path="lote", nombre="lote", operador_id=None, estado="notificado", notified_at=datetime.now())
    db.add(lote)
    db.commit()

    lote_service.sync_estado(db, lote)

    assert lote.operador_id is None
    assert lote.estado == "sin_asignar"


def test_listar_supervision_incluye_completado_huerfano(tmp_path: Path, monkeypatch):
    folder = tmp_path / "02-09-2026"
    folder.mkdir()
    (folder / "uno.pdf").write_bytes(b"pdf")

    db = _database()
    monkeypatch.setattr(lote_service, "raiz_origen", lambda _: str(tmp_path))
    worker = User(username="op", password_hash="hash", rol="usuario", estado="activo")
    sup = User(username="sup", password_hash="hash", rol="supervisor", estado="activo")
    db.add_all([worker, sup])
    db.flush()
    lote = Lote(relative_path="02-09-2026", nombre="02-09-2026", operador_id=None, estado="completado")
    db.add(lote)
    db.flush()
    db.add(Extraccion(user_id=worker.id, lote_id=lote.id, original_path=str(folder / "uno.pdf").replace("\\", "/"), destino_path="out/uno.pdf", pagina_inicio=1, pagina_fin=1))
    db.commit()

    supervision = lotes_router.listar(scope="supervision", user=sup, db=db)
    archived = lotes_router.listar(scope="archived", user=sup, db=db)
    counts = lotes_router.counts(user=sup, db=db)

    assert any(item["nombre"] == "02-09-2026" and item["estado"] == "completado" for item in supervision)
    assert all(item["nombre"] != "02-09-2026" for item in archived)
    assert counts["supervision"] >= 1
