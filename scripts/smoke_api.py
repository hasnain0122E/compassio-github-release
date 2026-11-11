"""End-to-end smoke test of a RUNNING local Compassio API over real HTTP (standard library only).

    uv run python scripts/smoke_api.py                                  # http://127.0.0.1:8000
    uv run python scripts/smoke_api.py --base http://127.0.0.1:8001 --capture out.json

Walks the demo journey (search -> detail -> ML screening -> evidence -> insights -> compare ->
prioritize -> hypothetical scenario) plus negative cases, asserting each step. Every number it
checks comes from the API's own responses on the real database; nothing is hard-coded except
real record identifiers. ``--capture`` writes trimmed request/response pairs (long strings cut,
lists shortened) for docs/hackathon/demo_api_examples.md. Read-only: it never sends save=true.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any

SCREEN_TEXT = {
    "title": "Example solar mini-grid for rural health clinics",
    "description": "Example text: install solar photovoltaic panels and battery storage to "
    "replace diesel generators at district health facilities.",
}


def _lower(headers: Any) -> dict[str, str]:
    return {str(k).lower(): str(v) for k, v in headers.items()}


class Smoke:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.log: list[dict[str, Any]] = []
        self.failures: list[str] = []

    def call(
        self, method: str, path: str, body: Any = None, raw: bytes | None = None
    ) -> tuple[int, Any, dict[str, str]]:
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                status, payload, headers = (
                    resp.status,
                    json.loads(resp.read()),
                    _lower(resp.headers),
                )
        except urllib.error.HTTPError as exc:
            payload = json.loads(exc.read() or b"null")
            status, headers = exc.code, _lower(exc.headers)
        elapsed = round((time.perf_counter() - start) * 1000, 1)
        self.log.append(
            {
                "method": method,
                "path": path,
                "request": body if raw is None else f"<{len(raw)} raw bytes>",
                "status": status,
                "elapsed_ms": elapsed,
                "response": payload,
            }
        )
        return status, payload, headers

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'}  {name}{(': ' + detail) if detail else ''}")
        if not ok:
            self.failures.append(name)


def run(s: Smoke) -> None:
    status, health, _ = s.call("GET", "/health")
    s.check("health", status == 200, str(health))
    status, models, headers = s.call("GET", "/api/v1/models")
    mode = models.get("operational", {})
    s.check(
        "models: authorized local demo, ML v2 default, ML v1 fallback",
        status == 200
        and mode.get("mode") == "authorized_local_demo"
        and mode.get("default_model") == "ml_v2"
        and mode.get("fallback_model") == "ml_v1",
        f"{mode.get('mode')} default={mode.get('default_model')} "
        f"fallback={mode.get('fallback_model')} access={headers.get('x-compassio-data-access')}",
    )

    # 1. discovery
    status, page, _ = s.call("GET", "/api/v1/projects?q=hydropower&country=PAK&page_size=5")
    s.check(
        "search PAK hydropower",
        status == 200 and page["pagination"]["total_items"] > 0,
        f"{page.get('pagination')}",
    )
    status, page2, _ = s.call(
        "GET", "/api/v1/projects?country=PAK&source=aiddata&page=2&page_size=5"
    )
    s.check("pagination page 2", status == 200 and page2["pagination"]["page"] == 2)
    status, detail, _ = s.call("GET", "/api/v1/projects/aiddata:35266")
    s.check("project detail", status == 200 and detail["id"] == "aiddata:35266")

    # 2. ML screening
    status, v2, _ = s.call("POST", "/api/v1/screening/text", SCREEN_TEXT)
    s.check(
        "screening text with ML v2 (default engine)",
        status == 200 and v2["model"]["model_key"] == "ml_v2" and not v2["saved"],
        f"score={v2.get('prediction', {}).get('label_score')} band="
        f"{v2.get('prediction', {}).get('band')}",
    )
    status, v1, _ = s.call("POST", "/api/v1/screening/text", {**SCREEN_TEXT, "model": "ml_v1"})
    s.check(
        "screening text with ML v1 (fallback available)",
        status == 200 and v1["model"]["model_key"] == "ml_v1",
        f"score={v1.get('prediction', {}).get('label_score')}",
    )
    status, proj, _ = s.call("POST", "/api/v1/screening/projects/aiddata:35266", {})
    s.check(
        "screening a permitted DB record keeps source evidence",
        status == 200 and proj["source_evidence"]["project_id"] == "aiddata:35266",
        f"model={proj.get('model', {}).get('model_key')}",
    )
    status, denied, _ = s.call("POST", "/api/v1/screening/projects/gcf_projects:FP085", {})
    s.check(
        "screening a non-permitted source is refused",
        status == 403 and denied["code"] == "source_not_permitted_for_model_input",
    )

    # 3. evidence and insights
    status, ev, _ = s.call("GET", "/api/v1/decision/evidence/aiddata:35266")
    s.check("evidence", status == 200 and ev["project"]["project_id"] == "aiddata:35266")
    metric = "adb_disbursements_usd"
    status, by_country, _ = s.call("GET", f"/api/v1/analytics/funding-by-country?metric={metric}")
    status_t, trends, _ = s.call("GET", f"/api/v1/analytics/trends?metric={metric}&country=PAK")
    pak = next(g for g in by_country["groups"] if g["key"] == "PAK")
    trend_sum = sum(
        (Decimal(p["total"]) for p in trends["points"] if p["total"] is not None), Decimal(0)
    )
    s.check(
        "insight total equals protected trends total (finance contract)",
        status == status_t == 200 and Decimal(pak["total"]) == trend_sum,
        f"PAK {metric} {pak['total']}",
    )
    status, _avd, _ = s.call("GET", "/api/v1/analytics/approved-vs-disbursed?country=PAK")
    s.check("approved vs disbursed", status == 200)
    status, _profile, _ = s.call("GET", "/api/v1/analytics/country-profile/PAK")
    s.check("country profile PAK", status == 200)

    # 4. comparison
    status, cmp, _ = s.call(
        "POST",
        "/api/v1/decision/compare",
        {"project_ids": ["gcf_projects:FP085", "aiddata:35266", "aiddata:54087"]},
    )
    aid = [g for g in cmp["comparable_groups"] if g["source_id"] == "aiddata"]
    s.check(
        "same-package AidData pair: shown, flagged, never totalled",
        status == 200
        and aid
        and all(g["selection_total"] is None for g in aid)
        and any(
            w["relation_type"] == "same_source_record_group" for w in cmp["duplicate_warnings"]
        ),
    )
    status, cmp2, _ = s.call(
        "POST",
        "/api/v1/decision/compare",
        {"project_ids": ["climate_funds_update:projects-r10", "gcf_projects:FP005"]},
    )
    s.check(
        "cross-source linked pair: never summed",
        status == 200
        and all(g["selection_total"] is None for g in cmp2["comparable_groups"])
        and any(
            w["relation_type"] == "cross_source_reference_code" for w in cmp2["duplicate_warnings"]
        ),
    )

    # 5. prioritization (deterministic)
    request = {
        "filters": {"country": "PAK", "source": "climate_funds_update"},
        "sectors_of_interest": ["energy"],
        "countries_of_interest": ["PAK"],
        "page_size": 5,
    }
    status, r1, _ = s.call("POST", "/api/v1/decision/prioritize", request)
    status2, r2, _ = s.call("POST", "/api/v1/decision/prioritize", request)
    s.check(
        "ranking deterministic (same fingerprint and order)",
        status == status2 == 200
        and r1["ranking_fingerprint"] == r2["ranking_fingerprint"]
        and [i["project_id"] for i in r1["items"]] == [i["project_id"] for i in r2["items"]],
        f"candidates={r1.get('candidates')} fingerprint={r1.get('ranking_fingerprint', '')[:12]}",
    )

    # 6. hypothetical scenario (exact conservation)
    ids = [i["project_id"] for i in r1["items"][:3]]
    status, sc, _ = s.call(
        "POST",
        "/api/v1/decision/scenarios",
        {"budget": {"amount": "1000000", "currency": "USD"}, "project_ids": ids, "method": "equal"},
    )
    allocated = sum((Decimal(a["allocation"]) for a in sc["allocations"]), Decimal(0))
    s.check(
        "scenario: allocations + unallocated == budget exactly",
        status == 200
        and allocated + Decimal(sc["unallocated"]) == Decimal("1000000")
        and allocated == Decimal(sc["allocated_total"]),
        f"{[a['allocation'] for a in sc['allocations']]} unallocated={sc.get('unallocated')}",
    )

    # 7. invalid and unauthorized requests
    negatives = [
        (
            "compare with one id",
            "POST",
            "/api/v1/decision/compare",
            {"project_ids": ["aiddata:35266"]},
            422,
            None,
        ),
        (
            "unknown request field",
            "POST",
            "/api/v1/decision/compare",
            {"project_ids": ["aiddata:35266", "aiddata:54087"], "extra": 1},
            422,
            None,
        ),
        (
            "unsupported scenario objective",
            "POST",
            "/api/v1/decision/scenarios",
            {
                "budget": {"amount": "1", "currency": "USD"},
                "project_ids": ids,
                "objective": "maximize_emission_reductions",
            },
            422,
            "objective_not_supported",
        ),
        (
            "unknown project",
            "GET",
            "/api/v1/projects/aiddata:example_missing",
            None,
            404,
            "project_not_found",
        ),
        (
            "restricted source record",
            "GET",
            "/api/v1/decision/evidence/gcf_historical:1",
            None,
            404,
            "project_not_found",
        ),
        (
            "ranking without filters",
            "POST",
            "/api/v1/decision/prioritize",
            {"filters": {}},
            422,
            "candidate_set_too_large",
        ),
        (
            "review write without token",
            "POST",
            "/api/v1/reviews",
            {"screening_id": "0" * 36, "decision": "agree", "reviewer": "example_reviewer"},
            403,
            None,
        ),
    ]
    for name, method, path, body, expected, code in negatives:
        status, payload, _ = s.call(method, path, body)
        ok = status == expected and (code is None or payload.get("code") == code)
        s.check(f"rejects: {name}", ok, f"{status} {payload.get('code') if payload else ''}")
    status, payload, _ = s.call(
        "POST", "/api/v1/screening/text", raw=b'{"title": "' + b"x" * 300_000 + b'"}'
    )
    s.check("rejects: oversized body", status == 413 and payload["code"] == "request_too_large")


def _trim(value: Any, depth: int = 0) -> Any:
    if isinstance(value, str):
        return value if len(value) <= 160 else value[:157] + "..."
    if isinstance(value, list):
        out = [_trim(v, depth + 1) for v in value[:3]]
        return [*out, f"... {len(value) - 3} more"] if len(value) > 3 else out
    if isinstance(value, dict):
        return {k: _trim(v, depth + 1) for k, v in value.items()}
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--capture")
    args = parser.parse_args()
    smoke = Smoke(args.base)
    run(smoke)
    if args.capture:
        with Path(args.capture).open("w", encoding="utf-8") as handle:
            json.dump([_trim(entry) for entry in smoke.log], handle, indent=1, ensure_ascii=False)
    total = sum(1 for _ in smoke.log)
    print(f"{total} requests; {len(smoke.failures)} failed checks")
    return 1 if smoke.failures else 0


if __name__ == "__main__":
    sys.exit(main())
