"""Database engine and per-request session (lazily initialised).

The engine is created on first use, not at import, so the app can be
imported without a DATABASE_URL (the pure endpoints still work); DB-backed
endpoints raise a clear error if the URL is missing.
"""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _ensure_engine() -> sessionmaker[Session]:
    global _engine, _SessionLocal
    if _SessionLocal is None:
        if not settings.database_url:
            raise RuntimeError(
                "DATABASE_URL is not set -- create a .env from .env.example."
            )
        # pool_pre_ping avoids stale-connection errors against the pooler.
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False,
                                     autocommit=False)
    return _SessionLocal


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yield a session, always close it."""
    db = _ensure_engine()()
    try:
        yield db
    finally:
        db.close()
