"""Seguridad de contrasenas y auditoria.

Revision ID: 20260928_12
Revises: 20260928_11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260928_12"
down_revision: Union[str, None] = "20260928_11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "users" in tables:
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "must_change_password" not in columns:
            op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        if "password_changed_at" not in columns:
            op.add_column("users", sa.Column("password_changed_at", sa.DateTime(), nullable=True))
        if "token_version" not in columns:
            op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default=sa.text("1")))

    inspector = sa.inspect(bind)
    if "security_audit" not in inspector.get_table_names():
        op.create_table(
            "security_audit",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("usuario_id", sa.Integer(), nullable=True),
            sa.Column("actor_id", sa.Integer(), nullable=True),
            sa.Column("evento", sa.String(length=40), nullable=False),
            sa.Column("ip", sa.String(length=45), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["usuario_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "security_audit" in inspector.get_table_names():
        op.drop_table("security_audit")
    inspector = sa.inspect(bind)
    if "users" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("users")}
        for name in ("token_version", "password_changed_at", "must_change_password"):
            if name in columns:
                op.drop_column("users", name)
