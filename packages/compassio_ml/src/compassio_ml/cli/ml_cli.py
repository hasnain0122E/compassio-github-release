"""``compassio-ml``: frozen-input checks, validation-stage benchmark, artifact smoke inference.

    uv run compassio-ml verify-frozen
    uv run compassio-ml benchmark --protocol primary --suite full
    uv run compassio-ml benchmark --protocol primary --suite fast --check-reproducible
    uv run compassio-ml predict --model-dir <run>/model --title "..." --description "..."

No command evaluates a frozen test partition.
"""

import argparse
import hashlib
import json
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from compassio_ml.cli.common import configure_stdout
from compassio_ml.modeling.benchmark import Benchmark
from compassio_ml.modeling.config import load_benchmark_config
from compassio_ml.modeling.frozen import (
    PROTOCOL_COLUMN,
    FrozenDataError,
    FrozenPaths,
    verify_frozen,
    write_lock,
)
from compassio_ml.modeling.inference import ClimateRelevanceClassifier
from compassio_ml.modeling.tracking import RunExistsError

DEFAULT_CONFIG = Path("configs") / "ml_benchmark_v1.yaml"
DEFAULT_OUT = Path("experiments") / "benchmarks"
REPRODUCIBLE_FILES = (
    "metrics_deterministic.json",
    "validation_slices.csv",
    "reliability.csv",
    "winner_validation_predictions.parquet",
    "model/model.joblib",
)


def _paths(config_path: Path) -> FrozenPaths:
    cfg = load_benchmark_config(config_path)
    return FrozenPaths(
        cfg.data.table, cfg.data.membership, cfg.data.split_config, cfg.data.split_lock
    )


def _cmd_verify(args: argparse.Namespace) -> int:
    try:
        report = verify_frozen(_paths(args.config))
    except FrozenDataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if report.ok:
        counts = report.lock["split_counts"]
        print(f"Frozen inputs match lock. Split counts: {json.dumps(counts, sort_keys=True)}")
        return 0
    for error in report.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1


def _cmd_write_lock(args: argparse.Namespace) -> int:
    paths = _paths(args.config)
    if paths.lock.exists() and not args.force:
        print(
            f"{paths.lock} exists; the lock is written once per split version (use --force only "
            "when intentionally freezing a NEW split version)",
            file=sys.stderr,
        )
        return 1
    lock = write_lock(paths)
    print(f"Wrote {paths.lock}: {json.dumps(lock['split_counts'], sort_keys=True)}")
    return 0


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cmd_benchmark(args: argparse.Namespace) -> int:
    config = load_benchmark_config(args.config)
    repo = Path.cwd()
    bench = Benchmark(
        config, args.protocol, args.suite, repo, args.out, seed=args.seed, overwrite=args.overwrite
    )
    try:
        result = bench.run()
    except (FrozenDataError, RunExistsError) as exc:
        print(f"compassio-ml: {exc}", file=sys.stderr)
        return 2
    print(
        f"Run {result.run_id}: train {len(result.train)} ({result.train.positives} pos), "
        f"validation {len(result.validation)} ({result.validation.positives} pos)"
    )
    print(f"{'rank':>4} {'val AP':>7} {'AP 95% CI':>15} {'F1@sel':>7} {'P':>6} {'R':>6}  key")
    for row in result.ranking:
        lo, hi = row["val_average_precision_ci_low"], row["val_average_precision_ci_high"]
        ci = f"[{lo:.3f},{hi:.3f}]" if lo is not None else "-"
        ap = row["val_average_precision"]
        print(
            f"{row['rank_by_val_ap']:>4} {ap:7.4f} {ci:>15} {row['val_f1@selected']:7.4f} "
            f"{row['val_precision@selected']:6.3f} {row['val_recall@selected']:6.3f}  {row['key']}"
            + ("  <= provisional validation winner" if row["is_provisional_winner"] else "")
        )
    print(f"Outputs: {result.run_dir}")

    if args.check_reproducible:
        with tempfile.TemporaryDirectory() as tmp:
            again = Benchmark(
                config, args.protocol, args.suite, repo, Path(tmp), seed=args.seed
            ).run()
            mismatched = [
                n
                for n in REPRODUCIBLE_FILES
                if _digest(result.run_dir / n) != _digest(again.run_dir / n)
            ]
        if mismatched:
            print(f"NOT reproducible: {', '.join(mismatched)}", file=sys.stderr)
            return 1
        print(f"Reproducible: {len(REPRODUCIBLE_FILES)} outputs byte-identical across two runs")
    return 0


def _cmd_error_analysis(args: argparse.Namespace) -> int:
    from compassio_ml.modeling.error_analysis import analyse, load_validation_predictions, top_terms
    from compassio_ml.modeling.inference import ClimateRelevanceClassifier

    config = load_benchmark_config(args.config)
    frame = load_validation_predictions(
        args.run_dir, config.data.table, config.data.membership, args.protocol
    )
    result = analyse(frame)
    out = args.run_dir / "error_analysis"
    out.mkdir(exist_ok=True)
    keep = [
        "record_id",
        "outcome",
        "score",
        "sector_name",
        "flow_type",
        "commitment_year",
        "recipient_iso3",
        "rio_overall",
        "rio_mitigation",
        "rio_adaptation",
        "keyword_hits",
        "description_chars",
        "title_chars",
        "retrospective_text_warning",
        "error_tags",
    ]
    errors = result.records[result.records["outcome"].isin(["FN", "FP"])][keep]
    errors.sort_values(["outcome", "record_id"]).to_csv(
        out / "validation_errors.csv", index=False, lineterminator="\n"
    )
    result.tag_summary.to_csv(out / "error_tag_summary.csv", index=False, lineterminator="\n")
    result.sector_summary.to_csv(
        out / "positive_recall_by_sector.csv", index=False, lineterminator="\n"
    )
    model = ClimateRelevanceClassifier.load(args.run_dir / "model")  # checksum-verified
    top_terms(model._model).to_csv(out / "top_terms.csv", index=False, lineterminator="\n")
    counts = result.records["outcome"].value_counts().to_dict()
    print(f"Validation outcomes: {counts}. Wrote {out}")
    return 0


def _final_paths(args: argparse.Namespace) -> FrozenPaths:
    cfg = load_benchmark_config(DEFAULT_CONFIG)
    return FrozenPaths(
        cfg.data.table, cfg.data.membership, cfg.data.split_config, cfg.data.split_lock
    )


def _cmd_final_dev(args: argparse.Namespace) -> int:
    from compassio_ml.modeling.final_eval import SelectedModel, development_report

    spec = SelectedModel.model_validate_json(args.model_spec.read_text(encoding="utf-8"))
    out: dict[str, object] = {}
    for protocol in args.protocols:
        report = development_report(spec, protocol, _final_paths(args), args.seed)
        report.pop("validation_scores")
        report.pop("validation_record_ids")
        out[protocol] = report
        print(json.dumps({protocol: report}, indent=2, default=str))
    if args.out:
        args.out.write_text(
            json.dumps(out, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
        )
    return 0


def _cmd_final_evaluate(args: argparse.Namespace) -> int:
    from compassio_ml.modeling.final_eval import (
        OneShotViolationError,
        PlanIntegrityError,
        final_evaluate,
    )

    try:
        result = final_evaluate(
            args.protocol, args.plan, args.plan_sha256, Path.cwd(), args.out, _final_paths(args)
        )
    except (PlanIntegrityError, OneShotViolationError, FrozenDataError) as exc:
        print(f"compassio-ml: refused: {exc}", file=sys.stderr)
        return 2
    m = result.results["model"]
    print(
        f"{args.protocol}: test {m['records']} records "
        f"({m['positives']} pos, {m['groups']} groups) "
        f"AP {m['average_precision']:.4f} CI {m['average_precision_ci95']} "
        f"F1 {m['f1']:.4f} P {m['precision']:.4f} R {m['recall']:.4f} "
        f"TP {m['tp']} FP {m['fp']} FN {m['fn']} TN {m['tn']}"
    )
    print(f"Outputs (read-only): {result.out_dir}")
    return 0


def _cmd_final_error_analysis(args: argparse.Namespace) -> int:
    from compassio_ml.modeling.error_analysis import analyse, load_final_test_predictions

    config = load_benchmark_config(args.config)
    final_dir = args.final_root / args.protocol
    result = analyse(
        load_final_test_predictions(
            final_dir, config.data.table, config.data.membership, args.protocol
        )
    )
    out = args.out / args.protocol
    out.mkdir(parents=True, exist_ok=True)
    keep = [
        "record_id",
        "outcome",
        "score",
        "sector_name",
        "flow_type",
        "commitment_year",
        "recipient_iso3",
        "rio_overall",
        "rio_mitigation",
        "rio_adaptation",
        "keyword_hits",
        "description_chars",
        "title_chars",
        "retrospective_text_warning",
        "error_tags",
    ]
    errors = result.records[result.records["outcome"].isin(["FN", "FP"])][keep]
    errors.sort_values(["outcome", "record_id"]).to_csv(out / "test_errors.csv", index=False)
    result.tag_summary.to_csv(out / "error_tag_summary.csv", index=False)
    result.sector_summary.to_csv(out / "positive_recall_by_sector.csv", index=False)
    print(f"{args.protocol}: {result.records['outcome'].value_counts().to_dict()} -> {out}")
    return 0


def _cmd_release(args: argparse.Namespace) -> int:
    from compassio_ml.modeling.final_eval import load_plan
    from compassio_ml.modeling.release import ReleaseError, build_release, evaluate_acceptance

    plan = load_plan(args.plan, args.plan_sha256)
    primary = json.loads((args.final_root / "primary" / "results.json").read_text(encoding="utf-8"))
    acceptance = evaluate_acceptance(primary, plan.acceptance_criteria)
    try:
        manifest = build_release(args.final_root, plan, args.plan_sha256, args.out, acceptance)
    except ReleaseError as exc:
        print(f"compassio-ml: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                k: manifest[k]
                for k in ("model_version", "release_status", "artifact_sha256", "model_fingerprint")
            },
            indent=2,
        )
    )
    print(json.dumps(acceptance, indent=2, default=str))
    return 0


def _cmd_release_predict(args: argparse.Namespace) -> int:
    from compassio_ml.modeling.release import EmptyInputError, ReleasedClassifier, ReleaseError

    try:
        model = ReleasedClassifier.load(args.release_dir, args.trusted)
        prediction = model.predict(args.title, args.description)
    except (EmptyInputError, ReleaseError) as exc:
        print(f"compassio-ml: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({k: getattr(prediction, k) for k in prediction.__slots__}, indent=2))
    return 0


def _cmd_predict(args: argparse.Namespace) -> int:
    model = ClimateRelevanceClassifier.load(args.model_dir)
    prediction = model.predict(args.title, args.description)
    print(
        json.dumps(
            prediction.__dict__
            if hasattr(prediction, "__dict__")
            else {k: getattr(prediction, k) for k in prediction.__slots__},
            indent=2,
            default=str,
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(prog="compassio-ml", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("verify-frozen", help="Check dataset/split checksums against the lock")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.set_defaults(func=_cmd_verify)

    p = sub.add_parser("write-lock", help="Freeze the current split version (once per version)")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=_cmd_write_lock)

    p = sub.add_parser("benchmark", help="Train on train, evaluate on validation (never test)")
    p.add_argument("--protocol", choices=sorted(PROTOCOL_COLUMN), default="primary")
    p.add_argument("--suite", default="fast")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--check-reproducible", action="store_true")
    p.set_defaults(func=_cmd_benchmark)

    p = sub.add_parser("error-analysis", help="Validation-only error taxonomy for a run's winner")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--protocol", choices=sorted(PROTOCOL_COLUMN), default="primary")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.set_defaults(func=_cmd_error_analysis)

    p = sub.add_parser("final-dev", help="Pre-registration: train-OOF thresholds, validation only")
    p.add_argument("--model-spec", type=Path, required=True)
    p.add_argument(
        "--protocols", nargs="+", default=["primary", "chronological", "pakistan_holdout"]
    )
    p.add_argument("--seed", type=int, default=20260109)
    p.add_argument("--out", type=Path, default=None)
    p.set_defaults(func=_cmd_final_dev)

    p = sub.add_parser("final-evaluate", help="ONE-SHOT frozen test evaluation for one protocol")
    p.add_argument("--protocol", choices=sorted(PROTOCOL_COLUMN), required=True)
    p.add_argument("--plan", type=Path, default=Path("configs") / "final_evaluation_v1.yaml")
    p.add_argument("--plan-sha256", required=True)
    p.add_argument("--out", type=Path, default=Path("experiments") / "final_evaluation_v1")
    p.set_defaults(func=_cmd_final_evaluate)

    p = sub.add_parser("final-error-analysis", help="POST-HOC error taxonomy of final test errors")
    p.add_argument("--protocol", choices=sorted(PROTOCOL_COLUMN), required=True)
    p.add_argument("--final-root", type=Path, default=Path("experiments") / "final_evaluation_v1")
    p.add_argument("--out", type=Path, default=Path("experiments") / "final_error_analysis_v1")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.set_defaults(func=_cmd_final_error_analysis)

    p = sub.add_parser("release", help="Build the internal MVP release from final results")
    p.add_argument("--final-root", type=Path, default=Path("experiments") / "final_evaluation_v1")
    p.add_argument("--plan", type=Path, default=Path("configs") / "final_evaluation_v1.yaml")
    p.add_argument("--plan-sha256", required=True)
    p.add_argument("--out", type=Path, default=Path("models") / "compassio_ccrc_v1")
    p.set_defaults(func=_cmd_release)

    p = sub.add_parser("release-predict", help="Score one title/description with a trusted release")
    p.add_argument("--release-dir", type=Path, default=Path("models") / "compassio_ccrc_v1")
    p.add_argument("--trusted", type=Path, default=Path("configs") / "trusted_model_releases.json")
    p.add_argument("--title", default="")
    p.add_argument("--description", default="")
    p.set_defaults(func=_cmd_release_predict)

    p = sub.add_parser("predict", help="Smoke-test a saved artifact on one title/description")
    p.add_argument("--model-dir", type=Path, required=True)
    p.add_argument("--title", default="")
    p.add_argument("--description", default="")
    p.set_defaults(func=_cmd_predict)

    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
