"""Offline C09 benchmark. Source roots are READ ONLY; outputs stay in artifacts/c09.

Usage: python -m compassio_ml.c09.benchmark prepare|baseline|guarded|report
       --source-root PATH [--output artifacts/c09]
No network, training, database queries, or sealed evaluation access.
"""

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from compassio_ml.c09.attacks import KINDS, attack, seed_for
from compassio_ml.external.paths import V2Paths
from compassio_ml.integrity.hashing import sha256_file
from compassio_ml.model_v2.artifact import CandidatePrediction, ExperimentalClassifier
from compassio_ml.model_v2.data import check_pins, membership_sha256, prepare
from compassio_ml.model_v2.plan import load_plan
from compassio_ml.quality_v2.audit import load_verified_development

REPO = Path(__file__).resolve().parents[5]


def read(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", "utf-8")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True, timeout=30
    ).stdout.strip()


def protocol() -> dict[str, Any]:
    return dict(read(REPO / "configs/c09_protocol.json"))


def integrity(source: Path) -> dict[str, Any]:
    """Hash named immutable resources only. Never open sealed evaluation payloads."""
    p = protocol()
    files = [
        source / "data/db/compassio_dev.sqlite",
        source / "data/ml_v2/models_v2_dev" / p["candidate"] / "model.joblib",
    ]
    files.extend(sorted((source / "models/compassio_ccrc_v1").glob("*")))
    # Tracked reference files are hashed by git, including finance and old release ledgers.
    tracked = git(
        "ls-files",
        "packages/compassio_ml/src/compassio_ml/finance",
        "configs/trusted_model_releases.json",
        "docs/research/final_evaluation_v1",
    )
    return {
        "resources": {str(f.relative_to(source)): sha256_file(f) for f in files if f.is_file()},
        "tracked": {name: sha256_file(REPO / name) for name in tracked.splitlines()},
        "protected_refs": {
            ref: git("rev-parse", ref)
            for ref in (
                "main",
                "backend-ready-for-battleverse^{commit}",
                "challenge/c05-poison-quarantine",
                "feature/task010-complete-frontend",
            )
        },
    }


def prepare_run(source: Path, output: Path) -> None:
    if git("branch", "--show-current") not in {
        "challenge/c09-adversarial-robustness",
        "integration/battleverse-final-product",
    }:
        raise ValueError("C09 or final integration branch required")
    p = protocol()
    if (output / "split_manifest.json").exists():
        raise FileExistsError("use a fresh output directory; never overwrite a frozen split")
    for ref in ("main", "backend-ready-for-battleverse^{commit}"):
        if git("rev-parse", ref) != p["frozen_backend"]:
            raise ValueError(f"frozen backend reference changed: {ref}")
    load_model(source)
    paths = V2Paths(REPO, source / "data/ml_v2", source / "data", source)
    # These functions perform no writes. Reuse the checksum-pinned completed audit rather
    # than rerunning its writer against another worktree.
    plan = load_plan(REPO / "configs/ml_v2_fast_experiment.yaml")
    check_pins(paths, plan)
    frame, provenance = load_verified_development(paths, plan.inputs.build_id)
    audit = paths.output_root / "automated_quality" / plan.inputs.audit_id
    quality = [
        json.loads(line)
        for line in (audit / "record_quality.jsonl").read_text("utf-8").splitlines()
    ]
    allowed = {r["candidate_id"] for r in quality if r["eligible_source_label"]}
    frame = frame[frame["candidate_id"].isin(allowed)]
    frame = prepare(frame[frame["v2_partition"] == "validation_candidate"], "valid")
    pin = plan.inputs.memberships["valid"]
    if len(frame) != pin.records or membership_sha256(frame) != pin.sha256:
        raise ValueError("validation membership pin mismatch")
    # Connected components enforce disjointness even when group/family/hash differ.
    parents = {str(x): str(x) for x in frame["candidate_id"]}

    def find(x: str) -> str:
        while parents[x] != x:
            parents[x] = parents[parents[x]]
            x = parents[x]
        return x

    for col in ("group", "family", "text_sha256"):
        for ids in frame.groupby(col)["candidate_id"]:
            members = sorted(str(x) for x in ids[1])
            for member in members[1:]:
                a, b = find(members[0]), find(member)
                parents[max(a, b)] = min(a, b)
    frame["component"] = [find(str(x)) for x in frame["candidate_id"]]
    frame["split_hash"] = [
        hashlib.sha256(f"c09-v1|{x}".encode()).hexdigest() for x in frame["component"]
    ]
    frame["split"] = [
        "tuning" if int(x, 16) % 4 == 0 else "assessment" for x in frame["split_hash"]
    ]
    frame = frame.sort_values(["split_hash", "candidate_id"])
    selected = pd.concat(
        [frame[frame["split"] == s].head(p[f"{s}_max_records"]) for s in ("tuning", "assessment")]
    )
    for col in ("group", "family", "text_sha256", "component"):
        if selected.groupby(col)["split"].nunique().max() > 1:
            raise ValueError("C09 split overlap")
    rows = json.loads(selected.to_json(orient="records"))
    write(output / "records.json", rows)
    write(output / "integrity_before.json", integrity(source))
    write(
        output / "split_manifest.json",
        {
            "protocol": p,
            "protocol_sha256": sha256_file(REPO / "configs/c09_protocol.json"),
            "provenance": provenance,
            "records_sha256": sha256_file(output / "records.json"),
            "membership": [{k: r[k] for k in ("candidate_id", "component", "split")} for r in rows],
            "sealed_evaluation_read": False,
            "training_performed": False,
        },
    )
    print(
        json.dumps(
            {"prepared": len(rows), "split_counts": selected["split"].value_counts().to_dict()}
        )
    )


class MeteredClassifier(ExperimentalClassifier):
    """Count frozen-model evaluations without changing features, weights or thresholds."""

    query_count: int = 0

    def predict(self, title: str | None, description: str | None) -> CandidatePrediction:
        self.query_count += 1
        return super().predict(title, description)


def load_model(source: Path) -> MeteredClassifier:
    p = protocol()
    directory = source / "data/ml_v2/models_v2_dev" / p["candidate"]
    # Independent committed pin BEFORE even the candidate loader may unpickle.
    manifest = read(directory / "candidate_manifest.json")
    for key, expected in (
        ("artifact_file", "model.joblib"),
        ("artifact_sha256", p["artifact_sha256"]),
        ("model_fingerprint", p["fingerprint"]),
        ("threshold", p["threshold"]),
        ("candidate_id", p["candidate"]),
    ):
        if manifest.get(key) != expected:
            raise ValueError(f"frozen candidate manifest pin mismatch: {key}")
    if sha256_file(directory / "model.joblib") != p["artifact_sha256"]:
        raise ValueError("frozen artifact pin mismatch")
    model = ExperimentalClassifier.load(directory, REPO / "configs/trusted_model_releases.json")
    if model.threshold != p["threshold"] or model.manifest["model_fingerprint"] != p["fingerprint"]:
        raise ValueError("frozen model identity mismatch")
    return MeteredClassifier(model._model, model.manifest)


def benchmark(source: Path, output: Path, guarded: bool) -> None:
    p = protocol()
    split = read(output / "split_manifest.json")
    if split["protocol"] != p or split["records_sha256"] != sha256_file(output / "records.json"):
        raise ValueError("protocol or inputs changed after split freeze")
    model = load_model(source)
    if guarded:
        from compassio_ml.c09.guard import GuardedClassifier

        adapter = GuardedClassifier(model)
    rows = read(output / "records.json")
    baseline = read(output / "baseline.json") if guarded else []
    results: list[dict[str, Any]] = []
    query_receipts: list[dict[str, Any]] = []
    trials: list[dict[str, Any]] = []
    for r in rows:
        start_queries = model.query_count
        fields = (r["title"], r["description"])
        clean = model.predict(*fields).label_score
        clean_guard = adapter.predict(*fields) if guarded else None
        candidates = [
            attack(fields, kind, seed_for(r["candidate_id"], i)) for i, kind in enumerate(KINDS)
        ]
        # Fixed-budget random score search. Every candidate starts from ORIGINAL fields;
        # budgets never accumulate across queries. Adaptive draws use a fresh seed domain.
        query_candidates = [
            attack(
                fields,
                KINDS[i % len(KINDS)],
                seed_for(r["candidate_id"], i + (1000 if guarded else 100)),
            )
            for i in range(p["query_budget_per_direction"])
        ]
        oracle_start = model.query_count
        q_scores: list[float] = []
        for i, a in enumerate(query_candidates):
            before_request = model.query_count
            if guarded:
                response = adapter.predict(*a.fields)
                value = response.guarded_score
                response_data = asdict(response)
            else:
                raw_response = model.predict(*a.fields)
                value = raw_response.label_score
                response_data = asdict(raw_response)
            q_scores.append(value)
            trials.append(
                {
                    "candidate_id": r["candidate_id"],
                    "split": r["split"],
                    "trial": i,
                    "seed": seed_for(r["candidate_id"], i + (1000 if guarded else 100)),
                    "receipt": a.receipt(),
                    "oracle_score": value,
                    "response": response_data,
                    "model_evaluations": model.query_count - before_request,
                }
            )
        oracle_model_evaluations = model.query_count - oracle_start
        chosen = [int(np.argmin(q_scores)), int(np.argmax(q_scores))]
        # Both directional searches share the same 12-query pool, reported explicitly.
        cases = [(a.kind, a, 1) for a in candidates]
        if guarded:
            from compassio_ml.c09.attacks import Attack, Edit

            for previous in baseline:
                if previous["candidate_id"] != r["candidate_id"]:
                    continue
                if not previous["attack"].startswith("search_"):
                    continue
                receipt = previous["receipt"]
                original_attack = Attack(
                    receipt["kind"],
                    (receipt["fields"][0], receipt["fields"][1]),
                    tuple(Edit(**e) for e in receipt["edits"]),
                    receipt["eligible_characters"],
                    receipt["edit_distance"],
                )
                cases.append((previous["attack"], original_attack, previous["query_count"]))
        cases += [
            (
                "adaptive_" + direction if guarded else "search_" + direction,
                query_candidates[j],
                len(query_candidates),
            )
            for direction, j in zip(("reduction", "inflation"), chosen, strict=True)
        ]
        for name, a, queries in cases:
            score = model.predict(*a.fields).label_score
            g = adapter.predict(*a.fields) if guarded else None
            results.append(
                {
                    "candidate_id": r["candidate_id"],
                    "split": r["split"],
                    "y": r["y"],
                    "non_energy": r["non_energy"],
                    "adaptation_only": r["adaptation_only"],
                    "attack": name,
                    "underlying_kind": a.kind,
                    "receipt": a.receipt(),
                    "original_fields": fields,
                    "clean_score": clean,
                    "perturbed_score": score,
                    "guarded_score": g.guarded_score if g else None,
                    "clean_guarded_score": clean_guard.guarded_score if clean_guard else None,
                    "review": g.requires_review if g else None,
                    "unstable_input": g.unstable_input if g else None,
                    "clean_review": clean_guard.requires_review if clean_guard else None,
                    "query_count": queries,
                    "shared_directional_query_pool": True,
                }
            )
        query_receipts.append(
            {
                "candidate_id": r["candidate_id"],
                "split": r["split"],
                "oracle_requests": len(query_candidates),
                "oracle_model_evaluations": oracle_model_evaluations,
                "all_model_evaluations_including_diagnostics": model.query_count - start_queries,
            }
        )
    write(output / ("guarded.json" if guarded else "baseline.json"), results)
    write(output / ("guarded_queries.json" if guarded else "baseline_queries.json"), query_receipts)
    write(output / ("guarded_trials.json" if guarded else "baseline_trials.json"), trials)
    print(json.dumps({"mode": "guarded" if guarded else "baseline", "pairs": len(results)}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "baseline", "guarded", "report"))
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=REPO / "artifacts/c09")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((REPO / "artifacts/c09").resolve()):
        raise ValueError("outputs must stay under this C09 worktree's artifacts/c09")
    output.mkdir(parents=True, exist_ok=True)
    source = args.source_root.resolve()
    if args.stage == "prepare":
        prepare_run(source, output)
    elif args.stage == "report":
        from compassio_ml.c09.report import report

        report(source, output)
    else:
        benchmark(source, output, args.stage == "guarded")


if __name__ == "__main__":
    main()
