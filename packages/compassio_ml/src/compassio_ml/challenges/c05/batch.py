"""The supplied training batch: what a training pipeline receives (and what the detector sees).

A batch carries record ids, model text, the SUPPLIED labels (possibly poisoned), group ids for
group-aware folds and the publisher. It never carries the poison oracle. Arrays are read-only so
no step can silently relabel records.
"""

import hashlib
from dataclasses import dataclass

import numpy as np


def _frozen(values: np.ndarray) -> np.ndarray:
    out = np.array(values, copy=True)
    out.setflags(write=False)
    return out


def labelled_fingerprint(ids: np.ndarray, labels: np.ndarray) -> str:
    """sha256 of sorted ``id|label`` lines (the ML v2 plan's membership hash format)."""
    lines = sorted(f"{i}|{int(y)}" for i, y in zip(ids, labels, strict=True))
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def text_fingerprint(ids: np.ndarray, texts: np.ndarray) -> str:
    digest = hashlib.sha256()
    for i, t in sorted(zip(ids, texts, strict=True)):
        digest.update(f"{i}\t{hashlib.sha256(str(t).encode('utf-8')).hexdigest()}\n".encode())
    return digest.hexdigest()


@dataclass(frozen=True)
class SuppliedBatch:
    ids: np.ndarray
    texts: np.ndarray
    labels: np.ndarray  # SUPPLIED labels (0/1), as received
    groups: np.ndarray
    sources: np.ndarray

    @classmethod
    def create(
        cls,
        ids: np.ndarray,
        texts: np.ndarray,
        labels: np.ndarray,
        groups: np.ndarray,
        sources: np.ndarray,
    ) -> "SuppliedBatch":
        n = len(ids)
        if not all(len(a) == n for a in (texts, labels, groups, sources)):
            raise ValueError("batch arrays differ in length")
        if len(set(map(str, ids))) != n:
            raise ValueError("record ids must be unique")
        if not set(np.unique(labels).tolist()) <= {0, 1}:
            raise ValueError("labels must be binary 0/1")
        return cls(
            _frozen(np.asarray(ids).astype(str)),
            _frozen(np.asarray(texts).astype(str)),
            _frozen(np.asarray(labels).astype(int)),
            _frozen(np.asarray(groups).astype(str)),
            _frozen(np.asarray(sources).astype(str)),
        )

    def __len__(self) -> int:
        return len(self.ids)

    def with_labels(self, labels: np.ndarray) -> "SuppliedBatch":
        return SuppliedBatch.create(self.ids, self.texts, labels, self.groups, self.sources)

    def subset(self, mask: np.ndarray) -> "SuppliedBatch":
        return SuppliedBatch.create(
            self.ids[mask],
            self.texts[mask],
            self.labels[mask],
            self.groups[mask],
            self.sources[mask],
        )

    def fingerprint(self) -> str:
        return labelled_fingerprint(self.ids, self.labels)
