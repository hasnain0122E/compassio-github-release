"""Controlled real canonical TCP probe in disposable ONE-worker processes.

Never hits the browser's demo server. No training or writes to the canonical DB.
Run: uv run python scripts/task012_probe.py
"""

import hashlib
import http.client
import json
import os
import socket
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/task012"


def request(
    port: int,
    path: str,
    body: bytes | None = None,
    *,
    peer: str = "127.0.0.1",
    chunked: bool = False,
) -> dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30, source_address=(peer, 0))
    headers = {"Origin": "http://localhost:3000", "Content-Type": "application/json"}
    started = time.perf_counter()
    try:
        payload: Any = [body[:100_000], body[100_000:]] if chunked and body else body
        conn.request(
            "POST" if body is not None else "GET", path, payload, headers, encode_chunked=chunked
        )
        response = conn.getresponse()
        data = json.loads(response.read())  # Detect Windows response-body resets here.
        return {
            "status": response.status,
            "headers": dict(response.getheaders()),
            "body": data,
            "seconds": time.perf_counter() - started,
        }
    finally:
        conn.close()


def start(enabled: bool, production: bool = False) -> tuple[subprocess.Popen[bytes], int]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {
        **os.environ,
        "COMPASSIO_ENVIRONMENT": "production" if production else "development",
        "COMPASSIO_SOURCE_DATA_ACCESS": "local_development",
        "COMPASSIO_EVENT_AUTHORIZATION": "battleverse_2026",
        "COMPASSIO_ML_V2_LOCAL_DEMO": "true",
        "COMPASSIO_PRELOAD_MODELS": "true",
        "COMPASSIO_C09_ENABLED": str(enabled),
        "COMPASSIO_C11_ENABLED": str(enabled),
        # Deliberately small local probe budget: exercise rejection without a flood.
        # This is not the recorded C11 capacity configuration.
        "COMPASSIO_C11_READ_RATE": "1",
        "COMPASSIO_C11_READ_BURST": "4",
    }
    log = (OUT / f"probe-server-{enabled}-{production}.log").open("wb")
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "compassio_api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--workers",
                "1",
                "--no-proxy-headers",
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    finally:
        log.close()
    for _ in range(120):
        try:
            if request(port, "/health")["status"] == 200:
                return process, port
        except (OSError, http.client.HTTPException):
            time.sleep(0.25)
        if process.poll() is not None:
            break
    process.terminate()
    raise RuntimeError("probe process failed to start; inspect its log")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    db = ROOT / "data/db/compassio_dev.sqlite"
    digest = hashlib.sha256(db.read_bytes()).hexdigest()
    results: dict[str, Any] = {"canonical_db_sha256": digest, "capacity_claim": False}
    baseline = None
    for enabled in (False, True):
        process, port = start(enabled)
        try:
            entry: dict[str, Any] = {"read_budget": {"rate": 1, "burst": 4}}
            for chunked in (False, True):
                response = request(port, "/api/v1/screening/text", b"x" * 300_000, chunked=chunked)
                assert response["status"] == 413 and response["body"]["code"] == "request_too_large"
                assert response["headers"]["access-control-allow-origin"] == "http://localhost:3000"
                entry[f"oversize_chunked_{chunked}"] = response
            project = request(port, "/api/v1/projects/aiddata:35266")["body"]
            body = json.dumps({"title": project["title"], "model": "ml_v2"}).encode()
            raw = request(port, "/api/v1/screening/text", body)
            assert raw["status"] == 200
            contract = {k: raw["body"][k] for k in ("prediction", "explanation", "model")}
            if baseline is None:
                baseline = contract
            else:
                assert baseline == contract
            guard_body = json.dumps({"title": project["title"]}).encode()
            guard = request(port, "/api/v1/challenges/c09/screen", guard_body)
            assert guard["status"] == (200 if enabled else 403)
            entry["c09"] = guard

            def mixed(i: int, probe_port: int = port) -> dict[str, Any]:
                time.sleep(0.025 * (i % 8))
                paths = [
                    "/api/v1/projects?country=PAK&page_size=5",
                    "/api/v1/filters",
                    "/api/v1/projects/aiddata:35266",
                    "/api/v1/analytics/overview",
                ]
                return request(probe_port, paths[i % len(paths)])

            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=8) as pool:
                rows = list(pool.map(mixed, range(64)))
            counts = Counter(str(row["status"]) for row in rows)
            assert not (set(counts) - {"200", "429"}), counts
            assert counts["200"] > 0
            if enabled:
                assert counts["429"] > 0
                assert all(
                    int(row["headers"]["retry-after"]) >= 1 for row in rows if row["status"] == 429
                )
            else:
                assert counts["200"] == 64
            independent = request(
                port, "/api/v1/projects?country=PAK&page_size=5", peer="127.0.0.2"
            )
            assert independent["status"] == 200
            entry["mixed"] = {
                "requests": len(rows),
                "concurrency": 8,
                "status_counts": counts,
                "seconds": time.perf_counter() - started,
                "independent_peer_status": independent["status"],
                "max_response_seconds": max(r["seconds"] for r in rows),
            }
            results[str(enabled)] = entry
        finally:
            process.terminate()
            process.wait(timeout=15)
    process, port = start(True, production=True)
    try:
        checks = [
            request(port, "/api/v1/projects"),
            request(port, "/api/v1/screening/text", b'{"title":"example_text"}'),
            request(port, "/api/v1/challenges/c09/screen", b'{"title":"example_text"}'),
        ]
        assert [r["status"] for r in checks] == [403, 403, 403]
        results["production"] = checks
    finally:
        process.terminate()
        process.wait(timeout=15)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == digest
    target = OUT / "canonical-probe.json"
    target.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "result": "PASS",
                "evidence": str(target),
                "mixed": {key: results[key]["mixed"] for key in ("False", "True")},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
