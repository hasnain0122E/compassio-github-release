"""Deterministic label-flip attack (the threat being defended against).

The attacker controls the supplied LABELS of exactly ``floor(n * rate + 0.5)`` records and
inverts them (0 -> 1 or 1 -> 0). Text, ids, groups, publishers, code and configuration are not
attacker-controlled. The flip positions form the private ORACLE, used only to evaluate the
detector afterwards; ``detector`` and ``gate`` never import this module.
"""

import math
from dataclasses import dataclass

import numpy as np

from compassio_ml.challenges.c05.batch import SuppliedBatch
from compassio_ml.challenges.c05.config import AttackMode


@dataclass(frozen=True)
class PoisonOracle:
    """Ground truth of the simulated attack. EVALUATION ONLY."""

    mode: AttackMode
    seed: int
    rate: float
    batch_size: int
    flipped_ids: tuple[str, ...]
    clean_fingerprint: str
    poisoned_fingerprint: str

    @property
    def count(self) -> int:
        return len(self.flipped_ids)


def poison_count(n: int, rate: float) -> int:
    return math.floor(n * rate + 0.5)


def inject_label_flips(
    batch: SuppliedBatch,
    rate: float,
    seed: int,
    mode: AttackMode,
    non_energy: np.ndarray | None = None,
) -> tuple[SuppliedBatch, PoisonOracle]:
    """Return a NEW batch with flipped labels and the oracle; ``batch`` is never modified."""
    n = len(batch)
    count = poison_count(n, rate)
    if mode == "uniform":
        eligible = np.arange(n)
    elif mode == "targeted_non_energy_positive":
        if non_energy is None or len(non_energy) != n:
            raise ValueError("targeted mode needs a non_energy flag per record")
        eligible = np.flatnonzero((batch.labels == 1) & np.asarray(non_energy, dtype=bool))
    else:
        raise ValueError(f"unknown attack mode {mode!r}")
    if count > len(eligible):
        raise ValueError(f"cannot flip {count} labels: only {len(eligible)} eligible records")
    rng = np.random.default_rng(seed)
    chosen = np.sort(rng.choice(eligible, size=count, replace=False))
    labels = np.array(batch.labels, copy=True)
    labels[chosen] = 1 - labels[chosen]
    poisoned = batch.with_labels(labels)
    oracle = PoisonOracle(
        mode=mode,
        seed=seed,
        rate=rate,
        batch_size=n,
        flipped_ids=tuple(str(i) for i in batch.ids[chosen]),
        clean_fingerprint=batch.fingerprint(),
        poisoned_fingerprint=poisoned.fingerprint(),
    )
    return poisoned, oracle
