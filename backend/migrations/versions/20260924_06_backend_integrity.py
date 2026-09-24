"""Integridad de extracciones, productividad e historial.

Revision ID: 20260924_06
Revises: 20260924_05
Create Date: 2026-09-24
"""
from hashlib import sha256
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260924_06"
down_revision: Union[str, None] = "20260924_05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _path_key(path: str) -> str:
    return sha256((path or "").replace("\\", "/").rstrip("/").encode("utf-8")).hexdigest()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    extraction_columns = {column["name"] for column in inspector.get_columns("extracciones")}
    history_columns = {column["name"] for column in inspector.get_columns("lote_asignaciones_historial")}
    if "original_key" not in extraction_columns:
        op.add_column("extracciones", sa.Column("original_key", sa.String(64), nullable=True))
    if "processed_at" not in extraction_columns:
        op.add_column("extracciones", sa.Column("processed_at", sa.DateTime(), nullable=True))
    if "completed_at" not in history_columns:
        op.add_column("lote_asignaciones_historial", sa.Column("completed_at", sa.DateTime(), nullable=True))
    if "notified_at" not in history_columns:
        op.add_column("lote_asignaciones_historial", sa.Column("notified_at", sa.DateTime(), nullable=True))

    rows = bind.execute(sa.text("SELECT id, original_path FROM extracciones ORDER BY id DESC")).fetchall()
    seen = set()
    for row in rows:
        key = _path_key(row.original_path)
        if key in seen:
            # Se conserva el archivo destino; sólo se elimina la fila histórica
            # incompatible con la regla vigente de una extracción por original.
            bind.execute(sa.text("DELETE FROM extracciones WHERE id = :id"), {"id": row.id})
        else:
            seen.add(key)
            bind.execute(sa.text(
                "UPDATE extracciones SET original_key = :key, processed_at = COALESCE(created_at, CURRENT_TIMESTAMP) WHERE id = :id"
            ), {"key": key, "id": row.id})

    # Recupera asociaciones de instalaciones con raíz X:/ o UNC antigua usando
    # el sufijo estable lote/ruta/nombre, sin depender de la raíz configurada.
    lots = bind.execute(sa.text("SELECT id, relative_path, nombre FROM lotes")).fetchall()
    pending = bind.execute(sa.text("SELECT id, original_path FROM extracciones WHERE lote_id IS NULL")).fetchall()
    for row in pending:
        normalized = (row.original_path or "").replace("\\", "/").rstrip("/").lower()
        matches = []
        for lot in lots:
            relative = (lot.relative_path or "").replace("\\", "/").strip("/").lower()
            name = (lot.nombre or "").strip("/").lower()
            if (relative and f"/{relative}/" in f"/{normalized}") or (name and f"/{name}/" in f"/{normalized}"):
                matches.append(lot.id)
        if len(set(matches)) == 1:
            bind.execute(sa.text("UPDATE extracciones SET lote_id = :lote WHERE id = :id"), {"lote": matches[0], "id": row.id})
    pending_errors = bind.execute(sa.text("SELECT id, original_path FROM tramite_errores WHERE lote_id IS NULL")).fetchall()
    for row in pending_errors:
        normalized = (row.original_path or "").replace("\\", "/").rstrip("/").lower()
        matches = [lot.id for lot in lots if (lot.relative_path and f"/{lot.relative_path.replace(chr(92), '/').strip('/').lower()}/" in f"/{normalized}")]
        if len(set(matches)) == 1:
            bind.execute(sa.text("UPDATE tramite_errores SET lote_id = :lote WHERE id = :id"), {"lote": matches[0], "id": row.id})

    # Reconciliación para bases donde 03 ya se aplicó: si aún existen duplicados,
    # conserva enviado antes que el id más reciente.
    notifications = bind.execute(sa.text(
        "SELECT id, lote_id, tipo, destinatario, estado FROM notificaciones "
        "ORDER BY lote_id, tipo, destinatario, CASE WHEN estado = 'enviado' THEN 0 ELSE 1 END, id DESC"
    )).fetchall()
    seen_notifications = set()
    for row in notifications:
        key = (row.lote_id, row.tipo, row.destinatario)
        if key in seen_notifications:
            bind.execute(sa.text("DELETE FROM notificaciones WHERE id = :id"), {"id": row.id})
        else:
            seen_notifications.add(key)

    unique_names = {item["name"] for item in sa.inspect(bind).get_unique_constraints("extracciones")}
    with op.batch_alter_table("extracciones") as batch:
        batch.alter_column("original_key", existing_type=sa.String(64), nullable=False)
        batch.alter_column("processed_at", existing_type=sa.DateTime(), nullable=False)
        if "uq_extracciones_original_key" not in unique_names:
            batch.create_unique_constraint("uq_extracciones_original_key", ["original_key"])


def downgrade() -> None:
    with op.batch_alter_table("extracciones") as batch:
        batch.drop_constraint("uq_extracciones_original_key", type_="unique")
        batch.drop_column("processed_at")
        batch.drop_column("original_key")
    op.drop_column("lote_asignaciones_historial", "notified_at")
    op.drop_column("lote_asignaciones_historial", "completed_at")
