"""``compassio-v2``: ML v2 external-data acquisition, dataset build and readiness reporting.

    uv run compassio-v2 paths
    uv run compassio-v2 verify-baseline
    uv run compassio-v2 acquire worldbank_projects|gcf_project_pages|iati_fcdo|iati_ec_intpa
    uv run compassio-v2 verify-retrievals
    uv run compassio-v2 build
    uv run compassio-v2 worksheets            # issue pilot + audit sheets (once per build)
    uv run compassio-v2 check-worksheets      # issued sheets intact, blind, empty, eligible
    uv run compassio-v2 validate-reviews      # validate returned sheets; agreement
    uv run compassio-v2 adjudication-sheet    # after A and B are complete
    uv run compassio-v2 freeze-labels         # seal adjudicated external-test labels

Reads v1 inputs only from $COMPASSIO_DATA_ROOT (read-only) and writes only under
$COMPASSIO_V2_OUTPUT_ROOT (default data/ml_v2). No command trains or evaluates a model.
"""

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from compassio_ml.cli.common import configure_stdout
from compassio_ml.external import gcf, iati, worldbank
from compassio_ml.external.fetch import FetchLimits, SafeFetcher
from compassio_ml.external.paths import MissingInputRootError, UnsafePathError, V2Paths
from compassio_ml.external.registry import (
    DEFAULT_REGISTRY,
    AccessStatus,
    RetrievalRun,
    latest_retrieval,
    load_registry,
    verify_retrieval,
)

ALLOWED_HOSTS: dict[str, frozenset[str]] = {
    worldbank.SOURCE_ID: frozenset({"search.worldbank.org", "www.worldbank.org"}),
    gcf.SOURCE_ID: frozenset({"www.greenclimate.fund", "data.greenclimate.fund"}),
    iati.FCDO.source_id: frozenset({"iatiregistry.org", "iati.fcdo.gov.uk"}),
    iati.EC_INTPA.source_id: frozenset(
        {"iatiregistry.org", "ec.europa.eu", "commission.europa.eu"}
    ),
}


def _paths() -> V2Paths:
    return V2Paths.from_env()


def _cmd_paths(_args: argparse.Namespace) -> int:
    p = _paths()
    print(
        json.dumps(
            {
                "repo_root": str(p.repo_root),
                "input_data_root (read-only)": str(p.input_data_root),
                "v1_project_root (read-only)": str(p.v1_project_root),
                "output_root (writable)": str(p.output_root),
                "external_raw (read-only when overridden)": str(p.external_raw),
            },
            indent=2,
        )
    )
    return 0


def _cmd_acquire(args: argparse.Namespace) -> int:
    paths = _paths()
    registry = load_registry(args.registry)
    source = registry.get(args.source)
    if source.access_status != AccessStatus.OPEN:
        print(
            f"{source.source_id}: access_status={source.access_status.value}. "
            f"{source.access_notes}",
            file=sys.stderr,
        )
        return 2
    fetcher = SafeFetcher(
        ALLOWED_HOSTS[source.source_id], FetchLimits(min_interval_s=args.min_interval)
    )
    run = RetrievalRun(paths, source, fetcher)
    run.start()
    acquirers: dict[str, Callable[[RetrievalRun], list[str]]] = {
        worldbank.SOURCE_ID: worldbank.acquire,
        gcf.SOURCE_ID: lambda r: gcf.acquire(r, limit=args.limit),
        iati.FCDO.source_id: lambda r: iati.acquire(r, iati.FCDO),
        iati.EC_INTPA.source_id: lambda r: iati.acquire(r, iati.EC_INTPA),
    }
    notes = acquirers[source.source_id](run)
    manifest = run.finish(notes)
    print(f"{source.source_id}: {len(run.files)} files saved, {len(run.failures)} failures")
    for note in notes:
        print(f"  {note}")
    for failure in run.failures[:20]:
        print(f"  FAILED {failure['url']}: {failure['error']}", file=sys.stderr)
    print(f"Manifest: {manifest}")
    return 0 if run.files else 1


def _cmd_verify_retrievals(_args: argparse.Namespace) -> int:
    paths = _paths()
    manifests = sorted(paths.external_raw.glob("*/*/retrieval_manifest.json"))
    if not manifests:
        print("No retrievals found", file=sys.stderr)
        return 1
    bad = 0
    for manifest in manifests:
        errors = verify_retrieval(manifest.parent)
        bad += len(errors)
        rel = "external_raw/" + manifest.parent.relative_to(paths.external_raw).as_posix()
        print(f"{rel}: {'OK' if not errors else f'{len(errors)} errors'}")
        for error in errors[:10]:
            print(f"  {error}", file=sys.stderr)
    return 1 if bad else 0


def _cmd_verify_baseline(args: argparse.Namespace) -> int:
    from compassio_ml.external.baseline import verify_baseline

    report = verify_baseline(_paths(), load_model=not args.skip_model_load)
    for check in report.checks:
        print(f"{'PASS' if check['ok'] else 'FAIL'}  {check['check']}: {check['detail']}")
    print("v1 baseline intact" if report.ok else "v1 BASELINE CHECK FAILED")
    return 0 if report.ok else 1


def _latest_build(paths: V2Paths, build_id: str | None) -> Path:
    if build_id:
        return paths.datasets / build_id
    builds = sorted(
        paths.datasets.glob("v2build_*/build_manifest.json"), key=lambda p: p.stat().st_mtime
    )
    if not builds:
        raise FileNotFoundError("No v2 build found; run `compassio-v2 build` first")
    return builds[-1].parent


def _registry_access(registry_path: Path) -> dict[str, str]:
    return {s.source_id: s.access_status.value for s in load_registry(registry_path).sources}


def _write_reports(paths: V2Paths, build_dir: Path, registry_path: Path) -> Path:
    import pandas as pd

    from compassio_ml.external import reports
    from compassio_ml.external.v1_inputs import load_v1_research
    from compassio_ml.external.weak_sectors import summary_targets, weak_sector_requirements

    build_id = build_dir.name
    sealed = paths.sealed / build_id
    # Counts only: reports never expose labels of the sealed pool (it has none) or texts.
    external = pd.concat(
        [
            pd.read_parquet(build_dir / "candidates.parquet"),
            pd.read_parquet(build_dir / "excluded_records.parquet"),
            pd.read_parquet(sealed / "candidate_pool.parquet"),
            pd.read_parquet(paths.restricted_reference / build_id / "records.parquet"),
        ],
        ignore_index=True,
    )
    membership = pd.read_parquet(build_dir / "partition_membership.parquet")
    links = pd.read_parquet(build_dir / "links.parquet")
    pilot_path = sealed / "pilot_v1.parquet"
    pilot = pd.read_parquet(pilot_path) if pilot_path.is_file() else None
    out = paths.writable(paths.reports / build_id)
    for source_id, frame in external.groupby("source_id"):
        reports.write_json(
            reports.inspect_source(frame, latest_retrieval(paths, str(source_id))),
            out / f"inspection_{source_id}.json",
        )
    reports.write_json(reports.timing_audit(external), out / "timing_audit.json")
    reports.write_json(reports.overlap_summary(links), out / "overlap_summary.json")
    verified = _human_verified_count(paths, build_id)
    coverage = reports.coverage_report(
        external,
        membership[membership["source_id"] == "aiddata"],
        links,
        pilot,
        verified,
        _registry_access(registry_path),
    )
    reports.write_json(coverage, out / "coverage_report.json")
    v1 = load_v1_research(paths)
    roles = membership[membership["source_id"] == "aiddata"][["candidate_id", "v2_partition"]]
    aiddata = v1.merge(roles, on="candidate_id", how="left")
    reports.write_json(
        {"targets": summary_targets(), "sectors": weak_sector_requirements(external, aiddata)},
        out / "weak_sector_requirements.json",
    )
    return out


def _human_verified_count(paths: V2Paths, build_id: str) -> int:
    lock = paths.sealed / build_id / "external_test_labels.lock.json"
    if not lock.is_file():
        return 0
    # Read aggregate freeze metadata only; reporting must never open sealed labels.
    return int(json.loads(lock.read_text(encoding="utf-8"))["verified_items"])


def _cmd_build(args: argparse.Namespace) -> int:
    from compassio_ml.external.dataset import build

    paths = _paths()
    result = build(paths)
    print(
        f"Build {result.build_id}: {len(result.external)} external records; "
        f"AidData records assigned: {len(result.aiddata)}"
    )
    print(result.external.groupby(["source_id", "v2_partition"]).size().to_string())
    print("AidData v2 roles:", result.aiddata["v2_partition"].value_counts().to_dict())
    if result.reproduced:
        print("Reproduced: rebuilt outputs are byte-identical to the existing build")
    out = _write_reports(paths, result.directory, args.registry)
    print(f"Outputs: {result.directory}")
    print(f"Sealed pool: {result.sealed_directory}")
    print(f"Reports: {out}")
    return 0


def _cmd_worksheets(args: argparse.Namespace) -> int:
    from compassio_ml.external.worksheets import create_worksheets

    paths = _paths()
    build_dir = _latest_build(paths, args.build_id)
    summary = create_worksheets(paths, build_dir)
    for line in summary:
        print(line)
    out = _write_reports(paths, build_dir, args.registry)
    print(f"Reports refreshed: {out}")
    return 0


def _cmd_validate_reviews(args: argparse.Namespace) -> int:
    from compassio_ml.external.worksheets import validate_reviews

    paths = _paths()
    build_dir = _latest_build(paths, args.build_id)
    report = validate_reviews(paths, build_dir)
    print(json.dumps(report, indent=2, default=str))
    return 1 if report.get("errors") else 0


def _cmd_check_worksheets(args: argparse.Namespace) -> int:
    from compassio_ml.external.worksheets import check_worksheets

    paths = _paths()
    report = check_worksheets(paths, _latest_build(paths, args.build_id))
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["ready_for_reviewers"] else 1


def _cmd_adjudication_sheet(args: argparse.Namespace) -> int:
    from compassio_ml.external.labeling import ReviewWorkflowError
    from compassio_ml.external.worksheets import create_adjudication_sheet

    paths = _paths()
    try:
        path = create_adjudication_sheet(paths, _latest_build(paths, args.build_id))
    except ReviewWorkflowError as exc:
        print(f"Not ready for adjudication: {exc}", file=sys.stderr)
        return 1
    print(f"Adjudication sheet: {path}")
    return 0


def _cmd_freeze_labels(args: argparse.Namespace) -> int:
    from compassio_ml.external.labeling import ReviewWorkflowError
    from compassio_ml.external.worksheets import freeze_pilot_labels

    paths = _paths()
    try:
        path = freeze_pilot_labels(paths, _latest_build(paths, args.build_id))
    except ReviewWorkflowError as exc:
        print(f"Cannot freeze: {exc}", file=sys.stderr)
        return 1
    print(f"Sealed labels: {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="compassio-v2", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("paths", help="show resolved input/output roots").set_defaults(func=_cmd_paths)
    p = sub.add_parser("acquire", help="retrieve one open external source")
    p.add_argument("source", choices=sorted(ALLOWED_HOSTS))
    p.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    p.add_argument("--min-interval", type=float, default=1.5)
    p.add_argument("--limit", type=int, default=None, help="GCF: max project pages")
    p.set_defaults(func=_cmd_acquire)
    sub.add_parser("verify-retrievals", help="re-hash all retrieved files").set_defaults(
        func=_cmd_verify_retrievals
    )
    p = sub.add_parser("verify-baseline", help="read-only check of all v1 artifacts")
    p.add_argument("--skip-model-load", action="store_true")
    p.set_defaults(func=_cmd_verify_baseline)
    p = sub.add_parser("build", help="build v2 candidate datasets, partitions and reports")
    p.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    p.set_defaults(func=_cmd_build)
    p = sub.add_parser("worksheets", help="sample the external-test pilot; write blind worksheets")
    p.add_argument("--build-id", default=None)
    p.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    p.set_defaults(func=_cmd_worksheets)
    p = sub.add_parser("validate-reviews", help="validate returned worksheets; agreement stats")
    p.add_argument("--build-id", default=None)
    p.set_defaults(func=_cmd_validate_reviews)
    for name, func, text in (
        ("check-worksheets", _cmd_check_worksheets, "check issued sheets are ready"),
        ("adjudication-sheet", _cmd_adjudication_sheet, "create the adjudication sheet"),
        ("freeze-labels", _cmd_freeze_labels, "seal adjudicated external-test labels"),
    ):
        p = sub.add_parser(name, help=text)
        p.add_argument("--build-id", default=None)
        p.set_defaults(func=func)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    configure_stdout()
    args = build_parser().parse_args(argv)
    try:
        result: int = args.func(args)
    except (UnsafePathError, MissingInputRootError) as exc:
        print(f"compassio-v2: {exc}", file=sys.stderr)
        return 2
    return result


if __name__ == "__main__":
    sys.exit(main())
