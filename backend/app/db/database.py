"""Conexión y sesiones de SQLAlchemy."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  (registra los modelos)

    Base.metadata.create_all(bind=engine)
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "observaciones" in insp.get_table_names():
        columnas = {c["name"] for c in insp.get_columns("observaciones")}
        if "orden" not in columnas:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE observaciones ADD COLUMN orden INTEGER NOT NULL DEFAULT 0"))
    if "users" in insp.get_table_names():
        columnas = {c["name"] for c in insp.get_columns("users")}
        with engine.begin() as conn:
            if "nombre" not in columnas:
                conn.execute(text("ALTER TABLE users ADD COLUMN nombre VARCHAR(100) NOT NULL DEFAULT ''"))
            if "estado" not in columnas:
                conn.execute(text("ALTER TABLE users ADD COLUMN estado VARCHAR(20) NOT NULL DEFAULT 'activo'"))