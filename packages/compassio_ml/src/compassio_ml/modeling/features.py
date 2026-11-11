"""Deterministic text construction and the pre-registered keyword baseline."""

import re
from collections.abc import Iterable, Sequence
from typing import Literal

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin

Representation = Literal["title", "description", "title_description"]
REPRESENTATIONS: tuple[Representation, ...] = ("title", "description", "title_description")
SEPARATOR = " \n "  # neutral separator; TF-IDF token patterns ignore it


def _clean(value: object) -> str:
    if value is None or value is pd.NA or (isinstance(value, float) and value != value):
        return ""
    return str(value)


def build_text(title: object, description: object, representation: Representation) -> str:
    """Concatenate the cleaned fields for one record (no further normalisation)."""
    t, d = _clean(title), _clean(description)
    if representation == "title":
        return t
    if representation == "description":
        return d
    if representation == "title_description":
        return f"{t}{SEPARATOR}{d}" if t and d else (t or d)
    raise ValueError(f"Unknown representation {representation!r}")


def build_texts(features: pd.DataFrame, representation: Representation) -> np.ndarray:
    if representation not in REPRESENTATIONS:
        raise ValueError(f"Unknown representation {representation!r}")
    return np.array(
        [
            build_text(t, d, representation)
            for t, d in zip(features["title_clean"], features["description_clean"], strict=True)
        ],
        dtype=object,
    )


# Pre-registered climate lexicon (written before any Task 004 metric was computed; never tuned on
# validation). Domain terms for mitigation and adaptation activities. Caveat: Task 002's audit
# looked at the association of a few of these words with the labels over the whole dataset, so
# this baseline is not fully blind (docs/research/task004_experiment_design.md).
KEYWORD_LEXICON: tuple[str, ...] = (
    r"climat\w*",
    r"renewable\w*",
    r"solar",
    r"photovoltaic\w*",
    r"wind (?:power|farm|turbine|energy)\w*",
    r"hydro ?power\w*",
    r"hydroelectric\w*",
    r"geothermal",
    r"biogas",
    r"biomass",
    r"energy[- ](?:efficien\w*|saving\w*|conservation)",
    r"emission\w*",
    r"low[- ]carbon",
    r"greenhouse",
    r"carbon",
    r"electric (?:vehicle|bus)\w*",
    r"adaptation",
    r"resilien\w*",
    r"drought\w*",
    r"flood (?:control|prevention|protection|management)",
    r"early warning",
    r"afforestation|reforestation",
    r"desertification",
    r"water[- ]saving",
)
_KEYWORD_RE = re.compile(r"\b(?:" + "|".join(KEYWORD_LEXICON) + r")\b", re.IGNORECASE)


def keyword_hits(text: str) -> int:
    return len(_KEYWORD_RE.findall(text))


class KeywordClassifier(ClassifierMixin, BaseEstimator):  # type: ignore[misc]
    """Predicts climate-related if any pre-registered keyword occurs. Learns nothing from data.

    ``decision_function`` returns the number of keyword hits (a score, not a probability).
    """

    def fit(self, X: Sequence[str], y: Iterable[int]) -> "KeywordClassifier":
        self.classes_ = np.array([0, 1])
        self.is_fitted_ = True
        return self

    def decision_function(self, X: Sequence[str]) -> np.ndarray:
        return np.array([keyword_hits(str(x)) for x in X], dtype=float)

    def predict(self, X: Sequence[str]) -> np.ndarray:
        return (self.decision_function(X) > 0).astype(int)
