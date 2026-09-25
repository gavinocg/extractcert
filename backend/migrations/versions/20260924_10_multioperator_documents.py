"""Backend multioperador e inventario documental.

Revision ID: 20260924_10
Revises: 20260924_09
"""
from typing import Sequence, Union
from hashlib import sha256
import os

from alembic import op
import sqlalchemy as sa

revision: str = "20260924_10"
down_revision: Union[str, None] = "20260924_09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str):
    inspector = sa.inspect(op.get_bind())
    return {i["name"] for i in inspector.get_indexes(table)} | {u["name"] for u in inspector.get_unique_constraints(table) if u.get("name")}


def upgrade() -> None:
    if "lote_operadores" not in _tables():
        op.create_table("lote_operadores", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("lote_id", sa.Integer(), sa.ForeignKey("lotes.id", ondelete="CASCADE"), nullable=False), sa.Column("operador_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("activo", sa.Boolean(), server_default=sa.text("1"), nullable=False), sa.Column("asignado_por_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("assigned_at", sa.DateTime(), server_default=sa.func.now(), nullable=False), sa.Column("unassigned_at", sa.DateTime()))
    if "uq_lote_operador" not in _indexes("lote_operadores"):
        op.create_index("uq_lote_operador", "lote_operadores", ["lote_id", "operador_id"], unique=True)
    op.get_bind().execute(sa.text("INSERT INTO lote_operadores (lote_id, operador_id, activo, asignado_por_id, assigned_at) SELECT l.id, l.operador_id, 1, l.asignado_por_id, COALESCE(l.assigned_at, l.created_at) FROM lotes l LEFT JOIN lote_operadores lo ON lo.lote_id=l.id AND lo.operador_id=l.operador_id WHERE l.operador_id IS NOT NULL AND lo.id IS NULL"))

    if "lote_documentos" not in _tables():
        op.create_table("lote_documentos", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("lote_id", sa.Integer(), sa.ForeignKey("lotes.id", ondelete="CASCADE"), nullable=False), sa.Column("document_key", sa.String(64), nullable=False), sa.Column("relative_path", sa.String(700), nullable=False), sa.Column("nombre", sa.String(255), nullable=False), sa.Column("estado", sa.String(30), server_default="pendiente", nullable=False), sa.Column("presente", sa.Boolean(), server_default=sa.text("1"), nullable=False), sa.Column("version", sa.Integer(), server_default="0", nullable=False), sa.Column("source_size", sa.BigInteger()), sa.Column("source_mtime_ns", sa.BigInteger()), sa.Column("reservado_por", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("lease_token", sa.String(64)), sa.Column("reservado_at", sa.DateTime()), sa.Column("lease_expires_at", sa.DateTime()), sa.Column("completed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("completed_at", sa.DateTime()), sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))
    for column in (sa.Column("source_size", sa.BigInteger()), sa.Column("source_mtime_ns", sa.BigInteger())):
        if column.name not in _columns("lote_documentos"):
            op.add_column("lote_documentos", column)
    for name, cols, unique in (("uq_lote_document_key", ["lote_id", "document_key"], True), ("ix_lote_documentos_estado", ["lote_id", "estado"], False), ("ix_lote_documentos_lease", ["lease_expires_at"], False)):
        if name not in _indexes("lote_documentos"):
            op.create_index(name, "lote_documentos", cols, unique=unique)

    if "documento_id" not in _columns("extracciones"):
        op.add_column("extracciones", sa.Column("documento_id", sa.Integer(), sa.ForeignKey("lote_documentos.id", ondelete="SET NULL")))
    if "ix_extracciones_documento_id" not in _indexes("extracciones"):
        op.create_index("ix_extracciones_documento_id", "extracciones", ["documento_id"])
    if "idempotency_key" not in _columns("extracciones"):
        op.add_column("extracciones", sa.Column("idempotency_key", sa.String(100)))
    if "uq_extracciones_idempotency_key" not in _indexes("extracciones"):
        op.create_unique_constraint("uq_extracciones_idempotency_key", "extracciones", ["idempotency_key"])
    if "documento_id" not in _columns("tramite_errores"):
        op.add_column("tramite_errores", sa.Column("documento_id", sa.Integer(), sa.ForeignKey("lote_documentos.id", ondelete="SET NULL")))
    if "ix_tramite_errores_documento_id" not in _indexes("tramite_errores"):
        op.create_index("ix_tramite_errores_documento_id", "tramite_errores", ["documento_id"])
    if "extraccion_versiones" not in _tables():
        op.create_table("extraccion_versiones", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("extraccion_id", sa.Integer(), sa.ForeignKey("extracciones.id", ondelete="CASCADE"), nullable=False), sa.Column("documento_id", sa.Integer(), sa.ForeignKey("lote_documentos.id", ondelete="RESTRICT"), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.Column("autor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("pagina_inicio", sa.Integer(), nullable=False), sa.Column("pagina_fin", sa.Integer(), nullable=False), sa.Column("destino_path", sa.Text(), nullable=False), sa.Column("tipo", sa.String(20), nullable=False), sa.Column("idempotency_key", sa.String(100), nullable=False), sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))
        op.create_index("uq_extraccion_version", "extraccion_versiones", ["extraccion_id", "version"], unique=True)
    else:
        if "idempotency_key" not in _columns("extraccion_versiones"):
            op.add_column("extraccion_versiones", sa.Column("idempotency_key", sa.String(100)))
        if "uq_extraccion_version" not in _indexes("extraccion_versiones"):
            op.create_index("uq_extraccion_version", "extraccion_versiones", ["extraccion_id", "version"], unique=True)
        if "uq_extraccion_versiones_idempotency_key" not in _indexes("extraccion_versiones"):
            op.create_unique_constraint("uq_extraccion_versiones_idempotency_key", "extraccion_versiones", ["idempotency_key"])
    if "uq_extraccion_versiones_idempotency_key" not in _indexes("extraccion_versiones"):
        op.create_unique_constraint("uq_extraccion_versiones_idempotency_key", "extraccion_versiones", ["idempotency_key"])
    _backfill_legacy()


def _document_key(lote_id: int, path: str) -> str:
    filename = os.path.normcase(os.path.basename((path or "").replace("\\", "/")))
    return sha256(f"{lote_id}:{filename}".encode("utf-8")).hexdigest()


def _backfill_legacy() -> None:
    bind = op.get_bind()
    sources = bind.execute(sa.text("SELECT lote_id, original_path, user_id, processed_at, 'completado' estado FROM extracciones WHERE lote_id IS NOT NULL UNION ALL SELECT lote_id, original_path, user_id, updated_at, 'error' estado FROM tramite_errores WHERE lote_id IS NOT NULL ORDER BY lote_id, original_path")).mappings().all()
    for source in sources:
        key = _document_key(source["lote_id"], source["original_path"])
        name = os.path.basename((source["original_path"] or "").replace("\\", "/"))[:255]
        bind.execute(sa.text("INSERT INTO lote_documentos (lote_id, document_key, relative_path, nombre, estado, presente, version, completed_by, completed_at) SELECT :lote_id, :key, :name, :name, :estado, 1, :version, :user_id, :completed_at WHERE NOT EXISTS (SELECT 1 FROM lote_documentos WHERE lote_id=:lote_id AND document_key=:key)"), {**source, "key": key, "name": name, "version": 1 if source["estado"] == "completado" else 0, "completed_at": source["processed_at"]})
        document_id = bind.execute(sa.text("SELECT id FROM lote_documentos WHERE lote_id=:lote_id AND document_key=:key"), {"lote_id": source["lote_id"], "key": key}).scalar()
        table = "extracciones" if source["estado"] == "completado" else "tramite_errores"
        bind.execute(sa.text(f"UPDATE {table} SET documento_id=:document_id WHERE lote_id=:lote_id AND original_path=:original_path AND documento_id IS NULL"), {"document_id": document_id, "lote_id": source["lote_id"], "original_path": source["original_path"]})
    rows = bind.execute(sa.text("SELECT id, documento_id, user_id, pagina_inicio, pagina_fin, destino_path, estado, processed_at FROM extracciones WHERE documento_id IS NOT NULL ORDER BY id")).mappings().all()
    for row in rows:
        bind.execute(sa.text("INSERT INTO extraccion_versiones (extraccion_id, documento_id, version, autor_id, pagina_inicio, pagina_fin, destino_path, tipo, idempotency_key, created_at) SELECT :id, :documento_id, 1, :user_id, :pagina_inicio, :pagina_fin, :destino_path, :estado, :key, :processed_at WHERE NOT EXISTS (SELECT 1 FROM extraccion_versiones WHERE idempotency_key=:key)"), {**row, "key": f"legacy:{row['id']}"})
        bind.execute(sa.text("UPDATE lote_documentos SET version=GREATEST(version, 1), estado='completado', completed_by=:user_id, completed_at=:processed_at WHERE id=:documento_id"), row)


def downgrade() -> None:
    for table in ("extraccion_versiones",):
        if table in _tables(): op.drop_table(table)
    if "documento_id" in _columns("tramite_errores"): op.drop_column("tramite_errores", "documento_id")
    if "idempotency_key" in _columns("extracciones"): op.drop_column("extracciones", "idempotency_key")
    if "documento_id" in _columns("extracciones"): op.drop_column("extracciones", "documento_id")
    for table in ("lote_documentos", "lote_operadores"):
        if table in _tables(): op.drop_table(table)
