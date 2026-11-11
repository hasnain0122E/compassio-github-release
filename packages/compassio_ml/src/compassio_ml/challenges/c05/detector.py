"""Out-of-fold, group-aware label-consistency detector (C05).

For each record of a SUPPLIED batch it asks: "is the supplied label consistent with what similar,
independently labelled records say?" Two independent signals, both computed out-of-fold:

1. **Text model (confident learning).** A word TF-IDF + logistic regression is fitted on the
   training folds only and predicts the held-out fold. Following confident learning
   (Northcutt et al. 2021), class ``c`` has threshold ``t_c`` = mean predicted probability of
   ``c`` over records supplied with label ``c`` (per publisher when it has enough records of that
   class, otherwise batch-wide). A record supplied with label ``i`` is flagged when its
   probability of the other label ``j`` reaches ``t_j``.
2. **Nearest neighbours.** Cosine similarity in the same fold-fitted TF-IDF space to the
   training-fold records; flagged when at most ``max_agreement`` of the ``k`` nearest neighbours
   carry the same supplied label, provided the neighbours are close enough to judge.

Decision: ``quarantined`` only when BOTH signals flag; ``insufficient_evidence`` when exactly one
does (or neighbours are too far); otherwise ``accepted``. A flag means *inconsistent with similar
records*, never *proven corruption*.

Leakage rules: folds are ``StratifiedGroupKFold`` on the batch's group ids (a group never spans
train and held-out folds); the vectoriser, classifier and neighbour index are fitted on the
training folds only. This module never reads or imports the attack oracle.
"""

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold

from compassio_ml.challenges.c05.batch import SuppliedBatch
from compassio_ml.challenges.c05.config import DetectorConfig

Status = Literal["accepted", "quarantined", "insufficient_evidence"]
NOT_PROOF = (
    "Flags mean the supplied label is inconsistent with independently labelled similar records. "
    "They are evidence for review, not proof that the label was corrupted."
)


@dataclass(frozen=True)
class DetectorResult:
    p_positive: np.ndarray  # out-of-fold P(label = 1); NaN when not assessable
    p_other: np.ndarray  # out-of-fold probability of the label NOT supplied
    threshold_other: np.ndarray  # confident-learning threshold for that other label
    model_flag: np.ndarray
    knn_agreement: np.ndarray  # share of k nearest neighbours with the same supplied label
    knn_similarity: np.ndarray  # mean cosine similarity of those neighbours
    knn_evidence: np.ndarray  # neighbours close enough to judge
    knn_flag: np.ndarray
    suspicion: np.ndarray  # 0..1 ranking score (explanatory; the decision uses the flags)
    status: np.ndarray  # Status per record
    fold: np.ndarray
    reasons: tuple[str, ...]
    thresholds: dict[str, dict[str, float]]
    notes: list[str] = field(default_factory=list)


def _vectorizer(spec: dict[str, object]) -> TfidfVectorizer:
    ngram = spec["ngram_range"]
    assert isinstance(ngram, list | tuple)
    return TfidfVectorizer(
        analyzer=str(spec["analyzer"]),
        ngram_range=(int(ngram[0]), int(ngram[1])),
        min_df=spec["min_df"],
        max_df=spec["max_df"],
        max_features=spec["max_features"],
        sublinear_tf=bool(spec["sublinear_tf"]),
        lowercase=True,
        dtype=np.float32,
    )


def _classifier(spec: dict[str, object], seed: int) -> LogisticRegression:
    weight = spec.get("class_weight")
    return LogisticRegression(
        C=float(spec["C"]),  # type: ignore[arg-type]
        class_weight=None if weight in (None, "none") else str(weight),
        solver="liblinear",
        max_iter=2000,
        random_state=seed,
    )


def _neighbours(
    x_test: object, x_train: object, train_labels: np.ndarray, test_labels: np.ndarray, k: int
) -> tuple[np.ndarray, np.ndarray]:
    """Agreement and mean similarity of the k most similar TRAINING-fold records (chunked)."""
    n = test_labels.shape[0]
    agreement = np.zeros(n)
    similarity = np.zeros(n)
    k_eff = min(k, train_labels.shape[0])
    for start in range(0, n, 512):
        stop = min(start + 512, n)
        sims = (x_test[start:stop] @ x_train.T).toarray()  # type: ignore[index, attr-defined]
        idx = np.argpartition(-sims, k_eff - 1, axis=1)[:, :k_eff]
        top = np.take_along_axis(sims, idx, axis=1)
        same = train_labels[idx] == test_labels[start:stop, None]
        agreement[start:stop] = same.mean(axis=1)
        similarity[start:stop] = top.mean(axis=1)
    return agreement, similarity


def _thresholds(
    batch: SuppliedBatch, p_pos: np.ndarray, min_support: int
) -> dict[str, dict[str, float]]:
    """Per-publisher (fallback: batch-wide) mean self-confidence per supplied class."""
    ok = ~np.isnan(p_pos)
    out: dict[str, dict[str, float]] = {}
    glob: dict[str, float] = {}
    for c in (0, 1):
        mask = ok & (batch.labels == c)
        prob_c = p_pos if c == 1 else 1.0 - p_pos
        glob[str(c)] = float(prob_c[mask].mean()) if mask.any() else float("nan")
    out["__batch__"] = glob
    for source in sorted(set(batch.sources.tolist())):
        per: dict[str, float] = {}
        for c in (0, 1):
            mask = ok & (batch.labels == c) & (batch.sources == source)
            prob_c = p_pos if c == 1 else 1.0 - p_pos
            per[str(c)] = float(prob_c[mask].mean()) if mask.sum() >= min_support else glob[str(c)]
        out[source] = per
    return out


def _reason(
    status: str,
    label: int,
    p_other: float,
    t_other: float,
    agree: float,
    sim: float,
    k: int,
    source: str,
) -> str:
    if status == "not_assessable":
        return "Not assessable: too few records of a class to judge. " + NOT_PROOF
    other = 1 - label
    same = round(agree * k)
    return (
        f"Supplied label {label}. Text model (out-of-fold) gives label {other} probability "
        f"{p_other:.2f} vs class threshold {t_other:.2f} for {source}; {k - same}/{k} nearest "
        f"training-fold neighbours carry label {other} (mean similarity {sim:.2f})."
    )


def assess(batch: SuppliedBatch, cfg: DetectorConfig) -> DetectorResult:
    n = len(batch)
    y = batch.labels
    p_pos = np.full(n, np.nan)
    agreement = np.full(n, np.nan)
    similarity = np.zeros(n)
    fold_of = np.full(n, -1)
    notes: list[str] = []

    counts = np.bincount(y, minlength=2)
    assessable = bool(counts.min() >= max(cfg.min_class_support, cfg.n_splits))
    if not assessable:
        notes.append(
            f"Class counts {counts.tolist()} below min_class_support "
            f"{cfg.min_class_support}: every record is insufficient_evidence (nothing quarantined)."
        )
    else:
        splitter = StratifiedGroupKFold(n_splits=cfg.n_splits, shuffle=True, random_state=cfg.seed)
        for f, (tr, te) in enumerate(splitter.split(np.zeros(n), y, batch.groups)):
            fold_of[te] = f
            if len(np.unique(y[tr])) < 2:
                notes.append(f"fold {f}: training folds hold one class; held-out rows skipped")
                continue
            vec = _vectorizer(cfg.text_model.features)
            x_tr = vec.fit_transform(batch.texts[tr])  # fitted on training folds only
            x_te = vec.transform(batch.texts[te])
            clf = _classifier(cfg.text_model.classifier, cfg.seed).fit(x_tr, y[tr])
            p_pos[te] = clf.predict_proba(x_te)[:, 1]
            agreement[te], similarity[te] = _neighbours(x_te, x_tr, y[tr], y[te], cfg.knn.k)

    ok = ~np.isnan(p_pos)
    thresholds = _thresholds(batch, p_pos, cfg.min_class_support)
    p_other = np.where(y == 1, 1.0 - p_pos, p_pos)
    t_other = np.array(
        [thresholds[s][str(1 - lab)] for s, lab in zip(batch.sources, y, strict=True)]
    )
    model_flag = ok & (p_other >= t_other)
    knn_evidence = ok & (similarity >= cfg.knn.min_mean_similarity)
    knn_flag = knn_evidence & (agreement <= cfg.knn.max_agreement)
    disagree = np.where(knn_evidence, 1.0 - np.nan_to_num(agreement), np.nan)
    suspicion = np.where(
        ok, np.where(knn_evidence, 0.5 * p_other + 0.5 * disagree, p_other), np.nan
    )

    status = np.full(n, "accepted", dtype=object)
    status[model_flag ^ knn_flag] = "insufficient_evidence"
    status[model_flag & ~knn_evidence] = "insufficient_evidence"
    status[model_flag & knn_flag] = "quarantined"
    status[~ok] = "insufficient_evidence"

    reasons = tuple(
        _reason(
            "not_assessable" if not ok[i] else str(status[i]),
            int(y[i]),
            float(p_other[i]) if ok[i] else 0.0,
            float(t_other[i]) if ok[i] else 0.0,
            float(agreement[i]) if ok[i] else 0.0,
            float(similarity[i]),
            cfg.knn.k,
            str(batch.sources[i]),
        )
        for i in range(n)
    )
    return DetectorResult(
        p_positive=p_pos,
        p_other=p_other,
        threshold_other=t_other,
        model_flag=model_flag,
        knn_agreement=agreement,
        knn_similarity=similarity,
        knn_evidence=knn_evidence,
        knn_flag=knn_flag,
        suspicion=suspicion,
        status=status.astype(str),
        fold=fold_of,
        reasons=reasons,
        thresholds=thresholds,
        notes=notes,
    )
