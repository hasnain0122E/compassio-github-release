"""Metrics for one scored population: overall, slices, calibration, group-bootstrap CIs."""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score

from compassio_ml.modeling.metrics import (
    GroupBootstrap,
    ap_difference_statistic,
    calibration_metrics,
    predict_at,
    ranking_metrics,
    threshold_metrics,
)


def basic(
    y: np.ndarray, score: np.ndarray, threshold: float, probabilistic: bool
) -> dict[str, Any]:
    pred = predict_at(score, threshold)
    out: dict[str, Any] = {"records": len(y), "positives": int(y.sum())}
    out.update(threshold_metrics(y, pred))
    out.update(ranking_metrics(y, score))
    if probabilistic and len(y):
        out.update(calibration_metrics(y, score))
    return out


def recall_only(y: np.ndarray, score: np.ndarray, threshold: float) -> dict[str, Any]:
    pred = predict_at(score, threshold)
    positives = int(y.sum())
    found = int(((pred == 1) & (y == 1)).sum())
    return {
        "positives": positives,
        "detected": found,
        "recall": found / positives if positives else None,
    }


def slice_table(
    frame: pd.DataFrame,
    score: np.ndarray,
    threshold: float,
    probabilistic: bool,
    sector_families: tuple[str, ...],
    min_records: int,
    min_positives: int,
) -> dict[str, Any]:
    y = frame["y"].to_numpy()
    masks: dict[str, np.ndarray] = {
        "energy": ~frame["non_energy"].to_numpy(),
        "non_energy": frame["non_energy"].to_numpy(),
    }
    for source in sorted(frame["source_id"].unique()):
        masks[f"publisher:{source}"] = (frame["source_id"] == source).to_numpy()
    for family in sector_families:
        masks[f"sector:{family}"] = (frame["sector_family"] == family).to_numpy()
    out: dict[str, Any] = {}
    for name, mask in masks.items():
        yy = y[mask]
        n, pos = int(mask.sum()), int(yy.sum())
        if n < min_records or pos < min_positives or n - pos < 1:
            out[name] = {"records": n, "positives": pos, "suppressed": True}
            continue
        out[name] = {"suppressed": False, **basic(yy, score[mask], threshold, probabilistic)}
    # Positives-only detection slices (recall is the only defined rate).
    for name, column in (
        ("adaptation_only", "adaptation_only"),
        ("mitigation_only", "mitigation_only"),
    ):
        mask = frame[column].to_numpy()
        out[f"positives:{name}"] = recall_only(y[mask], score[mask], threshold)
        ne = mask & frame["non_energy"].to_numpy()
        out[f"positives:{name}_non_energy"] = recall_only(y[ne], score[ne], threshold)
    return out


def _stat(fn: Any, y: np.ndarray, values: np.ndarray, mask: np.ndarray | None) -> Any:
    def stat(idx: np.ndarray) -> float | None:
        if mask is not None:
            idx = idx[mask[idx]]
        yy = y[idx]
        if len(yy) == 0 or yy.min() == yy.max():
            return None
        return float(fn(yy, values[idx]))

    return stat


def intervals(
    frame: pd.DataFrame,
    score: np.ndarray,
    threshold: float,
    boot: GroupBootstrap,
    confidence: float,
) -> dict[str, Any]:
    y = frame["y"].to_numpy()
    pred = predict_at(score, threshold)
    ne = frame["non_energy"].to_numpy()
    stats = {
        "average_precision": (average_precision_score, score, None),
        "f1": (lambda a, b: f1_score(a, b, zero_division=0), pred, None),
        "precision": (lambda a, b: precision_score(a, b, zero_division=0), pred, None),
        "recall": (lambda a, b: recall_score(a, b, zero_division=0), pred, None),
        "non_energy_average_precision": (average_precision_score, score, ne),
        "non_energy_precision": (lambda a, b: precision_score(a, b, zero_division=0), pred, ne),
        "non_energy_recall": (lambda a, b: recall_score(a, b, zero_division=0), pred, ne),
    }
    out: dict[str, Any] = {}
    for name, (fn, values, mask) in stats.items():
        lo, hi, n = boot.interval(_stat(fn, y, values, mask), confidence)
        out[name] = {"low": lo, "high": hi, "valid_resamples": n}
    ao = frame["adaptation_only"].to_numpy()

    def ao_recall(idx: np.ndarray) -> float | None:
        idx = idx[ao[idx]]
        return float(pred[idx].mean()) if len(idx) else None

    lo, hi, n = boot.interval(ao_recall, confidence)
    out["adaptation_only_recall"] = {"low": lo, "high": hi, "valid_resamples": n}
    return out


def paired_difference(
    frame: pd.DataFrame,
    score_a: np.ndarray,
    score_b: np.ndarray,
    boot: GroupBootstrap,
    confidence: float,
    subset: np.ndarray | None = None,
) -> dict[str, Any]:
    """AP(a) - AP(b) on the SAME records, resampling whole groups."""
    y = frame["y"].to_numpy()
    mask = np.ones(len(y), dtype=bool) if subset is None else subset
    base = ap_difference_statistic(y, score_a, score_b)

    def stat(idx: np.ndarray) -> float | None:
        return base(idx[mask[idx]])

    lo, hi, n = boot.interval(stat, confidence)
    point = float(
        average_precision_score(y[mask], score_a[mask])
        - average_precision_score(y[mask], score_b[mask])
    )
    return {"difference": point, "low": lo, "high": hi, "valid_resamples": n}


def summary(metrics: dict[str, Any], slices: dict[str, Any]) -> dict[str, Any]:
    """Flat view used for selection and tables."""
    ne = slices.get("non_energy", {})
    return {
        "average_precision": metrics.get("average_precision"),
        "f1": metrics.get("f1"),
        "precision": metrics.get("precision"),
        "recall": metrics.get("recall"),
        "roc_auc": metrics.get("roc_auc"),
        "brier": metrics.get("brier"),
        "ece_10bin": metrics.get("ece_10bin"),
        "non_energy_average_precision": ne.get("average_precision"),
        "non_energy_precision": ne.get("precision"),
        "non_energy_recall": ne.get("recall"),
        "energy_recall": slices.get("energy", {}).get("recall"),
        "adaptation_only_recall": slices.get("positives:adaptation_only", {}).get("recall"),
        "adaptation_only_non_energy_recall": slices.get(
            "positives:adaptation_only_non_energy", {}
        ).get("recall"),
    }
