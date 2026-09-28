from datetime import datetime, timedelta
import os
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.models import Extraccion, ExtraccionVersion, Lote, LoteDocumento, LoteOperador, User
from app.routers import extraccion as extraction_router
from app.routers import lotes as lotes_router
from app.services import lotes
from app.services import repo


def database() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def fixture_rows(db: Session):
    first = User(username="first", password_hash="x", rol="usuario")
    second = User(username="second", password_hash="x", rol="usuario")
    db.add_all((first, second))
    db.flush()
    lote = Lote(relative_path="lote", nombre="lote", operador_id=first.id)
    db.add(lote)
    db.flush()
    db.add_all((LoteOperador(lote_id=lote.id, operador_id=first.id), LoteOperador(lote_id=lote.id, operador_id=second.id)))
    document = LoteDocumento(lote_id=lote.id, document_key="k", relative_path="a.pdf", nombre="a.pdf")
    db.add(document)
    db.commit()
    return first, second, lote, document


def test_claim_es_exclusivo_y_recupera_lease_vencido():
    db = database()
    first, second, _, document = fixture_rows(db)
    claimed, token = lotes.claim_document(db, document.id, first.id)
    db.commit()
    assert token and claimed.reservado_por == first.id
    with pytest.raises(HTTPException) as conflict:
        lotes.claim_document(db, document.id, second.id)
    assert conflict.value.status_code == 409
    assert "Seleccione otro archivo" in conflict.value.detail
    db.rollback()
    document = db.get(LoteDocumento, document.id)
    document.lease_expires_at = datetime.now() - timedelta(seconds=1)
    db.commit()
    recovered, second_token = lotes.claim_document(db, document.id, second.id)
    assert recovered.reservado_por == second.id and second_token != token


def test_claim_requiere_membresia_activa():
    db = database()
    first, _, lote, document = fixture_rows(db)
    membership = db.query(LoteOperador).filter_by(lote_id=lote.id, operador_id=first.id).one()
    membership.activo = False
    db.commit()
    with pytest.raises(HTTPException) as forbidden:
        lotes.claim_document(db, document.id, first.id)
    assert forbidden.value.status_code == 403


def test_idempotency_key_de_version_es_unica():
    assert ExtraccionVersion.__table__.c.idempotency_key.unique


def test_metricas_directorio_sin_lote_no_crea_documentos(tmp_path, monkeypatch):
    folder = tmp_path / "sin-asignar"
    folder.mkdir()
    (folder / "a.pdf").write_bytes(b"pdf")
    db = database()
    monkeypatch.setattr(lotes, "raiz_origen", lambda _: str(tmp_path))

    assert lotes.metricas_directorio(db, "sin-asignar") == {
        "total": 1, "realizados": 0, "errores": 0, "pendientes": 1, "porcentaje": 0
    }
    assert db.query(LoteDocumento).count() == 0


def test_miembro_secundario_es_miembro_activo():
    db = database()
    _, second, lote, _ = fixture_rows(db)

    assert lote.operador_id != second.id
    assert lotes.is_member(db, lote.id, second.id)


def test_replay_idempotente_del_mismo_autor_no_requiere_lease():
    db = database()
    first, _, lote, document = fixture_rows(db)
    extraction = Extraccion(user_id=first.id, lote_id=lote.id, documento_id=document.id, original_path="a.pdf", original_key="original", destino_path="version.pdf", pagina_inicio=1, pagina_fin=2)
    db.add(extraction)
    db.flush()
    db.add(ExtraccionVersion(extraccion_id=extraction.id, documento_id=document.id, version=1, autor_id=first.id, pagina_inicio=1, pagina_fin=2, destino_path="version.pdf", tipo="realizado", idempotency_key="replay-key"))
    db.commit()
    body = extraction_router.GuardarIn(ruta="inexistente.pdf", documento_id=document.id, lease_token="", inicio=1, fin=2, idempotency_key="replay-key")

    response = extraction_router.guardar(body, first, db, None)

    assert response["version"] == 1
    assert response["documento_id"] == document.id


def test_replay_idempotente_ajeno_devuelve_conflicto():
    db = database()
    first, second, lote, document = fixture_rows(db)
    extraction = Extraccion(user_id=first.id, lote_id=lote.id, documento_id=document.id, original_path="a.pdf", original_key="original", destino_path="version.pdf", pagina_inicio=1, pagina_fin=1)
    db.add(extraction)
    db.flush()
    db.add(ExtraccionVersion(extraccion_id=extraction.id, documento_id=document.id, version=1, autor_id=first.id, pagina_inicio=1, pagina_fin=1, destino_path="version.pdf", tipo="realizado", idempotency_key="owned-key"))
    db.commit()
    body = extraction_router.GuardarIn(ruta="inexistente.pdf", documento_id=document.id, lease_token="", inicio=1, fin=1, idempotency_key="owned-key")

    with pytest.raises(HTTPException) as conflict:
        extraction_router.guardar(body, second, db, None)
    assert conflict.value.status_code == 409


def test_sync_detecta_reemplazo_del_mismo_nombre_por_fingerprint(tmp_path, monkeypatch):
    folder = tmp_path / "lote"
    folder.mkdir()
    source = folder / "a.pdf"
    source.write_bytes(b"primera")
    db = database()
    first, _, lote, _ = fixture_rows(db)
    first_id, lote_id = first.id, lote.id
    db.query(LoteDocumento).delete()
    lote.relative_path = "lote"
    db.commit()
    db.expunge_all()
    lote = db.get(Lote, lote_id)
    monkeypatch.setattr(lotes, "raiz_origen", lambda _: str(tmp_path))
    document = lotes.sync_documentos(db, lote)[0]
    extraction = Extraccion(user_id=first_id, lote_id=lote.id, documento_id=document.id, original_path=str(source), original_key=document.document_key, destino_path="out.pdf", pagina_inicio=1, pagina_fin=1, processed_at=datetime.now() + timedelta(seconds=1))
    db.add(extraction)
    db.commit()
    assert lotes.metricas(db, lote)["realizados"] == 1

    source.write_bytes(b"segunda-version")
    future_ns = int((datetime.now() + timedelta(seconds=2)).timestamp() * 1_000_000_000)
    os.utime(source, ns=(future_ns, future_ns))
    stats = lotes.metricas(db, lote)

    db.refresh(document)
    assert stats["pendientes"] == 1
    assert document.estado == "pendiente"
    assert document.source_size == len(b"segunda-version")


def test_lease_vigente_cuenta_aunque_documento_este_completado():
    db = database()
    first, _, lote, document = fixture_rows(db)
    document.estado = "completado"
    document.reservado_por = first.id
    document.lease_token = "token"
    document.lease_expires_at = datetime.now() + timedelta(minutes=10)
    db.commit()

    active = db.query(LoteDocumento.id).filter(LoteDocumento.lote_id == lote.id, LoteDocumento.lease_expires_at > datetime.now()).first()
    assert active is not None


def test_sync_documentos_selects_constantes_para_cien_documentos(tmp_path, monkeypatch):
    folder = tmp_path / "lote"
    folder.mkdir()
    db = database()
    _, _, lote, _ = fixture_rows(db)
    lote_id = lote.id
    db.query(LoteDocumento).delete(synchronize_session=False)
    db.commit()
    db.expunge_all()
    lote = db.get(Lote, lote_id)
    for index in range(100):
        name = f"{index:03}.pdf"
        (folder / name).write_bytes(b"pdf")
        db.add(LoteDocumento(
            lote_id=lote.id,
            document_key=lotes.document_key(lote.id, name),
            relative_path=name,
            nombre=name,
        ))
    db.commit()
    monkeypatch.setattr(lotes, "raiz_origen", lambda _: str(tmp_path))
    selects = 0

    def count_selects(_conn, _cursor, statement, _parameters, _context, _executemany):
        nonlocal selects
        if statement.lstrip().upper().startswith("SELECT"):
            selects += 1

    event.listen(db.get_bind(), "before_cursor_execute", count_selects)
    try:
        rows = lotes.sync_documentos(db, lote)
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", count_selects)

    assert len(rows) == 100
    assert selects <= 7


def test_metricas_db_preserva_payload_sin_reconciliar(tmp_path, monkeypatch):
    db = database()
    _, _, lote, document = fixture_rows(db)
    document.estado = "completado"
    db.commit()
    monkeypatch.setattr(lotes.fs, "listar_pdfs", lambda _: pytest.fail("no debe leer filesystem"))

    assert lotes.metricas_db(db, lote) == {
        "total": 1, "realizados": 1, "errores": 0, "pendientes": 0, "porcentaje": 100
    }


def test_sync_estado_con_metricas_db_actualiza_lote_sin_filesystem(monkeypatch):
    db = database()
    _, _, lote, document = fixture_rows(db)
    monkeypatch.setattr(lotes.fs, "listar_pdfs", lambda _: pytest.fail("no debe leer filesystem"))

    document.estado = "completado"
    db.flush()
    lotes.sync_estado(db, lote, lotes.metricas_db(db, lote))
    assert lote.estado == "completado"

    document.estado = "pendiente"
    db.flush()
    lotes.sync_estado(db, lote, lotes.metricas_db(db, lote))
    assert lote.estado == "asignado"
    assert lote.completed_at is None


def test_operator_stats_no_colapsa_lotes_vacios_del_mismo_operador():
    db = database()
    operator = User(username="empty", password_hash="x", rol="usuario")
    supervisor = User(username="super", password_hash="x", rol="supervisor")
    db.add_all((operator, supervisor))
    db.flush()
    first = Lote(relative_path="empty-1", nombre="empty-1", operador_id=operator.id)
    second = Lote(relative_path="empty-2", nombre="empty-2", operador_id=operator.id)
    db.add_all((first, second))
    db.flush()
    db.add_all((LoteOperador(lote_id=first.id, operador_id=operator.id), LoteOperador(lote_id=second.id, operador_id=operator.id)))
    db.commit()

    result = lotes_router.operator_stats(supervisor, db)
    stats = next(item for item in result if item["id"] == operator.id)

    assert stats["lotes_asignados"] == 2
    assert stats["total"] == 0


def test_limpieza_temporal_ejecuta_primero_y_throttlea(tmp_path, monkeypatch):
    old = tmp_path / "prev_old.pdf"
    old.write_bytes(b"pdf")
    os.utime(old, (0, 0))
    monkeypatch.setattr(repo, "settings", SimpleNamespace(temp_dir=tmp_path))
    monkeypatch.setattr(repo, "_last_temp_cleanup", None)

    repo.limpiar_temporales()
    assert not old.exists()

    recent = tmp_path / "prev_recent.pdf"
    recent.write_bytes(b"pdf")
    os.utime(recent, (0, 0))
    repo.limpiar_temporales()
    assert recent.exists()


def test_limpieza_temporal_permite_retry_si_falla(tmp_path, monkeypatch):
    class FallaUnaVez:
        def __init__(self):
            self.failed = False

        def glob(self, pattern):
            if not self.failed:
                self.failed = True
                raise OSError("temporalmente inaccesible")
            return tmp_path.glob(pattern)

    directory = FallaUnaVez()
    monkeypatch.setattr(repo, "settings", SimpleNamespace(temp_dir=directory))
    monkeypatch.setattr(repo, "_last_temp_cleanup", None)

    with pytest.raises(OSError):
        repo.limpiar_temporales()
    assert repo._last_temp_cleanup is None

    repo.limpiar_temporales()
    assert repo._last_temp_cleanup is not None
