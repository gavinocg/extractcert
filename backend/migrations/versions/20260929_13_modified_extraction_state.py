"""Agrega estado modificado a extracciones.

Revision ID: 20260929_13
Revises: 20260928_12
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260929_13"
down_revision: Union[str, None] = "20260928_12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE extracciones MODIFY estado ENUM('realizado','rehecho','modificado') NOT NULL DEFAULT 'realizado'")


def downgrade() -> None:
    op.execute("UPDATE extracciones SET estado='rehecho' WHERE estado='modificado'")
    op.execute("ALTER TABLE extracciones MODIFY estado ENUM('realizado','rehecho') NOT NULL DEFAULT 'realizado'")
