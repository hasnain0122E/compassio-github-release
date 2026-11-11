"""Engine and session factories.

* Writers (migrations, ingestion) use :func:`create_write_engine`.
* The HTTP API uses :func:`create_read_engine`: for SQLite the file is opened **read-only**
  (``mode=ro``), so a request can never modify data or create an empty database file.
"""

import sqlite3
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool


class DatabaseNotReadyError(RuntimeError):
    """The database file is missing or has not been migrated."""


def sqlite_path(url: str) -> Path | None:
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite" or not parsed.database:
        return None
    return Path(parsed.database)


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_write_engine(url: str) -> Engine:
    path = sqlite_path(url)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url)
    if path is not None:
        _enable_sqlite_foreign_keys(engine)
    return engine


def create_read_engine(url: str, *, bounded_pool: bool = True) -> Engine:
    path = sqlite_path(url)
    if path is None:
        return create_engine(url, pool_pre_ping=True)
    resolved = path.resolve()

    def _connect() -> sqlite3.Connection:
        if not resolved.is_file():
            raise DatabaseNotReadyError(
                f"database file not found: {resolved}; run `uv run compassio-db migrate` "
                "and `uv run compassio-db ingest --source all`"
            )
        return sqlite3.connect(f"{resolved.as_uri()}?mode=ro", uri=True, check_same_thread=False)

    # Safe with C11 on or off: SingletonThreadPool can close an in-use connection
    # when the API worker-thread population exceeds its pool size.
    engine = (
        create_engine(
            "sqlite://",
            creator=_connect,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_timeout=2,
        )
        if bounded_pool
        else create_engine("sqlite://", creator=_connect)
    )
    _enable_sqlite_foreign_keys(engine)
    return engine


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
