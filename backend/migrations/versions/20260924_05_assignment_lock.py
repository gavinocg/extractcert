"""Agrega fila estable para serializar asignaciones.

Revision ID: 20260924_05
Revises: 20260924_04
Create Date: 2026-09-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260924_05"
down_revision: Union[str, None] = "20260924_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assignment_locks",
        sa.Column("clave", sa.String(30), nullable=False),
        sa.PrimaryKeyConstraint("clave"),
    )
    op.execute("INSERT INTO assignment_locks (clave) VALUES ('global')")


def downgrade() -> None:
    op.drop_table("assignment_locks")
