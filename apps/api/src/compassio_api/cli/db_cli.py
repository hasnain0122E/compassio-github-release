"""`compassio-db`: migrations, idempotent source ingestion, status and integrity verification.

Run from the repository root::

    uv run compassio-db migrate
    uv run compassio-db ingest --source all          # or research_paper | gcf_projects | ...
    uv run compassio-db status
    uv run compassio-db verify [--report artifacts/db/integrity_report.json]
"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from compassio_api.core.config import Settings
from compassio_api.db import migrate
from compassio_api.db.models import ImportRun
from compassio_api.db.session import create_read_engine, create_write_engine
from compassio_ml.cli.common import add_data_dir, configure_stdout, layout_from

SOURCE_CHOICES = (
    "research_paper",
    "gcf_projects",
    "climate_funds_update",
    "adb_pakistan",
    "gcf_readiness",
    "gcf_countries",
    "climate_project_explorer",
    "gcf_historical",
    "gcf_api_projects",
    "core",
    "all",
)


def _settings(args: argparse.Namespace) -> Settings:
    if args.database_url:
        return Settings(database_url=args.database_url)
    return Settings()


def _require_migrated(url: str) -> None:
    engine = create_read_engine(url)
    try:
        revision = migrate.current_revision(engine)
    finally:
        engine.dispose()
    if revision is None:
        raise SystemExit("compassio-db: database not migrated; run `uv run compassio-db migrate`")


def _cmd_migrate(args: argparse.Namespace) -> int:
    url = _settings(args).database_url
    migrate.upgrade(url, "head")
    engine = create_write_engine(url)
    print(f"migrated to revision {migrate.current_revision(engine)}")
    engine.dispose()
    return 0


def _cmd_ingest(args: argparse.Namespace) -> int:
    from compassio_api.ingest.runner import ALL_ORDER, ORDER, IngestInputError, ingest
    from compassio_api.staging.registry import load_registry

    url = _settings(args).database_url
    _require_migrated(url)
    groups = {"all": list(ALL_ORDER), "core": list(ORDER)}
    keys = groups.get(args.source, [args.source])
    layout = layout_from(args)
    if args.source == "all" and load_registry(layout.root).latest("gcf_api_projects") is None:
        keys.remove("gcf_api_projects")
        print(
            "compassio-db: no gcf_api_projects snapshot registered; skipping the GCF API "
            "enrichment (run `uv run compassio-db fetch --source gcf_api_projects`).",
            file=sys.stderr,
        )
    engine = create_write_engine(url)
    try:
        report = ingest(engine, layout, keys, Path.cwd())
    except IngestInputError as exc:
        print(f"compassio-db: refused: {exc}", file=sys.stderr)
        return 2
    finally:
        engine.dispose()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    from compassio_api.services.integrity import table_counts

    url = _settings(args).database_url
    _require_migrated(url)
    engine = create_read_engine(url)
    with Session(engine) as session:
        runs = session.scalars(select(ImportRun).order_by(ImportRun.id.desc()).limit(12)).all()
        out = {
            "counts": table_counts(session),
            "recent_import_runs": [
                {
                    "id": r.id,
                    "source": r.source_key,
                    "status": r.status,
                    "started_at": r.started_at.isoformat(),
                    "inserted": r.inserted,
                    "updated": r.updated,
                    "unchanged": r.unchanged,
                    "rejected": r.rejected,
                    "removed": r.removed,
                    "message": r.message,
                }
                for r in runs
            ],
        }
    engine.dispose()
    print(json.dumps(out, indent=2))
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    from compassio_api.services.integrity import verify_database

    url = _settings(args).database_url
    _require_migrated(url)
    engine = create_read_engine(url)
    with Session(engine) as session:
        report = verify_database(session)
    engine.dispose()
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["ok"] else 1


def _cmd_fetch(args: argparse.Namespace) -> int:
    from compassio_api.staging.fetch import fetch_snapshot

    layout = layout_from(args)
    entry = fetch_snapshot(layout.root, args.source)
    print(json.dumps(entry.model_dump(mode="json"), indent=2))
    return 0


def _cmd_registry(args: argparse.Namespace) -> int:
    from compassio_api.staging.registry import load_registry, validate_registry

    layout = layout_from(args)
    report = validate_registry(layout.root)
    registry = load_registry(layout.root)
    out = {
        "ok": report.ok,
        "snapshots_checked": report.checked,
        "errors": report.errors,
        "snapshots": [
            {
                "backend_source_id": s.backend_source_id,
                "snapshot_id": s.snapshot_id,
                "sha256": s.sha256,
                "size_bytes": s.size_bytes,
                "rights_status": s.rights_status,
                "ingestion_status": s.ingestion_status,
            }
            for s in registry.snapshots
        ],
    }
    print(json.dumps(out, indent=2))
    return 0 if report.ok else 1


def _cmd_report(args: argparse.Namespace) -> int:
    from compassio_api.services.reports import REPORTS

    url = _settings(args).database_url
    _require_migrated(url)
    engine = create_read_engine(url)
    with Session(engine) as session:
        report = REPORTS[args.name](session)
    engine.dispose()
    text = json.dumps(report, indent=2, sort_keys=True, default=str)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + chr(10), encoding="utf-8")
    print(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="compassio-db", description=__doc__.splitlines()[0])
    parser.add_argument(
        "--database-url", default=None, help="Override COMPASSIO_DATABASE_URL for this command"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("migrate", help="Create/upgrade the schema (alembic upgrade head)")
    p.set_defaults(func=_cmd_migrate)
    p = sub.add_parser("init", help="Alias of migrate")
    p.set_defaults(func=_cmd_migrate)

    p = sub.add_parser("ingest", help="Idempotently import a registered source")
    p.add_argument("--source", choices=SOURCE_CHOICES, required=True)
    add_data_dir(p)
    p.set_defaults(func=_cmd_ingest)

    p = sub.add_parser("fetch", help="Download one NEW backend source snapshot (never overwrites)")
    p.add_argument("--source", choices=("gcf_api_projects",), required=True)
    add_data_dir(p)
    p.set_defaults(func=_cmd_fetch)

    p = sub.add_parser("registry", help="Validate the backend source registry (hashes, strays)")
    add_data_dir(p)
    p.set_defaults(func=_cmd_registry)

    p = sub.add_parser("report", help="Coverage / reconciliation reports from the database")
    p.add_argument("name", choices=("gcf-enrichment", "reconciliation", "historical-comparison"))
    p.add_argument("--out", type=Path, default=None, help="Also write the JSON report here")
    p.set_defaults(func=_cmd_report)

    p = sub.add_parser("status", help="Row counts and recent import runs")
    p.set_defaults(func=_cmd_status)

    p = sub.add_parser("verify", help="Database integrity checks against the audited sources")
    p.add_argument("--report", type=Path, default=None, help="Also write the JSON report here")
    p.set_defaults(func=_cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_stdout()
    args = build_parser().parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
