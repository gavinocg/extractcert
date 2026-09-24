"""Amplía el identificador de tipo de notificación.

Revision ID: 20260924_02
Revises: 20260924_01
Create Date: 2026-09-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260924_02"
down_revision: Union[str, None] = "20260924_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "notificaciones",
        "tipo",
        existing_type=sa.String(30),
        type_=sa.String(100),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "notificaciones",
        "tipo",
        existing_type=sa.String(100),
        type_=sa.String(30),
        existing_nullable=False,
    )
