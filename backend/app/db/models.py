"""Modelos ORM."""
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[str] = mapped_column(
        Enum("usuario", "administrador", name="rol"),
        default="usuario",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    extracciones: Mapped[list["Extraccion"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Setting(Base):
    __tablename__ = "settings"

    clave: Mapped[str] = mapped_column(String(100), primary_key=True)
    valor: Mapped[str] = mapped_column(Text, nullable=False)


class Extraccion(Base):
    __tablename__ = "extracciones"
    __table_args__ = (
        Index("idx_extracciones_original", "original_path"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    original_path: Mapped[str] = mapped_column(Text, nullable=False)
    destino_path: Mapped[str] = mapped_column(Text, nullable=False)
    pagina_inicio: Mapped[int] = mapped_column(Integer, nullable=False)
    pagina_fin: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(
        Enum("realizado", "rehecho", name="estado"),
        default="realizado",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="extracciones")


class TramiteError(Base):
    __tablename__ = "tramite_errores"
    __table_args__ = (Index("idx_tramite_error_original", "original_path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    observacion: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    user: Mapped[User] = relationship()


class Contacto(Base):
    __tablename__ = "contactos"
    __table_args__ = (Index("idx_contacto_email", "email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)