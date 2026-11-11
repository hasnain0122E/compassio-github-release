"""Pre-training quarantine gate (C05).

``quarantine_gate`` scores a supplied batch with the detector and splits it into accepted,
quarantined and review (insufficient evidence) records. Downstream training only accepts an
``AcceptedBatch``, which only the gate can create, so quarantined records are excluded BEFORE any
vectoriser or classifier is fitted. Labels are never corrected or rewritten: quarantined records
keep their original supplied label in the report for investigation.
"""

import hashlib
import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from compassio_ml.challenges.c05.batch import SuppliedBatch, labelled_fingerprint
from compassio_ml.challenges.c05.config import C05Config
from compassio_ml.challenges.c05.detector import NOT_PROOF, DetectorResult, assess

_GATE_TOKEN = object()


class GateBypassError(RuntimeError):
    """Training was attempted on records that did not pass the quarantine gate."""


@dataclass(frozen=True)
class AcceptedBatch:
    """Records cleared for training. Construct only via ``quarantine_gate``."""

    batch: SuppliedBatch
    gate_report_sha256: str
    _token: object

    def __post_init__(self) -> None:
        if self._token is not _GATE_TOKEN:
            raise GateBypassError("AcceptedBatch can only be created by quarantine_gate")


@dataclass(frozen=True)
class GateResult:
    accepted: AcceptedBatch
    accepted_ids: tuple[str, ...]
    quarantined_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    detector: DetectorResult
    report: dict[str, Any]


def _counts(batch: SuppliedBatch, mask: np.ndarray) -> dict[str, Any]:
    return {
        "records": int(mask.sum()),
        "by_supplied_label": {
            str(k): v for k, v in sorted(Counter(batch.labels[mask].tolist()).items())
        },
        "by_source": dict(sorted(Counter(batch.sources[mask].tolist()).items())),
    }


# A decision policy maps the detector result to (policy name, per-record status, reasons).
# It must use only the supplied batch, detector outputs and source metadata (never the oracle).
DecisionPolicy = Callable[[DetectorResult], tuple[str, np.ndarray, tuple[str, ...]]]


def quarantine_gate(
    batch: SuppliedBatch, cfg: C05Config, policy: DecisionPolicy | None = None
) -> GateResult:
    """Score ``batch`` and split it. ``policy=None`` is the deployed two-signal policy (its
    report is byte-identical to the base run's); a policy from ``policy.py`` may be passed."""
    result = assess(batch, cfg.detector)
    policy_name: str | None = None
    status, reasons = result.status, result.reasons
    if policy is not None:
        policy_name, status, reasons = policy(result)
    quarantined = status == "quarantined"
    review = status == "insufficient_evidence"
    excluded = quarantined | (
        review if cfg.detector.decision.insufficient_evidence_policy == "quarantine" else False
    )
    keep = ~excluded
    accepted_batch = batch.subset(keep)
    records = [
        {
            "record_id": str(batch.ids[i]),
            "source_id": str(batch.sources[i]),
            "supplied_label": int(batch.labels[i]),  # original supplied label, never rewritten
            "status": str(status[i]),
            "suspicion": None
            if np.isnan(result.suspicion[i])
            else round(float(result.suspicion[i]), 6),
            "model_flag": bool(result.model_flag[i]),
            "knn_flag": bool(result.knn_flag[i]),
            "reason": reasons[i],
        }
        for i in np.flatnonzero(quarantined | review)
    ]
    report: dict[str, Any] = {
        "detector_version": cfg.detector_version,
        "config_version": cfg.config_version,
        "thresholds": {
            "confident_learning_per_class": result.thresholds,
            "knn": cfg.detector.knn.model_dump(),
            "min_class_support": cfg.detector.min_class_support,
            "insufficient_evidence_policy": cfg.detector.decision.insufficient_evidence_policy,
        },
        "input_fingerprint": batch.fingerprint(),
        "output_fingerprint": labelled_fingerprint(accepted_batch.ids, accepted_batch.labels),
        "counts": {
            "input": _counts(batch, np.ones(len(batch), dtype=bool)),
            "accepted": _counts(batch, keep),
            "quarantined": _counts(batch, quarantined),
            "insufficient_evidence": _counts(batch, review),
        },
        "interpretation": NOT_PROOF,
        "notes": result.notes,
        "flagged_records": records,
    }
    if policy_name is not None:
        report["policy"] = policy_name
    digest = hashlib.sha256(json.dumps(report, sort_keys=True).encode("utf-8")).hexdigest()
    return GateResult(
        accepted=AcceptedBatch(accepted_batch, digest, _GATE_TOKEN),
        accepted_ids=tuple(accepted_batch.ids.tolist()),
        quarantined_ids=tuple(batch.ids[quarantined].tolist()),
        review_ids=tuple(batch.ids[review].tolist()),
        detector=result,
        report=report,
    )
