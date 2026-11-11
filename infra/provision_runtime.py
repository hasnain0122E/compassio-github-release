"""Private exact-runtime provisioning, dormant until cloud-transfer approval is recorded.

URLs belong in a provider secret file, never in Git or command arguments. No archives,
redirects, model deserialization, training, or canonical database edits are performed.
This transfer receipt does NOT grant public source/model serving rights.
"""

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from runtime_artifacts import ARTIFACTS, sha256


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Artifact redirects are forbidden")


def provision(root: Path, downloads: Path, approval: Path) -> None:
    receipt = json.loads(approval.read_text(encoding="utf-8"))
    if receipt.get("cloud_transfer_approved") is not True or not all(
        isinstance(receipt.get(key), str) and receipt[key].strip()
        for key in ("evidence_reference", "reviewed_by", "approved_provider")
    ):
        raise ValueError("An evidenced cloud-transfer approval receipt is required")
    locations = json.loads(downloads.read_text(encoding="utf-8"))
    if set(locations) != set(ARTIFACTS):
        raise ValueError("Download secret must identify exactly the five pinned artifacts")
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    opener = build_opener(NoRedirect())
    # Validate every location before making any network requests.
    for url in locations.values():
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Artifact locations must be HTTPS without URL credentials")
    for rel, (expected, _) in ARTIFACTS.items():
        destination = (root / rel).resolve()
        if not destination.is_relative_to(root):
            raise ValueError("Artifact path escapes runtime root")
        if destination.exists():
            if sha256(destination) != expected:
                raise ValueError(
                    "Existing artifact differs from frozen checksum; refusing overwrite"
                )
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Strict per-file cap: canonical SQLite is ~220 MiB; models are <4 MiB.
        limit = 250 * 1024 * 1024 if rel.endswith(".sqlite") else 8 * 1024 * 1024
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
                temporary = Path(handle.name)
                digest = hashlib.sha256()
                size = 0
                req = Request(locations[rel], headers={"Accept-Encoding": "identity"})
                with opener.open(req, timeout=60) as response:
                    if response.status != 200:
                        raise ValueError("Artifact server did not return HTTP 200")
                    while block := response.read(1024 * 1024):
                        size += len(block)
                        if size > limit:
                            raise ValueError("Artifact exceeds size budget")
                        handle.write(block)
                        digest.update(block)
                if digest.hexdigest() != expected:
                    raise ValueError("Artifact checksum mismatch")
            # Hard-link publishes atomically and refuses a concurrent existing destination.
            os.link(temporary, destination)
            destination.chmod(0o444)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    database = root / "data/db/compassio_dev.sqlite"
    with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("SQLite integrity check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("SQLite foreign key check failed")
    from compassio_api.db.session import create_read_engine, session_factory
    from compassio_api.services.integrity import verify_database

    engine = create_read_engine(f"sqlite:///{database.as_posix()}")
    try:
        with session_factory(engine)() as session:
            report = verify_database(session)
            if not report["ok"] or any(
                check["observed"] is None for check in report["audited_comparisons"].values()
            ):
                raise ValueError("Canonical database audit failed")
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        provision(
            Path(os.environ["COMPASSIO_RUNTIME_ROOT"]),
            Path(os.environ["COMPASSIO_RUNTIME_DOWNLOADS_FILE"]),
            Path(os.environ["COMPASSIO_RUNTIME_APPROVAL_FILE"]),
        )
    except Exception:  # noqa: BLE001 -- redact signed URLs from all provisioning failures
        # Download errors can include signed URLs. Never print exception strings/tracebacks.
        raise SystemExit(
            "Private runtime provisioning failed; check approval, network and hashes."
        ) from None
