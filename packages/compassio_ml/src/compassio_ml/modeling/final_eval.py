"""Task 005: one-shot final evaluation of the pre-selected model on the frozen test partitions.

Safeguards, in order, before any test row is read:
  1. the evaluation plan's SHA-256 must equal the value supplied by the operator;
  2. the frozen dataset/split lock must match, and match the plan;
  3. model code and benchmark/split configs must be unchanged since the plan's source commit;
  4. an exclusive-create test-access record is written; if it already exists the run refuses
     (one shot per protocol, including after a failure).
Only then is the protocol's ``test`` partition loaded (``allow_test=True``).
The model is fitted on the protocol's TRAIN partition only, with the plan's fixed threshold.
"""

import hashlib
import io
import json
import stat
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field
from sklearn.base import BaseEstimator

from compassio_ml.modeling.benchmark import group_folds
from compassio_ml.modeling.config import TfidfPreset
from compassio_ml.modeling.data import Partition, load_partitions
from compassio_ml.modeling.estimators import make_estimator, scores
from compassio_ml.modeling.features import KeywordClassifier, build_texts
from compassio_ml.modeling.frozen import FrozenPaths, require_frozen, sha256_file
from compassio_ml.modeling.metrics import (
    GroupBootstrap,
    ap_statistic,
    best_f1_threshold,
    calibration_metrics,
    f1_statistic,
    predict_at,
    ranking_metrics,
    threshold_metrics,
)

PROTOCOLS = ("primary", "chronological", "pakistan_holdout")
GUARDED_PATHS = (
    "packages/compassio_ml/src",
    "configs/ml_benchmark_v1.yaml",
    "configs/research_split_v1.yaml",
    "configs/research_split_v1.lock.json",
)


class PlanIntegrityError(RuntimeError):
    """The evaluation plan, data, or code differs from what was pre-registered."""


class OneShotViolationError(RuntimeError):
    """This protocol's test partition has already been accessed under this plan."""


# ---------------------------------------------------------------- plan model
class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SelectedModel(_Frozen):
    algorithm: str
    representation: str
    tfidf: TfidfPreset
    params: dict[str, Any]
    input_columns: tuple[str, ...]
    positive_label: str


class ProtocolPlan(_Frozen):
    fit_partition: str
    threshold: float
    threshold_source: str
    test_partition: str = "test"
    expected_test_records: int = Field(ge=1)


class FinalPlan(_Frozen):
    plan_version: str
    source_git_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    seed: int
    selected_model: SelectedModel
    data_checksums: dict[str, str]
    protocols: dict[str, ProtocolPlan]
    metrics: dict[str, Any]
    slices: dict[str, Any]
    confidence_intervals: dict[str, Any]
    latency_benchmark: dict[str, Any]
    acceptance_criteria: dict[str, Any]
    baselines: tuple[str, ...]
    notes: tuple[str, ...] = ()


def plan_sha256(path: Path) -> str:
    return sha256_file(path)


def load_plan(path: Path, expected_sha256: str) -> FinalPlan:
    actual = plan_sha256(path)
    if actual != expected_sha256:
        raise PlanIntegrityError(f"plan sha256 {actual} != supplied {expected_sha256}")
    return FinalPlan.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


# ---------------------------------------------------------------- selected model
def selected_estimator(model: SelectedModel, seed: int) -> BaseEstimator:
    return make_estimator(model.algorithm, dict(model.params), model.tfidf, seed)


def train_oof_threshold(
    model: SelectedModel, train: Partition, seed: int, n_splits: int = 3
) -> float:
    """Task 004 procedure: max-F1 threshold on group-aware out-of-fold TRAIN predictions."""
    texts = build_texts(train.features, model.representation)  # type: ignore[arg-type]
    oof = np.full(len(train), np.nan)
    for tr, te in group_folds(train.y, train.groups, n_splits, seed):
        est = selected_estimator(model, seed).fit(texts[tr], train.y[tr])
        oof[te] = scores(est, texts[te], model.algorithm)
    return best_f1_threshold(train.y, oof)


def fit_selected(model: SelectedModel, train: Partition, seed: int) -> BaseEstimator:
    texts = build_texts(train.features, model.representation)  # type: ignore[arg-type]
    return selected_estimator(model, seed).fit(texts, train.y)


def development_report(
    model: SelectedModel, protocol: str, paths: FrozenPaths, seed: int
) -> dict[str, Any]:
    """Pre-registration step (no test access): train-OOF threshold and validation metrics."""
    parts = load_partitions(paths.table, paths.membership, protocol, ("train", "validation"))
    train, val = parts["train"], parts["validation"]
    threshold = train_oof_threshold(model, train, seed)
    fitted = fit_selected(model, train, seed)
    val_score = scores(fitted, build_texts(val.features, model.representation), model.algorithm)  # type: ignore[arg-type]
    pred = predict_at(val_score, threshold)
    return {
        "protocol": protocol,
        "train_records": len(train),
        "train_positives": train.positives,
        "validation_records": len(val),
        "validation_positives": val.positives,
        "train_oof_threshold": threshold,
        "validation": threshold_metrics(val.y, pred) | ranking_metrics(val.y, val_score),
        "model_sha256": model_sha256(fitted),
        "model_fingerprint": model_fingerprint(fitted),
        "validation_scores": val_score,
        "validation_record_ids": val.record_ids,
    }


# ---------------------------------------------------------------- metrics
def full_metrics(
    y: np.ndarray,
    score: np.ndarray,
    threshold: float,
    groups: np.ndarray,
    *,
    resamples: int,
    confidence: float,
    seed: int,
    probabilistic: bool,
) -> dict[str, Any]:
    pred = predict_at(score, threshold)
    out: dict[str, Any] = {
        "records": len(y),
        "positives": int(y.sum()),
        "negatives": int(len(y) - y.sum()),
        "groups": len(set(groups)),
        "threshold": threshold,
    }
    out.update(threshold_metrics(y, pred))
    out.update(ranking_metrics(y, score))
    if probabilistic:
        out.update(calibration_metrics(y, score))
    boot = GroupBootstrap.build(groups, resamples, seed)
    for name, stat_fn in (
        ("average_precision", ap_statistic(y, score)),
        ("f1", f1_statistic(y, pred)),
    ):
        lo, hi, n = boot.interval(stat_fn, confidence)
        out[f"{name}_ci95"] = [lo, hi]
        out[f"{name}_ci_valid_resamples"] = n
    for name in ("precision", "recall"):

        def stat(idx: np.ndarray, name: str = name) -> float | None:
            m = threshold_metrics(y[idx], pred[idx])
            return float(m[name])

        lo, hi, _ = boot.interval(stat, confidence)
        out[f"{name}_ci95"] = [lo, hi]
    return out


def slice_metrics(
    y: np.ndarray,
    score: np.ndarray,
    threshold: float,
    mask: np.ndarray,
    *,
    min_records: int,
    min_positives: int,
) -> dict[str, Any]:
    pred = predict_at(score, threshold)
    n, pos = int(mask.sum()), int(y[mask].sum())
    row: dict[str, Any] = {"records": n, "positives": pos}
    if n == 0:
        return row | {"suppressed": True}
    tm = threshold_metrics(y[mask], pred[mask])
    row.update({k: tm[k] for k in ("tp", "fp", "fn", "tn")})
    suppressed = n < min_records or pos < min_positives
    row["suppressed"] = suppressed
    if pos:
        row["recall"] = tm["recall"]
    if not suppressed:
        row.update({"precision": tm["precision"], "f1": tm["f1"]})
        row.update(ranking_metrics(y[mask], score[mask]))
    return row


def build_slices(
    meta: pd.DataFrame,
    labels: pd.DataFrame,
    y: np.ndarray,
    score: np.ndarray,
    threshold: float,
    plan: FinalPlan,
) -> dict[str, Any]:
    mn, mp = plan.slices["min_records"], plan.slices["min_positives"]
    energy = (meta["sector_name"].fillna("") == "ENERGY").to_numpy()
    retro = meta["retrospective_text_warning"].fillna(False).astype(bool).to_numpy()
    years = meta["commitment_year"].astype(int).to_numpy()
    mit = labels["rio_mitigation"].fillna(0).astype(int).to_numpy()
    ada = labels["rio_adaptation"].fillna(0).astype(int).to_numpy()
    overall = labels["rio_overall"].fillna(0).astype(int).to_numpy()
    out: dict[str, Any] = {}

    def add(name: str, mask: np.ndarray) -> None:
        out[name] = slice_metrics(y, score, threshold, mask, min_records=mn, min_positives=mp)

    add("energy", energy)
    add("non_energy", ~energy)
    add("retrospective_warning", retro)
    add("no_retrospective_warning", ~retro)
    for lo, hi in plan.slices["year_bands"]:
        add(f"years_{lo}_{hi}", (years >= lo) & (years <= hi))
    # Label-defined slices exist only for positives: recall (and counts) are the metric.
    positive = y == 1
    for name, mask in (
        ("positives_mitigation_related", positive & (mit > 0)),
        ("positives_adaptation_related", positive & (ada > 0)),
        ("positives_adaptation_only", positive & (ada > 0) & (mit == 0)),
        ("positives_mitigation_only", positive & (mit > 0) & (ada == 0)),
        ("positives_significant_overall_1", positive & (overall == 1)),
        ("positives_principal_overall_2", positive & (overall == 2)),
        ("positives_non_energy_adaptation_related", positive & (ada > 0) & ~energy),
    ):
        pred = predict_at(score, threshold)
        tp = int((pred[mask] == 1).sum())
        out[name] = {
            "positives": int(mask.sum()),
            "tp": tp,
            "fn": int(mask.sum()) - tp,
            "recall": (tp / int(mask.sum())) if mask.sum() else None,
        }
    return out


def latency_ms_per_1000(
    model: BaseEstimator, texts: np.ndarray, algorithm: str, repeats: int
) -> float:
    timings = []
    for _ in range(repeats):
        start = time.perf_counter()
        scores(model, texts, algorithm)
        timings.append((time.perf_counter() - start) / len(texts) * 1_000_000)
    return round(float(np.median(timings)), 2)


# ---------------------------------------------------------------- guards
def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True, timeout=60
    ).stdout.strip()


def verify_code_unchanged(repo: Path, source_commit: str) -> str:
    head = _git(repo, "rev-parse", "HEAD")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, head], cwd=repo, timeout=60
    )
    if ancestry.returncode != 0:
        raise PlanIntegrityError(f"plan source commit {source_commit} is not an ancestor of HEAD")
    changed = _git(repo, "diff", "--name-only", source_commit, "--", *GUARDED_PATHS)
    if changed:
        raise PlanIntegrityError(
            f"guarded files changed since the plan commit: {changed.splitlines()}"
        )
    dirty = _git(repo, "status", "--porcelain", "--", *GUARDED_PATHS)
    if dirty:
        raise PlanIntegrityError(f"uncommitted changes in guarded paths: {dirty.splitlines()}")
    return head


def _verify_data(plan: FinalPlan, paths: FrozenPaths) -> None:
    lock = require_frozen(paths).lock
    current = {
        "table_sha256": lock["table"]["sha256"],
        "membership_sha256": lock["membership"]["sha256"],
        "split_config_sha256": lock["split_config"]["sha256"],
        "split_lock_sha256": sha256_file(paths.lock),
    }
    for key, value in plan.data_checksums.items():
        if current.get(key) != value:
            raise PlanIntegrityError(f"{key}: {current.get(key)} != plan {value}")


def _write_record(path: Path, record: dict[str, Any], *, create: bool) -> None:
    payload = json.dumps(record, indent=2, sort_keys=True, default=str) + "\n"
    if create:
        with path.open("x", encoding="utf-8") as handle:  # exclusive: fails if it exists
            handle.write(payload)
    else:
        path.chmod(stat.S_IWRITE | stat.S_IREAD)
        path.write_text(payload, encoding="utf-8")


def _make_read_only(path: Path) -> None:
    path.chmod(stat.S_IREAD)


# ---------------------------------------------------------------- one-shot evaluation
@dataclass
class FinalResult:
    protocol: str
    out_dir: Path
    results: dict[str, Any]


def final_evaluate(
    protocol: str,
    plan_path: Path,
    supplied_sha256: str,
    repo: Path,
    out_root: Path,
    paths: FrozenPaths,
    *,
    bootstrap_seed_offset: int = 0,
    check_git: bool = True,
) -> FinalResult:
    if protocol not in PROTOCOLS:
        raise ValueError(f"unknown protocol {protocol!r}")
    plan = load_plan(plan_path, supplied_sha256)
    if protocol not in plan.protocols:
        raise PlanIntegrityError(f"protocol {protocol} not pre-registered in the plan")
    _verify_data(plan, paths)
    head = verify_code_unchanged(repo, plan.source_git_commit) if check_git else "unchecked"
    proto = plan.protocols[protocol]

    out_dir = out_root / protocol
    out_dir.mkdir(parents=True, exist_ok=True)
    record_path = out_dir / "test_access.json"
    if record_path.exists():
        raise OneShotViolationError(f"{record_path} exists: {protocol} test already accessed")
    record: dict[str, Any] = {
        "protocol": protocol,
        "plan_sha256": supplied_sha256,
        "plan_version": plan.plan_version,
        "git_head": head,
        "source_git_commit": plan.source_git_commit,
        "opened_at": datetime.now(UTC).isoformat(),
        "status": "opened",
    }
    _write_record(record_path, record, create=True)
    try:
        results = _evaluate(plan, proto, protocol, paths, out_dir, bootstrap_seed_offset)
    except Exception as exc:
        record.update(
            {
                "status": "failed",
                "failed_at": datetime.now(UTC).isoformat(),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        _write_record(record_path, record, create=False)
        _make_read_only(record_path)
        raise
    outputs = {
        p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.name != record_path.name
    }
    record.update(
        {
            "status": "completed",
            "completed_at": datetime.now(UTC).isoformat(),
            "output_sha256": outputs,
        }
    )
    _write_record(record_path, record, create=False)
    for p in out_dir.iterdir():
        _make_read_only(p)
    return FinalResult(protocol, out_dir, results)


def _evaluate(
    plan: FinalPlan,
    proto: ProtocolPlan,
    protocol: str,
    paths: FrozenPaths,
    out_dir: Path,
    seed_offset: int,
) -> dict[str, Any]:
    model_spec = plan.selected_model
    train = load_partitions(paths.table, paths.membership, protocol, (proto.fit_partition,))[
        proto.fit_partition
    ]
    test = load_partitions(paths.table, paths.membership, protocol, ("test",), allow_test=True)[
        "test"
    ]
    if set(train.groups) & set(test.groups):
        raise PlanIntegrityError("train and test share leakage groups")
    if len(test) != proto.expected_test_records:
        raise PlanIntegrityError(
            f"test has {len(test)} records; plan expects {proto.expected_test_records}"
        )
    if protocol == "pakistan_holdout" and bool(train.meta["is_pakistan"].any()):
        raise PlanIntegrityError("Pakistan records present in Pakistan-holdout training data")

    model = fit_selected(model_spec, train, plan.seed)
    rep = model_spec.representation
    test_texts = build_texts(test.features, rep)  # type: ignore[arg-type]
    score = scores(model, test_texts, model_spec.algorithm)
    ci = plan.confidence_intervals
    seed = plan.seed + seed_offset
    results: dict[str, Any] = {
        "protocol": protocol,
        "fit_partition": proto.fit_partition,
        "train_records": len(train),
        "train_positives": train.positives,
        "model": full_metrics(
            test.y,
            score,
            proto.threshold,
            test.groups,
            resamples=ci["resamples"],
            confidence=ci["confidence"],
            seed=seed,
            probabilistic=True,
        ),
    }
    labels = _test_labels(paths.table, test.record_ids)
    results["slices"] = build_slices(test.meta, labels, test.y, score, proto.threshold, plan)
    if protocol == "pakistan_holdout":
        energy = (test.meta["sector_name"].fillna("") == "ENERGY").to_numpy()
        pred = predict_at(score, proto.threshold)
        results["pakistan_confusion"] = {
            name: threshold_metrics(test.y[m], pred[m])
            | {"records": int(m.sum()), "positives": int(test.y[m].sum())}
            for name, m in (
                ("all", np.ones(len(test), dtype=bool)),
                ("energy", energy),
                ("non_energy", ~energy),
            )
        }
    # Pre-registered comparators (no fitting on test).
    baselines: dict[str, Any] = {}
    if "keyword" in plan.baselines:
        kw = KeywordClassifier().fit([], [])
        kscore = kw.decision_function(list(test_texts))
        baselines["keyword"] = full_metrics(
            test.y,
            kscore,
            1.0,
            test.groups,
            resamples=ci["resamples"],
            confidence=ci["confidence"],
            seed=seed,
            probabilistic=False,
        )
    if "majority" in plan.baselines:
        baselines["majority"] = {
            "average_precision": float(test.y.mean()),
            **threshold_metrics(test.y, np.zeros(len(test), dtype=int)),
        }
    results["baselines"] = baselines

    buffer = io.BytesIO()
    joblib.dump(model, buffer, compress=3)
    results["model_size_kb"] = round(len(buffer.getvalue()) / 1024, 1)
    bench = plan.latency_benchmark
    dev = load_partitions(paths.table, paths.membership, "primary", ("validation",))["validation"]
    bench_texts = build_texts(dev.features, rep)[: bench["texts"]]  # type: ignore[arg-type]
    results["latency_ms_per_1000_texts"] = latency_ms_per_1000(
        model, bench_texts, model_spec.algorithm, bench["repeats"]
    )
    results["model_fingerprint"] = model_fingerprint(model)
    joblib.dump(model, out_dir / "model.joblib", compress=3)
    pd.DataFrame(
        {
            "record_id": test.record_ids,
            "leakage_group_id": test.groups,
            "y_true": test.y,
            "score": score,
            "pred": predict_at(score, proto.threshold),
        }
    ).to_parquet(out_dir / "test_predictions.parquet", index=False)
    (out_dir / "results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return results


def _test_labels(table_path: Path, record_ids: np.ndarray) -> pd.DataFrame:
    """Author label components for slice reporting only (never model inputs)."""
    table = pd.read_parquet(
        table_path, columns=["record_id", "rio_overall", "rio_mitigation", "rio_adaptation"]
    )
    table = table.set_index("record_id").loc[list(record_ids)]
    return table.reset_index()


def model_fingerprint(model: BaseEstimator) -> str:
    """Content fingerprint of a fitted TF-IDF linear pipeline, stable across processes.

    The pickled bytes are NOT stable: scikit-learn's TfidfVectorizer stores
    ``_stop_words_id = id(self.stop_words)``, a per-process memory address. File SHA-256
    therefore verifies one artifact's integrity; this fingerprint verifies reproducibility.
    """
    tfidf = model.named_steps["tfidf"]
    clf = model.named_steps["clf"]
    digest = hashlib.sha256()
    digest.update(json.dumps(model.get_params(deep=True), sort_keys=True, default=str).encode())
    for term, index in sorted(tfidf.vocabulary_.items()):
        digest.update(f"{term}\t{int(index)}\n".encode())
    for array in (tfidf.idf_, clf.coef_, clf.intercept_, clf.classes_):
        digest.update(np.ascontiguousarray(array).tobytes())
    return digest.hexdigest()


def model_sha256(model: BaseEstimator) -> str:
    buffer = io.BytesIO()
    joblib.dump(model, buffer, compress=3)
    return hashlib.sha256(buffer.getvalue()).hexdigest()
