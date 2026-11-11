"""Development-candidate artifact: save once, load only after integrity checks.

NOT a trusted release. Loading refuses: a missing/foreign manifest schema, any status other than
``development_candidate``, a checksum mismatch (checked BEFORE unpickling), an artifact that
appears in the trusted release registry, and a content-fingerprint mismatch after loading.
"""

import json
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import sklearn

from compassio_ml.integrity.hashing import sha256_file
from compassio_ml.model_v2.candidates import PROBABILISTIC, fingerprint, scores
from compassio_ml.modeling.features import build_text

SCHEMA = "compassio-ml-v2-dev-candidate/1"
STATUS = "development_candidate"
ARTIFACT = "model.joblib"
MANIFEST = "candidate_manifest.json"
LIMITATION = (
    "EXPERIMENTAL development candidate trained on publisher-reported (donor) Rio markers from "
    "FCDO/EC IATI records. Development-validation metrics only: no independent or human-verified "
    "evaluation exists. Internal research screening only; not a trusted release, not served by "
    "the API, not evidence of climate impact, funding approval or return. Requires human review."
)


class CandidateArtifactError(RuntimeError):
    """The artifact is missing, altered, foreign or not a development candidate."""


def save_candidate(model: Any, directory: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=False)  # never overwrite a saved candidate
    path = directory / ARTIFACT
    joblib.dump(model, path, compress=3)
    full = {
        **manifest,
        "schema": SCHEMA,
        "status": STATUS,
        "artifact_file": ARTIFACT,
        "artifact_sha256": sha256_file(path),
        "artifact_bytes": path.stat().st_size,
        "model_fingerprint": fingerprint(model),
        "limitation": LIMITATION,
        "environment": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
            "joblib": joblib.__version__,
        },
    }
    with (directory / MANIFEST).open("x", encoding="utf-8") as handle:
        json.dump(full, handle, indent=2, sort_keys=True, default=str)
    return full


@dataclass(frozen=True)
class CandidatePrediction:
    is_climate_related: bool
    label_score: float
    threshold: float
    candidate_id: str
    status: str
    limitation: str


class ExperimentalClassifier:
    def __init__(self, model: Any, manifest: dict[str, Any]) -> None:
        self._model = model
        self.manifest = manifest
        self.threshold = float(manifest["threshold"])

    @classmethod
    def load(cls, directory: Path, trusted_registry: Path) -> "ExperimentalClassifier":
        manifest_path = directory / MANIFEST
        if not manifest_path.is_file():
            raise CandidateArtifactError(f"no candidate manifest in {directory}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != SCHEMA or manifest.get("status") != STATUS:
            raise CandidateArtifactError("not a ML v2 development-candidate manifest")
        artifact = directory / str(manifest["artifact_file"])
        if not artifact.is_file():
            raise CandidateArtifactError("artifact file missing")
        digest = sha256_file(artifact)
        if digest != manifest["artifact_sha256"]:
            raise CandidateArtifactError("artifact checksum does not match the manifest")
        trusted = (
            json.loads(trusted_registry.read_text(encoding="utf-8"))
            if trusted_registry.is_file()
            else {}
        )
        if digest in set(trusted.values()):
            raise CandidateArtifactError("a trusted release must be loaded with ReleasedClassifier")
        model = joblib.load(artifact)  # only after the checksum check
        if fingerprint(model) != manifest["model_fingerprint"]:
            raise CandidateArtifactError("loaded content does not match the manifest fingerprint")
        return cls(model, manifest)

    def score_texts(self, texts: np.ndarray) -> np.ndarray:
        return scores(self._model, texts, str(self.manifest["classifier"]))

    def predict(self, title: str | None, description: str | None) -> CandidatePrediction:
        t, d = (title or "").strip(), (description or "").strip()
        if not t and not d:
            raise ValueError("title and description are both blank")
        text = build_text(t, d, "title_description")
        value = float(self.score_texts(np.array([text], dtype=object))[0])
        return CandidatePrediction(
            is_climate_related=value >= self.threshold,
            label_score=value,
            threshold=self.threshold,
            candidate_id=str(self.manifest["candidate_id"]),
            status=STATUS,
            limitation=LIMITATION,
        )

    @property
    def probabilistic(self) -> bool:
        return str(self.manifest["classifier"]) in PROBABILISTIC
