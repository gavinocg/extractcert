"""Indices para sincronizacion y metricas agregadas.

Revision ID: 20260928_11
Revises: 20260924_10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260928_11"
down_revision: Union[str, None] = "20260924_10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEXES = {
    "lote_operadores": [("ix_lote_operadores_operador_activo_lote", ["operador_id", "activo", "lote_id"])],
    "lote_documentos": [
        ("ix_lote_documentos_lote_lease", ["lote_id", "lease_expires_at"]),
        ("ix_lote_documentos_completed_estado_presente", ["completed_by", "estado", "presente"]),
    ],
    "extracciones": [
        ("ix_extracciones_lote_processed", ["lote_id", "processed_at"]),
        ("ix_extracciones_documento_processed", ["documento_id", "processed_at"]),
        ("ix_extracciones_user_created_id", ["user_id", "created_at", "id"]),
        ("ix_extracciones_created_id", ["created_at", "id"]),
    ],
    "extraccion_versiones": [
        ("ix_extraccion_versiones_autor_created", ["autor_id", "created_at"]),
        ("ix_extraccion_versiones_documento_version", ["documento_id", "version"]),
    ],
    "tramite_errores": [("ix_tramite_errores_lote_updated", ["lote_id", "updated_at"])],
    "lote_asignaciones_historial": [
        ("ix_lote_historial_lote_operador_unassigned", ["lote_id", "operador_id", "unassigned_at"]),
    ],
}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for table, definitions in INDEXES.items():
        if table not in tables:
            continue
        existing = {item["name"] for item in inspector.get_indexes(table)}
        for name, columns in definitions:
            if name not in existing:
                op.create_index(name, table, columns)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for table, definitions in reversed(list(INDEXES.items())):
        if table not in tables:
            continue
        existing = {item["name"] for item in inspector.get_indexes(table)}
        for name, _ in definitions:
            if name in existing:
                op.drop_index(name, table_name=table)
