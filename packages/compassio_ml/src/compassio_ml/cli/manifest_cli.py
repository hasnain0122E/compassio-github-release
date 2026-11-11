"""``compassio-manifest``: write and validate the committed source manifest.

uv run compassio-manifest write      # (re)build data/manifests/source_manifest.json
uv run compassio-manifest validate   # schema + hashes + coverage of data/raw
"""

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, datetime

from compassio_ml.audit.reports import run_audit
from compassio_ml.cli.common import add_data_dir, configure_stdout, layout_from
from compassio_ml.data.inventory import build_inventory
from compassio_ml.data.layout import MissingSourceDataError
from compassio_ml.data.manifest_io import build_manifest, validate_manifest, write_manifest


def _cmd_write(args: argparse.Namespace) -> int:
    layout = layout_from(args)
    try:
        run = run_audit(layout)
    except MissingSourceDataError as exc:
        print(f"compassio-manifest: {exc}", file=sys.stderr)
        return 2
    counts = {a.source_id: a.primary_record_count for a in run.sources}
    manifest = build_manifest(run.inventory, counts, datetime.now(UTC).replace(microsecond=0))
    path = write_manifest(manifest, layout)
    print(f"Wrote {len(manifest.entries)} entries to {path}")
    refused = [r for r in run.inventory.records if r.error]
    for record in refused:
        print(f"NOT registered (refused): {record.relpath}: {record.error}", file=sys.stderr)
    return 1 if refused else 0


def _cmd_validate(args: argparse.Namespace) -> int:
    layout = layout_from(args)
    inventory = build_inventory(layout) if layout.raw.is_dir() else None
    report = validate_manifest(layout, inventory)
    if report.ok:
        print(f"Manifest valid: {report.checked_entries} entries; hashes and sizes match data/raw")
        return 0
    for error in report.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(prog="compassio-manifest", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func in (("write", _cmd_write), ("validate", _cmd_validate)):
        p = sub.add_parser(name)
        add_data_dir(p)
        p.set_defaults(func=func)
    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
