"""Modelos ORM."""
import hashlib
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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
    nombre: Mapped[str] = mapped_column(String(100), default="", server_default="", nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[str] = mapped_column(
        Enum("usuario", "supervisor", "administrador", name="rol"),
        default="usuario",
        nullable=False,
    )
    estado: Mapped[str] = mapped_column(
        Enum("activo", "inactivo", name="estado_usuario"),
        default="activo",
        server_default="activo",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    extracciones: Mapped[list["Extraccion"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Lote(Base):
    __tablename__ = "lotes"
    __table_args__ = (Index("ix_lotes_operador_estado", "operador_id", "estado"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    relative_path: Mapped[str] = mapped_column(String(700), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    operador_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    asignado_por_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    estado: Mapped[str] = mapped_column(String(30), default="sin_asignar", server_default="sin_asignar", nullable=False)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notification_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notification_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    operador: Mapped[User | None] = relationship(foreign_keys=[operador_id])
    asignado_por: Mapped[User | None] = relationship(foreign_keys=[asignado_por_id])
    miembros: Mapped[list["LoteOperador"]] = relationship(back_populates="lote", cascade="all, delete-orphan")
    documentos: Mapped[list["LoteDocumento"]] = relationship(back_populates="lote", cascade="all, delete-orphan")


class LoteOperador(Base):
    __tablename__ = "lote_operadores"
    __table_args__ = (Index("uq_lote_operador", "lote_id", "operador_id", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lotes.id", ondelete="CASCADE"), nullable=False)
    operador_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)
    asignado_por_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    lote: Mapped[Lote] = relationship(back_populates="miembros")
    operador: Mapped[User] = relationship(foreign_keys=[operador_id])


class LoteDocumento(Base):
    __tablename__ = "lote_documentos"
    __table_args__ = (
        Index("uq_lote_document_key", "lote_id", "document_key", unique=True),
        Index("ix_lote_documentos_estado", "lote_id", "estado"),
        Index("ix_lote_documentos_lease", "lease_expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lotes.id", ondelete="CASCADE"), nullable=False)
    document_key: Mapped[str] = mapped_column(String(64), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(700), nullable=False)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[str] = mapped_column(String(30), default="pendiente", server_default="pendiente", nullable=False)
    presente: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    source_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_mtime_ns: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reservado_por: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reservado_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    lote: Mapped[Lote] = relationship(back_populates="documentos")


class LoteAsignacionHistorial(Base):
    __tablename__ = "lote_asignaciones_historial"
    __table_args__ = (Index("ix_lote_historial_lote", "lote_id", "assigned_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lotes.id", ondelete="CASCADE"), nullable=False)
    operador_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    asignado_por_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    motivo: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Notificacion(Base):
    __tablename__ = "notificaciones"
    __table_args__ = (
        Index("ix_notificaciones_lote_tipo", "lote_id", "tipo"),
        Index("uq_notificaciones_evento_destinatario", "lote_id", "tipo", "destinatario", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lotes.id", ondelete="CASCADE"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)
    destinatario: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), default="pendiente", server_default="pendiente", nullable=False)
    intentos: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    clave: Mapped[str] = mapped_column(String(100), primary_key=True)
    valor: Mapped[str] = mapped_column(Text, nullable=False)


class AssignmentLock(Base):
    __tablename__ = "assignment_locks"

    clave: Mapped[str] = mapped_column(String(30), primary_key=True)


class Extraccion(Base):
    __tablename__ = "extracciones"
    __table_args__ = (
        Index("idx_extracciones_original", "original_path"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    lote_id: Mapped[int | None] = mapped_column(ForeignKey("lotes.id", ondelete="SET NULL"), index=True, nullable=True)
    documento_id: Mapped[int | None] = mapped_column(ForeignKey("lote_documentos.id", ondelete="SET NULL"), index=True, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    original_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_key: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False,
        default=lambda context: hashlib.sha256(
            (context.get_current_parameters().get("original_path") or "").replace("\\", "/").rstrip("/").encode("utf-8")
        ).hexdigest(),
    )
    destino_path: Mapped[str] = mapped_column(Text, nullable=False)
    pagina_inicio: Mapped[int] = mapped_column(Integer, nullable=False)
    pagina_fin: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(
        Enum("realizado", "rehecho", name="estado"),
        default="realizado",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="extracciones")


class ExtraccionVersion(Base):
    __tablename__ = "extraccion_versiones"
    __table_args__ = (Index("uq_extraccion_version", "extraccion_id", "version", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    extraccion_id: Mapped[int] = mapped_column(ForeignKey("extracciones.id", ondelete="CASCADE"), nullable=False)
    documento_id: Mapped[int] = mapped_column(ForeignKey("lote_documentos.id", ondelete="RESTRICT"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    autor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    pagina_inicio: Mapped[int] = mapped_column(Integer, nullable=False)
    pagina_fin: Mapped[int] = mapped_column(Integer, nullable=False)
    destino_path: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class TramiteError(Base):
    __tablename__ = "tramite_errores"
    __table_args__ = (Index("idx_tramite_error_original", "original_path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    observacion: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lote_id: Mapped[int | None] = mapped_column(ForeignKey("lotes.id", ondelete="SET NULL"), index=True, nullable=True)
    documento_id: Mapped[int | None] = mapped_column(ForeignKey("lote_documentos.id", ondelete="SET NULL"), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    user: Mapped[User] = relationship()


class Observacion(Base):
    __tablename__ = "observaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    descripcion: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    orden: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Contacto(Base):
    __tablename__ = "contactos"
    __table_args__ = (Index("idx_contacto_email", "email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
