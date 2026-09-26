"""SQLAlchemy engine and session factory — authoritative DB access."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import get_settings

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_database_url() -> str:
    import os
    url = os.environ.get("DATABASE_URL") or getattr(get_settings(), "database_url", None) or "sqlite:///./cintexa_bi.db"
    # Sync engine cannot use aiosqlite driver
    if "+aiosqlite" in url:
        url = url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


def get_engine(url: Optional[str] = None) -> Engine:
    global _engine
    if _engine is not None and url is None:
        return _engine
    database_url = url or get_database_url()
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )

    # SQLite FK enforcement
    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):  # noqa: ARG001
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    if url is None:
        _engine = engine
    return engine


def get_session_factory(engine: Optional[Engine] = None) -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is not None and engine is None:
        return _SessionLocal
    eng = engine or get_engine()
    factory = sessionmaker(bind=eng, autocommit=False, autoflush=False, expire_on_commit=False)
    if engine is None:
        _SessionLocal = factory
    return factory


@contextmanager
def session_scope(factory: Optional[sessionmaker] = None) -> Generator[Session, None, None]:
    """Transactional scope: commit on success, rollback on error."""
    SessionLocal = factory or get_session_factory()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(url: Optional[str] = None) -> Engine:
    """Create all tables from models (dev/test). Prefer Alembic in production."""
    from database.models import Base

    engine = get_engine(url)
    Base.metadata.create_all(bind=engine)
    return engine


def reset_engine() -> None:
    """Reset global engine/session (tests / restart simulation)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
