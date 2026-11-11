"""Estimator factory. Every learned transformation lives inside one sklearn Pipeline so that it
is fitted only on the data passed to ``fit`` (the training partition, or a training fold)."""

from typing import Any

import numpy as np
from sklearn.base import BaseEstimator
from sklearn.calibration import CalibratedClassifierCV
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from compassio_ml.modeling.config import ALGORITHM_PARAMS, TfidfPreset
from compassio_ml.modeling.features import KeywordClassifier

LEARNS_FROM_TEXT = frozenset({"multinomial_nb", "logistic_regression", "linear_svm"})
PROBABILISTIC = frozenset({"multinomial_nb", "logistic_regression", "linear_svm_calibrated"})


def make_vectorizer(preset: TfidfPreset) -> TfidfVectorizer:
    return TfidfVectorizer(
        lowercase=True,
        ngram_range=preset.ngram_range,
        min_df=preset.min_df,
        max_df=preset.max_df,
        max_features=preset.max_features,
        sublinear_tf=preset.sublinear_tf,
        strip_accents=None,  # keep characters as cleaned in Task 003
        token_pattern=r"(?u)\b\w\w+\b",
        dtype=np.float64,
    )


def make_estimator(
    algorithm: str, params: dict[str, Any], preset: TfidfPreset | None, seed: int
) -> BaseEstimator:
    allowed = ALGORITHM_PARAMS.get(algorithm)
    if allowed is None:
        raise ValueError(f"Unknown algorithm {algorithm!r}")
    unknown = set(params) - allowed
    if unknown:
        raise ValueError(f"{algorithm}: unknown hyperparameters {sorted(unknown)}")
    if algorithm == "majority":
        return DummyClassifier(strategy="most_frequent")
    if algorithm == "keyword":
        return KeywordClassifier()
    if preset is None:
        raise ValueError(f"{algorithm} requires a TF-IDF preset")
    if algorithm == "multinomial_nb":
        clf: BaseEstimator = MultinomialNB(alpha=float(params["alpha"]))
    elif algorithm == "logistic_regression":
        clf = LogisticRegression(
            C=float(params["C"]),
            class_weight=params.get("class_weight"),
            solver="liblinear",
            max_iter=1000,
            random_state=seed,
        )
    else:
        clf = LinearSVC(
            C=float(params["C"]),
            class_weight=params.get("class_weight"),
            max_iter=5000,
            random_state=seed,
        )
    return Pipeline([("tfidf", make_vectorizer(preset)), ("clf", clf)])


def make_calibrated_svm(
    params: dict[str, Any],
    preset: TfidfPreset,
    seed: int,
    folds: list[tuple[np.ndarray, np.ndarray]],
) -> CalibratedClassifierCV:
    """Sigmoid-calibrated LinearSVC. Each calibration fold refits the whole pipeline (including
    TF-IDF) on its training-fold part and calibrates on its held-out part; ``folds`` must be
    group-aware splits of the TRAINING partition only."""
    base = make_estimator("linear_svm", params, preset, seed)
    return CalibratedClassifierCV(base, method="sigmoid", cv=folds, ensemble=True)


def score_kind(algorithm: str) -> str:
    return "probability" if algorithm in PROBABILISTIC else "decision_score"


def scores(model: BaseEstimator, texts: np.ndarray, algorithm: str) -> np.ndarray:
    """Positive-class probabilities for probabilistic models, else decision scores."""
    if algorithm in PROBABILISTIC:
        return np.asarray(model.predict_proba(texts))[:, 1]
    if algorithm == "majority":
        # Constant score: the predicted class (0 when the majority is negative). Not a probability.
        return np.asarray(model.predict(texts), dtype=float)
    return np.asarray(model.decision_function(texts), dtype=float)
