"""Generate an offline judge page and compact, tracked measured evidence from raw receipts."""

import hashlib
import html
import importlib.metadata
import json
import platform
import subprocess
import tracemalloc
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/c11"
DOC = ROOT / "docs/challenges"


def memory_pressure() -> dict[str, int]:
    from compassio_api.core.availability import Admission, Budget

    now = [0.0]
    gate = Admission(
        {"screen": (Budget(1, 2), Budget(100000, 100000))},
        max_keys=1024,
        idle_seconds=2,
        clock=lambda: now[0],
    )
    tracemalloc.start()
    for i in range(1024):
        assert gate.admit(str(i), "screen") == 0
    filled, _ = tracemalloc.get_traced_memory()
    for i in range(1024, 51024):
        assert gate.admit(str(i), "screen") > 0
    churned, peak = tracemalloc.get_traced_memory()
    assert gate.snapshot()["keys"] == 1024
    now[0] = 2
    assert gate.snapshot()["keys"] == 0
    cleared, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "filled_bytes": filled,
        "after_50000_rejected_keys_bytes": churned,
        "peak_bytes": peak,
        "after_expiry_bytes": cleared,
        **gate.snapshot(),
    }


def main() -> None:
    experiments = [
        json.loads((OUT / f"{mode}.json").read_text("utf-8")) for mode in ("baseline", "shield")
    ]
    runs = [run for experiment in experiments for run in experiment["runs"]]
    compact = [{k: v for k, v in run.items() if k != "records"} for run in runs]

    def log_lines(name: str) -> list[str]:
        data = (OUT / name).read_bytes()
        return data.decode("utf-16" if data.startswith(b"\xff\xfe") else "utf-8").splitlines()

    test_lines = log_lines("pytest-final.log")
    receipt: dict[str, Any] = {
        "schema": "c11-evidence-v1",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "policy": "c11-token-bucket-v1",
        "frozen_base": experiments[0]["base_commit"],
        "branch": subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True
        ).strip(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("fastapi", "uvicorn", "httpx2", "scikit-learn")
        },
        "fixtures": experiments[0]["fixture"],
        "integrity_unchanged": all(
            e["integrity_before"] == e["integrity_after"] for e in experiments
        ),
        "deterministic_memory_pressure": memory_pressure(),
        "quality_gates": {
            "pytest_summary": test_lines[-1],
            "pytest_skips": [line for line in test_lines if line.startswith("SKIPPED")],
            "mypy": log_lines("mypy.log"),
            "mypy_scripts": log_lines("mypy-scripts.log"),
            "ruff": log_lines("ruff-final.log"),
            "format": log_lines("format-final.log"),
        },
        "fixture_and_registry_hashes": experiments[0]["integrity_before"],
        "raw_sha256": {
            mode: hashlib.sha256((OUT / f"{mode}.json").read_bytes()).hexdigest()
            for mode in ("baseline", "shield")
        },
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [
                Path(__file__).resolve(),
                ROOT / "scripts/c11_benchmark.py",
                ROOT / "apps/api/src/compassio_api/core/availability.py",
                ROOT / "apps/api/src/compassio_api/main.py",
                ROOT / "apps/api/src/compassio_api/core/config.py",
                ROOT / "apps/api/src/compassio_api/db/session.py",
                ROOT / "uv.lock",
            ]
        },
        "runs": compact,
        "earlier_shield_validation": [
            {k: v for k, v in run.items() if k != "records"}
            for run in json.loads((OUT / "shield-initial-validation.json").read_text("utf-8"))[
                "runs"
            ]
        ]
        if (OUT / "shield-initial-validation.json").exists()
        else [],
    }
    if (OUT / "shield-initial-validation.json").exists():
        receipt["raw_sha256"]["earlier_shield_validation"] = hashlib.sha256(
            (OUT / "shield-initial-validation.json").read_bytes()
        ).hexdigest()
    DOC.mkdir(parents=True, exist_ok=True)
    (DOC / "c11_metrics.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    rows = []
    markdown = []
    for run in runs:
        attack, legit = run["abusive"], run["legitimate"]
        counts = attack["status_counts"]
        recovery = (
            f"{run['recovery_seconds']:.3f}s"
            if run["recovery_seconds"] is not None
            else ">3s (censored)"
        )
        if run["recovery_failure"]:
            recovery = str(run["recovery_failure"])
        vals = [
            run["mode"],
            run["scenario"],
            str(run["iteration"] + 1),
            f"{attack['actual_sent_rps']:.2f}",
            str(counts.get("200", 0)),
            str(counts.get("429", 0)),
            str(sum(v for k, v in counts.items() if k not in ("200", "429"))),
            f"{legit['success_percent']:.1f}%",
            f"{legit['latency_ms']['p95']:.1f}ms",
            recovery,
            "STOPPED" if run["safety_aborted"] else "complete",
        ]
        rows.append("<tr>" + "".join(f"<td>{html.escape(v)}</td>" for v in vals) + "</tr>")
        markdown.append("| " + " | ".join(vals) + " |")
    header = [
        "Mode",
        "Scenario",
        "Run",
        "Sent bot rps",
        "Bot 200",
        "Bot 429",
        "Bot other/fail",
        "Legit 2xx",
        "Legit p95",
        "Recovery",
        "Safety",
    ]
    table = "| " + " | ".join(header) + " |\n|" + "---|" * len(header) + "\n" + "\n".join(markdown)
    shield_runs = [run for run in runs if run["mode"] == "shield"]
    independent = [run for run in shield_runs if run["scenario"] != "shared_ip"]
    legit_total = sum(run["legitimate"]["sent"] for run in independent)
    legit_ok = sum(run["legitimate"]["status_counts"].get("200", 0) for run in independent)
    rejected = sum(run["abusive"]["status_counts"].get("429", 0) for run in shield_runs)
    rates = [run["abusive"]["actual_sent_rps"] for run in shield_runs]
    summary = (
        f"Final shield dispatch rate: **{min(rates):.2f}-{max(rates):.2f} bot rps**. "
        f"Independent legitimate requests: **{legit_ok}/{legit_total} HTTP 200**. "
        f"Abusive HTTP 429 responses: **{rejected}**. Shared-IP results are separate below. "
        "Near-target rates reflect measured scheduler variation; "
        "exact per-run values are shown.\n\n"
    )
    (DOC / "c11_results.md").write_text(
        "# C11 measured results\n\n"
        "Real local TCP/HTTP; artificial tiny models and invented database through the real "
        "guarded loaders and endpoints. No canonical-model capacity claim. Up to two repetitions "
        "per scenario; fresh one-worker server each time. Target: 800 abusive + 16 legitimate "
        "requests over four seconds; 200 bot rps plus four legitimate rps. Unsafe baseline "
        "scenarios stop early and omit their repeat. Actual dispatch rates are shown below; "
        "server ingress timing (including legitimate load) is also recorded independently.\n\n"
        + summary
        + table
        + "\n\nAll status counts, latency p50/p95/p99, process CPU seconds (including startup), "
        "RSS, scheduling lag, state counters and example 429 headers are in "
        "[c11_metrics.json](c11_metrics.json). Raw per-request records stay in artifacts/c11. "
        "Recovery polls the exhausted attacking peer for up to three seconds after draining "
        "the burst; null is censored, not a timeout or successful recovery.\n\n"
        "The baseline already rejects abuse and preserves independent-peer request success. "
        "C11 adds bounded state, a cross-peer safety ceiling, separate read budgets and faster "
        "continuous recovery. Shared-IP screening callers cannot be distinguished; mixed-route "
        "read access can survive while shared-IP screening is throttled. Small legitimate "
        "sample sizes and fixture inference limit generalization. Earlier shield validation, "
        "when available, is retained separately in the receipt (including below-target runs). "
        "Final protocol bounds pending dispatches to 128 "
        "(64 active HTTP + 64 queued) and clears stale process receipts before launching.\n",
        encoding="utf-8",
    )
    bars = []
    rejection_bars = []
    for scenario in ("single", "distributed", "mixed", "shared_ip"):
        for mode, color in (("baseline", "#d2863b"), ("shield", "#20a884")):
            selected = [r for r in runs if r["scenario"] == scenario and r["mode"] == mode]
            latency = sum(r["legitimate"]["latency_ms"]["p95"] for r in selected) / len(selected)
            bars.append(
                f"<div>{scenario} / {mode}: {latency:.1f} ms "
                f'<span style="display:block;background:{color};height:16px;'
                f'width:{min(100, latency / 15):.1f}%"></span></div>'
            )
            rejected = sum(r["abusive"]["status_counts"].get("429", 0) for r in selected)
            sent = sum(r["abusive"]["sent"] for r in selected)
            fraction = rejected / sent * 100
            rejection_bars.append(
                f"<div>{scenario} / {mode}: {rejected}/{sent} HTTP 429 ({fraction:.1f}%)"
                f'<span style="display:block;background:{color};height:16px;'
                f'width:{fraction:.1f}%"></span></div>'
            )
    example = next(r["example_429"] for r in runs if r["mode"] == "shield")
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>Compassio C11 Availability Shield</title><style>
body{{font:16px system-ui;max-width:1200px;margin:32px auto;padding:24px;
background:#f3f8f6;color:#183b36}}
table{{border-collapse:collapse;width:100%;font-size:14px}}
td,th{{padding:8px;border-bottom:1px solid #bdceca}}
pre{{white-space:pre-wrap;background:#e0ece8;padding:16px}}svg{{width:100%;height:110px}}
</style><h1>Compassio Availability Shield</h1>
<p>Measured bounded local HTTP at 200 offered bot requests/second, with simultaneous normal traffic.
Artificial model/data fixtures; genuine socket identities.
One worker, direct loopback, no proxy headers.</p>
<svg viewBox="0 0 1100 110" role="img" aria-label="Admission policy diagram">
<g fill="#d9eee6" stroke="#24735f"><rect x="5" y="20" width="230" height="65"/>
<rect x="285" y="20" width="340" height="65"/><rect x="675" y="20" width="410" height="65"/></g>
<g font-size="17" fill="#183b36"><text x="20" y="47">CORS → size → access</text>
<text x="250" y="57">→</text><text x="300" y="47">Peer + global bucket / route class</text>
<text x="300" y="72">429 + Retry-After on exhaustion</text><text x="642" y="57">→</text>
<text x="690" y="47">Admitted: existing auth → inference / read DB</text>
<text x="690" y="72">Separate read budgets and identity capacity</text></g></svg>
<h2>Measured before / after</h2><table><thead><tr>
{"".join(f"<th>{h}</th>" for h in header)}</tr></thead><tbody>{"".join(rows)}</tbody></table>
<h2>Mean of run-level legitimate p95 latencies</h2>{"".join(bars)}
<h2>Abusive requests rejected by admission</h2>{"".join(rejection_bars)}
<h2>Genuine HTTP 429 example</h2><pre>{html.escape(json.dumps(example, indent=2))}</pre>
<h2>Limits</h2><p>An IP limiter cannot distinguish devices behind NAT
or defeat a distributed botnet.
Global screening ceilings can throttle legitimate screening under identity churn. Read capacity is
separate. This fixture experiment does not establish canonical-model or unlimited-load capacity.
Baseline already throttles. Raw timing receipts are local in artifacts/c11;
compact metrics accompany
this page. No external assets, scripts, network calls or chart libraries are required.</p></html>"""
    (DOC / "c11_judge_results.html").write_text(page, encoding="utf-8")
    print("Generated c11_metrics.json, c11_results.md, c11_judge_results.html")


if __name__ == "__main__":
    main()
