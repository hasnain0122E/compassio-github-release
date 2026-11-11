"""Event-specific data-use authorizations (Task 009, ``configs/event_data_authorizations.yaml``).

An entry is a *user-reported organizer authorization* for a local event demonstration. It is
never a source-licence clearance: it does not change any ``rights_status`` and is honoured only
in ``COMPASSIO_SOURCE_DATA_ACCESS=hackathon_event`` (loopback clients only, never production).
See docs/hackathon/data_permission_scope.md.
"""

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class EventConfigError(RuntimeError):
    """The event authorization file or entry is missing or invalid (fail at startup)."""


class EventAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = ""
    event: str
    granted_by: str
    reported_scope: str
    evidence_status: Literal[
        "user_reported_verbal_confirmation",
        "user_asserted_no_written_evidence",
        "written_evidence_on_file",
    ]
    evidence_reference: str | None = None
    recorded_on: date
    # None = event dates not known yet (no assumed date). A set bound is enforced.
    valid_from: date | None = None
    valid_until: date | None = None
    permitted_uses: list[str] = Field(min_length=1)
    excluded_uses: list[str]
    sources: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> "EventAuthorization":
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValueError("valid_from is after valid_until")
        if self.evidence_status == "written_evidence_on_file" and not self.evidence_reference:
            raise ValueError("written_evidence_on_file requires evidence_reference")
        for use in ("public_deployment", "redistribution_of_records_or_files"):
            if use not in self.excluded_uses:
                raise ValueError(f"an event authorization must exclude {use}")
        return self

    def active_on(self, today: date) -> bool:
        if self.valid_from is not None and today < self.valid_from:
            return False
        return not (self.valid_until is not None and today > self.valid_until)

    @property
    def window(self) -> str:
        start = self.valid_from.isoformat() if self.valid_from else "not set"
        end = self.valid_until.isoformat() if self.valid_until else "not set"
        return f"{start} to {end}"


class _File(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    authorizations: dict[str, EventAuthorization]


def load_event_authorization(path: Path, key: str) -> EventAuthorization:
    if not path.is_file():
        raise EventConfigError(f"event authorization file not found: {path}")
    try:
        parsed = _File.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (ValidationError, yaml.YAMLError) as exc:
        raise EventConfigError(f"invalid event authorization file {path}: {exc}") from exc
    entry = parsed.authorizations.get(key)
    if entry is None:
        raise EventConfigError(f"unknown event authorization {key!r} in {path}")
    return entry.model_copy(update={"key": key})
