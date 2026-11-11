"""C05 hardening addendum (c05-1.1.0): compare decision policies on identical inputs.

* Re-reads the base run's clean batch, poisoned batches, oracles and benchmark (hash-verified;
  the base run directory is never modified).
* Reads the publisher DAC purpose codes through the sanctioned loader
  (``quality_v2.audit.load_eligible_donor_records`` after ``model_v2.data.check_pins`` and
  ``check_rights``) and checks the cohort fingerprint against the plan pin.
* Runs the unchanged detector once per poisoned batch and applies policy A (deployed two-signal),
  B (hardened candidate) and C (top-5% suspicion, analysis only).
* Measures detection on the final seed and on fresh robustness seeds, the no-attack floor, and
  trains disposable models for B and C with the base-run settings.
"""

import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from compassio_ml.challenges.c05.attack import PoisonOracle, inject_label_flips
from compassio_ml.challenges.c05.batch import SuppliedBatch
from compassio_ml.challenges.c05.config import C05Config, config_sha256, load_config
from compassio_ml.challenges.c05.detector import DetectorResult, assess
from compassio_ml.challenges.c05.experiment import (
    CHALLENGE_DIR,
    _git_head,
    _write_json,
    _write_jsonl,
    detection_metrics,
    peak_memory_mb,
    verify_run,
)
from compassio_ml.challenges.c05.gate import quarantine_gate
from compassio_ml.challenges.c05.policy import (
    Metadata,
    PolicyDecision,
    hardened,
    top_share,
    two_signal,
)
from compassio_ml.challenges.c05.train import evaluate, fit_downstream
from compassio_ml.external.partition import TRAIN
from compassio_ml.external.paths import V2Paths
from compassio_ml.integrity.hashing import sha256_file
from compassio_ml.model_v2.data import check_pins, check_rights, membership_sha256
from compassio_ml.model_v2.plan import load_plan
from compassio_ml.quality_v2.audit import load_eligible_donor_records

POLICY_LABELS = {
    "two_signal": "A. Deployed two-signal policy (text model AND neighbours)",
    "hardened": "B. Hardened candidate (+ independent provenance, protected positives)",
    "top_share": "C. Analysis only: top 5% by suspicion score (not deployed)",
}


def load_addendum(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


def _jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def load_sector_codes(paths: V2Paths, repo: Path, base: C05Config) -> dict[str, str]:
    plan = load_plan(repo / base.cohort.plan)
    check_pins(paths, plan)
    frame = load_eligible_donor_records(paths, plan.inputs.audit_id, TRAIN)
    check_rights(paths, set(frame["source_id"].astype(str)))
    probe = frame.assign(y=(frame["donor_rio_overall"].astype(float) > 0).astype(int))
    if membership_sha256(probe) != plan.inputs.memberships["train"].sha256:
        raise RuntimeError("TRAIN cohort differs from the plan pin")
    return dict(
        zip(
            frame["candidate_id"].astype(str),
            frame["sector_codes"].fillna("").astype(str),
            strict=True,
        )
    )


def _policies(
    batch: SuppliedBatch, meta: Metadata, intrinsic: frozenset[str], cfg: dict[str, Any]
) -> dict[str, Callable[[DetectorResult], PolicyDecision]]:
    hard = cfg["policies"]["hardened"]
    share = float(cfg["policies"]["top_share"]["share"])
    return {
        "two_signal": two_signal,
        "hardened": lambda det: hardened(batch, det, meta, intrinsic, hard),
        "top_share": lambda det: top_share(det, share),
    }


def _gate_policy(
    fn: Callable[[DetectorResult], PolicyDecision],
) -> Callable[[DetectorResult], tuple[str, np.ndarray, tuple[str, ...]]]:
    def apply(det: DetectorResult) -> tuple[str, np.ndarray, tuple[str, ...]]:
        decision = fn(det)
        return decision.policy, decision.status, decision.reasons

    return apply


def _escaped(
    batch: SuppliedBatch,
    decision: PolicyDecision,
    det: DetectorResult,
    flipped: np.ndarray,
    titles: dict[str, str],
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Poisoned records that were NOT quarantined (accepted or review), most suspicious first."""
    idx = np.flatnonzero(flipped & (decision.status != "quarantined"))
    order = idx[np.argsort(-np.nan_to_num(det.suspicion[idx], nan=-1.0), kind="stable")]
    rows = []
    for i in order[:limit]:
        title = titles.get(str(batch.ids[i]), "")
        rows.append(
            {
                "record_id": str(batch.ids[i]),
                "source_id": str(batch.sources[i]),
                "title_excerpt": title if len(title) <= 90 else title[:87] + "...",
                "supplied_label": int(batch.labels[i]),
                "status": str(decision.status[i]),
                "suspicion": None
                if np.isnan(det.suspicion[i])
                else round(float(det.suspicion[i]), 4),
                "reason": decision.reasons[i],
            }
        )
    return rows


def run_addendum(paths: V2Paths, addendum_path: Path, repo: Path) -> Path:
    started = time.perf_counter()
    acfg = load_addendum(addendum_path)
    base_path = repo / acfg["base_config"]
    base = load_config(base_path)
    base_dir = paths.output_root / CHALLENGE_DIR / acfg["base_run_id"]
    if f"c05_{config_sha256(base_path)[:12]}" != acfg["base_run_id"]:
        raise RuntimeError("base config changed since the base run")
    problems = verify_run(base_dir)
    if problems:
        raise RuntimeError(f"base run fails verification: {problems}")
    out = paths.writable(
        paths.output_root / CHALLENGE_DIR / f"addendum_{config_sha256(addendum_path)[:12]}"
    )
    if out.exists():
        raise FileExistsError(f"{out} exists; addendum runs are immutable")
    out.mkdir(parents=True)

    clean_rows = _jsonl(base_dir / "batch_A_clean.jsonl")
    bench = _jsonl(base_dir / "benchmark.jsonl")
    ids = np.array([r["record_id"] for r in clean_rows])
    clean = SuppliedBatch.create(
        ids,
        np.array([r["text"] for r in clean_rows]),
        np.array([r["label"] for r in clean_rows]),
        np.array([r["group"] for r in clean_rows]),
        np.array([r["source_id"] for r in clean_rows]),
    )
    titles = {r["record_id"]: r["title"] for r in clean_rows}
    adaptation_only = np.array([r["adaptation_only"] for r in clean_rows])
    t = time.perf_counter()
    sectors = load_sector_codes(paths, repo, base)
    load_seconds = round(time.perf_counter() - t, 1)
    meta = Metadata(
        sector_codes=np.array([sectors[i] for i in ids]),
        non_energy=np.array([r["non_energy"] for r in clean_rows]),
    )
    intrinsic = frozenset(str(c) for c in acfg["climate_intrinsic_dac_codes"])
    files: dict[str, str] = {}
    files["sector_metadata.jsonl"] = _write_jsonl(
        out / "sector_metadata.jsonl",
        [{"record_id": str(i), "sector_codes": sectors[str(i)]} for i in ids],
    )

    def run_policies(batch: SuppliedBatch, oracle: PoisonOracle | None) -> dict[str, Any]:
        det = assess(batch, base.detector)
        result: dict[str, Any] = {}
        for name, fn in _policies(batch, meta, intrinsic, acfg).items():
            decision = fn(det)
            entry: dict[str, Any] = {
                "label": POLICY_LABELS[name],
                "quarantined": int((decision.status == "quarantined").sum()),
                "insufficient_evidence": int((decision.status == "insufficient_evidence").sum()),
                "accepted": int((decision.status == "accepted").sum()),
            }
            if oracle is not None:
                flipped = np.isin(batch.ids, np.array(oracle.flipped_ids))
                entry["detection"] = detection_metrics(
                    batch.ids,
                    decision.status,
                    det.suspicion,
                    oracle,
                    clean.labels,
                    adaptation_only,
                )
                entry["escaped_examples"] = _escaped(batch, decision, det, flipped, titles)
                entry["poisoned_by_status"] = {
                    s: int((flipped & (decision.status == s)).sum())
                    for s in ("accepted", "insufficient_evidence", "quarantined")
                }
            else:
                pos = clean.labels == 1
                q = decision.status == "quarantined"
                entry["clean_positive_quarantined"] = int((q & pos).sum())
                entry["clean_adaptation_only_quarantined"] = int((q & pos & adaptation_only).sum())
            result[name] = entry
        return result

    summary: dict[str, Any] = {
        "addendum_version": acfg["addendum_version"],
        "base_run_id": acfg["base_run_id"],
        "policies": POLICY_LABELS,
        "independent_signal": "Publisher DAC purpose codes (source metadata, not the attacked "
        "Rio-marker label). Intrinsic code list fixed a priori in the addendum config.",
        "records_with_intrinsic_code": int(
            sum(bool(c) for c in (set(str(s).split(";")) & intrinsic for s in meta.sector_codes))
        ),
        "development_seed_used_for_design": acfg["evaluation"]["development_seed_used"],
    }
    t = time.perf_counter()
    summary["no_attack_floor"] = run_policies(clean, None)
    final: dict[str, Any] = {}
    oracles: dict[str, PoisonOracle] = {}
    for mode in base.attack.modes:
        oracle_doc = json.loads(
            (base_dir / "private_oracle" / f"oracle_{mode}.json").read_text("utf-8")
        )
        supplied = {
            r["record_id"]: r["supplied_label"]
            for r in _jsonl(base_dir / f"batch_B_poisoned_{mode}.jsonl")
        }
        poisoned = clean.with_labels(np.array([supplied[str(i)] for i in ids]))
        oracle = PoisonOracle(
            mode=mode,
            seed=int(oracle_doc["seed"]),
            rate=float(oracle_doc["rate"]),
            batch_size=int(oracle_doc["batch_size"]),
            flipped_ids=tuple(oracle_doc["flipped_ids"]),
            clean_fingerprint=oracle_doc["clean_fingerprint"],
            poisoned_fingerprint=oracle_doc["poisoned_fingerprint"],
        )
        if poisoned.fingerprint() != oracle.poisoned_fingerprint:
            raise RuntimeError(f"stored poisoned batch {mode} does not match its oracle")
        oracles[mode] = oracle
        final[mode] = run_policies(poisoned, oracle)
    summary["final_seed"] = {"seed": acfg["evaluation"]["final_seed"], "attacks": final}
    detection_seconds = round(time.perf_counter() - t, 1)

    robustness: dict[str, Any] = {}
    for seed in acfg["evaluation"]["robustness_seeds"]:
        for mode in base.attack.modes:
            poisoned, oracle = inject_label_flips(
                clean, base.attack.rate, int(seed), mode, meta.non_energy
            )
            runs = run_policies(poisoned, oracle)
            robustness[f"{mode}|{seed}"] = {
                name: {
                    k: r["detection"][k]
                    for k in (
                        "detection_precision",
                        "detection_recall",
                        "false_quarantine_rate",
                        "clean_climate_positive_quarantined",
                        "poisoned_accepted_into_training",
                    )
                }
                for name, r in runs.items()
            }
    summary["robustness_seeds"] = robustness

    t = time.perf_counter()
    ds = base.downstream
    specs = load_plan(repo / base.cohort.plan).features
    bench_args = (
        np.array([r["text"] for r in bench]),
        np.array([r["label"] for r in bench]),
        np.array([r["non_energy"] for r in bench]),
        np.array([r["adaptation_only"] for r in bench]),
        ds.classifier,
    )
    models: dict[str, Any] = {}
    for mode_name in oracles:
        supplied = {
            r["record_id"]: r["supplied_label"]
            for r in _jsonl(base_dir / f"batch_B_poisoned_{mode_name}.jsonl")
        }
        poisoned = clean.with_labels(np.array([supplied[str(i)] for i in ids]))
        fns = _policies(poisoned, meta, intrinsic, acfg)
        for name in acfg["evaluation"]["train_downstream_for"]:
            gate = quarantine_gate(poisoned, base, policy=_gate_policy(fns[name]))
            model = fit_downstream(gate.accepted, ds, specs)
            models[f"{mode_name}|{name}"] = {
                "policy": POLICY_LABELS[name],
                "training_records": model.training_records,
                "fit_seconds": model.seconds,
                "benchmark": evaluate(model, *bench_args),
            }
            files[f"gate_{mode_name}_{name}.json"] = _write_json(
                out / f"gate_{mode_name}_{name}.json", gate.report
            )
    summary["models"] = models
    summary["runtime"] = {
        "load_sector_metadata_s": load_seconds,
        "detection_and_policies_s": detection_seconds,
        "training_s": round(time.perf_counter() - t, 1),
        "total_s": round(time.perf_counter() - started, 1),
        "peak_memory_mb": peak_memory_mb(),
    }
    summary["finished_at"] = datetime.now(UTC).isoformat()
    files["summary.json"] = _write_json(out / "summary.json", summary)
    manifest = {
        "addendum_config": addendum_path.as_posix(),
        "addendum_config_sha256": config_sha256(addendum_path),
        "base_run_id": acfg["base_run_id"],
        "base_manifest_sha256": sha256_file(base_dir / "manifest.json"),
        "git_head": _git_head(repo),
        "files_sha256": files,
        "command": "uv run python -m compassio_ml.challenges.c05.cli addendum",
    }
    text = json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    (out / "manifest.json").write_text(text, encoding="utf-8", newline="\n")
    (out / "manifest.sha256").write_text(
        hashlib.sha256(text.encode("utf-8")).hexdigest() + "\n", encoding="utf-8", newline="\n"
    )
    return out
