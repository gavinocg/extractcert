"""Agrega default físico a processed_at.

Revision ID: 20260924_09
Revises: 20260924_08
Create Date: 2026-09-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260924_09"
down_revision: Union[str, None] = "20260924_08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "extracciones",
        "processed_at",
        existing_type=sa.DateTime(),
        existing_nullable=False,
        server_default=sa.func.now(),
    )


def downgrade() -> None:
    op.alter_column(
        "extracciones",
        "processed_at",
        existing_type=sa.DateTime(),
        existing_nullable=False,
        server_default=None,
    )
