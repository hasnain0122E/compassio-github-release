"""Lazy, verified model loading and scoring.

Nothing here imports scikit-learn/joblib at module import time: models are loaded on the first
screening request, through their own guarded loaders (``ReleasedClassifier.load`` for the trusted
v1 release, ``ExperimentalClassifier.load`` for the ML v2 development candidate), and then checked
again against the committed pins in ``configs/inference_models.yaml``.
"""

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from compassio_api.inference.explain import Explanation, FeatureNames, explain
from compassio_api.inference.registry import InferenceRegistry, ModelEntry, ModelKey


class ModelUnavailableError(RuntimeError):
    def __init__(self, key: str, message: str) -> None:
        super().__init__(message)
        self.key = key
        self.message = message


@dataclass
class LoadedModel:
    key: ModelKey
    entry: ModelEntry
    pipeline: Any
    names: FeatureNames
    manifest: dict[str, Any]

    def score_and_explain(self, text: str, top_k: int) -> Explanation:
        return explain(self.pipeline, self.names, text, top_k)


class ModelManager:
    def __init__(self, registry: InferenceRegistry, root: Path, trusted_registry: Path) -> None:
        self.registry = registry
        self.root = root
        self.trusted_registry = trusted_registry
        self._loaded: dict[str, LoadedModel] = {}
        self._lock = threading.Lock()

    def artifact_present(self, key: ModelKey) -> bool:
        directory = self.root / self.registry.models[key].artifact_dir
        return directory.is_dir()

    def get(self, key: ModelKey) -> LoadedModel:
        with self._lock:
            if key not in self._loaded:
                self._loaded[key] = self._load(key)
            return self._loaded[key]

    def _load(self, key: ModelKey) -> LoadedModel:
        entry = self.registry.models[key]
        directory = self.root / entry.artifact_dir
        if not directory.is_dir():
            raise ModelUnavailableError(key, f"model artifact directory not found: {directory}")
        model: Any
        try:
            if entry.loader == "trusted_release":
                from compassio_ml.modeling.release import ReleasedClassifier, ReleaseError

                try:
                    model = ReleasedClassifier.load(directory, self.trusted_registry)
                except ReleaseError as exc:
                    raise ModelUnavailableError(key, str(exc)) from exc
            else:
                from compassio_ml.model_v2.artifact import (
                    CandidateArtifactError,
                    ExperimentalClassifier,
                )

                try:
                    model = ExperimentalClassifier.load(directory, self.trusted_registry)
                except CandidateArtifactError as exc:
                    raise ModelUnavailableError(key, str(exc)) from exc
        except ImportError as exc:  # the ML package is not installed in this environment
            raise ModelUnavailableError(key, f"model loader unavailable: {exc}") from exc
        manifest: dict[str, Any] = dict(model.manifest)
        for field, expected in (
            ("artifact_sha256", entry.artifact_sha256),
            ("model_fingerprint", entry.model_fingerprint),
        ):
            if manifest.get(field) != expected:
                raise ModelUnavailableError(
                    key, f"{field} differs from configs/inference_models.yaml"
                )
        if float(manifest["threshold"]) != entry.threshold:
            raise ModelUnavailableError(key, "threshold differs from configs/inference_models.yaml")
        if entry.status == "development_candidate" and manifest.get("status") != entry.status:
            raise ModelUnavailableError(key, "candidate status changed; refusing to load")
        pipeline = model._model  # the verified, already loaded estimator (no second unpickle)
        if len(pipeline.steps) != 2:
            raise ModelUnavailableError(key, "expected a [vectoriser, classifier] pipeline")
        return LoadedModel(key, entry, pipeline, FeatureNames(pipeline.steps[0][1]), manifest)
