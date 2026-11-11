"""Latency profile of a RUNNING local API on the real database (standard library only).

    uv run python scripts/bench_api.py --base http://127.0.0.1:8000 [--repeat 5] [--out f.json]

Start the server freshly (and with COMPASSIO_PRELOAD_MODELS=false to measure first-load model
latency). For each request: the FIRST call (cold: includes caches and lazy model loading) and
the median of ``--repeat`` further calls (warm). Wall-clock from this client, so includes HTTP
overhead. Read-only; never sends save=true.
"""

import argparse
import json
import platform
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

TEXT = {
    "title": "Example solar mini-grid for rural health clinics",
    "description": "Example text: solar photovoltaic panels and batteries replace diesel.",
}
# Ten real GCF export ids (FP006 does not exist in the export).
GCF10 = [f"gcf_projects:FP{n:03d}" for n in (1, 2, 3, 4, 5, 7, 8, 9, 10, 11)]
CASES: list[tuple[str, str, str, Any]] = [
    ("discovery: list page 1", "GET", "/api/v1/projects?page_size=25", None),
    ("discovery: filters", "GET", "/api/v1/filters", None),
    ("discovery: text search", "GET", "/api/v1/projects?q=solar&page_size=25", None),
    (
        "discovery: PAK + sector filter",
        "GET",
        "/api/v1/projects?country=PAK&sector=Energy&page_size=25",
        None,
    ),
    ("discovery: deep page", "GET", "/api/v1/projects?page=500&page_size=25", None),
    ("detail", "GET", "/api/v1/projects/aiddata:35266", None),
    (
        "insight: funding by country",
        "GET",
        "/api/v1/analytics/funding-by-country?metric=cfu_approvals_usd",
        None,
    ),
    (
        "insight: funding by sector",
        "GET",
        "/api/v1/analytics/funding-by-sector?metric=cfu_approvals_usd",
        None,
    ),
    (
        "insight: approved vs disbursed PAK",
        "GET",
        "/api/v1/analytics/approved-vs-disbursed?country=PAK",
        None,
    ),
    ("insight: country profile PAK", "GET", "/api/v1/analytics/country-profile/PAK", None),
    ("insight: coverage", "GET", "/api/v1/analytics/coverage", None),
    (
        "compare: 3 records",
        "POST",
        "/api/v1/decision/compare",
        {"project_ids": ["gcf_projects:FP085", "aiddata:35266", "aiddata:54087"]},
    ),
    (
        "compare: 10 records",
        "POST",
        "/api/v1/decision/compare",
        {"project_ids": GCF10},
    ),
    (
        "prioritize: CFU PAK (31)",
        "POST",
        "/api/v1/decision/prioritize",
        {"filters": {"country": "PAK", "source": "climate_funds_update"}, "page_size": 25},
    ),
    (
        "prioritize: all PAK sources",
        "POST",
        "/api/v1/decision/prioritize",
        {"filters": {"country": "PAK"}, "page_size": 25},
    ),
    (
        "prioritize: GCF projects",
        "POST",
        "/api/v1/decision/prioritize",
        {"filters": {"source": "gcf_projects"}, "page_size": 25},
    ),
    (
        "scenario: 10 projects",
        "POST",
        "/api/v1/decision/scenarios",
        {
            "budget": {"amount": "10000000", "currency": "USD"},
            "project_ids": GCF10,
            "method": "equal",
            "constraints": {"max_per_project": "1500000"},
        },
    ),
    ("screening: ML v1 text", "POST", "/api/v1/screening/text", {**TEXT, "model": "ml_v1"}),
    ("screening: ML v2 text", "POST", "/api/v1/screening/text", {**TEXT, "model": "ml_v2"}),
    ("screening: ML v2 DB record", "POST", "/api/v1/screening/projects/aiddata:35266", {}),
]


def call(base: str, method: str, path: str, body: Any) -> tuple[int, float, Any]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            status, payload = resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        status, payload = exc.code, json.loads(exc.read() or b"null")
    return status, (time.perf_counter() - start) * 1000, payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--out")
    args = parser.parse_args()
    base = args.base.rstrip("/")
    rows = []
    for name, method, path, body in CASES:
        status, first, payload = call(base, method, path, body)
        warm = [call(base, method, path, body)[1] for _ in range(args.repeat)]
        note = ""
        if isinstance(payload, dict):
            if "candidates" in payload:
                note = f"candidates={payload['candidates']}"
            elif "pagination" in payload:
                note = f"total_items={payload['pagination']['total_items']}"
            elif "code" in payload:
                note = str(payload["code"])
        rows.append(
            {
                "case": name,
                "status": status,
                "first_ms": round(first, 1),
                "warm_median_ms": round(statistics.median(warm), 1),
                "note": note,
            }
        )
        print(
            f"{status}  first {first:8.1f} ms  warm median {statistics.median(warm):8.1f} ms  "
            f"{name} {note}"
        )
    if args.out:
        env = {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "repeat": args.repeat,
        }
        Path(args.out).write_text(
            json.dumps({"environment": env, "rows": rows}, indent=1), encoding="utf-8"
        )
    return 0 if all(r["status"] < 500 for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
