"""Validation-stage benchmark for one frozen protocol (Task 004).

Flow, per (representation, TF-IDF preset, algorithm):
  1. Hyperparameters chosen by group-aware stratified K-fold CV *inside the training partition*
     (``StratifiedGroupKFold`` on ``leakage_group_id``), scored by average precision.
  2. The chosen configuration's out-of-fold (OOF) training scores fix its decision threshold
     (max F1). Validation labels are never used to pick hyperparameters or thresholds.
  3. The finalist is refitted on the full training partition and scored on validation.
Finalists are then ranked on validation by the pre-registered rule in the config.
The test partition is never loaded (``load_partitions`` refuses it).
"""

import io
import json
import time
import tracemalloc
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.model_selection import StratifiedGroupKFold

from compassio_ml.modeling.config import BenchmarkConfig, Suite, stable_hash
from compassio_ml.modeling.data import Partition, load_partitions
from compassio_ml.modeling.estimators import (
    PROBABILISTIC,
    make_calibrated_svm,
    make_estimator,
    score_kind,
    scores,
)
from compassio_ml.modeling.features import Representation, build_texts
from compassio_ml.modeling.frozen import FrozenPaths, require_frozen, sha256_file
from compassio_ml.modeling.metrics import (
    GroupBootstrap,
    ap_difference_statistic,
    ap_statistic,
    best_f1_threshold,
    calibration_metrics,
    f1_statistic,
    predict_at,
    ranking_metrics,
    reliability_table,
    threshold_metrics,
)
from compassio_ml.modeling.slices import slice_report
from compassio_ml.modeling.tracking import Registry, environment, prepare_run_dir, trial_id

COMPLEXITY = {
    "majority": 0,
    "keyword": 0,
    "multinomial_nb": 1,
    "logistic_regression": 1,
    "linear_svm": 1,
    "linear_svm_calibrated": 2,
}
CONVENTIONAL_THRESHOLD = {"probability": 0.5, "decision_score": 0.0}
Folds = list[tuple[np.ndarray, np.ndarray]]


def group_folds(y: np.ndarray, groups: np.ndarray, n_splits: int, seed: int) -> Folds:
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    folds = [(tr, te) for tr, te in splitter.split(np.zeros(len(y)), y, groups)]
    for tr, te in folds:
        if set(groups[tr]) & set(groups[te]):
            raise AssertionError("group-aware fold leaked a leakage group")
    return folds


@dataclass
class Finalist:
    key: str
    algorithm: str
    representation: str
    tfidf: str | None
    params: dict[str, Any]
    model: BaseEstimator
    threshold: float
    threshold_source: str
    cv: dict[str, Any]
    val_score: np.ndarray
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    run_id: str
    run_dir: Path
    finalists: list[Finalist]
    winner: Finalist
    ranking: list[dict[str, Any]]
    train: Partition
    validation: Partition


class Benchmark:
    def __init__(
        self,
        config: BenchmarkConfig,
        protocol: str,
        suite_name: str,
        repo: Path,
        out_root: Path,
        *,
        seed: int | None = None,
        overwrite: bool = False,
    ) -> None:
        if suite_name not in config.suites:
            raise ValueError(f"Unknown suite {suite_name!r}; choose from {sorted(config.suites)}")
        self.config = config
        self.protocol = protocol
        self.suite_name = suite_name
        self.suite: Suite = config.suites[suite_name]
        self.seed = config.seed if seed is None else seed
        self.repo = repo
        self.paths = FrozenPaths(
            table=repo / config.data.table,
            membership=repo / config.data.membership,
            split_config=repo / config.data.split_config,
            lock=repo / config.data.split_lock,
        )
        self.config_hash = stable_hash(config.model_dump(mode="json"))
        self.run_id = f"{protocol}__{suite_name}__seed{self.seed}__cfg{self.config_hash[:8]}"
        self.out_root = out_root
        self.overwrite = overwrite

    # ---------------------------------------------------------------- helpers
    def _oof(
        self,
        algorithm: str,
        params: dict[str, Any],
        tfidf: str | None,
        texts: np.ndarray,
        y: np.ndarray,
        groups: np.ndarray,
        folds: Folds,
    ) -> np.ndarray:
        oof = np.full(len(y), np.nan)
        preset = self.config.tfidf_presets[tfidf] if tfidf else None
        for k, (tr, te) in enumerate(folds):
            if algorithm == "linear_svm_calibrated":
                assert preset is not None
                inner = group_folds(
                    y[tr], groups[tr], self.config.inner_cv.n_splits, self.seed + k + 1
                )
                model: BaseEstimator = make_calibrated_svm(params, preset, self.seed, inner)
            else:
                model = make_estimator(algorithm, params, preset, self.seed)
            model.fit(texts[tr], y[tr])
            oof[te] = scores(model, texts[te], algorithm)
        if np.isnan(oof).any():
            raise AssertionError("OOF scores incomplete")
        return oof

    def _fit_full(
        self,
        algorithm: str,
        params: dict[str, Any],
        tfidf: str | None,
        texts: np.ndarray,
        y: np.ndarray,
        folds: Folds,
    ) -> tuple[BaseEstimator, dict[str, Any]]:
        preset = self.config.tfidf_presets[tfidf] if tfidf else None
        if algorithm == "linear_svm_calibrated":
            assert preset is not None
            model: BaseEstimator = make_calibrated_svm(params, preset, self.seed, folds)
        else:
            model = make_estimator(algorithm, params, preset, self.seed)
        tracemalloc.start()
        start = time.perf_counter()
        model.fit(texts, y)
        fit_seconds = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        info: dict[str, Any] = {
            "fit_seconds": round(fit_seconds, 3),
            "fit_peak_tracemalloc_mb": round(peak / 2**20, 1),
        }
        vectorizer = _vectorizer_of(model)
        if vectorizer is not None:
            matrix = vectorizer.transform(texts)
            info["tfidf_features"] = len(vectorizer.vocabulary_)
            info["train_matrix_nnz"] = int(matrix.nnz)
            info["train_matrix_mb"] = round(
                (matrix.data.nbytes + matrix.indices.nbytes + matrix.indptr.nbytes) / 2**20, 2
            )
        return model, info

    # ---------------------------------------------------------------- run
    def run(self) -> BenchmarkResult:
        frozen = require_frozen(self.paths)
        parts = load_partitions(self.paths.table, self.paths.membership, self.protocol)
        train, val = parts["train"], parts["validation"]
        run_dir = prepare_run_dir(self.out_root, self.run_id, overwrite=self.overwrite)
        registry = Registry(run_dir, self.run_id)
        manifest = {
            "run_id": self.run_id,
            "protocol": self.protocol,
            "suite": self.suite_name,
            "seed": self.seed,
            "config_hash": self.config_hash,
            "config": self.config.model_dump(mode="json"),
            "frozen_lock": frozen.lock,
            "environment": environment(self.repo),
            "partitions": {
                p.name: {"records": len(p), "positives": p.positives, "groups": len(set(p.groups))}
                for p in (train, val)
            },
            "test_partition_loaded": False,
        }
        (run_dir / "run_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
        )
        folds = group_folds(train.y, train.groups, self.config.inner_cv.n_splits, self.seed)
        finalists: list[Finalist] = []
        for rep in self.suite.representations:
            tr_texts = build_texts(train.features, rep)
            va_texts = build_texts(val.features, rep)
            finalists += self._run_representation(
                rep, tr_texts, va_texts, train, val, folds, registry
            )
        ranking, winner = self._rank(finalists, val)
        self._write_outputs(run_dir, finalists, ranking, winner, train, val)
        return BenchmarkResult(self.run_id, run_dir, finalists, winner, ranking, train, val)

    def _trial(
        self,
        registry: Registry,
        spec: dict[str, Any],
        fn: Any,
    ) -> Any:
        tid = trial_id(self.run_id, spec)
        registry.log({"trial_id": tid, "status": "started", **spec})
        start = time.perf_counter()
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001 - recorded as a failed trial, never silently dropped
            registry.log(
                {
                    "trial_id": tid,
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "seconds": round(time.perf_counter() - start, 3),
                    **spec,
                }
            )
            return None
        registry.log(
            {
                "trial_id": tid,
                "status": "completed",
                "seconds": round(time.perf_counter() - start, 3),
                **spec,
                **result[0],
            }
        )
        return result

    def _run_representation(
        self,
        rep: Representation,
        tr_texts: np.ndarray,
        va_texts: np.ndarray,
        train: Partition,
        val: Partition,
        folds: Folds,
        registry: Registry,
    ) -> list[Finalist]:
        out: list[Finalist] = []
        # Baselines (nothing tuned).
        for algorithm in ("majority", "keyword"):
            if algorithm not in self.suite.candidates:
                continue
            spec: dict[str, Any] = {
                "stage": "finalist",
                "algorithm": algorithm,
                "representation": rep,
                "tfidf": None,
                "params": {},
            }

            def fit_baseline(algorithm: str = algorithm) -> tuple[dict[str, Any], Finalist]:
                model, info = self._fit_full(algorithm, {}, None, tr_texts, train.y, folds)
                threshold = 1.0 if algorithm == "keyword" else 0.5
                f = Finalist(
                    f"{algorithm}|{rep}",
                    algorithm,
                    rep,
                    None,
                    {},
                    model,
                    threshold,
                    "fixed_rule",
                    {},
                    scores(model, va_texts, algorithm),
                    dict(info),
                )
                return info, f

            res = self._trial(registry, spec, fit_baseline)
            if res is not None:
                out.append(res[1])

        for algorithm in ("multinomial_nb", "logistic_regression", "linear_svm"):
            grid = self.suite.candidates.get(algorithm)  # type: ignore[call-overload]
            if not grid:
                continue
            for tfidf in self.suite.tfidf:
                cv_rows: list[tuple[float, int, dict[str, Any], dict[str, Any], np.ndarray]] = []
                for order, params in enumerate(grid):
                    spec = {
                        "stage": "inner_cv",
                        "algorithm": algorithm,
                        "representation": rep,
                        "tfidf": tfidf,
                        "params": dict(params),
                    }
                    run_cv = partial(
                        self._inner_cv, algorithm, dict(params), tfidf, tr_texts, train, folds
                    )
                    res = self._trial(registry, spec, run_cv)
                    if res is not None:
                        info, oof = res
                        cv_rows.append(
                            (info["cv_average_precision_mean"], order, dict(params), info, oof)
                        )
                if not cv_rows:
                    continue
                _, _, best_params, cv_info, best_oof = max(cv_rows, key=lambda r: (r[0], -r[1]))
                out += self._finalists_for(
                    algorithm,
                    rep,
                    tfidf,
                    best_params,
                    best_oof,
                    cv_info,
                    tr_texts,
                    va_texts,
                    train,
                    folds,
                    registry,
                )
        return out

    def _inner_cv(
        self,
        algorithm: str,
        params: dict[str, Any],
        tfidf: str,
        tr_texts: np.ndarray,
        train: Partition,
        folds: Folds,
    ) -> tuple[dict[str, Any], np.ndarray]:
        oof = self._oof(algorithm, params, tfidf, tr_texts, train.y, train.groups, folds)
        fold_ap = [ranking_metrics(train.y[te], oof[te])["average_precision"] for _, te in folds]
        aps = [float(a) for a in fold_ap if a is not None]
        return {
            "cv_average_precision_mean": float(np.mean(aps)),
            "cv_average_precision_std": float(np.std(aps)),
            "cv_oof_average_precision": ranking_metrics(train.y, oof)["average_precision"],
        }, oof

    def _finalists_for(
        self,
        algorithm: str,
        rep: Representation,
        tfidf: str,
        params: dict[str, Any],
        oof: np.ndarray,
        cv_info: dict[str, Any],
        tr_texts: np.ndarray,
        va_texts: np.ndarray,
        train: Partition,
        folds: Folds,
        registry: Registry,
    ) -> list[Finalist]:
        out: list[Finalist] = []
        variants = [(algorithm, oof)]
        if algorithm == "linear_svm" and self.suite.calibrate_best_svm:
            variants.append(("linear_svm_calibrated", None))  # type: ignore[arg-type]
        for algo, algo_oof in variants:
            spec = {
                "stage": "finalist",
                "algorithm": algo,
                "representation": rep,
                "tfidf": tfidf,
                "params": dict(params),
            }

            def fit_finalist(
                algo: str = algo, algo_oof: np.ndarray | None = algo_oof
            ) -> tuple[dict[str, Any], Finalist]:
                if algo_oof is None:  # calibrated SVM: nested OOF probabilities for its threshold
                    algo_oof = self._oof(
                        algo, params, tfidf, tr_texts, train.y, train.groups, folds
                    )
                threshold = best_f1_threshold(train.y, algo_oof)
                model, info = self._fit_full(algo, params, tfidf, tr_texts, train.y, folds)
                info.update({"threshold": threshold, **cv_info})
                f = Finalist(
                    f"{algo}|{rep}|{tfidf}",
                    algo,
                    rep,
                    tfidf,
                    dict(params),
                    model,
                    threshold,
                    "train_oof_max_f1",
                    cv_info,
                    scores(model, va_texts, algo),
                    dict(info),
                )
                return info, f

            res = self._trial(registry, spec, fit_finalist)
            if res is not None:
                out.append(res[1])
        return out

    # ---------------------------------------------------------------- evaluation and ranking
    def _evaluate(
        self,
        f: Finalist,
        val: Partition,
        va_texts_by_rep: Mapping[str, np.ndarray],
        boot: GroupBootstrap,
    ) -> None:
        y, s = val.y, f.val_score
        kind = score_kind(f.algorithm) if f.algorithm != "majority" else "constant"
        m: dict[str, Any] = {"score_kind": kind}
        m.update({f"val_{k}": v for k, v in ranking_metrics(y, s).items()})
        pred_sel = predict_at(s, f.threshold)
        m.update({f"val_{k}@selected": v for k, v in threshold_metrics(y, pred_sel).items()})
        if kind in CONVENTIONAL_THRESHOLD:
            conv = CONVENTIONAL_THRESHOLD[kind]
            m["conventional_threshold"] = conv
            m.update(
                {
                    f"val_{k}@conventional": v
                    for k, v in threshold_metrics(y, predict_at(s, conv)).items()
                }
            )
        oracle = best_f1_threshold(y, s)
        m["oracle_threshold_not_for_selection"] = oracle
        m["val_f1@oracle_not_for_selection"] = threshold_metrics(y, predict_at(s, oracle))["f1"]
        if f.algorithm in PROBABILISTIC:
            m.update({f"val_{k}": v for k, v in calibration_metrics(y, s).items()})
        conf = self.config.bootstrap.confidence
        lo, hi, n = boot.interval(ap_statistic(y, s), conf)
        m.update({"val_average_precision_ci_low": lo, "val_average_precision_ci_high": hi})
        lo, hi, n2 = boot.interval(f1_statistic(y, pred_sel), conf)
        m.update(
            {
                "val_f1@selected_ci_low": lo,
                "val_f1@selected_ci_high": hi,
                "bootstrap_valid_resamples": min(n, n2),
            }
        )
        texts = va_texts_by_rep[f.representation]
        start = time.perf_counter()
        scores(f.model, texts, f.algorithm)
        m["latency_ms_per_1000"] = round(
            (time.perf_counter() - start) / len(texts) * 1000 * 1000, 2
        )
        buffer = io.BytesIO()
        joblib.dump(f.model, buffer, compress=3)
        m["model_size_kb"] = round(len(buffer.getvalue()) / 1024, 1)
        m["provides_probability"] = f.algorithm in PROBABILISTIC
        m["complexity_tier"] = COMPLEXITY[f.algorithm]
        f.metrics.update(m)

    def _rank(
        self, finalists: list[Finalist], val: Partition
    ) -> tuple[list[dict[str, Any]], Finalist]:
        if not finalists:
            raise RuntimeError("No finalist completed; see trials.jsonl for failures")
        boot = GroupBootstrap.build(val.groups, self.config.bootstrap.resamples, self.seed)
        va_texts: dict[str, np.ndarray] = {
            str(rep): build_texts(val.features, rep) for rep in self.suite.representations
        }
        for f in finalists:
            self._evaluate(f, val, va_texts, boot)
        learned = [f for f in finalists if f.algorithm not in ("majority",)]
        top = max(learned, key=lambda f: f.metrics["val_average_precision"] or -1)
        conf = self.config.bootstrap.confidence
        for f in finalists:
            if f is top or f.metrics["val_average_precision"] is None:
                f.metrics["ap_diff_vs_top_ci"] = (0.0, 0.0) if f is top else (None, None)
                f.metrics["tied_with_top"] = f is top
                continue
            lo, hi, _ = boot.interval(
                ap_difference_statistic(val.y, top.val_score, f.val_score), conf
            )
            f.metrics["ap_diff_vs_top_ci"] = (lo, hi)
            f.metrics["tied_with_top"] = bool(lo is not None and lo <= 0.0)
        tie_set = [f for f in finalists if f.metrics["tied_with_top"]]

        def tie_key(f: Finalist) -> tuple[Any, ...]:
            m = f.metrics
            return (
                not m["provides_probability"],
                m["complexity_tier"],
                -(m["val_f1@selected"]),
                m["latency_ms_per_1000"],
                f.key,
            )

        winner = min(tie_set, key=tie_key)
        ordered = sorted(
            finalists, key=lambda f: (-(f.metrics["val_average_precision"] or -1), f.key)
        )
        ranking = []
        for rank, f in enumerate(ordered, start=1):
            ranking.append(
                {
                    "rank_by_val_ap": rank,
                    "key": f.key,
                    "algorithm": f.algorithm,
                    "representation": f.representation,
                    "tfidf": f.tfidf,
                    "params": json.dumps(f.params, sort_keys=True),
                    "threshold": f.threshold,
                    "threshold_source": f.threshold_source,
                    "is_top_ap": f is top,
                    "is_provisional_winner": f is winner,
                    **{k: v for k, v in f.metrics.items() if not isinstance(v, list)},
                }
            )
        return ranking, winner

    # ---------------------------------------------------------------- outputs
    def _write_outputs(
        self,
        run_dir: Path,
        finalists: list[Finalist],
        ranking: list[dict[str, Any]],
        winner: Finalist,
        train: Partition,
        val: Partition,
    ) -> None:
        pd.DataFrame(ranking).to_csv(run_dir / "finalists.csv", index=False, lineterminator="\n")
        timing = {
            "fit_seconds",
            "fit_peak_tracemalloc_mb",
            "latency_ms_per_1000",
            "model_size_kb",
            "seconds",
        }
        deterministic = [{k: v for k, v in r.items() if k not in timing} for r in ranking]
        (run_dir / "metrics_deterministic.json").write_text(
            json.dumps(deterministic, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        cfg = self.config
        slices = []
        for f in finalists:
            if f.algorithm == "majority":
                continue
            for row in slice_report(
                val.meta,
                val.y,
                f.val_score,
                predict_at(f.val_score, f.threshold),
                min_records=cfg.slice_min_records,
                min_positives=cfg.slice_min_positives,
            ):
                slices.append({"key": f.key, "is_provisional_winner": f is winner, **row})
        pd.DataFrame(slices).to_csv(
            run_dir / "validation_slices.csv", index=False, lineterminator="\n"
        )
        reliability: list[dict[str, Any]] = []
        for f in finalists:
            if f.algorithm in PROBABILISTIC:
                for rel_row in reliability_table(val.y, f.val_score):
                    reliability.append({"key": f.key, **rel_row})
        pd.DataFrame(reliability).to_csv(
            run_dir / "reliability.csv", index=False, lineterminator="\n"
        )
        predictions = pd.DataFrame(
            {
                "record_id": val.record_ids,
                "leakage_group_id": val.groups,
                "y_true": val.y,
                "score": winner.val_score,
                "pred_at_selected_threshold": predict_at(winner.val_score, winner.threshold),
            }
        )
        predictions.to_parquet(run_dir / "winner_validation_predictions.parquet", index=False)
        self._save_model(run_dir, winner)

    def _save_model(self, run_dir: Path, winner: Finalist) -> None:
        model_dir = run_dir / "model"
        model_dir.mkdir(exist_ok=True)
        path = model_dir / "model.joblib"
        joblib.dump(winner.model, path, compress=3)
        lock = json.loads(self.paths.lock.read_text(encoding="utf-8"))
        metadata = {
            "model_version": f"{self.run_id}__{winner.key.replace('|', '__')}",
            "status": "provisional_validation_winner (not a production model)",
            "artifact_file": path.name,
            "artifact_sha256": sha256_file(path),
            "algorithm": winner.algorithm,
            "representation": winner.representation,
            "tfidf_preset": winner.tfidf,
            "tfidf_settings": (
                self.config.tfidf_presets[winner.tfidf].model_dump(mode="json")
                if winner.tfidf
                else None
            ),
            "params": winner.params,
            "score_kind": score_kind(winner.algorithm),
            "provides_probability": winner.algorithm in PROBABILISTIC,
            "threshold": winner.threshold,
            "threshold_source": winner.threshold_source,
            "protocol": self.protocol,
            "trained_on": "train partition of the protocol only",
            "dataset_version": {
                "table_sha256": lock["table"]["sha256"],
                "membership_sha256": lock["membership"]["sha256"],
                "split_config_sha256": lock["split_config"]["sha256"],
            },
            "config_hash": self.config_hash,
            "seed": self.seed,
            "intended_use": "Decision support: flags text resembling climate-relevant annotations. "
            "Not funding approval, impact or return assessment.",
        }
        (model_dir / "model_metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def _vectorizer_of(model: BaseEstimator) -> Any:
    steps = getattr(model, "named_steps", None)
    if steps is not None and "tfidf" in steps:
        return steps["tfidf"]
    calibrated = getattr(model, "calibrated_classifiers_", None)
    if calibrated:
        inner = calibrated[0].estimator
        return inner.named_steps["tfidf"]
    return None
