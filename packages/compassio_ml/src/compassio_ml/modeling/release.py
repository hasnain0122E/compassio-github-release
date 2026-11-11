"""Internal model release: acceptance check, release manifest, and a safe loader.

Loading rules (pickle/joblib can execute code):
  * the release manifest schema and model version must be known to this code;
  * the artifact's SHA-256 must equal the manifest AND a committed trusted-release registry
    (``configs/trusted_model_releases.json``) entry for that version, checked BEFORE unpickling;
  * after loading, the content fingerprint must equal the manifest.
The loader needs only the release directory, never the training data.
"""

import json
import platform
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from compassio_ml.modeling.estimators import scores
from compassio_ml.modeling.features import build_text
from compassio_ml.modeling.final_eval import FinalPlan, model_fingerprint
from compassio_ml.modeling.frozen import sha256_file

RELEASE_SCHEMA = "compassio-model-release/1"
MODEL_NAME = "Compassio Climate Relevance Classifier v1 — MVP Research Screening"
MODEL_VERSION = "compassio-ccrc-1.0.0-mvp-research-screening"
SUPPORTED_VERSIONS = frozenset({MODEL_VERSION})
LIMITATION_MESSAGE = (
    "Research screening only. The label score reflects similarity to the paper authors' climate "
    "annotations of retrospective project descriptions. It is not a probability of funding, "
    "approval, project success, environmental impact or financial return. Reliable mainly for "
    "energy-sector text; adaptation and other non-energy projects are often missed. A negative "
    "result does not mean a project is not climate-relevant. Requires human review."
)
PROHIBITED_CLAIMS = (
    "predicts investment returns",
    "predicts funding approval",
    "verifies environmental impact",
    "detects fraud",
    "reliable proposal-time classification without external validation",
    "reliably classifies all adaptation or non-energy project types",
)
DEPENDENCIES = ("scikit-learn", "scipy", "numpy", "joblib", "pandas", "compassio-ml")


class ReleaseError(RuntimeError):
    """The release is unknown, incompatible, untrusted or corrupted."""


class EmptyInputError(ValueError):
    """Title and description are both blank."""


def evaluate_acceptance(primary: dict[str, Any], criteria: dict[str, Any]) -> dict[str, Any]:
    """Apply the pre-registered acceptance criteria to the primary-test results."""
    model, slices = primary["model"], primary["slices"]
    keyword_ap = primary["baselines"]["keyword"]["average_precision"]
    checks = {
        "ap_ci_lower_above_keyword_ap": {
            "value": model["average_precision_ci95"][0],
            "required": f"> {keyword_ap}",
            "passed": model["average_precision_ci95"][0] > keyword_ap,
        },
        "f1_at_threshold": {
            "value": model["f1"],
            "required": f">= {criteria['min_f1']}",
            "passed": model["f1"] >= criteria["min_f1"],
        },
        "energy_recall": {
            "value": slices["energy"].get("recall"),
            "required": f">= {criteria['min_energy_recall']}",
            "passed": (slices["energy"].get("recall") or 0) >= criteria["min_energy_recall"],
        },
        "ece": {
            "value": model["ece_10bin"],
            "required": f"<= {criteria['max_ece']}",
            "passed": model["ece_10bin"] <= criteria["max_ece"],
        },
    }
    non_energy = slices["non_energy"].get("recall")
    return {
        "checks": checks,
        "all_passed": all(c["passed"] for c in checks.values()),
        "non_energy_recall": non_energy,
        "non_energy_limitation_required": non_energy is None
        or non_energy < criteria["non_energy_recall_limitation_below"],
    }


def build_release(
    final_root: Path, plan: FinalPlan, plan_sha: str, out_dir: Path, acceptance: dict[str, Any]
) -> dict[str, Any]:
    if out_dir.exists():
        raise ReleaseError(f"{out_dir} already exists; releases are immutable")
    primary = final_root / "primary"
    record = json.loads((primary / "test_access.json").read_text(encoding="utf-8"))
    if record.get("status") != "completed":
        raise ReleaseError("primary final evaluation is not completed")
    model_file = primary / "model.joblib"
    if sha256_file(model_file) != record["output_sha256"]["model.joblib"]:
        raise ReleaseError("primary model artifact does not match its test-access record")
    results = json.loads((primary / "results.json").read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True)
    shutil.copyfile(model_file, out_dir / "model.joblib")
    status = "mvp_research_screening" if acceptance["all_passed"] else "research_only"
    summaries = {}
    for protocol in ("primary", "chronological", "pakistan_holdout"):
        path = final_root / protocol / "results.json"
        if path.is_file():
            summaries[protocol] = sha256_file(path)
    manifest = {
        "schema": RELEASE_SCHEMA,
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "release_status": status,
        "created_at": datetime.now(UTC).isoformat(),
        "artifact_file": "model.joblib",
        "artifact_sha256": sha256_file(out_dir / "model.joblib"),
        "model_fingerprint": results["model_fingerprint"],
        "algorithm": plan.selected_model.algorithm,
        "representation": plan.selected_model.representation,
        "input_columns": list(plan.selected_model.input_columns),
        "tfidf": plan.selected_model.tfidf.model_dump(mode="json"),
        "params": plan.selected_model.params,
        "threshold": plan.protocols["primary"].threshold,
        "score_semantics": (
            "model-estimated label score in [0, 1]; not a probability of success or impact"
        ),
        "trained_on": "primary protocol TRAIN partition only (frozen research_split_v1)",
        "train_records": results["train_records"],
        "evaluation_plan_sha256": plan_sha,
        "evaluation_plan_version": plan.plan_version,
        "source_git_commit": plan.source_git_commit,
        "data_checksums": plan.data_checksums,
        "evaluation_summaries_sha256": summaries,
        "acceptance": acceptance,
        "dependencies": {d: version(d) for d in DEPENDENCIES},
        "python": platform.python_version(),
        "intended_use": "Human-reviewed screening of climate relevance in project descriptions.",
        "prohibited_claims": list(PROHIBITED_CLAIMS),
        "limitation_message": LIMITATION_MESSAGE,
        "attribution": [
            "Labels: Qi, J. et al. (2026) Scientific Data 13:277, doi:10.1038/s41597-026-06605-9 "
            "(data: doi:10.6084/m9.figshare.30015124)",
            "Text: AidData's Global Chinese Development Finance Dataset, Version 3.0 (ODC-By 1.0)",
        ],
    }
    (out_dir / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return manifest


@dataclass(frozen=True, slots=True)
class ReleasePrediction:
    is_climate_related: bool
    label_score: float
    threshold: float
    model_version: str
    release_status: str
    limitation: str
    score_semantics: str = "Label score, not a probability of success, approval or impact."


class ReleasedClassifier:
    def __init__(self, model: Any, manifest: dict[str, Any]) -> None:
        self._model = model
        self.manifest = manifest
        self.threshold = float(manifest["threshold"])

    @classmethod
    def load(cls, release_dir: Path, trusted_registry: Path) -> "ReleasedClassifier":
        manifest_path = release_dir / "release_manifest.json"
        if not manifest_path.is_file():
            raise ReleaseError(f"no release manifest in {release_dir}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != RELEASE_SCHEMA:
            raise ReleaseError(f"unsupported release schema {manifest.get('schema')!r}")
        version_id = manifest.get("model_version")
        if version_id not in SUPPORTED_VERSIONS:
            raise ReleaseError(f"unknown or incompatible model version {version_id!r}")
        trusted = (
            json.loads(trusted_registry.read_text(encoding="utf-8"))
            if trusted_registry.is_file()
            else {}
        )
        artifact = release_dir / str(manifest["artifact_file"])
        actual = sha256_file(artifact)
        if actual != manifest["artifact_sha256"]:
            raise ReleaseError("artifact checksum does not match the release manifest")
        if trusted.get(version_id) != actual:
            raise ReleaseError(f"artifact {actual[:12]} is not in the trusted release registry")
        model = joblib.load(artifact)  # only after both checksum checks
        if model_fingerprint(model) != manifest["model_fingerprint"]:
            raise ReleaseError("loaded model content does not match the release fingerprint")
        return cls(model, manifest)

    def predict(self, title: str | None, description: str | None) -> ReleasePrediction:
        t, d = (title or "").strip(), (description or "").strip()
        if not t and not d:
            raise EmptyInputError("title and description are both blank")
        text = build_text(t, d, self.manifest["representation"])
        score = float(
            scores(self._model, np.array([text], dtype=object), self.manifest["algorithm"])[0]
        )
        return ReleasePrediction(
            is_climate_related=score >= self.threshold,
            label_score=score,
            threshold=self.threshold,
            model_version=str(self.manifest["model_version"]),
            release_status=str(self.manifest["release_status"]),
            limitation=LIMITATION_MESSAGE,
        )
