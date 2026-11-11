"""Read-only verification of every v1 artifact ML v2 depends on or must not disturb.

Checks (all against the read-only input roots; nothing is written there):

1. Raw source manifest: schema + SHA-256 + size of all registered raw files.
2. Frozen v1 dataset/split: table, membership, split config and lock hashes, and split counts.
3. Final evaluation plan v1: SHA-256 equals ``configs/final_evaluation_v1.sha256``.
4. Released model: artifact SHA-256 equals ``configs/trusted_model_releases.json``; the release
   manifest equals the committed copy; the content fingerprint matches after a trusted load.
5. Consumed v1 tests: every protocol's ``test_access.json`` is ``completed``, matches the
   committed copy, and its output hashes match the files on disk.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from compassio_ml.data.layout import DataLayout
from compassio_ml.data.manifest_io import validate_manifest
from compassio_ml.external.paths import V2Paths
from compassio_ml.integrity import sha256_file
from compassio_ml.modeling.frozen import FrozenPaths, verify_frozen

PROTOCOLS = ("primary", "chronological", "pakistan_holdout")
RELEASE_ID = "compassio-ccrc-1.0.0-mvp-research-screening"


@dataclass
class BaselineReport:
    checks: list[dict[str, Any]] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append({"check": name, "ok": ok, "detail": detail})

    @property
    def ok(self) -> bool:
        return all(c["ok"] for c in self.checks)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_baseline(paths: V2Paths, *, load_model: bool = True) -> BaselineReport:
    report = BaselineReport()
    data_root = paths.require_input()
    project = paths.require_v1_project()
    repo = paths.repo_root

    manifest = validate_manifest(DataLayout(data_root))
    report.add(
        "raw_manifest",
        manifest.ok,
        f"{manifest.checked_entries} entries checked; errors={manifest.errors[:3]}",
    )
    same = _json(data_root / "manifests" / "source_manifest.json") == _json(
        repo / "data" / "manifests" / "source_manifest.json"
    )
    report.add("raw_manifest_matches_worktree_copy", same, "input manifest == committed manifest")

    lock_path = repo / "configs" / "research_split_v1.lock.json"
    lock = _json(lock_path)
    frozen = verify_frozen(
        FrozenPaths(
            table=data_root / "processed" / Path(lock["table"]["path"]).name,
            membership=data_root / "processed" / Path(lock["membership"]["path"]).name,
            split_config=repo / lock["split_config"]["path"],
            lock=lock_path,
        )
    )
    report.add(
        "frozen_v1_split",
        frozen.ok,
        f"split_counts={json.dumps(lock['split_counts'], sort_keys=True)}; "
        f"errors={frozen.errors[:3]}",
    )

    plan = repo / "configs" / "final_evaluation_v1.yaml"
    expected_plan = (repo / "configs" / "final_evaluation_v1.sha256").read_text().split()[0]
    plan_sha = sha256_file(plan)
    report.add("final_evaluation_plan_v1", plan_sha == expected_plan, f"sha256={plan_sha}")
    pinned = yaml.safe_load(plan.read_text(encoding="utf-8"))["data_checksums"]
    lock_sha = sha256_file(lock_path)
    table_sha = lock["table"]["sha256"]
    membership_sha = lock["membership"]["sha256"]
    report.add(
        "plan_pins_match_lock",
        lock_sha == pinned["split_lock_sha256"]
        and table_sha == pinned["table_sha256"]
        and membership_sha == pinned["membership_sha256"],
        f"lock sha256={lock_sha}",
    )

    trusted = _json(repo / "configs" / "trusted_model_releases.json")
    release_dir = project / "models" / "compassio_ccrc_v1"
    artifact_sha = sha256_file(release_dir / "model.joblib")
    report.add(
        "release_artifact_sha256",
        artifact_sha == trusted.get(RELEASE_ID),
        f"model.joblib sha256={artifact_sha}",
    )
    on_disk = _json(release_dir / "release_manifest.json")
    committed = _json(repo / "docs" / "research" / "final_evaluation_v1" / "release_manifest.json")
    report.add(
        "release_manifest_matches_committed",
        on_disk == committed,
        f"model_fingerprint={on_disk.get('model_fingerprint')}",
    )
    if load_model:
        from compassio_ml.modeling.release import ReleasedClassifier, ReleaseError

        try:
            ReleasedClassifier.load(release_dir, repo / "configs" / "trusted_model_releases.json")
            report.add("release_fingerprint_after_trusted_load", True, "fingerprint verified")
        except ReleaseError as exc:
            report.add("release_fingerprint_after_trusted_load", False, str(exc))

    for protocol in PROTOCOLS:
        run_dir = project / "experiments" / "final_evaluation_v1" / protocol
        access = _json(run_dir / "test_access.json")
        committed_access = _json(
            repo / "docs" / "research" / "final_evaluation_v1" / f"{protocol}_test_access.json"
        )
        outputs_ok = all(
            sha256_file(run_dir / name) == sha for name, sha in access["output_sha256"].items()
        )
        ok = access["status"] == "completed" and access == committed_access and outputs_ok
        report.add(
            f"consumed_test_{protocol}",
            ok,
            f"status={access['status']} opened_at={access['opened_at']} "
            f"outputs_hash_ok={outputs_ok}",
        )
    return report
