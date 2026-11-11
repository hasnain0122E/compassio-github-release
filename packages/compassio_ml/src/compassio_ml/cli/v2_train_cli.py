"""`compassio-v2-train`: frozen fast-track benchmark, reproducibility check, guarded predictor.

    uv run compassio-v2-train plan-hash
    uv run compassio-v2-train benchmark --plan-sha256 <sha>
    uv run compassio-v2-train reproduce --plan-sha256 <sha> --run-dir <dir>
    uv run compassio-v2-train predict --candidate-dir <dir> --title ... --description ...

Development only: reads eligible TRAIN/VALID donor records through the sanctioned loader;
never sealed, external-test or consumed-v1-test data. Outputs stay under data/ml_v2/.
"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from compassio_ml.cli.common import configure_stdout
from compassio_ml.external.paths import V2Paths
from compassio_ml.model_v2.plan import DEFAULT_PLAN, PlanError, load_plan, plan_sha256


def _cmd_plan_hash(args: argparse.Namespace) -> int:
    print(plan_sha256(args.plan))
    return 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    from compassio_ml.model_v2.benchmark import run_benchmark

    plan = load_plan(args.plan, args.plan_sha256)
    out = run_benchmark(V2Paths.from_env(), plan, args.plan_sha256, Path.cwd())
    print(f"Outputs: {out}")
    return 0


def _cmd_reproduce(args: argparse.Namespace) -> int:
    from compassio_ml.model_v2.reproduce import reproduce_champion

    plan = load_plan(args.plan, args.plan_sha256)
    report = reproduce_champion(V2Paths.from_env(), plan, args.run_dir)
    print(json.dumps(report, indent=2))
    ok = report["fingerprint_identical"] and report["threshold_identical"]
    return 0 if ok and report["max_abs_valid_score_difference"] == 0.0 else 1


def _cmd_escalate(args: argparse.Namespace) -> int:
    from compassio_ml.model_v2.escalation import load_addendum, run_escalation

    plan = load_plan(args.plan, args.plan_sha256)
    addendum = load_addendum(args.addendum, args.addendum_sha256)
    if addendum.base_plan_sha256 != args.plan_sha256:
        raise PlanError("addendum was written for a different base plan")
    out = run_escalation(V2Paths.from_env(), plan, addendum, args.addendum_sha256, Path.cwd())
    print(f"Outputs: {out}")
    return 0


def _cmd_export_aggregates(args: argparse.Namespace) -> int:
    from compassio_ml.model_v2.aggregates import export_aggregates

    payload = export_aggregates(args.run_dir)
    text = json.dumps(payload, indent=2, sort_keys=True) + chr(10)
    args.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {args.out}")
    return 0


def _cmd_predict(args: argparse.Namespace) -> int:
    from compassio_ml.model_v2.artifact import CandidateArtifactError, ExperimentalClassifier

    paths = V2Paths.from_env()
    root = paths.v1_project_root or paths.repo_root
    try:
        model = ExperimentalClassifier.load(
            args.candidate_dir, root / "configs" / "trusted_model_releases.json"
        )
        prediction = model.predict(args.title, args.description)
    except (CandidateArtifactError, ValueError) as exc:
        print(f"compassio-v2-train: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(asdict(prediction), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(prog="compassio-v2-train", description=__doc__.splitlines()[0])
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan-hash").set_defaults(func=_cmd_plan_hash)
    p = sub.add_parser("benchmark")
    p.add_argument("--plan-sha256", required=True)
    p.set_defaults(func=_cmd_benchmark)
    p = sub.add_parser("reproduce")
    p.add_argument("--plan-sha256", required=True)
    p.add_argument("--run-dir", type=Path, required=True)
    p.set_defaults(func=_cmd_reproduce)
    p = sub.add_parser("escalate", help="Section 7: one frozen encoder (needs --all-extras)")
    p.add_argument("--plan-sha256", required=True)
    p.add_argument("--addendum", type=Path, default=Path("configs") / "ml_v2_fast_escalation.yaml")
    p.add_argument("--addendum-sha256", required=True)
    p.set_defaults(func=_cmd_escalate)
    p = sub.add_parser("export-aggregates", help="Aggregate-only v1 vs v2 comparison JSON")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument(
        "--out", type=Path, default=Path("docs/research/model_v2/fast_benchmark_aggregates.json")
    )
    p.set_defaults(func=_cmd_export_aggregates)
    p = sub.add_parser("predict")
    p.add_argument("--candidate-dir", type=Path, required=True)
    p.add_argument("--title", default="")
    p.add_argument("--description", default="")
    p.set_defaults(func=_cmd_predict)
    args = parser.parse_args(argv)
    try:
        result: int = args.func(args)
    except PlanError as exc:
        print(f"compassio-v2-train: {exc}", file=sys.stderr)
        return 2
    return result


if __name__ == "__main__":
    raise SystemExit(main())
