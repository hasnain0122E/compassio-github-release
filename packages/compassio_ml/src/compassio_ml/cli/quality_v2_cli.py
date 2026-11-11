"""Development-only donor audit and optional blinded AI file exchange. Never trains a model."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from compassio_ml.cli.common import configure_stdout
from compassio_ml.external.paths import V2Paths
from compassio_ml.quality_v2.assessments import (
    fixture_demo,
    import_assessments,
    prepare_assessments,
)
from compassio_ml.quality_v2.audit import audit_dataset, dump_json


def main(argv: Sequence[str] | None = None) -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("audit")
    p.add_argument("--build-id", required=True)
    sub.add_parser("assessment-demo")
    p = sub.add_parser("prepare-assessments")
    p.add_argument("--audit-id", required=True)
    p.add_argument(
        "--permissions", type=Path, default=Path("configs/ai_assessment_permissions_v2.json")
    )
    p.add_argument("--limit", type=int, default=100)
    p = sub.add_parser("import-assessments")
    p.add_argument("--pool-id", required=True)
    p.add_argument("--responses-a", required=True, type=Path)
    p.add_argument("--responses-b", required=True, type=Path)
    args = parser.parse_args(argv)
    paths = V2Paths.from_env()
    try:
        if args.command == "audit":
            out = audit_dataset(paths, args.build_id)
            report = json.loads((out / "quality_report.json").read_text("utf-8"))
            print(
                json.dumps(
                    {
                        "output": str(out),
                        "counts": report["counts"],
                        "flags": report["flag_counts"],
                        "readiness": report["readiness"],
                    },
                    indent=2,
                )
            )
        elif args.command == "assessment-demo":
            out = paths.writable(
                paths.output_root / "automated_assessments" / "ARTIFICIAL_fixture_demo"
            )
            out.mkdir(parents=True, exist_ok=True)
            dump_json(out / "demo.json", fixture_demo())
            print(f"ARTIFICIAL fixture demonstration only; no provider calls or real labels: {out}")
        elif args.command == "prepare-assessments":
            print(prepare_assessments(paths, args.audit_id, args.permissions, args.limit))
        else:
            print(import_assessments(paths, args.pool_id, args.responses_a, args.responses_b))
    except (ValueError, PermissionError, FileNotFoundError, FileExistsError) as exc:
        print(f"Quality workflow refused: {exc}")
        return 2
    return 0
