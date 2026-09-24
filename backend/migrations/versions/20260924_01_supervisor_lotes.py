"""Agrega supervisor, correo y estructura de lotes.

Revision ID: 20260924_01
Revises:
Create Date: 2026-09-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260924_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    op.execute("ALTER TABLE users MODIFY rol ENUM('usuario','supervisor','administrador') NOT NULL DEFAULT 'usuario'")
    if "email" not in {column["name"] for column in inspector.get_columns("users")}:
        op.add_column("users", sa.Column("email", sa.String(255), nullable=True))
    inspector = sa.inspect(op.get_bind())
    if "uq_users_email" not in {constraint["name"] for constraint in inspector.get_unique_constraints("users")}:
        op.create_unique_constraint("uq_users_email", "users", ["email"])

    if "lotes" not in inspector.get_table_names():
        op.create_table(
        "lotes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("relative_path", sa.String(700), nullable=False),
        sa.Column("nombre", sa.String(255), nullable=False),
        sa.Column("operador_id", sa.Integer(), nullable=True),
        sa.Column("asignado_por_id", sa.Integer(), nullable=True),
        sa.Column("estado", sa.String(30), server_default="sin_asignar", nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("notified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["operador_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["asignado_por_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("relative_path", name="uq_lotes_relative_path"),
        )
        op.create_index("ix_lotes_operador_estado", "lotes", ["operador_id", "estado"])

    inspector = sa.inspect(op.get_bind())
    if "lote_asignaciones_historial" not in inspector.get_table_names():
        op.create_table(
        "lote_asignaciones_historial",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lote_id", sa.Integer(), nullable=False),
        sa.Column("operador_id", sa.Integer(), nullable=False),
        sa.Column("asignado_por_id", sa.Integer(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("unassigned_at", sa.DateTime(), nullable=True),
        sa.Column("motivo", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(["lote_id"], ["lotes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["operador_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["asignado_por_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_lote_historial_lote", "lote_asignaciones_historial", ["lote_id", "assigned_at"])

    inspector = sa.inspect(op.get_bind())
    if "notificaciones" not in inspector.get_table_names():
        op.create_table(
        "notificaciones",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lote_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("destinatario", sa.String(255), nullable=False),
        sa.Column("estado", sa.String(20), server_default="pendiente", nullable=False),
        sa.Column("intentos", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["lote_id"], ["lotes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_notificaciones_lote_tipo", "notificaciones", ["lote_id", "tipo"])

    inspector = sa.inspect(op.get_bind())
    if "lote_id" not in {column["name"] for column in inspector.get_columns("extracciones")}:
        op.add_column("extracciones", sa.Column("lote_id", sa.Integer(), nullable=True))
        op.create_foreign_key("fk_extracciones_lote", "extracciones", "lotes", ["lote_id"], ["id"], ondelete="SET NULL")
        op.create_index("ix_extracciones_lote", "extracciones", ["lote_id"])
    if "lote_id" not in {column["name"] for column in inspector.get_columns("tramite_errores")}:
        op.add_column("tramite_errores", sa.Column("lote_id", sa.Integer(), nullable=True))
        op.create_foreign_key("fk_tramite_errores_lote", "tramite_errores", "lotes", ["lote_id"], ["id"], ondelete="SET NULL")
        op.create_index("ix_tramite_errores_lote", "tramite_errores", ["lote_id"])


def downgrade() -> None:
    op.drop_index("ix_tramite_errores_lote", table_name="tramite_errores")
    op.drop_constraint("fk_tramite_errores_lote", "tramite_errores", type_="foreignkey")
    op.drop_column("tramite_errores", "lote_id")
    op.drop_index("ix_extracciones_lote", table_name="extracciones")
    op.drop_constraint("fk_extracciones_lote", "extracciones", type_="foreignkey")
    op.drop_column("extracciones", "lote_id")
    op.drop_table("notificaciones")
    op.drop_table("lote_asignaciones_historial")
    op.drop_table("lotes")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_column("users", "email")
    op.execute("ALTER TABLE users MODIFY rol ENUM('usuario','administrador') NOT NULL DEFAULT 'usuario'")
