"""Alinea claves documentales con sensibilidad del filesystem.

Revision ID: 20260924_08
Revises: 20260924_07
Create Date: 2026-09-24
"""
from hashlib import sha256
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260924_08"
down_revision: Union[str, None] = "20260924_07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, lote_id, original_path FROM extracciones ORDER BY id DESC"
    )).fetchall()
    seen: set[str] = set()
    for row in rows:
        filename = os.path.normcase(os.path.basename((row.original_path or "").replace("\\", "/")))
        key = sha256(f"{row.lote_id or 0}:{filename}".encode("utf-8")).hexdigest()
        if key in seen:
            bind.execute(sa.text("DELETE FROM extracciones WHERE id = :id"), {"id": row.id})
        else:
            seen.add(key)
            bind.execute(sa.text("UPDATE extracciones SET original_key = :key WHERE id = :id"), {"key": key, "id": row.id})


def downgrade() -> None:
    pass
