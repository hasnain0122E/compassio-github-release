"""``compassio-research``: build the cleaned research dataset and frozen split membership.

    uv run compassio-research build                       # validate sources, build, write
    uv run compassio-research build --check-reproducible  # build twice, compare checksums

No model is trained by this command.
"""

import argparse
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from compassio_ml.cli.common import add_data_dir, configure_stdout, layout_from
from compassio_ml.data.layout import MissingSourceDataError
from compassio_ml.research.pipeline import (
    DEFAULT_CONFIG,
    DEFAULT_REPORT_DIR,
    PipelineError,
    build,
    write_outputs,
)


def _cmd_build(args: argparse.Namespace) -> int:
    layout = layout_from(args)
    try:
        result = build(layout, args.config)
    except (PipelineError, MissingSourceDataError) as exc:
        print(f"compassio-research: {exc}", file=sys.stderr)
        return 2
    checksums = write_outputs(result, layout.processed, args.report_dir)
    s = result.summary
    print(f"Rows: {s['rows']}  eligibility: {s['eligibility']}")
    print(f"Climate-related: {s['climate_related']}  Pakistan: {s['pakistan']}")
    leak = s["leakage"]
    assert isinstance(leak, dict)
    print(
        f"Leakage groups: {leak['groups']} ({leak['multi_record_groups']} multi-record, "
        f"largest {leak['largest_group_size']}); disjointness violations: "
        f"{s['disjointness_violations']}"
    )
    print(f"Wrote {len(checksums)} files ({layout.processed}, {args.report_dir})")

    if args.check_reproducible:
        second = build(layout, args.config)
        with tempfile.TemporaryDirectory() as tmp:
            other = write_outputs(second, Path(tmp) / "processed", Path(tmp) / "reports")
        differing = sorted(n for n in checksums if checksums[n] != other.get(n))
        if differing:
            print(f"NOT reproducible: {', '.join(differing)}", file=sys.stderr)
            return 1
        print(f"Reproducible: {len(checksums)} output files byte-identical across two builds")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(prog="compassio-research", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build", help="Build the research table and split membership")
    add_data_dir(p)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    p.add_argument("--check-reproducible", action="store_true")
    p.set_defaults(func=_cmd_build)
    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
