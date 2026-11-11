"""External HTTPS acceptance probe. A healthy code-only deployment fails product acceptance.

Supply --web https://APP --api https://API --out artifacts/task013/public.json.
No records, submitted text, credentials, or response bodies are written to the report.
"""

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

PINS = {
    "ml_v1": "53b226f6e866bd5377b951aaeb87f9be86c72dc9ac444a807bf0d49c857d3656",
    "ml_v2": "654336052ba75aae97a5c20db1c3ce9bb06792640abe6f660973318852358574",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web", required=True)
    parser.add_argument("--api", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    for origin in (args.web, args.api):
        parts = urlsplit(origin)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.path
            or parts.query
            or parts.fragment
        ):
            parser.error("Supply HTTPS origins without paths or credentials")
    checks = []

    def check(name, origin, path, expected, payload=None, validate=None):
        start = time.perf_counter()
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Origin": args.web, "Content-Type": "application/json"}
        req = Request(origin + path, data=body, headers=headers)
        try:
            try:
                response = urlopen(req, timeout=120)
            except HTTPError as exc:
                response = exc
            with response:
                raw = response.read()
                content = json.loads(raw) if validate else None
                ok = (
                    response.status == expected
                    and response.url.startswith(origin + "/")
                    and (validate(content) if validate else True)
                )
                if origin == args.api:
                    ok = ok and response.headers.get("Access-Control-Allow-Origin") == args.web
                checks.append(
                    {
                        "check": name,
                        "status": response.status,
                        "ok": bool(ok),
                        "seconds": round(time.perf_counter() - start, 4),
                    }
                )
                return content if ok else None
        except (URLError, TimeoutError, ValueError, KeyError, TypeError):
            checks.append({"check": name, "status": None, "ok": False})
            return None

    for route in ("/", "/projects", "/workspace", "/screening", "/challenges"):
        check(f"web {route}", args.web, route, 200)
    check("health", args.api, "/health", 200, validate=lambda d: d["status"] == "ok")
    check(
        "real discovery",
        args.api,
        "/api/v1/projects?country=PAK&page_size=5",
        200,
        validate=lambda d: bool(d.get("items")),
    )
    for model, pin in PINS.items():
        check(
            f"frozen {model}",
            args.api,
            "/api/v1/screening/text",
            200,
            {"title": "Solar power for rural health clinics", "model": model},
            lambda d, pin=pin: (
                d["model"]["artifact_sha256"] == pin
                and 0 <= d["prediction"]["label_score"] <= 1
                and not d["fallback_used"]
            ),
        )
    for route in ("/docs", "/redoc", "/openapi.json"):
        check(f"hidden {route}", args.api, route, 404)
    result = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "web": args.web,
        "api": args.api,
        "checks": checks,
        "http_smoke_passed": all(c["ok"] for c in checks),
        "browser_journey": "Must be run separately; HTTP smoke is not full acceptance",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["http_smoke_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
