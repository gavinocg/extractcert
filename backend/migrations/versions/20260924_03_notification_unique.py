"""Evita notificaciones duplicadas por evento y destinatario.

Revision ID: 20260924_03
Revises: 20260924_02
Create Date: 2026-09-24
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260924_03"
down_revision: Union[str, None] = "20260924_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(__import__("sqlalchemy").text(
        "SELECT id, lote_id, tipo, destinatario, estado FROM notificaciones "
        "ORDER BY lote_id, tipo, destinatario, CASE WHEN estado = 'enviado' THEN 0 ELSE 1 END, id DESC"
    )).fetchall()
    seen = set()
    duplicate_ids = []
    for row in rows:
        key = (row.lote_id, row.tipo, row.destinatario)
        if key in seen:
            duplicate_ids.append(row.id)
        else:
            seen.add(key)
    for row_id in duplicate_ids:
        bind.execute(__import__("sqlalchemy").text("DELETE FROM notificaciones WHERE id = :id"), {"id": row_id})
    op.create_index(
        "uq_notificaciones_evento_destinatario",
        "notificaciones",
        ["lote_id", "tipo", "destinatario"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_notificaciones_evento_destinatario", table_name="notificaciones")
