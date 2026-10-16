import os
from datetime import datetime, timedelta
from pathlib import Path

import fitz
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.models import AssignmentLock, Extraccion, Lote, LoteDocumento, LoteOperador, User
from app.routers import dashboard as dashboard_router
from app.routers import extraccion as extraction_router
from app.services import lotes as lote_service


def _database() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _escenario(tmp_path: Path, monkeypatch, rol: str = "usuario"):
    folder = tmp_path / "lote"
    folder.mkdir()
    pdf = folder / "uno.pdf"
    pdf.write_bytes(b"pdf")

    db = _database()
    monkeypatch.setattr(lote_service, "raiz_origen", lambda _: str(tmp_path))
    monkeypatch.setattr(dashboard_router, "raiz_origen", lambda _: str(tmp_path))
    monkeypatch.setattr(dashboard_router, "raiz_repo", lambda _: str(tmp_path / "repo"))
    user = User(username="operador", password_hash="hash", rol=rol, estado="activo")
    db.add(user)
    db.flush()
    lote = Lote(relative_path="lote", nombre="lote", operador_id=user.id)
    db.add(lote)
    db.flush()
    db.add(LoteOperador(lote_id=lote.id, operador_id=user.id, activo=True))
    return db, user, lote, pdf


def test_metricas_confia_en_huella_ante_reloj_adelantado(tmp_path: Path, monkeypatch):
    db, user, lote, pdf = _escenario(tmp_path, monkeypatch)
    stat = os.stat(pdf)
    # El equipo que cargó el PDF por CIFS iba adelantado: el mtime quedó "en el
    # futuro" respecto al reloj del servidor, pero la huella del origen coincide
    # con el archivo actual (nadie lo reemplazó).
    db.add(Extraccion(
        user_id=user.id, lote_id=lote.id,
        original_path=str(pdf).replace("\\", "/"),
        destino_path="out/uno.pdf", pagina_inicio=1, pagina_fin=1,
        processed_at=datetime.fromtimestamp(stat.st_mtime) - timedelta(seconds=25),
        source_size=stat.st_size, source_mtime_ns=stat.st_mtime_ns,
    ))
    db.commit()

    assert lote_service.metricas(db, lote)["realizados"] == 1


def test_metricas_invalida_extraccion_con_huella_distinta(tmp_path: Path, monkeypatch):
    db, user, lote, pdf = _escenario(tmp_path, monkeypatch)
    stat = os.stat(pdf)
    db.add(Extraccion(
        user_id=user.id, lote_id=lote.id,
        original_path=str(pdf).replace("\\", "/"),
        destino_path="out/uno.pdf", pagina_inicio=1, pagina_fin=1,
        processed_at=datetime.fromtimestamp(stat.st_mtime),
        source_size=stat.st_size, source_mtime_ns=stat.st_mtime_ns,
    ))
    db.commit()
    assert lote_service.metricas(db, lote)["realizados"] == 1

    # El origen fue reemplazado: la huella ya no coincide con el archivo.
    pdf.write_bytes(b"otra-version-del-documento")

    stats = lote_service.metricas(db, lote)
    assert stats["realizados"] == 0
    assert stats["pendientes"] == 1


def test_metricas_conserva_criterio_antiguo_sin_huella(tmp_path: Path, monkeypatch):
    db, user, lote, pdf = _escenario(tmp_path, monkeypatch)
    mtime = os.path.getmtime(pdf)
    # Filas antiguas sin huella: se mantiene el criterio de fechas estricto.
    db.add(Extraccion(
        user_id=user.id, lote_id=lote.id,
        original_path=str(pdf).replace("\\", "/"),
        destino_path="out/uno.pdf", pagina_inicio=1, pagina_fin=1,
        processed_at=datetime.fromtimestamp(mtime) - timedelta(hours=1),
    ))
    db.commit()

    stats = lote_service.metricas(db, lote)
    assert stats["realizados"] == 0
    assert stats["pendientes"] == 1


def test_dashboard_no_oculta_pendiente_con_extraccion_obsoleta(tmp_path: Path, monkeypatch):
    db, user, lote, pdf = _escenario(tmp_path, monkeypatch, rol="supervisor")
    mtime = os.path.getmtime(pdf)
    db.add(Extraccion(
        user_id=user.id, lote_id=lote.id,
        original_path=str(pdf).replace("\\", "/"),
        destino_path="out/uno.pdf", pagina_inicio=1, pagina_fin=1,
        processed_at=datetime.fromtimestamp(mtime) - timedelta(hours=1),
    ))
    db.commit()

    result = dashboard_router.dashboard(path="lote", pagina=1, tam=20, user=user, db=db)

    assert result["pendientes_count"] == 1
    assert result["pendientes"] == ["uno.pdf"]
    item = result["items"][0]
    assert item["estado"] == "pendiente"
    assert item["extraccion_id"] is None
    assert item["destino_path"] is None


def test_dashboard_mantiene_realizado_con_extraccion_vigente(tmp_path: Path, monkeypatch):
    db, user, lote, pdf = _escenario(tmp_path, monkeypatch, rol="supervisor")
    stat = os.stat(pdf)
    db.add(Extraccion(
        user_id=user.id, lote_id=lote.id,
        original_path=str(pdf).replace("\\", "/"),
        destino_path="out/uno.pdf", pagina_inicio=1, pagina_fin=1,
        processed_at=datetime.fromtimestamp(stat.st_mtime),
        source_size=stat.st_size, source_mtime_ns=stat.st_mtime_ns,
    ))
    db.commit()

    result = dashboard_router.dashboard(path="lote", pagina=1, tam=20, user=user, db=db)

    assert result["pendientes_count"] == 0
    item = result["items"][0]
    assert item["estado"] == "realizado"
    assert item["destino_path"] == "out/uno.pdf"


def test_guardar_registra_huella_del_origen(tmp_path: Path, monkeypatch):
    folder = tmp_path / "lote"
    folder.mkdir()
    source = folder / "a.pdf"
    pdf = fitz.open()
    pdf.new_page()
    pdf.save(str(source))
    pdf.close()

    db = _database()
    monkeypatch.setattr(lote_service, "raiz_origen", lambda _: str(tmp_path))
    monkeypatch.setattr(extraction_router, "raiz_origen", lambda _: str(tmp_path))
    monkeypatch.setattr(extraction_router, "raiz_repo", lambda _: str(tmp_path / "repo"))
    user = User(username="operador", password_hash="hash", rol="usuario", estado="activo")
    db.add(user)
    db.flush()
    lote = Lote(relative_path="lote", nombre="lote", operador_id=user.id)
    db.add(lote)
    db.flush()
    db.add(LoteOperador(lote_id=lote.id, operador_id=user.id, activo=True))
    document = LoteDocumento(
        lote_id=lote.id,
        document_key=lote_service.document_key(lote.id, str(source)),
        relative_path="a.pdf",
        nombre="a.pdf",
    )
    db.add(document)
    db.add(AssignmentLock(clave="global"))
    db.commit()

    _, token = lote_service.claim_document(db, document.id, user.id)
    db.commit()
    body = extraction_router.GuardarIn(
        ruta=str(source), documento_id=document.id, lease_token=token,
        inicio=1, fin=1, idempotency_key="huella-1",
    )
    assert extraction_router.guardar(body, user, db, None)["ok"]

    extraccion = db.query(Extraccion).one()
    stat = os.stat(source)
    assert extraccion.source_size == stat.st_size
    assert extraccion.source_mtime_ns == stat.st_mtime_ns

    # Aunque el equipo de carga haya dejado el mtime adelantado, la huella manda.
    extraccion.processed_at = datetime.fromtimestamp(stat.st_mtime) - timedelta(seconds=25)
    db.commit()
    assert lote_service.metricas(db, lote)["realizados"] == 1
