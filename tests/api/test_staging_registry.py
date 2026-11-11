"""Backend source registry: snapshot integrity, strays, drift, no-overwrite fetch (ARTIFICIAL;
the network is never contacted -- urlopen is replaced by a fake)."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from compassio_api.staging import fetch as fetch_module
from compassio_api.staging.registry import (
    TRACKED_REGISTRY,
    BackendRegistry,
    RegistryError,
    SnapshotEntry,
    load_registry,
    raw_db_dir,
    save_registry,
    validate_registry,
)
from compassio_ml.integrity.hashing import sha256_file


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.status = status
        self.headers = {"Content-Type": "application/json", "Date": "example-date"}
        self._body = body

    def read(self, limit: int) -> bytes:
        return self._body[:limit]

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _fake_urlopen(body: bytes, status: int = 200) -> Any:
    def opener(request: object, timeout: int) -> _FakeResponse:
        return _FakeResponse(body, status)

    return opener


def _freeze(monkeypatch: pytest.MonkeyPatch, moment: datetime) -> None:
    class _Frozen(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> "_Frozen":
            return cls.fromtimestamp(moment.timestamp(), tz=tz)

    monkeypatch.setattr(fetch_module, "datetime", _Frozen)


def _register_file(root: Path, content: bytes = b'[{"example": 1}]') -> SnapshotEntry:
    folder = raw_db_dir(root) / "gcf_api_projects" / "20260101T000000Z"
    folder.mkdir(parents=True)
    target = folder / "projects.json"
    target.write_bytes(content)
    entry = SnapshotEntry(
        backend_source_id="gcf_api_projects",
        snapshot_id="20260101T000000Z",
        publisher="example publisher",
        description="example",
        landing_url="https://example.invalid/",
        retrieval_url="https://example.invalid/v1/projects",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        http_status=200,
        http_metadata={},
        original_filename="projects",
        stored_relpath="gcf_api_projects/20260101T000000Z/projects.json",
        sha256=sha256_file(target),
        size_bytes=target.stat().st_size,
        file_format="json",
        source_update_date=None,
        source_update_date_note="example",
        attribution_notes="example",
        unit_of_observation="example",
    )
    save_registry(root, BackendRegistry(snapshots=[entry]))
    return entry


def test_valid_registry_passes_and_tracked_copy_is_identical(tmp_path: Path) -> None:
    _register_file(tmp_path)

    report = validate_registry(tmp_path)

    assert report.ok, report.errors
    local = (raw_db_dir(tmp_path) / "registry.json").read_text(encoding="utf-8")
    assert (tmp_path / TRACKED_REGISTRY).read_text(encoding="utf-8") == local
    assert '"rights_status": "not_reviewed"' in local


def test_changed_snapshot_is_rejected(tmp_path: Path) -> None:
    _register_file(tmp_path)
    (raw_db_dir(tmp_path) / "gcf_api_projects/20260101T000000Z/projects.json").write_bytes(
        b'[{"example": 2}]'
    )

    errors = validate_registry(tmp_path).errors

    assert any("sha256 changed" in e for e in errors)


def test_missing_snapshot_is_rejected(tmp_path: Path) -> None:
    _register_file(tmp_path)
    (raw_db_dir(tmp_path) / "gcf_api_projects/20260101T000000Z/projects.json").unlink()

    assert any("missing" in e for e in validate_registry(tmp_path).errors)


def test_unregistered_file_is_rejected(tmp_path: Path) -> None:
    _register_file(tmp_path)
    (raw_db_dir(tmp_path) / "gcf_api_projects" / "example_stray.json").write_text("[]")

    assert any("unregistered file" in e for e in validate_registry(tmp_path).errors)


def test_registry_drift_is_rejected(tmp_path: Path) -> None:
    _register_file(tmp_path)
    tracked = tmp_path / TRACKED_REGISTRY
    tracked.write_text(tracked.read_text(encoding="utf-8").replace("example publisher", "x"))

    assert any("differ" in e for e in validate_registry(tmp_path).errors)


def test_registry_model_cannot_claim_a_clearance() -> None:
    with pytest.raises(ValueError):
        SnapshotEntry.model_validate(
            {**_entry_dict(), "rights_status": "permitted"}  # not an allowed backend status
        )


def _entry_dict() -> dict[str, Any]:
    return {
        "backend_source_id": "gcf_api_projects",
        "snapshot_id": "20260101T000000Z",
        "publisher": "p",
        "description": "d",
        "landing_url": "u",
        "retrieval_url": "u",
        "retrieved_at": "2026-01-01T00:00:00Z",
        "http_status": 200,
        "http_metadata": {},
        "original_filename": "f",
        "stored_relpath": "r",
        "sha256": "0" * 64,
        "size_bytes": 1,
        "file_format": "json",
        "source_update_date": None,
        "source_update_date_note": "n",
        "attribution_notes": "a",
        "unit_of_observation": "u",
    }


def test_fetch_registers_a_new_snapshot_and_never_overwrites(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = json.dumps([{"ApprovedRef": "FP901"}]).encode()
    monkeypatch.setattr(fetch_module, "urlopen", _fake_urlopen(body))
    _freeze(monkeypatch, datetime(2026, 2, 3, 4, 5, 6, tzinfo=UTC))

    entry = fetch_module.fetch_snapshot(tmp_path, "gcf_api_projects")

    assert entry.snapshot_id == "20260203T040506Z"
    assert entry.source_update_date is None  # no Last-Modified header: not invented
    assert validate_registry(tmp_path).ok
    with pytest.raises(FileExistsError):  # same timestamp -> same folder -> refused
        fetch_module.fetch_snapshot(tmp_path, "gcf_api_projects")
    assert len(load_registry(tmp_path).snapshots) == 1


def test_fetch_refuses_non_json_and_unknown_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch_module, "urlopen", _fake_urlopen(b"<html>not json</html>"))

    with pytest.raises(ValueError):
        fetch_module.fetch_snapshot(tmp_path, "gcf_api_projects")
    assert load_registry(tmp_path).snapshots == []
    with pytest.raises(RegistryError):
        fetch_module.fetch_snapshot(tmp_path, "example_unknown_source")
