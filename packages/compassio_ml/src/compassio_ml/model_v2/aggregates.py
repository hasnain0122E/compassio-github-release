"""Export fixed, aggregate-only comparison figures from a completed fast-track run.

The output contains no record IDs, texts or scores: only population counts, metrics, intervals
and paired differences, plus the hashes of the run files they were read from. It is the ONLY
source the API uses for the v1-vs-v2 comparison (no data is re-queried at request time).
"""

import json
from pathlib import Path
from typing import Any

from compassio_ml.integrity.hashing import sha256_file

SCHEMA = "compassio-ml-v2-comparison-aggregates/1"
METRICS = (
    "average_precision",
    "f1",
    "precision",
    "recall",
    "roc_auc",
    "non_energy_average_precision",
    "non_energy_precision",
    "non_energy_recall",
    "energy_recall",
    "adaptation_only_recall",
    "ece_10bin",
)


def _model_block(entry: dict[str, Any]) -> dict[str, Any]:
    m = entry["metrics"]
    slices = entry["slices"]
    return {
        "threshold": entry.get("threshold"),
        "metrics": {k: entry["summary"].get(k) for k in METRICS},
        "intervals_95": {k: [v["low"], v["high"]] for k, v in entry.get("intervals", {}).items()},
        "confusion": {k: m[k] for k in ("tp", "fp", "fn", "tn")},
        "predicted_positive": m["tp"] + m["fp"],
        "adaptation_only": slices["positives:adaptation_only"],
        "publisher": {
            k.split(":", 1)[1]: {
                x: slices[k].get(x)
                for x in ("records", "positives", "precision", "recall", "average_precision")
            }
            for k in slices
            if k.startswith("publisher:")
        },
    }


def export_aggregates(run_dir: Path) -> dict[str, Any]:
    results_path = run_dir / "results.json"
    manifest_path = run_dir / "run_manifest.json"
    results = json.loads(results_path.read_text("utf-8"))
    manifest = json.loads(manifest_path.read_text("utf-8"))
    champion_key = results["selection"]["champion"]
    population, name = champion_key.split("/", 1)
    champion = results["populations"][population][name]
    v1 = results["baselines"]["v1_release"]
    counts = manifest["profile"]["counts"]
    valid = {k: v for k, v in counts.items() if k.endswith("/valid")}
    return {
        "schema": SCHEMA,
        "run_id": manifest["run_id"],
        "plan_sha256": manifest["plan_sha256"],
        "git_commit": manifest["git_commit"],
        "source_files_sha256": {
            "results.json": sha256_file(results_path),
            "run_manifest.json": sha256_file(manifest_path),
        },
        "population": {
            "description": "Eligible ML v2 development-validation records (FCDO + EC IATI); "
            "labels are publisher-reported Rio markers, not human-verified",
            "records": champion["metrics"]["records"],
            "positives": champion["metrics"]["positives"],
            "by_publisher": {
                k.split("/")[0]: {"records": v["records"], "positives": v["positives"]}
                for k, v in valid.items()
            },
            "used_for_model_selection": True,
        },
        "ml_v1": {"model_version": v1["model_version"], **_model_block(v1)},
        "ml_v2": {"candidate": champion_key, **_model_block(champion)},
        "paired_differences_ml_v2_minus_ml_v1": {
            k: v for k, v in results["comparisons"].items() if k.startswith("champion_minus_v1")
        },
        "caveats": [
            "Same 2,550 records for both models; v1 threshold unchanged (0.474).",
            "VALID was used once to select ML v2, so ML v2's scores are optimistic.",
            "Agreement with publisher markers, not independently verified accuracy.",
            "v1's threshold was set on AidData (6-8% prevalence); part of the gap is a "
            "population/label-policy shift.",
            "Do not compare with v1's Task 005 AidData final-test metrics (different data).",
        ],
    }
