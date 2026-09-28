from pathlib import Path
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.models import AssignmentLock, Lote, LoteDocumento, LoteOperador, User
from app.routers import extraccion
from app.routers.extraccion import GuardarIn
from app.services import lotes as lote_service
from app.services.repo import generar_nombre_sin_colision


def test_nombre_sin_colision_usa_c_mayuscula(tmp_path: Path):
    (tmp_path / "2369926.pdf").write_bytes(b"original")
    assert generar_nombre_sin_colision(str(tmp_path), "2369926.pdf") == "2369926C.pdf"

    (tmp_path / "2369926C.pdf").write_bytes(b"duplicado")
    assert generar_nombre_sin_colision(str(tmp_path), "2369926.pdf") == "2369926CC.pdf"


def test_nombre_sin_colision_conserva_nombre_si_no_existe(tmp_path: Path):
    assert generar_nombre_sin_colision(str(tmp_path), "2369926.pdf") == "2369926.pdf"


def test_guardado_plano_colision_y_reextraccion_reemplaza(tmp_path: Path, monkeypatch):
    origin = tmp_path / "origen"
    repo = tmp_path / "repo"
    first_dir, second_dir = origin / "lote1", origin / "lote2"
    first_dir.mkdir(parents=True)
    second_dir.mkdir(parents=True)
    repo.mkdir()
    first_pdf, second_pdf = first_dir / "2369926.pdf", second_dir / "2369926.pdf"
    first_pdf.write_bytes(b"original-1")
    second_pdf.write_bytes(b"original-2")

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    user = User(username="operador", password_hash="x", rol="usuario", estado="activo")
    db.add(user)
    db.add(AssignmentLock(clave="global"))
    db.flush()

    def add_document(relative: str, source: Path):
        lote = Lote(relative_path=relative, nombre=relative, operador_id=user.id)
        db.add(lote)
        db.flush()
        db.add(LoteOperador(lote_id=lote.id, operador_id=user.id))
        document = LoteDocumento(
            lote_id=lote.id,
            document_key=lote_service.document_key(lote.id, str(source)),
            relative_path=source.name,
            nombre=source.name,
            reservado_por=user.id,
            lease_token=f"lease-{lote.id}",
            reservado_at=datetime.now(),
            lease_expires_at=datetime.now() + timedelta(minutes=10),
        )
        db.add(document)
        db.flush()
        return document

    first_doc = add_document("lote1", first_pdf)
    second_doc = add_document("lote2", second_pdf)
    db.commit()

    monkeypatch.setattr(extraccion, "raiz_origen", lambda _: str(origin))
    monkeypatch.setattr(extraccion, "raiz_repo", lambda _: str(repo))
    monkeypatch.setattr(extraccion, "extraer_paginas", lambda _src, inicio, _fin, destino, **_kwargs: Path(destino).write_bytes(f"pagina-{inicio}".encode()))

    first = extraccion.guardar(GuardarIn(ruta=str(first_pdf), documento_id=first_doc.id, lease_token="lease-1", inicio=1, fin=1, idempotency_key="save-1"), user, db, None)
    second = extraccion.guardar(GuardarIn(ruta=str(second_pdf), documento_id=second_doc.id, lease_token="lease-2", inicio=2, fin=2, idempotency_key="save-2"), user, db, None)
    assert Path(first["destino"]).parent == repo
    assert Path(first["destino"]).name == "2369926.pdf"
    assert Path(second["destino"]).name == "2369926C.pdf"

    first_doc = db.get(LoteDocumento, first_doc.id)
    first_doc.reservado_por = user.id
    first_doc.lease_token = "lease-reextra"
    first_doc.lease_expires_at = datetime.now() + timedelta(minutes=10)
    db.commit()
    redone = extraccion.guardar(GuardarIn(ruta=str(first_pdf), documento_id=first_doc.id, lease_token="lease-reextra", inicio=3, fin=3, reextra=1, extraccion_id=first["extraccion_id"], idempotency_key="save-3"), user, db, None)
    assert redone["destino"] == first["destino"]
    assert Path(redone["destino"]).read_bytes() == b"pagina-3"
    assert not any(path.is_dir() for path in repo.iterdir())
