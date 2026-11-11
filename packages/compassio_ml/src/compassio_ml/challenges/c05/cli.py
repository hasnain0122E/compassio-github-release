"""C05 command line.

    uv run python -m compassio_ml.challenges.c05.cli run       # full experiment (~20 min)
    uv run python -m compassio_ml.challenges.c05.cli verify    # re-hash the cached run
    uv run python -m compassio_ml.challenges.c05.cli show      # print results + write HTML report
    uv run python -m compassio_ml.challenges.c05.cli live --sample 3000   # LIVE detection demo

``run`` needs the ML v2 environment (COMPASSIO_DATA_ROOT, COMPASSIO_V1_PROJECT_ROOT,
COMPASSIO_V2_OUTPUT_ROOT, COMPASSIO_V2_EXTERNAL_INPUT_ROOT). ``verify``/``show``/``live`` only
need the cached run under data/ml_v2/challenges/c05/.
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from compassio_ml.challenges.c05.attack import inject_label_flips
from compassio_ml.challenges.c05.batch import SuppliedBatch
from compassio_ml.challenges.c05.config import DEFAULT_CONFIG, config_sha256, load_config
from compassio_ml.challenges.c05.experiment import (
    CHALLENGE_DIR,
    detection_metrics,
    peak_memory_mb,
    run_experiment,
    verify_run,
)
from compassio_ml.challenges.c05.gate import quarantine_gate
from compassio_ml.challenges.c05.report import POLICY_SHORT, render, scorecard_rows
from compassio_ml.external.paths import V2Paths


def _run_dir(paths: V2Paths, config: Path) -> Path:
    return paths.output_root / CHALLENGE_DIR / f"c05_{config_sha256(config)[:12]}"


def _verified(run_dir: Path) -> None:
    problems = verify_run(run_dir)
    if problems:
        raise SystemExit("C05 run failed verification:\n  " + "\n  ".join(problems))


def _cmd_run(args: argparse.Namespace) -> int:
    paths = V2Paths.from_env()
    out = run_experiment(paths, load_config(args.config), args.config, Path.cwd())
    print(f"C05 run written to {out}")
    return 0


ADDENDUM_CONFIG = Path("configs") / "c05_hardening_addendum.yaml"


def _addendum_dir(paths: V2Paths) -> Path:
    return paths.output_root / CHALLENGE_DIR / f"addendum_{config_sha256(ADDENDUM_CONFIG)[:12]}"


def _cmd_addendum(args: argparse.Namespace) -> int:
    from compassio_ml.challenges.c05.addendum import run_addendum

    out = run_addendum(V2Paths.from_env(), ADDENDUM_CONFIG, Path.cwd())
    print(f"C05 addendum written to {out}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    run_dir = _run_dir(V2Paths.from_env(), args.config)
    problems = verify_run(run_dir)
    for p in problems:
        print(f"FAIL  {p}")
    manifest = json.loads((run_dir / "manifest.json").read_text("utf-8")) if not problems else {}
    print(
        f"OK  {run_dir.name}: {len(manifest.get('files_sha256', {}))} files match manifest.json"
        if not problems
        else "C05 run verification FAILED"
    )
    add_dir = _addendum_dir(V2Paths.from_env())
    if add_dir.is_dir():
        add_problems = verify_run(add_dir)
        for p in add_problems:
            print(f"FAIL  addendum: {p}")
        if not add_problems:
            n = len(json.loads((add_dir / "manifest.json").read_text("utf-8"))["files_sha256"])
            print(f"OK  {add_dir.name}: {n} files match manifest.json")
        problems = problems + add_problems
    return 1 if problems else 0


def _line(name: str, m: dict[str, Any]) -> str:
    b = m["benchmark"]
    return (
        f"  {name:<34} n={m['training_records']:>6}  AP {b['average_precision']:.4f}  "
        f"F1 {b['f1']:.4f}  P {b['precision']:.4f}  R {b['recall']:.4f}  "
        f"non-energy R {b['non_energy_recall']['recall']:.4f}  "
        f"adaptation-only R {b['adaptation_only_recall']['recall']:.4f}"
    )


def _ordered(attacks: dict[str, Any]) -> list[tuple[str, Any]]:
    """The organizers' core scenario (uniform) first, then the targeted variant."""
    return sorted(attacks.items(), key=lambda kv: (kv[0] != "uniform", kv[0]))


def _load_addendum() -> dict[str, Any] | None:
    add_dir = _addendum_dir(V2Paths.from_env())
    if not add_dir.is_dir():
        return None
    _verified(add_dir)
    data: dict[str, Any] = json.loads((add_dir / "summary.json").read_text("utf-8"))
    return data


def _print_scorecard(summary: dict[str, Any], addendum: dict[str, Any]) -> None:
    print("\nC05 SCORECARD (final seed; A = deployed, B = hardened candidate, C = analysis only)")
    for r in scorecard_rows(summary, addendum):
        print(
            f"  {r['attack']:<29} {POLICY_SHORT[r['policy']]:<36} "
            f"precision {r['precision']:.3f} recall {r['recall']:.3f} "
            f"false-quarantine {r['false_quarantine_rate']:.4f} "
            f"poisoned-accepted {r['poisoned_accepted']:>3} "
            f"model F1 {r['model_f1']:.4f} (naive {r['naive_f1']:.4f}) "
            f"recall {r['model_recall']:.4f} (naive {r['naive_recall']:.4f})"
        )


def _cmd_show(args: argparse.Namespace) -> int:
    run_dir = _run_dir(V2Paths.from_env(), args.config)
    _verified(run_dir)
    summary = json.loads((run_dir / "summary.json").read_text("utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text("utf-8"))
    print(f"CACHED RESULTS (verified) - run {summary['run_id']} finished {summary['finished_at']}")
    print(f"Batch: {summary['batch']['records']} records; {summary['benchmark_label']}")
    nat = summary["natural_disagreement_on_unpoisoned_batch"]
    print(
        f"No-attack false-alarm floor: {nat['quarantined']} quarantined "
        f"({nat['share_quarantined']:.2%})"
    )
    for mode, e in _ordered(summary["attacks"]):
        d = e["detection"]
        print(
            f"\n[{mode}] flipped {e['attack']['flipped']} ({e['attack']['flipped_share']:.3%}), "
            f"seed {e['attack']['seed']}"
        )
        print(
            f"  gate: accepted {e['gate']['accepted']}, quarantined {e['gate']['quarantined']}, "
            f"review {e['gate']['insufficient_evidence']}"
        )
        print(
            f"  detection: TP {d['detected_poison_true_positives']} FP {d['false_positives']} "
            f"FN {d['false_negatives']}  precision {d['detection_precision']:.4f}  "
            f"recall {d['detection_recall']:.4f}  "
            f"false-quarantine rate {d['false_quarantine_rate']:.4f}"
        )
        print(_line("clean reference", summary["models"]["clean_reference"]))
        for name, m in e["models"].items():
            print(_line(name, m))
    addendum = _load_addendum()
    if addendum is not None:
        _print_scorecard(summary, addendum)
    out = run_dir / "judge_report.html"
    out.write_text(render(run_dir, summary, manifest, addendum), encoding="utf-8", newline="\n")
    print(f"\nJudge report: {out}")
    return 0


def _live_hardened(poisoned: SuppliedBatch, sub: list[dict[str, Any]]) -> Any:
    """Policy B for the live demo: sector metadata from the verified addendum run."""
    from compassio_ml.challenges.c05.addendum import _gate_policy, load_addendum
    from compassio_ml.challenges.c05.policy import Metadata, hardened

    add_dir = _addendum_dir(V2Paths.from_env())
    _verified(add_dir)
    sectors = {}
    with (add_dir / "sector_metadata.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            sectors[row["record_id"]] = row["sector_codes"]
    acfg = load_addendum(ADDENDUM_CONFIG)
    meta = Metadata(
        sector_codes=np.array([sectors[r["record_id"]] for r in sub]),
        non_energy=np.array([r["non_energy"] for r in sub]),
    )
    intrinsic = frozenset(str(c) for c in acfg["climate_intrinsic_dac_codes"])
    params = acfg["policies"]["hardened"]
    return _gate_policy(lambda det: hardened(poisoned, det, meta, intrinsic, params))


def _cmd_live(args: argparse.Namespace) -> int:
    """LIVE: attack + detector + gate on a deterministic subsample of the cached clean batch."""
    cfg = load_config(args.config)
    run_dir = _run_dir(V2Paths.from_env(), args.config)
    _verified(run_dir)
    rows = [json.loads(line) for line in (run_dir / "batch_A_clean.jsonl").open(encoding="utf-8")]
    groups = sorted(
        {r["group"] for r in rows}, key=lambda g: hashlib.sha256(g.encode()).hexdigest()
    )
    chosen: set[str] = set()
    size = 0
    per_group: dict[str, int] = {}
    for r in rows:
        per_group[r["group"]] = per_group.get(r["group"], 0) + 1
    for g in groups:  # whole groups only, so group-aware folds stay valid
        if size >= args.sample:
            break
        if per_group[g] > args.sample // 4:
            continue
        chosen.add(g)
        size += per_group[g]
    sub = [r for r in rows if r["group"] in chosen]
    batch = SuppliedBatch.create(
        np.array([r["record_id"] for r in sub]),
        np.array([r["text"] for r in sub]),
        np.array([r["label"] for r in sub]),
        np.array([r["group"] for r in sub]),
        np.array([r["source_id"] for r in sub]),
    )
    print(f"LIVE RUN on {len(batch)} records (deterministic subsample of the verified clean batch)")
    print(f"  attack type: {args.attack}")
    start = time.perf_counter()
    poisoned, oracle = inject_label_flips(
        batch, cfg.attack.rate, args.seed, args.attack, np.array([r["non_energy"] for r in sub])
    )
    print(
        f"  attack: inverted {oracle.count} labels ({oracle.count / len(batch):.2%}), "
        f"seed {args.seed}"
    )
    policy_fn = _live_hardened(poisoned, sub) if args.policy == "hardened" else None
    gate = quarantine_gate(poisoned, cfg, policy=policy_fn)  # oracle not passed
    seconds = time.perf_counter() - start
    quarantined_set, review_set = set(gate.quarantined_ids), set(gate.review_ids)
    status = np.array(
        [
            "quarantined"
            if i in quarantined_set
            else "insufficient_evidence"
            if i in review_set
            else "accepted"
            for i in poisoned.ids
        ]
    )
    d = detection_metrics(
        poisoned.ids,
        status,
        gate.detector.suspicion,
        oracle,
        batch.labels,
        np.array([r["adaptation_only"] for r in sub]),
    )
    label = "B hardened candidate" if args.policy == "hardened" else "A deployed two-signal"
    print(
        f"  policy {label} ({seconds:.1f} s): accepted {len(gate.accepted_ids)}, quarantined "
        f"{len(gate.quarantined_ids)}, insufficient evidence {len(gate.review_ids)} "
        "(kept for training, sent to review)"
    )
    flipped = np.isin(poisoned.ids, np.array(oracle.flipped_ids))
    print(
        "  where the poisoned labels went: "
        f"quarantined {int((flipped & (status == 'quarantined')).sum())}, "
        f"review {int((flipped & (status == 'insufficient_evidence')).sum())}, "
        f"accepted silently {int((flipped & (status == 'accepted')).sum())}"
    )
    print(
        f"  oracle check AFTER the decision: caught {d['detected_poison_true_positives']} of "
        f"{oracle.count} (recall {d['detection_recall']:.2%}), precision "
        f"{d['detection_precision']:.2%}, clean records wrongly quarantined {d['false_positives']}"
    )
    shown = [r for r in gate.report["flagged_records"] if r["status"] == "quarantined"][:3]
    for r in shown:
        print(f"  e.g. {r['record_id']}: {r['reason']}")
    print(f"  detector {cfg.detector_version}; peak process memory {peak_memory_mb()} MB")
    print("  (a flag is evidence for review, not proof that a label was corrupted)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="C05 poisoned training batch quarantine")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run").set_defaults(fn=_cmd_run)
    sub.add_parser("verify").set_defaults(fn=_cmd_verify)
    sub.add_parser("addendum").set_defaults(fn=_cmd_addendum)
    sub.add_parser("show").set_defaults(fn=_cmd_show)
    live = sub.add_parser("live")
    live.add_argument("--sample", type=int, default=3000)
    live.add_argument("--seed", type=int, default=7, help="live-demo attack seed")
    live.add_argument(
        "--policy",
        choices=["two_signal", "hardened"],
        default="two_signal",
        help="two_signal = deployed policy A; hardened = candidate policy B",
    )
    live.add_argument(
        "--attack", choices=["uniform", "targeted_non_energy_positive"], default="uniform"
    )
    live.set_defaults(fn=_cmd_live)
    args = parser.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
