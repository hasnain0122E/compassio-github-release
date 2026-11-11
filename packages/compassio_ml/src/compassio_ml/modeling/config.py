"""Typed benchmark configuration (``configs/ml_benchmark_v1.yaml``)."""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from compassio_ml.modeling.features import REPRESENTATIONS, Representation

Algorithm = Literal["majority", "keyword", "multinomial_nb", "logistic_regression", "linear_svm"]
ALGORITHM_PARAMS: dict[str, frozenset[str]] = {
    "majority": frozenset(),
    "keyword": frozenset(),
    "multinomial_nb": frozenset({"alpha"}),
    "logistic_regression": frozenset({"C", "class_weight"}),
    "linear_svm": frozenset({"C", "class_weight"}),
}


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TfidfPreset(_Frozen):
    ngram_range: tuple[int, int]
    min_df: int = Field(ge=1)
    max_df: float = Field(gt=0, le=1)
    max_features: int | None = Field(default=None, ge=1)
    sublinear_tf: bool = True

    @model_validator(mode="after")
    def _ngrams(self) -> "TfidfPreset":
        lo, hi = self.ngram_range
        if not 1 <= lo <= hi <= 3:
            raise ValueError("ngram_range must satisfy 1 <= low <= high <= 3")
        return self


class Suite(_Frozen):
    representations: tuple[Representation, ...]
    tfidf: tuple[str, ...]
    candidates: dict[Algorithm, tuple[dict[str, Any], ...]]
    calibrate_best_svm: bool = False

    @model_validator(mode="after")
    def _params(self) -> "Suite":
        for rep in self.representations:
            if rep not in REPRESENTATIONS:
                raise ValueError(f"unknown representation {rep}")
        for algo, grid in self.candidates.items():
            if not grid:
                raise ValueError(f"{algo}: empty parameter grid")
            for params in grid:
                unknown = set(params) - ALGORITHM_PARAMS[algo]
                if unknown:
                    raise ValueError(f"{algo}: unknown hyperparameters {sorted(unknown)}")
                if params.get("class_weight") not in (None, "balanced"):
                    raise ValueError(f"{algo}: class_weight must be null or 'balanced'")
                for key in ("C", "alpha"):
                    if key in params and not float(params[key]) > 0:
                        raise ValueError(f"{algo}: {key} must be > 0")
        return self


class InnerCV(_Frozen):
    n_splits: int = Field(ge=2, le=10)
    shuffle: bool = True


class Bootstrap(_Frozen):
    resamples: int = Field(ge=100)
    confidence: float = Field(gt=0.5, lt=1)


class SelectionRule(_Frozen):
    primary_metric: Literal["average_precision"]
    tie_rule: Literal["paired_bootstrap_ci_includes_zero"]
    tie_breakers: tuple[str, ...]


class DataPaths(_Frozen):
    table: Path
    membership: Path
    split_config: Path
    split_lock: Path


class BenchmarkConfig(_Frozen):
    version: str
    seed: int
    target: Literal["is_climate_related"]
    data: DataPaths
    tfidf_presets: dict[str, TfidfPreset]
    inner_cv: InnerCV
    threshold_objective: Literal["f1"]
    bootstrap: Bootstrap
    selection: SelectionRule
    slice_min_records: int = Field(ge=1)
    slice_min_positives: int = Field(ge=1)
    suites: dict[str, Suite]

    @model_validator(mode="after")
    def _presets_exist(self) -> "BenchmarkConfig":
        for name, suite in self.suites.items():
            missing = set(suite.tfidf) - set(self.tfidf_presets)
            if missing:
                raise ValueError(f"suite {name}: unknown tfidf presets {sorted(missing)}")
        return self


def load_benchmark_config(path: Path) -> BenchmarkConfig:
    return BenchmarkConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def stable_hash(payload: object) -> str:
    text = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
