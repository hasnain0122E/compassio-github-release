"""``compassio-data``: source inventory and full read-only data audit.

uv run compassio-data inventory              # hash + format-check data/raw
uv run compassio-data audit                  # inventory + per-source inspection reports
uv run compassio-data audit --check-reproducible
"""

import argparse
import hashlib
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from compassio_ml.audit.reports import (
    DEFAULT_ARTIFACT_DIR,
    DETERMINISTIC_FILES,
    run_audit,
    write_audit,
    write_inventory,
)
from compassio_ml.cli.common import add_data_dir, configure_stdout, data_root_label, layout_from
from compassio_ml.data.inventory import build_inventory
from compassio_ml.data.layout import MissingSourceDataError


def _digest_dir(directory: Path) -> dict[str, str]:
    return {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in DETERMINISTIC_FILES
    }


def _cmd_inventory(args: argparse.Namespace) -> int:
    layout = layout_from(args)
    inventory = build_inventory(layout)
    path = write_inventory(inventory, args.out, data_root_label(layout))
    for record in inventory.records:
        status = "OK " if record.error is None else "ERR"
        fmt = record.file_format.value if record.file_format else "-"
        print(f"{status} {record.sha256[:12]} {record.size_bytes:>11,} {fmt:5} {record.relpath}")
        if record.error:
            print(f"      {record.error}")
    print(f"\n{len(inventory.records)} files, {inventory.distinct_file_count} distinct by SHA-256")
    for group in inventory.duplicate_hash_groups:
        print(f"Identical content: {', '.join(group)}")
    if inventory.missing_critical_sources:
        print(f"MISSING critical sources: {', '.join(inventory.missing_critical_sources)}")
    if inventory.missing_optional_sources:
        print(f"Missing optional sources: {', '.join(inventory.missing_optional_sources)}")
    print(f"Wrote {path}")
    return 1 if inventory.has_errors else 0


def _cmd_audit(args: argparse.Namespace) -> int:
    layout = layout_from(args)
    label = data_root_label(layout)
    try:
        run = run_audit(layout)
    except MissingSourceDataError as exc:
        print(f"compassio-data: {exc}", file=sys.stderr)
        return 2
    paths = write_audit(run, args.out, label)
    for a in run.sources:
        print(
            f"{a.source_id:26} {a.primary_record_count:>7} primary records, {len(a.issues)} issues"
        )
    print(f"Wrote {len(paths)} files to {args.out}")

    if args.check_reproducible:
        with tempfile.TemporaryDirectory() as tmp:
            second = Path(tmp)
            write_audit(run_audit(layout), second, label)
            first_digest, second_digest = _digest_dir(args.out), _digest_dir(second)
        differing = sorted(n for n in first_digest if first_digest[n] != second_digest[n])
        if differing:
            print(f"NOT reproducible: {', '.join(differing)}", file=sys.stderr)
            return 1
        print(f"Reproducible: {len(first_digest)} deterministic files identical across two runs")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(prog="compassio-data", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func, help_text in (
        ("inventory", _cmd_inventory, "Hash and format-check every raw file"),
        ("audit", _cmd_audit, "Run the full read-only audit and write reports"),
    ):
        p = sub.add_parser(name, help=help_text)
        add_data_dir(p)
        p.add_argument("--out", type=Path, default=DEFAULT_ARTIFACT_DIR, help="Artifact directory")
        p.set_defaults(func=func)
        if name == "audit":
            p.add_argument(
                "--check-reproducible",
                action="store_true",
                help="Run the audit twice and compare deterministic outputs",
            )
    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
