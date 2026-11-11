"""§7 escalation: ONE frozen multilingual sentence encoder + logistic regression.

The encoder is pretrained and frozen (no parameters are fitted on Compassio data), so encoding
VALID texts leaks nothing; the logistic regression, its C, and its threshold are fitted on
TRAIN only (group-aware OOF), exactly as for the lexical candidates. Requires the optional
``embeddings`` extra (``uv run --all-extras ...``); inference is local, no text leaves the host.
"""

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.metrics import average_precision_score
from sklearn.pipeline import Pipeline

from compassio_ml.external.paths import V2Paths
from compassio_ml.integrity.hashing import sha256_file
from compassio_ml.model_v2 import candidates as cm
from compassio_ml.model_v2 import evaluate as ev
from compassio_ml.model_v2.benchmark import _jsonable, evaluate_scores, latency_ms_per_1000
from compassio_ml.model_v2.data import load_development
from compassio_ml.model_v2.plan import FastPlan
from compassio_ml.modeling.metrics import GroupBootstrap, best_f1_threshold

DEFAULT_ADDENDUM = Path("configs") / "ml_v2_fast_escalation.yaml"


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EncoderSpec(_Frozen):
    model_id: str
    revision: str
    license: str
    weights_file: str
    weights_sha256: str
    local_dir: str
    text_prefix: str
    max_seq_length: int
    normalize_embeddings: bool
    batch_size: int


class EscalationCandidate(_Frozen):
    name: str
    population: str
    classifier: str
    grid: list[dict[str, Any]]
    hyperparameter_selection: str
    threshold: str


class ReplacementRule(_Frozen):
    guard_min_non_energy_precision: float
    must_exceed_champion_non_energy_ap_by: float
    paired_ci_of_non_energy_ap_difference_must_exclude_zero: bool
    otherwise: str


class Addendum(_Frozen):
    addendum_version: str
    base_plan_sha256: str
    base_run_id: str
    base_champion: str
    seed: int
    encoder: EncoderSpec
    candidate: EscalationCandidate
    replacement_rule: ReplacementRule


def load_addendum(path: Path, expected_sha256: str) -> Addendum:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"addendum sha256 {actual} != expected {expected_sha256}")
    return Addendum.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


class FrozenSentenceEncoder(TransformerMixin, BaseEstimator):  # type: ignore[misc]
    """Pretrained encoder as a stateless transformer. ``fit`` learns nothing; the model is
    loaded lazily from a verified local directory and is never pickled."""

    def __init__(
        self,
        model_dir: str = "",
        weights_sha256: str = "",
        prefix: str = "query: ",
        max_seq_length: int = 256,
        batch_size: int = 64,
        normalize: bool = True,
    ) -> None:
        self.model_dir = model_dir
        self.weights_sha256 = weights_sha256
        self.prefix = prefix
        self.max_seq_length = max_seq_length
        self.batch_size = batch_size
        self.normalize = normalize

    def _model(self) -> Any:
        cached = self.__dict__.get("_loaded")
        if cached is not None:
            return cached
        weights = Path(self.model_dir) / "model.safetensors"
        if sha256_file(weights) != self.weights_sha256:
            raise ValueError("encoder weights do not match the pinned sha256")
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(self.model_dir, device="cpu")
        model.max_seq_length = self.max_seq_length
        self.__dict__["_loaded"] = model
        return model

    def __getstate__(self) -> dict[str, Any]:
        state = dict(self.__dict__)
        state.pop("_loaded", None)
        return state

    def fit(self, X: Any, y: Any = None) -> "FrozenSentenceEncoder":
        self.is_fitted_ = True  # nothing is learned from data
        return self

    def transform(self, X: Any) -> np.ndarray:
        texts = [self.prefix + str(t) for t in X]
        result: np.ndarray = self._model().encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=self.normalize,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return result


def run_escalation(
    paths: V2Paths, plan: FastPlan, addendum: Addendum, addendum_sha: str, repo: Path
) -> Path:
    base_run = paths.output_root / plan.artifacts.run_root / addendum.base_run_id
    base_results = json.loads((base_run / "results.json").read_text("utf-8"))
    if base_results["selection"]["champion"] != addendum.base_champion:
        raise ValueError("base run champion differs from the addendum")
    out = paths.writable(
        paths.output_root
        / plan.artifacts.run_root
        / f"{addendum.base_run_id}__escalation_{addendum_sha[:8]}"
    )
    out.mkdir(parents=True, exist_ok=False)
    enc = addendum.encoder
    model_dir = paths.output_root / enc.local_dir
    encoder = FrozenSentenceEncoder(
        str(model_dir),
        enc.weights_sha256,
        enc.text_prefix,
        enc.max_seq_length,
        enc.batch_size,
        enc.normalize_embeddings,
    )

    data = load_development(paths, plan)
    pop = plan.populations[addendum.candidate.population]
    train = data.part("train")
    train = train[train["source_id"].isin(pop.train_sources)].reset_index(drop=True)
    valid = data.part("valid")
    valid = valid[valid["source_id"].isin(pop.valid_sources)].reset_index(drop=True)

    start = time.perf_counter()
    X_train = encoder.fit(train["text"]).transform(train["text"].to_numpy())
    X_valid = encoder.transform(valid["text"].to_numpy())
    encode_seconds = time.perf_counter() - start
    y, groups = train["y"].to_numpy(), train["group"].to_numpy()
    folds = list(cm.group_folds(y, groups, plan.cv.n_splits, plan.seed))

    trials, best = [], None
    for params in addendum.candidate.grid:
        oof = np.zeros(len(y))
        for tr, te in folds:
            clf = cm.classifier("lr", params, plan.seed, plan.cv.n_splits).fit(X_train[tr], y[tr])
            oof[te] = clf.predict_proba(X_train[te])[:, 1]
        ap = float(average_precision_score(y, oof))
        trials.append({"params": params, "oof_average_precision": ap})
        if best is None or ap > best[0]:
            best = (ap, params, oof)
    assert best is not None
    clf = cm.classifier("lr", best[1], plan.seed, plan.cv.n_splits).fit(X_train, y)
    threshold = best_f1_threshold(y, best[2])
    score = np.asarray(clf.predict_proba(X_valid)[:, 1], dtype=float)
    boot = GroupBootstrap.build(valid["group"].to_numpy(), plan.bootstrap.resamples, plan.seed)
    evaluation = evaluate_scores(valid, score, threshold, True, plan, boot)
    pipeline = Pipeline([("features", encoder), ("clf", clf)])
    evaluation["latency_ms_per_1000"] = latency_ms_per_1000(
        pipeline, valid["text"].to_numpy()[: plan.latency.texts], "lr", plan.latency.repeats
    )

    saved = pd.read_parquet(base_run / "valid_predictions.parquet").set_index("candidate_id")
    order = valid["candidate_id"]
    champion = saved.loc[order, f"score::{addendum.base_champion}"].to_numpy()
    v1 = saved.loc[order, "score::baseline/v1_release"].to_numpy()
    ne = valid["non_energy"].to_numpy()
    conf = plan.bootstrap.confidence
    comparisons = {
        "F_minus_champion_non_energy_ap": ev.paired_difference(
            valid, score, champion, boot, conf, ne
        ),
        "F_minus_champion_ap": ev.paired_difference(valid, score, champion, boot, conf),
        "F_minus_v1_ap": ev.paired_difference(valid, score, v1, boot, conf),
    }
    rule = addendum.replacement_rule
    diff = comparisons["F_minus_champion_non_energy_ap"]
    summary = evaluation["summary"]
    replaces = (
        (summary["non_energy_precision"] or 0) >= rule.guard_min_non_energy_precision
        and diff["difference"] > rule.must_exceed_champion_non_energy_ap_by
        and (
            not rule.paired_ci_of_non_energy_ap_difference_must_exclude_zero
            or (diff["low"] is not None and diff["low"] > 0)
        )
    )
    result = {
        "addendum_sha256": addendum_sha,
        "candidate": addendum.candidate.name,
        "encoder": enc.model_dump(),
        "encode_seconds_train_plus_valid": round(encode_seconds, 1),
        "train_records": len(train),
        "valid_records": len(valid),
        "trials": trials,
        "selected_params": best[1],
        "oof_average_precision": best[0],
        "threshold": threshold,
        "evaluation": evaluation,
        "comparisons": comparisons,
        "decision": "F_replaces_champion" if replaces else rule.otherwise,
        "finished_at": datetime.now(UTC).isoformat(),
        "test_or_sealed_data_loaded": False,
    }
    (out / "escalation_results.json").write_text(
        json.dumps(_jsonable(result), indent=2, sort_keys=True, default=str) + "\n", "utf-8"
    )
    pd.DataFrame({"candidate_id": order, "score::F_e5_lr": score}).to_parquet(
        out / "valid_predictions_F.parquet", index=False
    )
    return out
