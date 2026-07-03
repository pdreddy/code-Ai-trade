"""Database engine and session construction."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import Settings
from backend.app.core.database_url import normalize_sqlalchemy_database_url


def create_database_engine(settings: Settings) -> Engine:
    """Create a SQLAlchemy engine from application settings."""

    return create_engine(
        normalize_sqlalchemy_database_url(str(settings.database_url)), pool_pre_ping=True
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a typed SQLAlchemy session factory."""

    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Provide a transactional session scope for repository operations."""

    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
