"""Classification metrics, threshold selection, calibration and group bootstrap.

Positive class is always 1 (climate-related).
"""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

POSITIVE = 1


@dataclass(frozen=True, slots=True)
class ConfusionCounts:
    tn: int
    fp: int
    fn: int
    tp: int


def confusion(y_true: np.ndarray, y_pred: np.ndarray) -> ConfusionCounts:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return ConfusionCounts(int(tn), int(fp), int(fn), int(tp))


def threshold_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float | int]:
    c = confusion(y_true, y_pred)
    return {
        "precision": float(precision_score(y_true, y_pred, pos_label=POSITIVE, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, pos_label=POSITIVE, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, pos_label=POSITIVE, zero_division=0)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "tn": c.tn,
        "fp": c.fp,
        "fn": c.fn,
        "tp": c.tp,
        "predicted_positive": c.tp + c.fp,
    }


def ranking_metrics(y_true: np.ndarray, score: np.ndarray) -> dict[str, float | None]:
    if len(np.unique(y_true)) < 2:
        return {"average_precision": None, "roc_auc": None}
    return {
        "average_precision": float(average_precision_score(y_true, score, pos_label=POSITIVE)),
        "roc_auc": float(roc_auc_score(y_true, score)),
    }


def expected_calibration_error(y_true: np.ndarray, prob: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(prob, edges[1:-1], right=True), 0, bins - 1)
    total = 0.0
    for b in range(bins):
        mask = idx == b
        if mask.any():
            total += mask.mean() * abs(float(prob[mask].mean()) - float(y_true[mask].mean()))
    return float(total)


def reliability_table(
    y_true: np.ndarray, prob: np.ndarray, bins: int = 10
) -> list[dict[str, float | int]]:
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(prob, edges[1:-1], right=True), 0, bins - 1)
    rows: list[dict[str, float | int]] = []
    for b in range(bins):
        mask = idx == b
        rows.append(
            {
                "bin_low": float(edges[b]),
                "bin_high": float(edges[b + 1]),
                "count": int(mask.sum()),
                "mean_predicted": float(prob[mask].mean()) if mask.any() else float("nan"),
                "observed_rate": float(y_true[mask].mean()) if mask.any() else float("nan"),
            }
        )
    return rows


def calibration_metrics(y_true: np.ndarray, prob: np.ndarray) -> dict[str, float]:
    if prob.min() < 0 or prob.max() > 1:
        raise ValueError("Calibration metrics require probabilities in [0, 1]")
    return {
        "brier": float(brier_score_loss(y_true, prob, pos_label=POSITIVE)),
        "ece_10bin": expected_calibration_error(y_true, prob),
        "mean_predicted_probability": float(prob.mean()),
        "observed_positive_rate": float(y_true.mean()),
    }


def best_f1_threshold(y_true: np.ndarray, score: np.ndarray) -> float:
    """Threshold maximising F1; ties resolved towards the higher threshold (fewer positives).

    Predictions use ``score >= threshold``.
    """
    order = np.argsort(-score, kind="stable")
    s, y = score[order], y_true[order]
    tp = np.cumsum(y)
    fp = np.cumsum(1 - y)
    positives = y.sum()
    if positives == 0:
        return float(np.inf)
    # Evaluate only at the last index of each distinct score value.
    last = np.r_[s[1:] != s[:-1], True]
    precision = tp[last] / (tp[last] + fp[last])
    recall = tp[last] / positives
    with np.errstate(invalid="ignore", divide="ignore"):
        f1 = np.where(precision + recall > 0, 2 * precision * recall / (precision + recall), 0.0)
    best = int(np.flatnonzero(f1 == f1.max())[0])  # first = highest threshold among ties
    return float(s[last][best])


def predict_at(score: np.ndarray, threshold: float) -> np.ndarray:
    return (score >= threshold).astype(int)


@dataclass(frozen=True)
class GroupBootstrap:
    """Resamples whole leakage groups with replacement (cluster bootstrap)."""

    index_sets: list[np.ndarray]

    @classmethod
    def build(cls, groups: np.ndarray, resamples: int, seed: int) -> "GroupBootstrap":
        unique, inverse = np.unique(groups, return_inverse=True)
        members = [np.flatnonzero(inverse == g) for g in range(len(unique))]
        rng = np.random.default_rng(seed)
        sets = []
        for _ in range(resamples):
            chosen = rng.integers(0, len(unique), size=len(unique))
            sets.append(np.concatenate([members[g] for g in chosen]))
        return cls(sets)

    def interval(
        self,
        statistic: Callable[[np.ndarray], float | None],
        confidence: float,
    ) -> tuple[float | None, float | None, int]:
        values = [v for idx in self.index_sets if (v := statistic(idx)) is not None]
        if not values:
            return None, None, 0
        alpha = (1 - confidence) / 2
        lo, hi = np.quantile(values, [alpha, 1 - alpha])
        return float(lo), float(hi), len(values)


def ap_statistic(y: np.ndarray, score: np.ndarray) -> Callable[[np.ndarray], float | None]:
    def stat(idx: np.ndarray) -> float | None:
        yy = y[idx]
        if yy.min() == yy.max():
            return None
        return float(average_precision_score(yy, score[idx]))

    return stat


def f1_statistic(y: np.ndarray, pred: np.ndarray) -> Callable[[np.ndarray], float | None]:
    def stat(idx: np.ndarray) -> float | None:
        return float(f1_score(y[idx], pred[idx], pos_label=POSITIVE, zero_division=0))

    return stat


def ap_difference_statistic(
    y: np.ndarray, score_a: np.ndarray, score_b: np.ndarray
) -> Callable[[np.ndarray], float | None]:
    def stat(idx: np.ndarray) -> float | None:
        yy = y[idx]
        if yy.min() == yy.max():
            return None
        return float(
            average_precision_score(yy, score_a[idx]) - average_precision_score(yy, score_b[idx])
        )

    return stat
