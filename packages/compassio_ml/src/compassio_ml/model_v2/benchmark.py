"""Fast-track benchmark: train-only model fitting, one VALID comparison, champion selection.

Leakage controls (all enforced in code):

* every vectoriser, classifier, Platt calibrator, hyper-parameter choice and threshold is fitted
  on TRAIN rows only (outer StratifiedGroupKFold on partition groups; Platt uses inner group
  folds inside each training fold);
* VALID rows are scored, never fitted; they are used ONCE to choose among finalists with the
  pre-registered rule in the plan;
* inputs are text only; publisher/family are used only as optional TRAINING sample weights.
"""

import io
import json
import statistics
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.metrics import average_precision_score
from sklearn.pipeline import FeatureUnion, Pipeline

from compassio_ml.external.paths import V2Paths
from compassio_ml.model_v2 import candidates as cm
from compassio_ml.model_v2 import evaluate as ev
from compassio_ml.model_v2.artifact import save_candidate
from compassio_ml.model_v2.data import (
    DevData,
    cross_publisher_families,
    french_share,
    load_aiddata_training,
    load_development,
    resolve_release_dir,
)
from compassio_ml.model_v2.plan import Candidate, FastPlan
from compassio_ml.modeling.features import KeywordClassifier
from compassio_ml.modeling.metrics import GroupBootstrap, best_f1_threshold
from compassio_ml.modeling.release import ReleasedClassifier

LETTERS = {
    "A": ("A_word_lr",),
    "B": ("B_char_lr",),
    "C": ("C_wordchar_lr", "C_wordchar_svm"),
    "D": ("D_word_svm_platt",),
    "E": ("E_publisher_balanced", "E_family_inverse"),
}
BASE_KINDS = ("word", "char")


@dataclass
class Finalist:
    population: str
    name: str
    feature_kind: str
    classifier_kind: str
    params: dict[str, Any]
    weighting: str
    oof_average_precision: float
    threshold: float
    model: Pipeline
    fit_seconds: float
    train_records: int
    train_positives: int
    valid_scores: dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def probabilistic(self) -> bool:
        return self.classifier_kind in cm.PROBABILISTIC

    def key(self) -> str:
        return f"{self.population}/{self.name}"


# ---------------------------------------------------------------------------- feature cache
class FoldFeatures:
    """TF-IDF matrices per outer fold, each vectoriser fitted on that fold's TRAIN rows."""

    def __init__(
        self, texts: np.ndarray, y: np.ndarray, groups: np.ndarray, plan: FastPlan, kinds: set[str]
    ) -> None:
        self.folds = list(cm.group_folds(y, groups, plan.cv.n_splits, plan.seed))
        base = {k for kind in kinds for k in (BASE_KINDS if kind == "word_char" else (kind,))}
        self.mats: dict[str, list[tuple[Any, Any]]] = {}
        for kind in sorted(base):
            per_fold = []
            for tr, te in self.folds:
                vec = cm.vectorizer(plan.features[kind])
                per_fold.append((vec.fit_transform(texts[tr]), vec.transform(texts[te])))
            self.mats[kind] = per_fold

    def get(self, kind: str, fold: int) -> tuple[Any, Any]:
        if kind == "word_char":
            (wtr, wte), (ctr, cte) = self.mats["word"][fold], self.mats["char"][fold]
            return sp.hstack([wtr, ctr], format="csr"), sp.hstack([wte, cte], format="csr")
        return self.mats[kind][fold]


class FullFeatures:
    """Vectorisers fitted on ALL training rows of a population (for the final model)."""

    def __init__(self, texts: np.ndarray, plan: FastPlan, kinds: set[str]) -> None:
        base = {k for kind in kinds for k in (BASE_KINDS if kind == "word_char" else (kind,))}
        self.vecs: dict[str, Any] = {}
        self.mats: dict[str, Any] = {}
        for kind in sorted(base):
            vec = cm.vectorizer(plan.features[kind])
            self.mats[kind] = vec.fit_transform(texts)
            self.vecs[kind] = vec

    def matrix(self, kind: str) -> Any:
        if kind == "word_char":
            return sp.hstack([self.mats["word"], self.mats["char"]], format="csr")
        return self.mats[kind]

    def transformer(self, kind: str) -> Any:
        if kind == "word_char":
            return FeatureUnion([("word", self.vecs["word"]), ("char", self.vecs["char"])])
        return self.vecs[kind]


def _clf_scores(clf: Any, X: Any, kind: str) -> np.ndarray:
    if kind in cm.PROBABILISTIC:
        return np.asarray(clf.predict_proba(X)[:, 1], dtype=float)
    return np.asarray(clf.decision_function(X), dtype=float)


def _fit_clf(
    kind: str,
    params: dict[str, Any],
    plan: FastPlan,
    X: Any,
    y: np.ndarray,
    groups: np.ndarray,
    weights: np.ndarray | None,
) -> Any:
    clf = cm.classifier(kind, params, plan.seed, plan.cv.n_splits)
    if kind == "svm_platt":
        return clf.fit(X, y, groups=groups, sample_weight=weights)
    return clf.fit(X, y, sample_weight=weights)


def oof_scores(
    cache: FoldFeatures,
    kind: str,
    clf_kind: str,
    params: dict[str, Any],
    plan: FastPlan,
    y: np.ndarray,
    groups: np.ndarray,
    weights: np.ndarray | None,
) -> np.ndarray:
    oof = np.zeros(len(y), dtype=float)
    for i, (tr, te) in enumerate(cache.folds):
        Xtr, Xte = cache.get(kind, i)
        clf = _fit_clf(
            clf_kind, params, plan, Xtr, y[tr], groups[tr], None if weights is None else weights[tr]
        )
        oof[te] = _clf_scores(clf, Xte, clf_kind)
    return oof


# ------------------------------------------------------------------------------ population
@dataclass
class PopulationResult:
    finalists: list[Finalist]
    trials: list[dict[str, Any]]


def run_population(
    name: str,
    train: pd.DataFrame,
    plan: FastPlan,
    candidate_names: list[str],
    threshold_mask: np.ndarray | None = None,
    log: Callable[[str], None] = print,
) -> PopulationResult:
    """Fit every candidate on ``train`` only. ``threshold_mask`` restricts the OOF rows used for
    the threshold (e.g. IATI rows when AidData augments training); still TRAIN-only."""
    train = train.reset_index(drop=True)
    texts, y, groups = train["text"].to_numpy(), train["y"].to_numpy(), train["group"].to_numpy()
    cands = [plan.candidate(n) for n in candidate_names]
    grid_cands = [c for c in cands if c.grid != "best_of_ABC"]
    kinds = {c.features for c in grid_cands} or {"word"}
    cache = FoldFeatures(texts, y, groups, plan, kinds)
    full = FullFeatures(texts, plan, kinds)
    trials: list[dict[str, Any]] = []
    finalists: list[Finalist] = []
    thr_mask = np.ones(len(y), dtype=bool) if threshold_mask is None else threshold_mask

    def finalize(
        cand: Candidate,
        kind: str,
        clf_kind: str,
        params: dict[str, Any],
        weighting: str,
        oof: np.ndarray,
        oof_ap: float,
    ) -> Finalist:
        start = time.perf_counter()
        weights = cm.sample_weights(train, weighting)
        clf = _fit_clf(clf_kind, params, plan, full.matrix(kind), y, groups, weights)
        model = Pipeline([("features", full.transformer(kind)), ("clf", clf)])
        return Finalist(
            population=name,
            name=cand.name,
            feature_kind=kind,
            classifier_kind=clf_kind,
            params=params,
            weighting=weighting,
            oof_average_precision=oof_ap,
            threshold=best_f1_threshold(y[thr_mask], oof[thr_mask]),
            model=model,
            fit_seconds=time.perf_counter() - start,
            train_records=len(y),
            train_positives=int(y.sum()),
        )

    for cand in grid_cands:
        assert isinstance(cand.grid, list)
        best: tuple[float, dict[str, Any], np.ndarray] | None = None
        for params in cand.grid:
            start = time.perf_counter()
            try:
                oof = oof_scores(
                    cache, cand.features, cand.classifier, params, plan, y, groups, None
                )
                ap = float(average_precision_score(y[thr_mask], oof[thr_mask]))
                status, error = "ok", None
            except (ValueError, MemoryError) as exc:  # recorded, never hidden
                ap, oof, status, error = float("nan"), np.zeros(len(y)), "failed", repr(exc)
            trials.append(
                {
                    "population": name,
                    "candidate": cand.name,
                    "params": params,
                    "weighting": "none",
                    "oof_average_precision": ap,
                    "status": status,
                    "error": error,
                    "seconds": round(time.perf_counter() - start, 2),
                }
            )
            log(f"  [{name}] {cand.name} {params} OOF AP={ap:.4f}")
            if status == "ok" and (best is None or ap > best[0]):
                best = (ap, params, oof)
        if best is not None:
            finalists.append(
                finalize(cand, cand.features, cand.classifier, best[1], "none", best[2], best[0])
            )

    abc = [f for f in finalists if f.name[0] in "ABC"]
    for cand in (c for c in cands if c.grid == "best_of_ABC"):
        if not abc:
            continue
        base = max(abc, key=lambda f: f.oof_average_precision)
        weights = cm.sample_weights(train, cand.weighting)
        start = time.perf_counter()
        oof = oof_scores(
            cache, base.feature_kind, base.classifier_kind, base.params, plan, y, groups, weights
        )
        ap = float(average_precision_score(y[thr_mask], oof[thr_mask]))
        trials.append(
            {
                "population": name,
                "candidate": cand.name,
                "params": base.params,
                "base": base.name,
                "weighting": cand.weighting,
                "oof_average_precision": ap,
                "status": "ok",
                "error": None,
                "seconds": round(time.perf_counter() - start, 2),
            }
        )
        log(f"  [{name}] {cand.name} on {base.name} OOF AP={ap:.4f}")
        finalists.append(
            finalize(
                cand, base.feature_kind, base.classifier_kind, base.params, cand.weighting, oof, ap
            )
        )
    return PopulationResult(finalists, trials)


def expand(letters: tuple[str, ...]) -> list[str]:
    return [n for letter in letters for n in LETTERS.get(letter, ())]


# ------------------------------------------------------------------------------ evaluation
def evaluate_scores(
    frame: pd.DataFrame,
    score: np.ndarray,
    threshold: float,
    probabilistic: bool,
    plan: FastPlan,
    boot: GroupBootstrap | None,
) -> dict[str, Any]:
    y = frame["y"].to_numpy()
    metrics = ev.basic(y, score, threshold, probabilistic)
    slices = ev.slice_table(
        frame,
        score,
        threshold,
        probabilistic,
        plan.slices.sector_families,
        plan.slices.min_records,
        plan.slices.min_positives,
    )
    out: dict[str, Any] = {
        "metrics": metrics,
        "slices": slices,
        "summary": ev.summary(metrics, slices),
    }
    if boot is not None:
        out["intervals"] = ev.intervals(frame, score, threshold, boot, plan.bootstrap.confidence)
    return out


def latency_ms_per_1000(model: Any, texts: np.ndarray, kind: str, repeats: int) -> float:
    times = []
    for _ in range(repeats):
        start = time.perf_counter()
        cm.scores(model, texts, kind)
        times.append((time.perf_counter() - start) * 1000 * 1000 / len(texts))
    return float(statistics.median(times))


def artifact_bytes(model: Any) -> int:
    buffer = io.BytesIO()
    joblib.dump(model, buffer, compress=3)
    return len(buffer.getvalue())


# ------------------------------------------------------------------------------- selection
def select_champion(rows: list[dict[str, Any]], plan: FastPlan) -> dict[str, Any]:
    """Pre-registered rule; ``rows`` are finalists scored on the selection population."""
    rule = plan.selection
    eligible = [
        r
        for r in rows
        if (r["summary"]["non_energy_precision"] or 0) >= rule.guard_min_non_energy_precision
    ]
    if not eligible:
        return {
            "champion": None,
            "decision": rule.if_no_candidate_passes_guard,
            "eligible": [],
            "reason": "no finalist met the non-energy precision guard",
        }
    primary = rule.primary_metric
    eligible = [r for r in eligible if r["summary"][primary] is not None]
    if not eligible:
        return {
            "champion": None,
            "decision": rule.if_no_candidate_passes_guard,
            "eligible": [],
            "reason": f"{primary} undefined for every finalist",
        }
    top = max(r["summary"][primary] for r in eligible)
    tied = [r for r in eligible if top - r["summary"][primary] <= rule.tie_window]

    def key(r: dict[str, Any]) -> tuple[float, ...]:
        values: list[float] = []
        for name in rule.tie_breakers:
            value = r[name] if name in r else r["summary"][name]
            values.append(-float(value) if name == "artifact_bytes" else float(value or 0))
        return tuple(values)

    champion = max(tied, key=key)
    return {
        "champion": champion["key"],
        "decision": "champion_selected",
        "eligible": [r["key"] for r in eligible],
        "tied_within_window": [r["key"] for r in tied],
        "primary_metric": primary,
        "top_value": top,
    }


# ---------------------------------------------------------------------------------- runner
def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, float) and value != value:
        return None
    return value


def run_benchmark(
    paths: V2Paths, plan: FastPlan, plan_sha: str, repo: Path, log: Callable[[str], None] = print
) -> Path:
    commit = _git(repo, "rev-parse", "HEAD")
    dirty = bool(_git(repo, "status", "--porcelain", "--untracked-files=no"))
    started = datetime.now(UTC)
    run_id = f"ml2fast_{plan_sha[:8]}_{commit[:8]}_{started:%Y%m%dT%H%M%SZ}"
    out = paths.writable(paths.output_root / plan.artifacts.run_root / run_id)
    out.mkdir(parents=True, exist_ok=False)
    log(f"run {run_id} (commit {commit[:8]}, dirty={dirty})")

    data: DevData = load_development(paths, plan)
    aid = load_aiddata_training(paths, plan)
    frame = data.frame
    train_all, valid_all = data.part("train"), data.part("valid").reset_index(drop=True)
    profile = _profile(frame, aid)
    log(json.dumps(profile["counts"], default=str)[:400])

    pops = plan.populations
    valid_sets = {
        n: valid_all[valid_all["source_id"].isin(p.valid_sources)].reset_index(drop=True)
        for n, p in pops.items()
    }
    boots = {
        n: GroupBootstrap.build(v["group"].to_numpy(), plan.bootstrap.resamples, plan.seed)
        for n, v in valid_sets.items()
    }
    results: dict[str, Any] = {"populations": {}, "transfer": [], "baselines": {}}
    trials: list[dict[str, Any]] = []
    finalists: dict[str, Finalist] = {}

    combined_best: Finalist | None = None
    for name, pop in pops.items():
        if name == "combined_plus_aiddata":
            continue
        train = train_all[train_all["source_id"].isin(pop.train_sources)]
        log(f"population {name}: train {len(train)} ({int(train['y'].sum())} pos)")
        res = run_population(name, train, plan, expand(pop.candidates), log=log)
        trials += res.trials
        for f in res.finalists:
            finalists[f.key()] = f
        if name == "combined":
            combined_best = max(
                (f for f in res.finalists if f.name[0] in "ABCD"),
                key=lambda f: f.oof_average_precision,
            )

    if "combined_plus_aiddata" in pops and combined_best is not None:
        iati = train_all[train_all["source_id"].isin(pops["combined"].train_sources)]
        plus = pd.concat([iati, aid], ignore_index=True)
        mask = (plus["source_id"] != "aiddata").to_numpy()
        log(f"population combined_plus_aiddata: train {len(plus)} (+{len(aid)} AidData)")
        res = run_population(
            "combined_plus_aiddata", plus, plan, [combined_best.name], threshold_mask=mask, log=log
        )
        trials += res.trials
        for f in res.finalists:
            finalists[f.key()] = f

    # Score VALID (each finalist on its own population's VALID; combined-type on combined VALID).
    for key, f in finalists.items():
        target = "combined" if f.population == "combined_plus_aiddata" else f.population
        vset = valid_sets[target]
        f.valid_scores[target] = cm.scores(f.model, vset["text"].to_numpy(), f.classifier_kind)
        evaluation = evaluate_scores(
            vset, f.valid_scores[target], f.threshold, f.probabilistic, plan, boots[target]
        )
        evaluation.update(
            {
                "key": key,
                "population": f.population,
                "evaluated_on": target,
                "candidate": f.name,
                "feature_kind": f.feature_kind,
                "classifier": f.classifier_kind,
                "params": f.params,
                "weighting": f.weighting,
                "threshold": f.threshold,
                "oof_average_precision": f.oof_average_precision,
                "train_records": f.train_records,
                "train_positives": f.train_positives,
                "fit_seconds": round(f.fit_seconds, 2),
            }
        )
        if target == "combined":
            evaluation["latency_ms_per_1000"] = latency_ms_per_1000(
                f.model,
                vset["text"].to_numpy()[: plan.latency.texts],
                f.classifier_kind,
                plan.latency.repeats,
            )
            evaluation["artifact_bytes"] = artifact_bytes(f.model)
        results["populations"].setdefault(f.population, {})[f.name] = evaluation
        log(
            f"  VALID {key}: AP={evaluation['summary']['average_precision']:.4f} "
            f"F1={evaluation['summary']['f1']:.4f} "
            f"NE-AP={evaluation['summary']['non_energy_average_precision']}"
        )

    # Publisher transfer (families of the target publisher are excluded from training).
    for t in plan.transfer:
        src = pops[t.train]
        target_valid = valid_all[valid_all["source_id"] == t.evaluate_on].reset_index(drop=True)
        target_families = set(frame.loc[frame["source_id"] == t.evaluate_on, "family"])
        base_train = train_all[train_all["source_id"].isin(src.train_sources)]
        train = base_train[~base_train["family"].isin(target_families)]
        excluded = len(base_train) - len(train)
        log(f"transfer {t.train}->{t.evaluate_on}: excluded {excluded} family-linked rows")
        for f in [f for f in finalists.values() if f.population == t.train]:
            model, threshold = f.model, f.threshold
            if excluded:
                res = run_population(f"transfer_{t.train}", train, plan, [f.name], log=log)
                model, threshold = res.finalists[0].model, res.finalists[0].threshold
            score = cm.scores(model, target_valid["text"].to_numpy(), f.classifier_kind)
            evaluation = evaluate_scores(
                target_valid, score, threshold, f.probabilistic, plan, None
            )
            evaluation.update(
                {
                    "train_population": t.train,
                    "evaluated_on": t.evaluate_on,
                    "candidate": f.name,
                    "excluded_family_rows": excluded,
                    "threshold": threshold,
                }
            )
            results["transfer"].append(evaluation)

    # Fixed baselines on the identical VALID records.
    combined_valid = valid_sets["combined"]
    texts_valid = combined_valid["text"].to_numpy()
    baseline_scores: dict[str, np.ndarray] = {}
    v1 = _load_v1(paths, plan, repo)
    start = time.perf_counter()
    v1_scores = np.array(
        [
            v1.predict(t, d).label_score
            for t, d in zip(combined_valid["title"], combined_valid["description"], strict=True)
        ]
    )
    v1_latency = (time.perf_counter() - start) * 1000 * 1000 / max(len(texts_valid), 1)
    baseline_scores["v1_release"] = v1_scores
    results["baselines"]["v1_release"] = {
        **evaluate_scores(combined_valid, v1_scores, v1.threshold, True, plan, boots["combined"]),
        "threshold": v1.threshold,
        "model_version": v1.manifest["model_version"],
        "latency_ms_per_1000_single_record_calls": v1_latency,
        "artifact_bytes": (
            resolve_release_dir(paths, plan.inputs.v1_release.release_dir) / "model.joblib"
        )
        .stat()
        .st_size,
    }
    valid_text_list = [str(t) for t in texts_valid]
    kw = KeywordClassifier().fit(valid_text_list[:1], [0]).decision_function(valid_text_list)
    baseline_scores["keyword"] = kw
    results["baselines"]["keyword"] = evaluate_scores(
        combined_valid, kw, 1.0, False, plan, boots["combined"]
    )
    majority = np.zeros(len(texts_valid))
    results["baselines"]["majority"] = evaluate_scores(
        combined_valid, majority, 1.0, False, plan, None
    )
    for source in ("iati_fcdo", "iati_ec_intpa"):
        mask = (combined_valid["source_id"] == source).to_numpy()
        results["baselines"][f"v1_release@{source}"] = evaluate_scores(
            combined_valid[mask].reset_index(drop=True),
            v1_scores[mask],
            v1.threshold,
            True,
            plan,
            None,
        )

    # Selection (once) among finalists scored on combined VALID.
    rows = [
        dict(results["populations"][f.population][f.name], key=k)
        for k, f in finalists.items()
        if f.population in ("combined", "combined_plus_aiddata")
    ]
    selection = select_champion(rows, plan)
    results["selection"] = selection
    comparisons: dict[str, Any] = {}
    if selection["champion"] is not None:
        champ = finalists[selection["champion"]]
        c_scores = champ.valid_scores["combined"]
        ne = combined_valid["non_energy"].to_numpy()
        boot = boots["combined"]
        comparisons["champion_minus_v1_ap"] = ev.paired_difference(
            combined_valid, c_scores, v1_scores, boot, plan.bootstrap.confidence
        )
        comparisons["champion_minus_v1_non_energy_ap"] = ev.paired_difference(
            combined_valid, c_scores, v1_scores, boot, plan.bootstrap.confidence, ne
        )
        for source in ("iati_fcdo", "iati_ec_intpa"):
            mask = (combined_valid["source_id"] == source).to_numpy()
            comparisons[f"champion_minus_v1_ap@{source}"] = ev.paired_difference(
                combined_valid, c_scores, v1_scores, boot, plan.bootstrap.confidence, mask
            )
        others = sorted(
            (r for r in rows if r["key"] != champ.key()),
            key=lambda r: -r["summary"][plan.selection.primary_metric],
        )
        if others:
            runner = finalists[others[0]["key"]]
            comparisons["champion_minus_runner_up_non_energy_ap"] = {
                "runner_up": runner.key(),
                **ev.paired_difference(
                    combined_valid,
                    c_scores,
                    runner.valid_scores["combined"],
                    boot,
                    plan.bootstrap.confidence,
                    ne,
                ),
            }
            comparisons["champion_minus_runner_up_ap"] = ev.paired_difference(
                combined_valid,
                c_scores,
                runner.valid_scores["combined"],
                boot,
                plan.bootstrap.confidence,
            )
        results["comparisons"] = comparisons
        results["champion_artifact"] = _save_champion(
            paths, plan, plan_sha, commit, run_id, champ, results
        )

    # Predictions (git-ignored run directory only).
    pred = combined_valid[
        [
            "candidate_id",
            "source_id",
            "y",
            "non_energy",
            "adaptation_only",
            "sector_family",
            "group",
        ]
    ].copy()
    for k, f in finalists.items():
        if "combined" in f.valid_scores:
            pred[f"score::{k}"] = f.valid_scores["combined"]
    for k, s in baseline_scores.items():
        pred[f"score::baseline/{k}"] = s
    pred.to_parquet(out / "valid_predictions.parquet", index=False)

    manifest = {
        "run_id": run_id,
        "plan_sha256": plan_sha,
        "plan_version": plan.plan_version,
        "git_commit": commit,
        "dirty": dirty,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "inputs": plan.inputs.model_dump(),
        "test_or_sealed_data_loaded": False,
        "consumed_v1_tests_rerun": False,
        "profile": profile,
        "environment": _environment(),
    }
    for name, payload in (("run_manifest.json", manifest), ("results.json", results)):
        (out / name).write_text(
            json.dumps(_jsonable(payload), indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
    with (out / "trials.jsonl").open("w", encoding="utf-8") as handle:
        for row in trials:
            handle.write(json.dumps(_jsonable(row), sort_keys=True, default=str) + "\n")
    log(f"done: {out}")
    return out


def _load_v1(paths: V2Paths, plan: FastPlan, repo: Path) -> ReleasedClassifier:
    release = resolve_release_dir(paths, plan.inputs.v1_release.release_dir)
    root = paths.v1_project_root or repo
    model = ReleasedClassifier.load(release, root / "configs" / "trusted_model_releases.json")
    if model.manifest["artifact_sha256"] != plan.inputs.v1_release.artifact_sha256:
        raise RuntimeError("v1 release artifact differs from the plan pin")
    if model.manifest["model_fingerprint"] != plan.inputs.v1_release.fingerprint:
        raise RuntimeError("v1 release fingerprint differs from the plan pin")
    return model


def _save_champion(
    paths: V2Paths,
    plan: FastPlan,
    plan_sha: str,
    commit: str,
    run_id: str,
    champ: Finalist,
    results: dict[str, Any],
) -> dict[str, Any]:
    fp = cm.fingerprint(champ.model)
    candidate_id = f"ml2fast_{plan_sha[:8]}_{fp[:12]}"
    directory = paths.writable(paths.output_root / plan.artifacts.model_root / candidate_id)
    if directory.exists():
        existing = json.loads((directory / "candidate_manifest.json").read_text("utf-8"))
        if existing["model_fingerprint"] != fp:
            raise RuntimeError("existing candidate directory has a different fingerprint")
        return {
            "candidate_id": candidate_id,
            "directory": str(directory),
            "reused": True,
            "model_fingerprint": fp,
            "artifact_sha256": existing["artifact_sha256"],
        }
    row = results["populations"][champ.population][champ.name]
    manifest = save_candidate(
        champ.model,
        directory,
        {
            "candidate_id": candidate_id,
            "run_id": run_id,
            "plan_sha256": plan_sha,
            "git_commit": commit,
            "population": champ.population,
            "candidate": champ.name,
            "feature_kind": champ.feature_kind,
            "classifier": champ.classifier_kind,
            "params": champ.params,
            "weighting": champ.weighting,
            "threshold": champ.threshold,
            "threshold_method": plan.threshold,
            "calibration": plan.calibration.get(
                "lr" if champ.classifier_kind == "lr" else champ.classifier_kind, "none"
            ),
            "training_data": {
                "audit_id": plan.inputs.audit_id,
                "build_id": plan.inputs.build_id,
                "train_membership_sha256": plan.inputs.memberships["train"].sha256,
                "train_records": champ.train_records,
                "train_positives": champ.train_positives,
            },
            "development_validation_summary": row["summary"],
            "allowed_use": "internal development research only; "
            "not for production or public claims",
        },
    )
    return {
        "candidate_id": candidate_id,
        "directory": str(directory),
        "reused": False,
        "model_fingerprint": manifest["model_fingerprint"],
        "artifact_sha256": manifest["artifact_sha256"],
        "artifact_bytes": manifest["artifact_bytes"],
    }


def _profile(frame: pd.DataFrame, aid: pd.DataFrame) -> dict[str, Any]:
    counts: dict[str, Any] = {}
    for (source, part), g in frame.groupby(["source_id", "part"]):
        counts[f"{source}/{part}"] = {
            "records": len(g),
            "positives": int(g["y"].sum()),
            "non_energy_positives": int((g["y"].astype(bool) & g["non_energy"]).sum()),
            "adaptation_only": int(g["adaptation_only"].sum()),
            "families": int(g["family"].nunique()),
            "groups": int(g["group"].nunique()),
            "french_share": round(french_share(g["text"].to_numpy()), 4),
            "positive_rate": round(float(g["y"].mean()), 4),
        }
    counts["aiddata/train"] = {
        "records": len(aid),
        "positives": int(aid["y"].sum()),
        "positive_rate": round(float(aid["y"].mean()), 4) if len(aid) else None,
    }
    return {"counts": counts, "cross_publisher_families": len(cross_publisher_families(frame))}


def _environment() -> dict[str, str]:
    import platform

    import scipy
    import sklearn

    return {
        "python": platform.python_version(),
        "scikit_learn": sklearn.__version__,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "pandas": pd.__version__,
    }
