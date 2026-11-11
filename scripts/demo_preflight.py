"""Read-only preflight for the local demo: are the runtime artifacts present and intact?

    uv run python scripts/demo_preflight.py            # human-readable report, exit 1 on failure
    uv run python scripts/demo_preflight.py --json     # machine-readable

Checks ONLY what the running API needs (docs/hackathon/local_demo_runbook.md):
the SQLite database (opened read-only), the ML v1 release and ML v2 candidate files pinned in
configs/inference_models.yaml, and the tracked configs. It never writes, never loads a model
into memory and never needs the ML v2 raw training inputs or the network.
"""

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "data" / "db" / "compassio_dev.sqlite"
# Pinned at the Task 008 integration checkpoint (docs/phases/task008_final_integration_report.md).
EXPECTED_DB_SHA256 = "d2b39adda32914eb9059ea80792a1a77d8dea62aca0f6d55ed37b5c1114dd385"
EXPECTED_OBSERVATIONS = 93_881
TRACKED = (
    "configs/inference_models.yaml",
    "configs/trusted_model_releases.json",
    "configs/ml_rights_eligibility_v2.yaml",
    "configs/event_data_authorizations.yaml",
    "docs/research/model_v2/fast_benchmark_aggregates.json",
)
MANIFESTS = {"ml_v1": "release_manifest.json", "ml_v2": "candidate_manifest.json"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})

    for rel in TRACKED:
        add(f"file {rel}", (REPO / rel).is_file(), "tracked in git")

    if DB.is_file():
        digest = _sha256(DB)
        add("database sha256", digest == EXPECTED_DB_SHA256, digest)
        con = sqlite3.connect(f"{DB.as_uri()}?mode=ro", uri=True)
        try:
            (revision,) = con.execute("select version_num from alembic_version").fetchone()
            (observations,) = con.execute("select count(*) from financial_observations").fetchone()
            (projects,) = con.execute("select count(*) from projects").fetchone()
        finally:
            con.close()
        add("database schema revision", revision == "0003", str(revision))
        add(
            "financial observations",
            observations == EXPECTED_OBSERVATIONS,
            f"{observations} (expected {EXPECTED_OBSERVATIONS}); projects {projects}",
        )
    else:
        add("database present", False, f"missing {DB.relative_to(REPO)}")

    registry = yaml.safe_load((REPO / "configs" / "inference_models.yaml").read_text("utf-8"))
    for key, entry in registry["models"].items():
        directory = REPO / entry["artifact_dir"]
        manifest = directory / MANIFESTS[key]
        add(f"{key} manifest", manifest.is_file(), str(manifest.relative_to(REPO)))
        if not manifest.is_file():
            continue
        artifact = directory / json.loads(manifest.read_text("utf-8"))["artifact_file"]
        if artifact.is_file():
            digest = _sha256(artifact)
            add(f"{key} artifact sha256", digest == entry["artifact_sha256"], digest)
        else:
            add(f"{key} artifact", False, f"missing {artifact.relative_to(REPO)}")
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    checks = run()
    ok = all(c["ok"] for c in checks)
    if args.json:
        print(json.dumps({"ok": ok, "checks": checks}, indent=2))
    else:
        for c in checks:
            print(f"{'PASS' if c['ok'] else 'FAIL'}  {c['check']}: {c['detail']}")
        print("Preflight OK" if ok else "Preflight FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
