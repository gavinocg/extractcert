"""Agrega leases para notificaciones recuperables.

Revision ID: 20260924_04
Revises: 20260924_03
Create Date: 2026-09-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260924_04"
down_revision: Union[str, None] = "20260924_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lotes", sa.Column("notification_token", sa.String(36), nullable=True))
    op.add_column("lotes", sa.Column("notification_started_at", sa.DateTime(), nullable=True))
    op.add_column("notificaciones", sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    op.drop_column("notificaciones", "updated_at")
    op.drop_column("lotes", "notification_started_at")
    op.drop_column("lotes", "notification_token")
