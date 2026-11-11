"""Review store: saved screenings and user-initiated review decisions (separate SQLite file).

Kept apart from the project database, which the API opens read-only and whose finance tables
are never touched. Submitted text is stored ONLY when the caller explicitly asks to save it.
Review decisions are append-only and hash-chained: each row's hash covers its content, EVERY
field of the screening it refers to and the previous row's hash. ``verify_chain`` therefore
detects an edit of any stored field, and a deletion or reordering of decisions that has a
successor.

Threat model: this is TAMPER EVIDENCE against accidental or casual edits of the SQLite file. It
does not protect against an attacker who can rewrite the database and recompute every hash, and
deleting the newest decisions (the tail) leaves a valid shorter chain. Neither is detectable
without an external anchor (e.g. a periodically exported head hash), which is not implemented.
Writes are serialised by a per-process lock; a single API process is assumed.
"""

import hashlib
import json
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    create_engine,
    event,
    select,
)
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

GENESIS = "0" * 64
SCHEMA_VERSION = "compassio-review-store/1"


class ReviewBase(DeclarativeBase):
    metadata = MetaData()


class ScreeningRecord(ReviewBase):
    __tablename__ = "screenings"

    screening_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    model_key: Mapped[str] = mapped_column(String(10))
    model_version: Mapped[str] = mapped_column(String(120))
    model_status: Mapped[str] = mapped_column(String(40))
    operational_mode: Mapped[str] = mapped_column(String(40))
    artifact_sha256: Mapped[str] = mapped_column(String(64))
    model_fingerprint: Mapped[str] = mapped_column(String(64))
    threshold: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    is_climate_related: Mapped[bool] = mapped_column(Boolean)
    input_sha256: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[str | None] = mapped_column(String(240))
    source_id: Mapped[str | None] = mapped_column(String(80))
    saved_title: Mapped[str | None] = mapped_column(Text)
    saved_description: Mapped[str | None] = mapped_column(Text)


class ReviewDecision(ReviewBase):
    __tablename__ = "review_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screening_id: Mapped[str] = mapped_column(ForeignKey("screenings.screening_id"))
    decision: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)
    reviewer: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    prev_hash: Mapped[str] = mapped_column(String(64))
    row_hash: Mapped[str] = mapped_column(String(64))


def _iso(moment: datetime) -> str:
    aware = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat()


SCREENING_FIELDS = (
    "screening_id",
    "model_key",
    "model_version",
    "model_status",
    "operational_mode",
    "artifact_sha256",
    "model_fingerprint",
    "threshold",
    "score",
    "is_climate_related",
    "input_sha256",
    "project_id",
    "source_id",
    "saved_title",
    "saved_description",
)


def screening_digest(rec: ScreeningRecord) -> str:
    """Hash of every stored screening field (an edit of any one breaks the review chain)."""
    payload: dict[str, Any] = {k: getattr(rec, k) for k in SCREENING_FIELDS}
    payload["created_at"] = _iso(rec.created_at)
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def row_hash(
    prev: str, screening: str, decision: str, note: str | None, reviewer: str, created_at: datetime
) -> str:
    payload = json.dumps(
        [prev, screening, decision, note or "", reviewer, _iso(created_at)], ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChainStatus:
    valid: bool
    decisions: int
    first_invalid_id: int | None


class ReviewStore:
    def __init__(self, url: str) -> None:
        parsed = make_url(url)
        if parsed.get_backend_name() == "sqlite" and parsed.database:
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url)
        self._write_lock = threading.Lock()
        if parsed.get_backend_name() == "sqlite":

            @event.listens_for(self.engine, "connect")
            def _fk(dbapi_connection: Any, _record: Any) -> None:
                dbapi_connection.execute("PRAGMA foreign_keys=ON")

        ReviewBase.metadata.create_all(self.engine)

    def save_screening(self, **fields: Any) -> ScreeningRecord:
        record = ScreeningRecord(
            screening_id=str(uuid.uuid4()), created_at=datetime.now(UTC), **fields
        )
        with Session(self.engine, expire_on_commit=False) as session, session.begin():
            session.add(record)
        return record

    def get_screening(self, screening_id: str) -> ScreeningRecord | None:
        with Session(self.engine, expire_on_commit=False) as session:
            return session.get(ScreeningRecord, screening_id)

    def add_review(
        self, screening_id: str, decision: str, note: str | None, reviewer: str
    ) -> ReviewDecision:
        with (
            self._write_lock,
            Session(self.engine, expire_on_commit=False) as session,
            session.begin(),
        ):
            screening = session.get(ScreeningRecord, screening_id)
            if screening is None:
                raise KeyError(screening_id)
            last = session.scalars(
                select(ReviewDecision).order_by(ReviewDecision.id.desc()).limit(1)
            ).first()
            prev = last.row_hash if last else GENESIS
            now = datetime.now(UTC)
            row = ReviewDecision(
                screening_id=screening_id,
                decision=decision,
                note=note,
                reviewer=reviewer,
                created_at=now,
                prev_hash=prev,
                row_hash=row_hash(prev, screening_digest(screening), decision, note, reviewer, now),
            )
            session.add(row)
        return row

    def reviews_for(self, screening_id: str) -> list[ReviewDecision]:
        with Session(self.engine, expire_on_commit=False) as session:
            return list(
                session.scalars(
                    select(ReviewDecision)
                    .where(ReviewDecision.screening_id == screening_id)
                    .order_by(ReviewDecision.id)
                )
            )

    def verify_chain(self) -> ChainStatus:
        with Session(self.engine, expire_on_commit=False) as session:
            prev, count = GENESIS, 0
            for row in session.scalars(select(ReviewDecision).order_by(ReviewDecision.id)):
                screening = session.get(ScreeningRecord, row.screening_id)
                expected = (
                    row_hash(
                        prev,
                        screening_digest(screening),
                        row.decision,
                        row.note,
                        row.reviewer,
                        row.created_at,
                    )
                    if screening is not None
                    else None
                )
                if row.prev_hash != prev or row.row_hash != expected:
                    return ChainStatus(False, count, row.id)
                prev, count = row.row_hash, count + 1
            return ChainStatus(True, count, None)
