from collections.abc import Callable, Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def configure_sqlite(engine: Engine) -> None:
    """SQLite (dev/tests only): let SQLAlchemy control transactions so SAVEPOINTs work, and enforce FKs.

    This is the workaround documented by SQLAlchemy for the pysqlite driver's transaction handling.
    """

    @event.listens_for(engine, "connect")
    def _connect(dbapi_conn, _):
        dbapi_conn.isolation_level = None
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine, "begin")
    def _begin(conn):
        conn.exec_driver_sql("BEGIN")


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
if engine.dialect.name == "sqlite":
    configure_sqlite(engine)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session_factory() -> Callable[[], Session]:
    """Background jobs open their own sessions from this factory (overridden in tests)."""
    return SessionLocal
