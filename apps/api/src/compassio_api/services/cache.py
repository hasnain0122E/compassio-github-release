"""In-process cache for aggregate responses, keyed on the database's data version.

The API is read-only; data changes only through ``compassio-db ingest``, which records a
completed ``import_runs`` row. The version key (latest completed run id + run count) therefore
invalidates every entry after any successful ingestion. Entries are per engine (one database),
and keys include the access mode and visible sources, so a rights change can never be served
from a stale entry.
"""

from collections.abc import Callable, Hashable
from threading import Lock
from typing import Any, cast
from weakref import WeakKeyDictionary

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from compassio_api.db.models import ImportRun

MAX_ENTRIES = 256

_lock = Lock()
_stores: "WeakKeyDictionary[Engine, dict[Hashable, Any]]" = WeakKeyDictionary()


def data_version(session: Session) -> tuple[int, int]:
    latest, runs = session.execute(
        select(func.max(ImportRun.id), func.count(ImportRun.id)).where(
            ImportRun.status == "completed"
        )
    ).one()
    return int(latest or 0), int(runs or 0)


def cached[T](session: Session, key: Hashable, compute: Callable[[], T]) -> T:
    engine = session.get_bind()
    if not isinstance(engine, Engine):
        return compute()
    full_key = (data_version(session), key)
    with _lock:
        store = _stores.setdefault(engine, {})
        if full_key in store:
            return cast(T, store[full_key])
    value = compute()
    with _lock:
        if len(store) >= MAX_ENTRIES:
            store.clear()
        store[full_key] = value
    return value
