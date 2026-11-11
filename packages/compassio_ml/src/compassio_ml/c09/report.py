"""Deterministic aggregate evidence and an escaped, self-contained offline HTML scorecard."""

import html
import json
import time
import tracemalloc
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np

from compassio_ml.c09.attacks import KINDS, Edit, distance, replay
from compassio_ml.c09.benchmark import git, integrity, load_model, protocol, read, write
from compassio_ml.c09.guard import GuardedClassifier, normalize
from compassio_ml.integrity.hashing import sha256_file


def distribution(values: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p95": float(np.quantile(values, 0.95)),
        "max": float(np.max(values)),
    }


def metrics(rows: list[dict[str, Any]], score: str, threshold: float) -> dict[str, Any]:
    clean = np.array([r["clean_score"] for r in rows])
    perturbed = np.array([r[score] for r in rows])
    delta = perturbed - clean
    old, new = clean >= threshold, perturbed >= threshold
    y = np.array([r["y"] for r in rows], dtype=bool)
    out: dict[str, Any] = {
        "pairs": len(rows),
        "unique_records": len({r["candidate_id"] for r in rows}),
        "changed_inputs": sum(r["receipt"]["edit_distance"] > 0 for r in rows),
        "flips": int(np.sum(old != new)),
        "flip_rate": float(np.mean(old != new)),
        "absolute_score_shift": distribution(abs(delta)),
        "score_inflation_any": int(np.sum(delta > 1e-12)),
        "score_reduction_any": int(np.sum(delta < -1e-12)),
        "score_inflation_ge_001": int(np.sum(delta >= 0.01)),
        "score_reduction_ge_001": int(np.sum(delta <= -0.01)),
        "negative_to_positive": int(np.sum(~old & new)),
        "positive_to_negative": int(np.sum(old & ~new)),
        "clean_positive_pairs": int(np.sum(old)),
        "clean_negative_pairs": int(np.sum(~old)),
        "changed_only_flip_rate": (
            float(np.sum(old != new)) / sum(r["receipt"]["edit_distance"] > 0 for r in rows)
            if any(r["receipt"]["edit_distance"] > 0 for r in rows)
            else 0.0
        ),
        "climate_positive_records": int(y.sum()),
        "clean_false_negatives": int(np.sum(y & ~old)),
        "attacked_false_negatives": int(np.sum(y & ~new)),
        "new_false_negatives": int(np.sum(y & old & ~new)),
        "review_pairs": sum(bool(r["review"]) for r in rows),
        "unstable_pairs": sum(bool(r["unstable_input"]) for r in rows),
        "guard_unflagged_flips": sum(
            bool(a != b and not r["review"]) for a, b, r in zip(old, new, rows, strict=True)
        ),
    }
    for name in ("non_energy", "adaptation_only"):
        mask = np.array([r[name] for r in rows], dtype=bool)
        positives = mask & y
        out[name] = {
            "pairs": int(mask.sum()),
            "positives": int(positives.sum()),
            "flips": int(np.sum(mask & (old != new))),
            "new_false_negatives": int(np.sum(positives & old & ~new)),
            "clean_false_negatives": int(np.sum(positives & ~old)),
            "attacked_false_negatives": int(np.sum(positives & ~new)),
            "unique_positive_records": len({r["candidate_id"] for r in rows if r[name] and r["y"]}),
            "small_slice_warning": len({r["candidate_id"] for r in rows if r[name] and r["y"]})
            < 15,
        }
    return out


def validate_evidence(baseline: list[dict[str, Any]], guarded: list[dict[str, Any]]) -> None:
    index = {(r["candidate_id"], r["attack"]): r for r in baseline}
    for row in guarded:
        receipt = row["receipt"]
        fields = (row["original_fields"][0], row["original_fields"][1])
        edits = tuple(Edit(**e) for e in receipt["edits"])
        changed = replay(fields, edits)
        if list(changed) != receipt["fields"]:
            raise ValueError("receipt replay mismatch")
        d = sum(distance(a, b, len(edits)) for a, b in zip(fields, changed, strict=True))
        if d != receipt["edit_distance"] or 50 * d > receipt["eligible_characters"]:
            raise ValueError("budget mismatch")
        for text in (*fields, *changed):
            n = normalize(text).text
            if normalize(n).text != n:
                raise ValueError("non-idempotent normalization")
        if not row["attack"].startswith("adaptive_"):
            original = index[(row["candidate_id"], row["attack"])]
            for key in ("receipt", "clean_score", "perturbed_score"):
                if original[key] != row[key]:
                    raise ValueError(f"unpaired comparison: {key}")


def performance(source: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    model = load_model(source)
    adapter = GuardedClassifier(model)
    fields = [(r["title"], r["description"]) for r in records if r["split"] == "assessment"][:64]
    model.predict(*fields[0])
    adapter.predict(*fields[0])
    result: dict[str, Any] = {}
    for name, predict in (("raw", model.predict), ("guarded", adapter.predict)):
        timings: list[float] = []
        for _ in range(3):
            for pair in fields:
                start = time.perf_counter_ns()
                predict(*pair)
                timings.append((time.perf_counter_ns() - start) / 1e6)
        # Allocator measurement is separate so tracing does not inflate latency.
        tracemalloc.start()
        for pair in fields:
            predict(*pair)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        result[name] = {
            "latency_ms": distribution(np.array(timings)),
            "python_peak_bytes": peak,
            "calls": len(timings),
        }
    result["mean_latency_ratio"] = (
        result["guarded"]["latency_ms"]["mean"] / result["raw"]["latency_ms"]["mean"]
    )
    result["python_peak_delta_bytes"] = (
        result["guarded"]["python_peak_bytes"] - result["raw"]["python_peak_bytes"]
    )
    result["memory_scope"] = (
        "Python traced peak incremental allocations; excludes native/RSS/model loading"
    )
    # Explicitly ARTIFICIAL metadata engineering control, on a real unchanged text.
    control = [
        adapter.predict(*fields[0], amount=Decimal(v), currency="USD").guarded_score
        for v in ("100.00", "98.00", "102.00")
    ]
    result["unused_numeric_metadata_control"] = {
        "amounts": ["100.00", "98.00", "102.00"],
        "scores": control,
        "absolute_score_shift": max(control) - min(control),
        "scope": "Artificial metadata control; no observed finance or numeric model inputs.",
    }
    return result


def render_html(output: Path, aggregate: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    threshold = protocol()["threshold"]

    def esc(value: object) -> str:
        return html.escape(str(value))

    table: list[str] = []
    for name, m in aggregate["assessment"].items():
        table.append(
            f"<tr><th>{esc(name)}</th><td>{m['pairs']}</td><td>{m['flips']}</td>"
            f"<td>{m['flip_rate']:.3%}</td><td>{m['absolute_score_shift']['p95']:.6f}</td>"
            f"<td>{m['new_false_negatives']}</td><td>{m['review_pairs']}</td></tr>"
        )
    # Display all examples offline; failures sorted first, never hidden.
    cases = []
    assessment = [r for r in rows if r["split"] == "assessment"]
    assessment.sort(
        key=lambda r: (
            -int((r["guarded_score"] >= threshold) != (r["clean_score"] >= threshold)),
            -abs(r["guarded_score"] - r["clean_score"]),
            r["candidate_id"],
            r["attack"],
        )
    )
    for r in assessment:
        original = "\n".join(r["original_fields"])
        changed = "\n".join(r["receipt"]["fields"])
        # Escaped representation makes otherwise invisible perturbations inspectable.
        visible = changed.encode("unicode_escape").decode("ascii")
        raw_flip = (r["perturbed_score"] >= threshold) != (r["clean_score"] >= threshold)
        guard_flip = (r["guarded_score"] >= threshold) != (r["clean_score"] >= threshold)
        cases.append(
            f"<details><summary>{esc(r['candidate_id'])} · {esc(r['attack'])} · "
            f"{r['receipt']['edit_percent']:.4f}% · raw flip {raw_flip} · "
            f"guarded flip {guard_flip}</summary>"
            f"<p>Original {r['clean_score']:.9f} | Perturbed {r['perturbed_score']:.9f} | "
            f"Guarded {r['guarded_score']:.9f} | Review {r['review']}</p>"
            f"<p>{r['receipt']['edit_distance']} edits / "
            f"{r['receipt']['eligible_characters']} eligible "
            f"original characters. Query pool {r['query_count']} (shared by directions).</p>"
            f"<h3>Original</h3><pre>{esc(original)}</pre><h3>Manipulated</h3><pre>{esc(changed)}</pre>"
            f"<h3>Visible Unicode escapes</h3><pre>{esc(visible)}</pre>"
            "<h3>Exact edit receipt</h3>"
            f"<pre>{esc(json.dumps(r['receipt']['edits'], indent=2))}</pre></details>"
        )
    document = (
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<title>Compassio C09 scorecard</title>"
        "<style>body{font:16px system-ui;max-width:1200px;margin:40px auto;"
        "padding:20px;background:#f5f8f6;color:#173e35}"
        "table{border-collapse:collapse;width:100%}td,th{padding:9px;border:1px solid #bbcfc7;"
        "text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:16px}"
        "details{margin:12px 0;border:1px solid #bbcfc7;padding:12px}"
        "summary{cursor:pointer}</style>"
        "<h1>Compassio C09 · Adversarial feature perturbation</h1>"
        "<p>Challenge benchmark evidence on sampled development-validation records. "
        "Not an independent external test, impact assessment, green rating or funding decision. "
        "Donor labels are unverified. Every example below is a measured source record.</p>"
        f"<p>Frozen ML v2 threshold: {threshold}. Guard: {esc(protocol()['guard_version'])}. "
        "Review flags do not count as prevented flips. "
        "Zero-edit attacks remain in denominators.</p>"
        "<table><tr><th>Assessment comparison</th><th>Pairs</th><th>Flips</th><th>Flip rate</th>"
        "<th>P95 absolute shift</th><th>New positive FNs</th><th>Review pairs</th></tr>"
        + "".join(table)
        + "</table>"
        "<h2>Limits and known failures</h2><p>Duplicated-letter typos are not repaired. "
        "Unsupported or whole-script confusables may remain. Normalization can shift a clean "
        "near-threshold record. The fixed search is bounded random score search, not a global "
        "robustness certificate. Administrative-word edits are a conservative operational "
        "meaning-preservation rule, not human-verified equivalence.</p>"
        "<h2>Clean inputs, slices, performance and integrity</h2><pre>"
        + esc(json.dumps(aggregate, indent=2))
        + "</pre><h2>Measured examples (failures first)</h2>"
        + "".join(cases)
        + "<footer>Source: FCDO IATI (OGL v3.0), EC DG INTPA IATI "
        "(EU-owned content CC BY 4.0; third-party rights may differ). Compassio modifications "
        "are explicitly shown. Local internal research only; "
        "do not redistribute source texts.</footer></html>"
    )
    (output / "scorecard.html").write_text(document, "utf-8")


def report(source: Path, output: Path) -> None:
    p = protocol()
    baseline, guarded = read(output / "baseline.json"), read(output / "guarded.json")
    validate_evidence(baseline, guarded)
    aggregate: dict[str, Any] = {"evidence": "C09 challenge benchmark, development records only"}
    for split in ("tuning", "assessment"):
        selected = [r for r in guarded if r["split"] == split]
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in selected:
            groups[r["attack"]].append(r)
        aggregate[split] = {}
        for attack_name, cases in groups.items():
            for label, key in (("raw", "perturbed_score"), ("guarded", "guarded_score")):
                aggregate[split][f"{attack_name}/{label}"] = metrics(cases, key, p["threshold"])
        fixed = [r for r in selected if r["attack"] in KINDS]
        transferred = [r for r in selected if r["attack"].startswith("search_")]
        adaptive = [r for r in selected if r["attack"].startswith("adaptive_")]
        for name, cases in (
            ("fixed", fixed),
            ("transferred_search", transferred),
            ("adaptive", adaptive),
        ):
            for label, key in (("raw", "perturbed_score"), ("guarded", "guarded_score")):
                aggregate[split][f"ALL_{name}/{label}"] = metrics(cases, key, p["threshold"])
        unique = {r["candidate_id"]: r for r in selected}
        clean = list(unique.values())
        aggregate[f"{split}_clean"] = {
            "records": len(clean),
            "positives": sum(r["y"] for r in clean),
            "non_energy": sum(r["non_energy"] for r in clean),
            "adaptation_only": sum(r["adaptation_only"] for r in clean),
            "disagreements": sum(
                (r["clean_score"] >= p["threshold"]) != (r["clean_guarded_score"] >= p["threshold"])
                for r in clean
            ),
            "review": sum(r["clean_review"] for r in clean),
            "absolute_shift": distribution(
                np.array([abs(r["clean_guarded_score"] - r["clean_score"]) for r in clean])
            ),
        }
    before, after = read(output / "integrity_before.json"), integrity(source)
    write(output / "integrity_after.json", after)
    immutable_refs = (
        "main",
        "backend-ready-for-battleverse^{commit}",
        "challenge/c05-poison-quarantine",
    )
    aggregate["integrity"] = {
        "resources": before["resources"] == after["resources"],
        "tracked": before["tracked"] == after["tracked"],
        "frozen_and_c05_refs": all(
            before["protected_refs"][k] == after["protected_refs"][k] for k in immutable_refs
        ),
    }
    write(
        output / "integrity_comparison.json",
        {
            **aggregate["integrity"],
            "frontend_ref_unchanged_during_run": (
                before["protected_refs"]["feature/task010-complete-frontend"]
                == after["protected_refs"]["feature/task010-complete-frontend"]
            ),
            "before_refs": before["protected_refs"],
            "after_refs": after["protected_refs"],
            "note": (
                "Concurrent frontend commits are external activity; C09 never writes that branch."
            ),
        },
    )
    if not all(aggregate["integrity"][k] for k in ("resources", "tracked", "frozen_and_c05_refs")):
        raise ValueError("protected resource/ref changed; inspect integrity receipts")
    aggregate["maximum_edit_percent"] = max(r["receipt"]["edit_percent"] for r in guarded)
    aggregate["query_accounting"] = {
        "baseline_oracle_per_record": p["query_budget_per_direction"],
        "adaptive_oracle_per_record": p["query_budget_per_direction"],
        "directions_share_pool": True,
        "note": (
            "Oracle queries are candidate requests; clean, five fixed probes and diagnostic "
            "rescoring are separate. Guard requests use one or two frozen-model evaluations."
        ),
    }
    aggregate["query_accounting"]["measured_totals"] = {}
    for mode in ("baseline", "guarded"):
        queries = read(output / f"{mode}_queries.json")
        trials = read(output / f"{mode}_trials.json")
        if len(trials) != sum(q["oracle_requests"] for q in queries):
            raise ValueError("missing query trial receipts")
        if any(q["oracle_requests"] != p["query_budget_per_direction"] for q in queries):
            raise ValueError("query budget mismatch")
        aggregate["query_accounting"]["measured_totals"][mode] = {
            "records": len(queries),
            "oracle_requests": len(trials),
            "oracle_model_evaluations": sum(q["oracle_model_evaluations"] for q in queries),
            "all_model_evaluations_including_diagnostics": sum(
                q["all_model_evaluations_including_diagnostics"] for q in queries
            ),
        }
    write(output / "metrics.json", aggregate)
    write(output / "performance.json", performance(source, read(output / "records.json")))
    render_html(
        output,
        {
            **aggregate,
            "performance": read(output / "performance.json"),
            "integrity_observation": read(output / "integrity_comparison.json"),
        },
        guarded,
    )
    # Provenance and timing are separate from deterministic metrics.
    write(
        output / "run_receipt.json",
        {
            "commit": git("rev-parse", "HEAD"),
            "dirty": bool(git("status", "--porcelain")),
            "hashes": {
                name: sha256_file(output / name)
                for name in (
                    "records.json",
                    "split_manifest.json",
                    "baseline.json",
                    "guarded.json",
                    "metrics.json",
                    "baseline_queries.json",
                    "guarded_queries.json",
                    "baseline_trials.json",
                    "guarded_trials.json",
                    "performance.json",
                    "scorecard.html",
                    "integrity_before.json",
                    "integrity_after.json",
                    "integrity_comparison.json",
                )
            },
            "source_code_sha256": {
                f.name: sha256_file(f) for f in Path(__file__).parent.glob("*.py")
            },
            "protocol": p,
            "no_training": True,
            "no_sealed_evaluation_payloads_read": True,
        },
    )
    print(
        json.dumps(
            {
                "assessment_fixed_raw": aggregate["assessment"]["ALL_fixed/raw"]["flips"],
                "assessment_fixed_guarded": aggregate["assessment"]["ALL_fixed/guarded"]["flips"],
                "clean_disagreements": aggregate["assessment_clean"]["disagreements"],
                "integrity": aggregate["integrity"],
            }
        )
    )
