"""Typed inference wrapper for a saved benchmark artifact (engineering use only).

Loading verifies the artifact's SHA-256 against its metadata before unpickling: joblib/pickle
can execute code, so only artifacts produced by this repository's benchmark may be loaded.
Not connected to any API. Outputs are decision support, never funding approval.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from compassio_ml.modeling.estimators import scores
from compassio_ml.modeling.features import Representation, build_text
from compassio_ml.modeling.frozen import sha256_file


class ArtifactIntegrityError(RuntimeError):
    """The model file does not match the checksum recorded in its metadata."""


class EmptyInputError(ValueError):
    """The text needed by the model's representation is blank."""


@dataclass(frozen=True, slots=True)
class Prediction:
    is_climate_related: bool
    score: float
    score_kind: str  # "probability" or "decision_score"
    probability: float | None  # only when the model provides calibrated/native probabilities
    threshold: float
    model_version: str
    representation: str
    dataset_version: dict[str, str]
    disclaimer: str = (
        "Text similarity to the authors' climate annotations; not evidence of impact, "
        "funding quality or a funding decision."
    )


class ClimateRelevanceClassifier:
    def __init__(self, model: Any, metadata: dict[str, Any]) -> None:
        self._model = model
        self.metadata = metadata
        self.representation: Representation = metadata["representation"]
        self.threshold = float(metadata["threshold"])

    @classmethod
    def load(cls, model_dir: Path) -> "ClimateRelevanceClassifier":
        metadata_path = model_dir / "model_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        artifact = model_dir / metadata["artifact_file"]
        actual = sha256_file(artifact)
        if actual != metadata["artifact_sha256"]:
            raise ArtifactIntegrityError(
                f"{artifact}: sha256 {actual} != recorded {metadata['artifact_sha256']}; "
                "refusing to load"
            )
        return cls(joblib.load(artifact), metadata)

    def _text(self, title: str | None, description: str | None) -> str:
        t = (title or "").strip()
        d = (description or "").strip()
        needed = {"title": t, "description": d, "title_description": t or d}[self.representation]
        if not needed:
            raise EmptyInputError(
                f"Model uses representation {self.representation!r}; the required text is blank"
            )
        return build_text(t, d, self.representation)

    def predict(self, title: str | None, description: str | None) -> Prediction:
        text = self._text(title, description)
        score = float(
            scores(self._model, np.array([text], dtype=object), self.metadata["algorithm"])[0]
        )
        probabilistic = bool(self.metadata["provides_probability"])
        return Prediction(
            is_climate_related=score >= self.threshold,
            score=score,
            score_kind=str(self.metadata["score_kind"]),
            probability=score if probabilistic else None,
            threshold=self.threshold,
            model_version=str(self.metadata["model_version"]),
            representation=self.representation,
            dataset_version=dict(self.metadata["dataset_version"]),
        )
