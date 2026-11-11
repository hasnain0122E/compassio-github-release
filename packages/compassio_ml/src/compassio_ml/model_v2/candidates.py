"""Candidate pipelines, training-only weighting, group-aware CV and a stable fingerprint."""

import hashlib
import json
from collections.abc import Iterator
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

PROBABILISTIC = frozenset({"lr", "svm_platt"})


class PlattLinearSVC(ClassifierMixin, BaseEstimator):  # type: ignore[misc]
    """LinearSVC + Platt sigmoid fitted on group-aware out-of-fold decision scores of the
    training data passed to ``fit`` (train-only calibration; no held-out data involved)."""

    def __init__(
        self,
        C: float = 1.0,
        class_weight: str | None = "balanced",
        n_splits: int = 3,
        random_state: int = 0,
    ) -> None:
        self.C = C
        self.class_weight = class_weight
        self.n_splits = n_splits
        self.random_state = random_state

    def _svc(self) -> LinearSVC:
        return LinearSVC(C=self.C, class_weight=self.class_weight, random_state=self.random_state)

    def fit(
        self,
        X: Any,
        y: np.ndarray,
        groups: np.ndarray | None = None,
        sample_weight: np.ndarray | None = None,
    ) -> "PlattLinearSVC":
        y = np.asarray(y)
        if groups is None:
            raise ValueError("PlattLinearSVC needs groups for group-aware calibration folds")
        oof = np.zeros(len(y), dtype=float)
        for tr, te in group_folds(y, np.asarray(groups), self.n_splits, self.random_state):
            svc = self._svc().fit(X[tr], y[tr], sample_weight=_take(sample_weight, tr))
            oof[te] = svc.decision_function(X[te])
        self.platt_ = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000).fit(
            oof.reshape(-1, 1), y
        )
        self.svc_ = self._svc().fit(X, y, sample_weight=sample_weight)
        self.classes_ = self.svc_.classes_
        return self

    def decision_function(self, X: Any) -> np.ndarray:
        result: np.ndarray = self.svc_.decision_function(X)
        return result

    def predict_proba(self, X: Any) -> np.ndarray:
        result: np.ndarray = self.platt_.predict_proba(self.decision_function(X).reshape(-1, 1))
        return result

    def predict(self, X: Any) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


def _take(weights: np.ndarray | None, idx: np.ndarray) -> np.ndarray | None:
    return None if weights is None else weights[idx]


def vectorizer(spec: dict[str, Any]) -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer=spec["analyzer"],
        ngram_range=tuple(spec["ngram_range"]),
        min_df=spec["min_df"],
        max_df=spec["max_df"],
        max_features=spec["max_features"],
        sublinear_tf=spec["sublinear_tf"],
        lowercase=True,
        dtype=np.float32,
    )


def features(kind: str, specs: dict[str, dict[str, Any]]) -> Any:
    if kind == "word":
        return vectorizer(specs["word"])
    if kind == "char":
        return vectorizer(specs["char"])
    if kind == "word_char":
        return FeatureUnion(
            [("word", vectorizer(specs["word"])), ("char", vectorizer(specs["char"]))]
        )
    raise ValueError(f"unknown feature set {kind!r}")


def classifier(kind: str, params: dict[str, Any], seed: int, n_splits: int) -> Any:
    weight = None if params.get("class_weight") in (None, "none") else params["class_weight"]
    if kind == "lr":
        return LogisticRegression(
            C=float(params["C"]),
            class_weight=weight,
            solver="liblinear",
            max_iter=2000,
            random_state=seed,
        )
    if kind == "linear_svm":
        return LinearSVC(C=float(params["C"]), class_weight=weight, random_state=seed)
    if kind == "svm_platt":
        return PlattLinearSVC(
            C=float(params["C"]), class_weight=weight, n_splits=n_splits, random_state=seed
        )
    raise ValueError(f"unknown classifier {kind!r}")


def make_pipeline(
    feature_kind: str,
    classifier_kind: str,
    params: dict[str, Any],
    specs: dict[str, dict[str, Any]],
    seed: int,
    n_splits: int,
) -> Pipeline:
    return Pipeline(
        [
            ("features", features(feature_kind, specs)),
            ("clf", classifier(classifier_kind, params, seed, n_splits)),
        ]
    )


def fit_pipeline(
    pipe: Pipeline,
    texts: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    weights: np.ndarray | None,
    classifier_kind: str,
) -> Pipeline:
    """Fit vectoriser AND classifier on the given (training) rows only."""
    fit_params: dict[str, Any] = {}
    if weights is not None:
        fit_params["clf__sample_weight"] = weights
    if classifier_kind == "svm_platt":
        fit_params["clf__groups"] = groups
    pipe.fit(texts, y, **fit_params)
    return pipe


def scores(pipe: Pipeline, texts: np.ndarray, classifier_kind: str) -> np.ndarray:
    if classifier_kind in PROBABILISTIC:
        return np.asarray(pipe.predict_proba(texts)[:, 1], dtype=float)
    return np.asarray(pipe.decision_function(texts), dtype=float)


def group_folds(
    y: np.ndarray, groups: np.ndarray, n_splits: int, seed: int
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    yield from splitter.split(np.zeros(len(y)), y, groups)


def sample_weights(frame: pd.DataFrame, scheme: str) -> np.ndarray | None:
    """Training-only weights; the weighting variable never becomes a model input."""
    if scheme == "none":
        return None
    if scheme == "publisher_balanced":
        counts = frame["source_id"].map(frame["source_id"].value_counts()).to_numpy(float)
        w = len(frame) / (frame["source_id"].nunique() * counts)
    elif scheme == "family_inverse":
        w = 1.0 / frame["family"].map(frame["family"].value_counts()).to_numpy(float)
    else:
        raise ValueError(f"unknown weighting {scheme!r}")
    return np.asarray(w / w.mean(), dtype=float)


def _fitted_state(obj: Any, digest: Any, seen: set[int]) -> None:
    if id(obj) in seen:
        return
    seen.add(id(obj))
    for name in sorted(vars(obj)):
        if not name.endswith("_") or name.startswith("_"):
            continue
        value = getattr(obj, name)
        digest.update(name.encode())
        _value(value, digest, seen)
    for child in _children(obj):
        _fitted_state(child, digest, seen)


def _value(value: Any, digest: Any, seen: set[int]) -> None:
    if isinstance(value, np.ndarray):
        digest.update(str(value.dtype).encode())
        digest.update(np.ascontiguousarray(value).tobytes())
    elif isinstance(value, dict):
        for key in sorted(value, key=str):
            digest.update(f"{key}\t".encode())
            _value(value[key], digest, seen)
    elif isinstance(value, set | frozenset):
        digest.update(json.dumps(sorted(map(str, value))).encode())
    elif isinstance(value, BaseEstimator):
        _fitted_state(value, digest, seen)
    elif isinstance(value, list | tuple):
        for item in value:
            _value(item, digest, seen)
    else:
        digest.update(repr(value).encode())


def _children(obj: Any) -> list[Any]:
    if isinstance(obj, Pipeline):
        return [step for _, step in obj.steps]
    if isinstance(obj, FeatureUnion):
        return [t for _, t in obj.transformer_list]
    return []


def fingerprint(model: Any) -> str:
    """Content fingerprint over parameters and every public fitted attribute (``*_``).

    Ignores private state such as TfidfVectorizer's per-process ``_stop_words_id``, so it is
    stable across processes while any change to vocabulary, IDF or weights changes it.
    """
    digest = hashlib.sha256()
    digest.update(json.dumps(model.get_params(deep=True), sort_keys=True, default=str).encode())
    _fitted_state(model, digest, set())
    return digest.hexdigest()
