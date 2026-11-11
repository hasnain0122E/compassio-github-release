"""The reproducible C05 experiment (clean vs poisoned vs protected).

Steps (``run_experiment``):

1. Load the eligible ML v2 cohort via ``model_v2.data.load_development`` (pins, rights and
   isolation re-checked); TRAIN = incoming batch A, VALID = challenge development benchmark.
2. Snapshot A and the benchmark (immutable JSONL + SHA-256) under the git-ignored output root.
3. Per attack mode: inject exactly 5% label flips -> batch B; the oracle is written to a separate
   ``private_oracle/`` file. The gate scores B WITHOUT the oracle -> accepted batch C.
4. Evaluate the detector against the oracle (evaluation only), also on the unpoisoned batch A
   (natural disagreement floor), plus a suspicion-rank sweep.
5. Train disposable models (clean reference, naive on B, protected on C, strict variant) with
   identical settings; score them on the benchmark.
6. Write ``summary.json`` and ``manifest.json`` (hashes of every input and output).

Nothing canonical is modified; the run directory is immutable (refuses to overwrite).
"""

import ctypes
import hashlib
import json
import platform
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn

from compassio_ml.challenges.c05.attack import PoisonOracle, inject_label_flips
from compassio_ml.challenges.c05.batch import SuppliedBatch, labelled_fingerprint
from compassio_ml.challenges.c05.config import C05Config, config_sha256
from compassio_ml.challenges.c05.gate import GateResult, quarantine_gate
from compassio_ml.challenges.c05.train import Baseline, evaluate, fit_downstream
from compassio_ml.external.paths import V2Paths
from compassio_ml.integrity.hashing import sha256_file
from compassio_ml.model_v2.data import load_development
from compassio_ml.model_v2.plan import load_plan, plan_sha256

CHALLENGE_DIR = Path("challenges") / "c05"
BENCHMARK_LABEL = (
    "CHALLENGE DEVELOPMENT BENCHMARK: the ML v2 development-validation partition (2,550 FCDO/EC "
    "records). Not an independent or sealed test; scores measure agreement with donor Rio markers."
)


def peak_memory_mb() -> float | None:
    """Peak resident memory of this process (Windows: PeakWorkingSetSize; POSIX: ru_maxrss)."""
    windll = getattr(ctypes, "windll", None)
    if windll is not None:

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        kernel32 = windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p  # a HANDLE, not a 32-bit int
        kernel32.K32GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(Counters),
            ctypes.c_ulong,
        ]
        handle = kernel32.GetCurrentProcess()
        if kernel32.K32GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return round(float(counters.PeakWorkingSetSize) / 2**20, 1)
        return None
    resource = __import__("resource")
    return round(float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024, 1)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return sha256_file(path)


def _write_json(path: Path, payload: Any) -> str:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    return sha256_file(path)


def _git_head(repo: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def detection_metrics(
    ids: np.ndarray,
    status: np.ndarray,
    suspicion: np.ndarray,
    oracle: PoisonOracle,
    clean_labels: np.ndarray,
    adaptation_only: np.ndarray,
) -> dict[str, Any]:
    """Detector quality against the oracle. EVALUATION ONLY (never feeds a decision)."""
    flipped = np.isin(ids, np.array(oracle.flipped_ids))
    quarantined = status == "quarantined"
    review = status == "insufficient_evidence"
    tp = int((quarantined & flipped).sum())
    fp = int((quarantined & ~flipped).sum())
    fn = int((~quarantined & flipped).sum())
    clean = ~flipped
    clean_pos = clean & (clean_labels == 1)
    clean_ad = clean_pos & np.asarray(adaptation_only, dtype=bool)
    sweep = []
    score = np.nan_to_num(suspicion, nan=-1.0)
    order = np.argsort(-score, kind="stable")
    for share in (0.02, 0.03, 0.05, 0.075, 0.10):
        top = np.zeros(len(ids), dtype=bool)
        top[order[: round(len(ids) * share)]] = True
        hit = int((top & flipped).sum())
        sweep.append(
            {
                "quarantine_share": share,
                "quarantined": int(top.sum()),
                "true_positives": hit,
                "precision": round(hit / max(int(top.sum()), 1), 4),
                "recall": round(hit / oracle.count, 4),
            }
        )
    return {
        "injected_poison": oracle.count,
        "quarantined": int(quarantined.sum()),
        "detected_poison_true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "detection_precision": round(tp / max(tp + fp, 1), 4),
        "detection_recall": round(tp / oracle.count, 4),
        "false_quarantine_rate": round(fp / max(int(clean.sum()), 1), 4),
        "clean_records": int(clean.sum()),
        "clean_records_retained": int((clean & ~quarantined).sum()),
        "clean_climate_positive_quarantined": int((quarantined & clean_pos).sum()),
        "clean_climate_positive_total": int(clean_pos.sum()),
        "clean_adaptation_only_positive_quarantined": int((quarantined & clean_ad).sum()),
        "clean_adaptation_only_positive_total": int(clean_ad.sum()),
        "insufficient_evidence": int(review.sum()),
        "insufficient_evidence_poisoned": int((review & flipped).sum()),
        "poisoned_accepted_into_training": int((flipped & ~quarantined).sum()),
        "flipped_by_original_label": {
            str(c): int((flipped & (clean_labels == c)).sum()) for c in (0, 1)
        },
        "recall_by_original_label": {
            str(c): round(
                int((quarantined & flipped & (clean_labels == c)).sum())
                / max(int((flipped & (clean_labels == c)).sum()), 1),
                4,
            )
            for c in (0, 1)
        },
        "suspicion_rank_sweep": sweep,
    }


def _batch(frame: pd.DataFrame) -> SuppliedBatch:
    return SuppliedBatch.create(
        frame["candidate_id"].to_numpy(),
        frame["text"].to_numpy(),
        frame["y"].to_numpy(),
        frame["group"].to_numpy(),
        frame["source_id"].to_numpy(),
    )


def _snapshot_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    columns = ("candidate_id", "source_id", "group", "y", "non_energy", "adaptation_only")
    ids, sources, groups, labels, non_energy, adaptation = (frame[c].to_numpy() for c in columns)
    return [
        {
            "record_id": str(ids[i]),
            "source_id": str(sources[i]),
            "group": str(groups[i]),
            "label": int(labels[i]),
            "non_energy": bool(non_energy[i]),
            "adaptation_only": bool(adaptation[i]),
            "title": str(frame["title"].iat[i]),
            "text": str(frame["text"].iat[i]),
        }
        for i in range(len(frame))
    ]


def run_experiment(paths: V2Paths, cfg: C05Config, config_path: Path, repo: Path) -> Path:
    started = time.perf_counter()
    timings: dict[str, float] = {}
    plan_path = repo / cfg.cohort.plan
    plan = load_plan(plan_path)
    run_id = f"c05_{config_sha256(config_path)[:12]}"
    out = paths.writable(paths.output_root / CHALLENGE_DIR / run_id)
    if out.exists():
        raise FileExistsError(f"{out} exists; C05 runs are immutable")
    (out / "private_oracle").mkdir(parents=True)
    (out / "gate").mkdir()

    t = time.perf_counter()
    dev = load_development(paths, plan)
    timings["load_cohort_s"] = round(time.perf_counter() - t, 1)
    train = dev.part(cfg.cohort.batch_partition).reset_index(drop=True)
    bench = dev.part(cfg.cohort.benchmark_partition).reset_index(drop=True)
    batch_a = _batch(train)
    pinned = plan.inputs.memberships["train"].sha256
    if batch_a.fingerprint() != pinned:
        raise RuntimeError("clean batch fingerprint differs from the ML v2 plan's TRAIN pin")

    files: dict[str, str] = {}
    files["batch_A_clean.jsonl"] = _write_jsonl(out / "batch_A_clean.jsonl", _snapshot_rows(train))
    files["benchmark.jsonl"] = _write_jsonl(out / "benchmark.jsonl", _snapshot_rows(bench))
    non_energy = train["non_energy"].to_numpy()
    adaptation_only = train["adaptation_only"].to_numpy()
    clean_labels = batch_a.labels

    summary: dict[str, Any] = {
        "challenge": "C05 poisoned training batch quarantine",
        "run_id": run_id,
        "benchmark_label": BENCHMARK_LABEL,
        "batch": {
            "records": len(batch_a),
            "positives": int(clean_labels.sum()),
            "by_source": train["source_id"].value_counts().sort_index().to_dict(),
            "clean_fingerprint": batch_a.fingerprint(),
            "matches_ml_v2_plan_train_pin": True,
        },
        "benchmark": {"records": len(bench), "positives": int(bench["y"].sum())},
        "attacks": {},
    }

    t = time.perf_counter()
    gate_clean = quarantine_gate(batch_a, cfg)
    timings["detector_clean_batch_s"] = round(time.perf_counter() - t, 1)
    summary["natural_disagreement_on_unpoisoned_batch"] = {
        "quarantined": len(gate_clean.quarantined_ids),
        "insufficient_evidence": len(gate_clean.review_ids),
        "share_quarantined": round(len(gate_clean.quarantined_ids) / len(batch_a), 4),
        "meaning": "Records the detector quarantines when NO label was poisoned: disagreements "
        "between donor Rio markers and similar records (natural label noise or genuinely "
        "ambiguous projects). This is the false-alarm floor of the method.",
    }
    files["gate/clean_batch_report.json"] = _write_json(
        out / "gate" / "clean_batch_report.json", gate_clean.report
    )

    specs = plan.features
    ds = cfg.downstream

    def score(model: Any) -> dict[str, Any]:
        return evaluate(
            model,
            bench["text"].to_numpy(),
            bench["y"].to_numpy(),
            bench["non_energy"].to_numpy(),
            bench["adaptation_only"].to_numpy(),
            ds.classifier,
        )

    t = time.perf_counter()
    clean_model = fit_downstream(Baseline("clean_reference", batch_a), ds, specs)
    summary["models"] = {
        "clean_reference": {
            "training_records": clean_model.training_records,
            "training_fingerprint": clean_model.training_fingerprint,
            "fit_seconds": clean_model.seconds,
            "benchmark": score(clean_model),
        }
    }
    timings["train_clean_s"] = round(time.perf_counter() - t, 1)

    for mode in cfg.attack.modes:
        t = time.perf_counter()
        batch_b, oracle = inject_label_flips(
            batch_a, cfg.attack.rate, cfg.attack.seed, mode, non_energy
        )
        if not np.array_equal(batch_a.labels, clean_labels):
            raise RuntimeError("the clean batch changed during the attack")
        files[f"batch_B_poisoned_{mode}.jsonl"] = _write_jsonl(
            out / f"batch_B_poisoned_{mode}.jsonl",
            [
                {"record_id": str(i), "supplied_label": int(y)}
                for i, y in zip(batch_b.ids, batch_b.labels, strict=True)
            ],
        )
        files[f"private_oracle/oracle_{mode}.json"] = _write_json(
            out / "private_oracle" / f"oracle_{mode}.json",
            {
                "warning": "PRIVATE EVALUATION ORACLE. Never an input to the detector or gate.",
                "mode": oracle.mode,
                "seed": oracle.seed,
                "rate": oracle.rate,
                "batch_size": oracle.batch_size,
                "count": oracle.count,
                "flipped_ids": list(oracle.flipped_ids),
                "clean_fingerprint": oracle.clean_fingerprint,
                "poisoned_fingerprint": oracle.poisoned_fingerprint,
            },
        )
        gate: GateResult = quarantine_gate(batch_b, cfg)  # the oracle is NOT passed
        gate_seconds = round(time.perf_counter() - t, 1)
        files[f"gate/{mode}_report.json"] = _write_json(
            out / "gate" / f"{mode}_report.json", gate.report
        )
        files[f"batch_C_protected_{mode}.jsonl"] = _write_jsonl(
            out / f"batch_C_protected_{mode}.jsonl",
            [{"record_id": i} for i in gate.accepted_ids],
        )
        detection = detection_metrics(
            batch_b.ids,
            gate.detector.status,
            gate.detector.suspicion,
            oracle,
            clean_labels,
            adaptation_only,
        )
        entry: dict[str, Any] = {
            "attack": {
                "mode": mode,
                "seed": oracle.seed,
                "rate": oracle.rate,
                "flipped": oracle.count,
                "flipped_share": round(oracle.count / len(batch_b), 6),
                "clean_fingerprint": oracle.clean_fingerprint,
                "poisoned_fingerprint": oracle.poisoned_fingerprint,
            },
            "gate": {
                "seconds": gate_seconds,
                "accepted": len(gate.accepted_ids),
                "quarantined": len(gate.quarantined_ids),
                "insufficient_evidence": len(gate.review_ids),
                "output_fingerprint": gate.report["output_fingerprint"],
                "counts": gate.report["counts"],
            },
            "detection": detection,
            "models": {},
        }
        t = time.perf_counter()
        naive = fit_downstream(Baseline("naive_poisoned", batch_b), ds, specs)
        entry["models"]["naive_poisoned"] = {
            "training_records": naive.training_records,
            "fit_seconds": naive.seconds,
            "benchmark": score(naive),
        }
        protected = fit_downstream(gate.accepted, ds, specs)
        entry["models"]["protected_after_quarantine"] = {
            "training_records": protected.training_records,
            "training_fingerprint": protected.training_fingerprint,
            "fit_seconds": protected.seconds,
            "benchmark": score(protected),
        }
        if mode == "uniform":
            strict_keep = gate.detector.status == "accepted"
            strict_ids = batch_b.ids[strict_keep]
            strict = fit_downstream(
                Baseline("naive_poisoned", batch_b.subset(strict_keep)), ds, specs
            )
            entry["models"]["strict_variant_excluding_review"] = {
                "training_records": strict.training_records,
                "fit_seconds": strict.seconds,
                "note": "Sensitivity analysis only: also excludes insufficient_evidence records.",
                "training_fingerprint": labelled_fingerprint(
                    strict_ids, batch_b.labels[strict_keep]
                ),
                "benchmark": score(strict),
            }
        timings[f"train_{mode}_s"] = round(time.perf_counter() - t, 1)
        summary["attacks"][mode] = entry

    timings["total_s"] = round(time.perf_counter() - started, 1)
    summary["runtime"] = {
        "timings": timings,
        "peak_memory_mb": peak_memory_mb(),
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
    }
    summary["versions"] = {
        "config_version": cfg.config_version,
        "detector_version": cfg.detector_version,
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
    }
    summary["finished_at"] = datetime.now(UTC).isoformat()
    files["summary.json"] = _write_json(out / "summary.json", summary)
    manifest = {
        "run_id": run_id,
        "config_path": str(config_path.as_posix()),
        "config_sha256": config_sha256(config_path),
        "plan_sha256": plan_sha256(plan_path),
        "git_head": _git_head(repo),
        "attack_seed": cfg.attack.seed,
        "attack_rate": cfg.attack.rate,
        "detector_version": cfg.detector_version,
        "clean_batch_fingerprint": batch_a.fingerprint(),
        "files_sha256": files,
        "command": "uv run python -m compassio_ml.challenges.c05.cli run",
    }
    manifest_text = json.dumps(manifest, indent=1, sort_keys=True)
    (out / "manifest.json").write_text(manifest_text + "\n", encoding="utf-8", newline="\n")
    (out / "manifest.sha256").write_text(
        hashlib.sha256((manifest_text + "\n").encode("utf-8")).hexdigest() + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return out


def verify_run(run_dir: Path) -> list[str]:
    """Re-hash every file listed in the manifest. Returns a list of problems (empty = ok)."""
    problems: list[str] = []
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        return [f"missing {manifest_path}"]
    expected_manifest = (run_dir / "manifest.sha256").read_text(encoding="utf-8").strip()
    if sha256_file(manifest_path) != expected_manifest:
        problems.append("manifest.json does not match manifest.sha256")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for rel, digest in manifest["files_sha256"].items():
        path = run_dir / rel
        if not path.is_file():
            problems.append(f"missing {rel}")
        elif sha256_file(path) != digest:
            problems.append(f"hash mismatch {rel}")
    return problems
