"""Disposable downstream training for the C05 comparison (never registered, never served).

``fit_downstream`` accepts:

* an ``AcceptedBatch`` from the quarantine gate (the protected path), or
* an explicitly declared ``Baseline`` (``clean_reference`` or ``naive_poisoned``) used only to
  measure the effect of the attack and of the defence.

A raw ``SuppliedBatch`` is refused (``GateBypassError``). The model family is the ML v2 champion's
(character TF-IDF + logistic regression); the decision threshold is chosen on group-aware
out-of-fold scores of the SAME labels the model is trained with (a realistic pipeline cannot see
clean labels).
"""

import time
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score

from compassio_ml.challenges.c05.batch import SuppliedBatch
from compassio_ml.challenges.c05.config import Downstream
from compassio_ml.challenges.c05.gate import AcceptedBatch, GateBypassError
from compassio_ml.model_v2.candidates import fit_pipeline, group_folds, make_pipeline, scores
from compassio_ml.modeling.metrics import best_f1_threshold


@dataclass(frozen=True)
class Baseline:
    """An UNGATED comparison batch, declared as such."""

    purpose: Literal["clean_reference", "naive_poisoned"]
    batch: SuppliedBatch


@dataclass(frozen=True)
class TrainedModel:
    pipeline: Any
    threshold: float
    training_records: int
    training_fingerprint: str
    seconds: float


def _batch(training: object) -> SuppliedBatch:
    if isinstance(training, AcceptedBatch):
        return training.batch
    if isinstance(training, Baseline):
        return training.batch
    raise GateBypassError(
        "fit_downstream needs an AcceptedBatch from quarantine_gate (or a declared Baseline)"
    )


def fit_downstream(
    training: AcceptedBatch | Baseline, cfg: Downstream, specs: dict[str, dict[str, Any]]
) -> TrainedModel:
    batch = _batch(training)
    start = time.perf_counter()
    texts, y, groups = batch.texts, batch.labels, batch.groups
    oof = np.zeros(len(y))
    for tr, te in group_folds(y, groups, cfg.n_splits, cfg.seed):
        pipe = make_pipeline(
            cfg.features, cfg.classifier, cfg.params, specs, cfg.seed, cfg.n_splits
        )
        fit_pipeline(pipe, texts[tr], y[tr], groups[tr], None, cfg.classifier)
        oof[te] = scores(pipe, texts[te], cfg.classifier)
    threshold = float(best_f1_threshold(y, oof))
    final = make_pipeline(cfg.features, cfg.classifier, cfg.params, specs, cfg.seed, cfg.n_splits)
    fit_pipeline(final, texts, y, groups, None, cfg.classifier)
    return TrainedModel(
        final, threshold, len(y), batch.fingerprint(), round(time.perf_counter() - start, 2)
    )


def _recall(y: np.ndarray, pred: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    positives = int((y[mask] == 1).sum())
    found = int(((pred == 1) & (y == 1) & mask).sum())
    return {
        "positives": positives,
        "detected": found,
        "recall": found / positives if positives else None,
    }


def evaluate(
    model: TrainedModel,
    texts: np.ndarray,
    y: np.ndarray,
    non_energy: np.ndarray,
    adaptation_only: np.ndarray,
    classifier_kind: str,
) -> dict[str, Any]:
    score = scores(model.pipeline, texts, classifier_kind)
    pred = (score >= model.threshold).astype(int)
    ne = np.asarray(non_energy, dtype=bool)
    return {
        "records": len(y),
        "positives": int(y.sum()),
        "threshold": round(model.threshold, 6),
        "average_precision": round(float(average_precision_score(y, score)), 4),
        "f1": round(float(f1_score(y, pred, zero_division=0)), 4),
        "precision": round(float(precision_score(y, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y, pred, zero_division=0)), 4),
        "non_energy_average_precision": round(float(average_precision_score(y[ne], score[ne])), 4),
        "non_energy_recall": _recall(y, pred, ne),
        "adaptation_only_recall": _recall(y, pred, np.asarray(adaptation_only, dtype=bool)),
    }
