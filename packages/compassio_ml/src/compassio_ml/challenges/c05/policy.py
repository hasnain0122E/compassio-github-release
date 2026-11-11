"""Quarantine decision policies applied to the SAME detector outputs (C05 addendum, c05-1.1.0).

* **A ``two_signal`` (DEPLOYED):** quarantine when the text model AND the neighbours disagree
  with the supplied label (identical to ``detector.assess`` statuses).
* **B ``hardened`` (CANDIDATE):** adds an independent provenance signal, the publisher's DAC
  purpose codes, and protects ambiguous positive records:
  - quarantine if (text model AND neighbours) OR (text model AND provenance-inconsistent);
  - never quarantine a label-1 record whose purpose code corroborates it (review instead);
  - label-1 non-energy records are quarantined only with strong evidence from both signals.
* **C ``top_share`` (ANALYSIS ONLY):** quarantine the top X% by suspicion score.

Inputs are the supplied batch, the detector result and SOURCE METADATA the attacker does not
control (purpose codes, energy-sector flag). Never the oracle, never clean labels.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np

from compassio_ml.challenges.c05.batch import SuppliedBatch
from compassio_ml.challenges.c05.detector import DetectorResult


@dataclass(frozen=True)
class Metadata:
    """Per-record source metadata, aligned with the batch order."""

    sector_codes: np.ndarray  # publisher DAC purpose codes, ';'-separated strings
    non_energy: np.ndarray  # from the publisher sector codes (not the label)


@dataclass(frozen=True)
class PolicyDecision:
    policy: str
    status: np.ndarray
    reasons: tuple[str, ...]
    provenance_inconsistent: np.ndarray
    provenance_corroborated: np.ndarray


def intrinsic_codes(sector_codes: np.ndarray, intrinsic: frozenset[str]) -> list[list[str]]:
    out = []
    for value in sector_codes:
        parts = str(value).replace(",", ";").replace(" ", ";").split(";")
        out.append(sorted({p for p in parts if p in intrinsic}))
    return out


def _status(quarantine: np.ndarray, review: np.ndarray, assessable: np.ndarray) -> np.ndarray:
    status = np.full(len(quarantine), "accepted", dtype=object)
    status[review] = "insufficient_evidence"
    status[quarantine] = "quarantined"
    status[~assessable] = "insufficient_evidence"
    return status.astype(str)


def two_signal(det: DetectorResult) -> PolicyDecision:
    none = np.zeros(len(det.status), dtype=bool)
    return PolicyDecision("two_signal", det.status.copy(), det.reasons, none, none)


def hardened(
    batch: SuppliedBatch,
    det: DetectorResult,
    meta: Metadata,
    intrinsic: frozenset[str],
    params: dict[str, Any],
) -> PolicyDecision:
    y = batch.labels
    assessable = ~np.isnan(det.p_positive)
    found = intrinsic_codes(meta.sector_codes, intrinsic)
    has_code = np.array([bool(c) for c in found])
    inconsistent = (y == 0) & has_code
    corroborated = (y == 1) & has_code
    m, k = det.model_flag, det.knn_flag
    quarantine = m & k
    if params.get("provenance_second_signal", False):
        quarantine = quarantine | (m & inconsistent)
    protected = np.zeros(len(y), dtype=bool)
    if params.get("protect_provenance_corroborated_positives", False):
        protected |= corroborated
    strict = params.get("positive_non_energy_strict")
    if strict:
        agreement = np.nan_to_num(det.knn_agreement, nan=1.0)
        strong = (
            det.knn_evidence
            & (agreement <= float(strict["max_knn_agreement"]) + 1e-9)
            & (det.p_other >= det.threshold_other + float(strict["min_probability_margin"]))
        )
        protected |= (y == 1) & np.asarray(meta.non_energy, dtype=bool) & ~strong
    quarantine = quarantine & ~protected & assessable
    review = (m | k | inconsistent) & ~quarantine
    status = _status(quarantine, review, assessable)
    reasons = []
    for i, base in enumerate(det.reasons):
        extra = ""
        if found[i] and y[i] == 0:
            extra = (
                f" Publisher purpose code {', '.join(found[i])} is climate/environment-intrinsic"
                " but the supplied label is 0 (provenance-inconsistent)."
            )
        elif found[i] and y[i] == 1:
            extra = f" Publisher purpose code {', '.join(found[i])} corroborates label 1."
        if protected[i] and (m[i] or k[i]):
            extra += " Protected positive: sent to review instead of quarantine."
        reasons.append(base + extra)
    return PolicyDecision("hardened", status, tuple(reasons), inconsistent, corroborated)


def top_share(det: DetectorResult, share: float) -> PolicyDecision:
    n = len(det.status)
    score = np.nan_to_num(det.suspicion, nan=-1.0)
    order = np.argsort(-score, kind="stable")
    quarantine = np.zeros(n, dtype=bool)
    quarantine[order[: round(n * share)]] = True
    assessable = ~np.isnan(det.p_positive)
    status = _status(quarantine & assessable, np.zeros(n, dtype=bool), assessable)
    none = np.zeros(n, dtype=bool)
    return PolicyDecision(f"top_share_{share}", status, det.reasons, none, none)
