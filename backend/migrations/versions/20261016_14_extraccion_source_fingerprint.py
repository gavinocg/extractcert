"""Guarda la huella del origen (tamaño y mtime) en cada extracción.

Revision ID: 20261016_14
Revises: 20260929_13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261016_14"
down_revision: Union[str, None] = "20260929_13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("extracciones", sa.Column("source_size", sa.BigInteger(), nullable=True))
    op.add_column("extracciones", sa.Column("source_mtime_ns", sa.BigInteger(), nullable=True))
    op.add_column("tramite_errores", sa.Column("source_size", sa.BigInteger(), nullable=True))
    op.add_column("tramite_errores", sa.Column("source_mtime_ns", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("tramite_errores", "source_mtime_ns")
    op.drop_column("tramite_errores", "source_size")
    op.drop_column("extracciones", "source_mtime_ns")
    op.drop_column("extracciones", "source_size")
