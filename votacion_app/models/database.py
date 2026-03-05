"""
Modelos de base de datos - Sistema de Registro Electoral
"""
import os
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime,
    ForeignKey, Enum, UniqueConstraint, event
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.pool import StaticPool
import enum

Base = declarative_base()


class EstadoCedula(str, enum.Enum):
    DISPONIBLE = "DISPONIBLE"
    INHABILITADA = "INHABILITADA"


class EstadoLider(str, enum.Enum):
    ACTIVO = "ACTIVO"
    INACTIVO = "INACTIVO"


class Lider(Base):
    __tablename__ = "lider"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(200), nullable=False)
    total_votantes = Column(Integer, default=0, nullable=False)
    estado = Column(String(20), default=EstadoLider.ACTIVO, nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

    votantes = relationship("Votante", back_populates="lider")

    def __repr__(self):
        return f"<Lider(id={self.id}, nombre='{self.nombre}', total={self.total_votantes})>"


class Votante(Base):
    __tablename__ = "votante"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cedula = Column(String(20), nullable=False, unique=True)
    nombre = Column(String(200), nullable=False)
    lider_id = Column(Integer, ForeignKey("lider.id"), nullable=False)
    fecha_registro = Column(DateTime, default=datetime.utcnow)

    lider = relationship("Lider", back_populates="votantes")

    __table_args__ = (
        UniqueConstraint("cedula", name="uq_votante_cedula"),
    )

    def __repr__(self):
        return f"<Votante(cedula='{self.cedula}', nombre='{self.nombre}')>"


class ControlCedula(Base):
    __tablename__ = "control_cedula"

    cedula = Column(String(20), primary_key=True)
    estado = Column(String(20), nullable=False, default=EstadoCedula.DISPONIBLE)
    fecha_inhabilitacion = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<ControlCedula(cedula='{self.cedula}', estado='{self.estado}')>"


# ─── Engine & Session ───────────────────────────────────────────────────────

def _resolve_database_url() -> str:
    """Resuelve la URL de BD.

    Prioridad:
    1) TEST_MODE=1  -> SQLite en memoria
    2) DATABASE_URL -> lo provisto por entorno
    3) Default      -> sqlite local ./votacion.db
    """
    if os.getenv("TEST_MODE") == "1":
        return "sqlite+pysqlite:///:memory:"
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return _normalize_database_url(env_url)

    # Vercel tiene filesystem efímero; /tmp es el lugar permitido para escritura.
    if os.getenv("VERCEL") == "1" or os.getenv("NOW_REGION"):
        return "sqlite+pysqlite:////tmp/votacion.db"

    return "sqlite+pysqlite:///./votacion.db"


def _normalize_database_url(url: str) -> str:
    """Normaliza DATABASE_URL para SQLAlchemy.

    - Convierte `postgres://` -> `postgresql://`.
    - Fuerza el driver `psycopg` (psycopg3) cuando el esquema es `postgresql`.
    - En Supabase, agrega `sslmode=require` si no está presente.
    """
    raw = (url or "").strip()
    if not raw:
        return raw

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()

    # Soporta `postgres://...` además de `postgresql://...`
    if scheme == "postgres":
        parsed = parsed._replace(scheme="postgresql")
        scheme = "postgresql"

    # SQLAlchemy por defecto usa psycopg2 si no se especifica driver.
    # En Vercel instalamos psycopg3, así que forzamos `+psycopg`.
    if scheme == "postgresql":
        parsed = parsed._replace(scheme="postgresql+psycopg")
        scheme = "postgresql+psycopg"

    # Si alguien pega una URL con psycopg2, la reescribimos a psycopg3.
    if scheme.startswith("postgresql+psycopg2"):
        parsed = parsed._replace(scheme="postgresql+psycopg")
        scheme = "postgresql+psycopg"

    host = (parsed.hostname or "").lower()
    is_supabase = ("supabase.co" in host) or ("supabase.com" in host)

    if is_supabase:
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.setdefault("sslmode", "require")
        parsed = parsed._replace(query=urlencode(query))

    return urlunparse(parsed)


DATABASE_URL = _resolve_database_url()
_IS_SQLITE = DATABASE_URL.lower().startswith("sqlite")

engine_kwargs = {"echo": False}
if _IS_SQLITE:
    engine_kwargs.update(
        {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
    )

engine = create_engine(DATABASE_URL, **engine_kwargs)

# Habilitar WAL mode y FK enforcement en SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if not _IS_SQLITE:
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db():
    """Crea todas las tablas si no existen."""
    Base.metadata.create_all(bind=engine)


def get_session():
    """Context manager para sesiones DB."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
