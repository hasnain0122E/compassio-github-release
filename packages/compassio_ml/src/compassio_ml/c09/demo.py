"""Reproduce the complete C09 judge demonstration offline, from a clean C09 commit."""

import argparse
import json
from pathlib import Path

from compassio_ml.c09.benchmark import (
    REPO,
    benchmark,
    git,
    prepare_run,
    protocol,
    read,
    write,
)
from compassio_ml.c09.report import report
from compassio_ml.integrity.hashing import sha256_file


def run(source: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    prepare_run(source, output)
    benchmark(source, output, False)
    benchmark(source, output, True)
    report(source, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=REPO / "artifacts/c09/judge")
    parser.add_argument("--check-reproducible", action="store_true")
    parser.add_argument(
        "--existing", action="store_true", help="verify and show a completed local run"
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((REPO / "artifacts/c09").resolve()):
        raise ValueError("output must be under artifacts/c09 in the C09 worktree")
    if not args.existing:
        if git("status", "--porcelain"):
            raise ValueError("commit safe C09 changes before producing judge evidence")
        run(args.source_root.resolve(), output)
    if args.check_reproducible:
        other = output / "reproduce"
        run(args.source_root.resolve(), other)
        names = (
            "records.json",
            "split_manifest.json",
            "baseline.json",
            "guarded.json",
            "metrics.json",
            "baseline_queries.json",
            "guarded_queries.json",
            "baseline_trials.json",
            "guarded_trials.json",
        )
        identical = {
            name: sha256_file(output / name) == sha256_file(other / name) for name in names
        }
        write(output / "reproducibility.json", identical)
        if not all(identical.values()):
            raise ValueError("non-reproducible evidence")
    receipt = read(output / "run_receipt.json")
    for name, digest in receipt["hashes"].items():
        if sha256_file(output / name) != digest:
            raise ValueError(f"completed evidence checksum mismatch: {name}")
    threshold = protocol()["threshold"]
    rows = [r for r in read(output / "guarded.json") if r["split"] == "assessment"]
    successes = [
        r
        for r in rows
        if (r["clean_score"] >= threshold) != (r["perturbed_score"] >= threshold)
        and (r["clean_score"] >= threshold) == (r["guarded_score"] >= threshold)
    ]
    failures = [
        r for r in rows if (r["clean_score"] >= threshold) != (r["guarded_score"] >= threshold)
    ]
    for name, cases in (
        ("measured_prevented_flip", successes),
        ("measured_residual_failure", failures),
    ):
        if cases:
            example = max(cases, key=lambda r: abs(r["perturbed_score"] - r["clean_score"]))
            print(json.dumps({"example_kind": name, **example}, indent=2, ensure_ascii=True))
    print(
        json.dumps(
            {
                "scorecard": str(output / "scorecard.html"),
                "metrics": str(output / "metrics.json"),
                "reproducible": read(output / "reproducibility.json")
                if (output / "reproducibility.json").exists()
                else "not rerun",
            }
        )
    )


if __name__ == "__main__":
    main()
