"""Respectful, bounded download of one backend source snapshot.

One HTTPS GET per run (no crawling, no page scraping), a generic client name, a timeout and a
size cap. Each run writes a NEW timestamped directory with exclusive-create semantics, so an
earlier snapshot is never overwritten. The payload must parse as the declared format before it
is registered.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from compassio_api.staging.registry import (
    BACKEND_SOURCES,
    RegistryError,
    SnapshotEntry,
    load_registry,
    raw_db_dir,
    save_registry,
    snapshot_id_for,
)
from compassio_ml.integrity.hashing import sha256_file

USER_AGENT = "compassio-backend-ingest/0.1 (non-commercial research; provenance-tracked)"
KEPT_HEADERS = ("content-type", "date", "last-modified", "etag", "content-length", "expires")
TIMEOUT_SECONDS = 120


def fetch_snapshot(data_root: Path, backend_source_id: str) -> SnapshotEntry:
    definition = BACKEND_SOURCES.get(backend_source_id)
    if definition is None:
        raise RegistryError(f"unknown backend source {backend_source_id!r}")
    retrieved_at = datetime.now(UTC).replace(microsecond=0)
    snapshot_id = snapshot_id_for(retrieved_at)
    folder = raw_db_dir(data_root) / backend_source_id / snapshot_id
    folder.mkdir(parents=True, exist_ok=False)  # never reuse a snapshot directory
    filename = Path(urlparse(definition.retrieval_url).path).name or "payload"
    target = folder / f"{filename}.{definition.file_format}"

    request = Request(definition.retrieval_url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        status = int(response.status)
        headers = {k.lower(): v for k, v in response.headers.items() if k.lower() in KEPT_HEADERS}
        payload = response.read(definition.max_bytes + 1)
    if status != 200:
        raise RegistryError(f"{definition.retrieval_url} returned HTTP {status}")
    if len(payload) > definition.max_bytes:
        raise RegistryError(f"payload exceeds the {definition.max_bytes}-byte cap")
    json.loads(payload)  # must be valid JSON before it is registered
    with target.open("xb") as handle:  # exclusive create: never overwrite
        handle.write(payload)
    (folder / "http_headers.json").write_text(
        json.dumps({"status": status, "headers": headers}, indent=2) + "\n", encoding="utf-8"
    )

    entry = SnapshotEntry(
        backend_source_id=backend_source_id,
        snapshot_id=snapshot_id,
        publisher=definition.publisher,
        description=definition.description,
        landing_url=definition.landing_url,
        retrieval_url=definition.retrieval_url,
        retrieved_at=retrieved_at,
        http_status=status,
        http_metadata=headers,
        original_filename=filename,
        stored_relpath=target.relative_to(raw_db_dir(data_root)).as_posix(),
        sha256=sha256_file(target),
        size_bytes=target.stat().st_size,
        file_format=definition.file_format,
        source_update_date=headers.get("last-modified"),
        source_update_date_note=(
            "HTTP Last-Modified header"
            if "last-modified" in headers
            else "The publisher states no update date for this payload (no Last-Modified "
            "header, no date field in the payload); values are 'as retrieved' at retrieved_at."
        ),
        attribution_notes=definition.attribution_notes,
        unit_of_observation=definition.unit_of_observation,
    )
    registry = load_registry(data_root)
    registry.snapshots.append(entry)
    save_registry(data_root, registry)
    return entry
