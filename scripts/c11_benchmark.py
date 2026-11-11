"""Bounded loopback-only real HTTP experiment; artificial models are explicitly labeled."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import io
import json
import math
import socket
import subprocess
import sys
import time
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx2 as httpx
from fastapi import Request

monotonic = time.perf_counter  # monotonic high-resolution scheduler on Windows

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "artifacts/c11"
TEXT = {"title": "example flood resilience", "description": "example climate adaptation works"}


def prepare() -> None:
    """Reuse audited test fixture formats, never copy canonical data or model artifacts."""
    from tests.api.conftest import seed_extended
    from tests.api.test_screening import models_root

    from compassio_api.db.migrate import upgrade
    from compassio_api.db.session import create_write_engine

    OUT.mkdir(parents=True, exist_ok=True)
    frozen = OUT / "frozen/apps/api/src/compassio_api/main.py"
    if not frozen.exists():
        archive = subprocess.check_output(
            [
                "git",
                "archive",
                "--format=zip",
                "8c083509e324d76aafc7ee097dc4345a94314afd",
                "apps/api/src",
            ],
            cwd=ROOT,
        )
        with zipfile.ZipFile(io.BytesIO(archive)) as source:
            source.extractall(OUT / "frozen")
    if not (OUT / "root/registry.yaml").exists():
        models_root.__wrapped__(OUT)  # type: ignore[attr-defined]
    db = OUT / "example.sqlite"
    if not db.exists():
        url = f"sqlite:///{db.as_posix()}"
        upgrade(url)
        engine = create_write_engine(url)
        seed_extended(engine)
        engine.dispose()


def integrity() -> dict[str, str]:
    paths = [OUT / "example.sqlite", *sorted((OUT / "root").rglob("*"))]
    paths += [ROOT / "configs/inference_models.yaml", ROOT / "configs/trusted_model_releases.json"]
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths
        if p.is_file() and "reviews" not in p.name
    }


def server(mode: str, port: int, receipt: Path) -> None:
    import ctypes
    from ctypes import wintypes

    import uvicorn

    if mode == "baseline":
        sys.path.insert(0, str(OUT / "frozen/apps/api/src"))

    from compassio_api.core.config import Settings
    from compassio_api.main import create_app

    source_path = Path(inspect.getfile(create_app)).resolve()
    if mode == "baseline":
        assert source_path.is_relative_to(OUT / "frozen"), source_path

    values: dict[str, Any] = {}
    if mode == "shield":
        values["c11_enabled"] = True
    app = create_app(
        Settings(
            _env_file=None,
            source_data_access="local_development",
            database_url=f"sqlite:///{(OUT / 'example.sqlite').as_posix()}",
            inference_root=str(OUT / "root"),
            inference_registry_path="registry.yaml",
            trusted_registry_path="trusted.json",
            ml_v2_local_demo=True,
            preload_models=True,
            **values,
        )
    )

    class Memory(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("faults", wintypes.DWORD),
            *[
                (name, ctypes.c_size_t)
                for name in (
                    "peak_rss",
                    "rss",
                    "peak_paged",
                    "paged",
                    "peak_nonpaged",
                    "nonpaged",
                    "pagefile",
                    "peak_pagefile",
                )
            ],
        ]

    @app.get("/_c11_peer")
    def peer(request: Request) -> dict[str, str]:
        return {"peer": request.client.host if request.client else "unknown"}

    ingress: list[float] = []

    async def observed(scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http" and dict(scope["headers"]).get(b"x-c11-load") == b"1":
            ingress.append(monotonic())
        await app(scope, receive, send)

    instance = uvicorn.Server(
        uvicorn.Config(
            observed,
            host="127.0.0.1",
            port=port,
            workers=1,
            proxy_headers=False,
            access_log=False,
            log_level="error",
        )
    )

    async def serve() -> None:
        async def stop() -> None:
            while not receipt.with_suffix(".stop").exists():
                await asyncio.sleep(0.1)
            instance.should_exit = True

        watcher = asyncio.create_task(stop())
        try:
            await instance.serve()
        finally:
            watcher.cancel()

    start = time.process_time()
    try:
        asyncio.run(serve())
    finally:
        memory = Memory()
        memory.cb = ctypes.sizeof(memory)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        memory_info = ctypes.WinDLL("psapi").GetProcessMemoryInfo
        memory_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Memory), wintypes.DWORD]
        memory_info(kernel.GetCurrentProcess(), ctypes.byref(memory), memory.cb)
        limiter = getattr(app.state, "c11_limiter", None)
        receipt.write_text(
            json.dumps(
                {
                    "cpu_seconds_including_startup": time.process_time() - start,
                    "app_source": str(source_path.relative_to(ROOT)),
                    "app_source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                    "rss_bytes": memory.rss,
                    "peak_rss_bytes": memory.peak_rss,
                    "limiter": limiter.snapshot() if limiter else None,
                    "server_observed_load_count": len(ingress),
                    "server_observed_load_rps": (len(ingress) - 1) / (ingress[-1] - ingress[0])
                    if len(ingress) > 1
                    else None,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def percentiles(values: list[float]) -> dict[str, float | None]:
    ordered = sorted(values)
    return {
        f"p{q}": ordered[min(len(ordered) - 1, math.ceil(len(ordered) * q / 100) - 1)]
        if ordered
        else None
        for q in (50, 95, 99)
    }


async def workload(mode: str, scenario: str, seconds: int, port: int) -> dict[str, Any]:
    base = f"http://127.0.0.1:{port}"
    # These are genuine socket-bound source IPs, not forwarded headers or client IDs.
    peers = ["127.0.0.2", "127.0.0.3", "127.0.0.4", "127.0.0.5", "127.0.0.9"]
    clients = [
        httpx.AsyncClient(
            transport=httpx.AsyncHTTPTransport(local_address=peer, retries=0),
            timeout=3,
            limits=httpx.Limits(max_connections=32),
            trust_env=False,
        )
        for peer in peers
    ]
    for peer, client in zip(peers, clients, strict=True):
        observed = (await client.get(base + "/_c11_peer")).json()
        assert observed == {"peer": peer}, observed
    records: list[dict[str, Any]] = []
    semaphore = asyncio.Semaphore(64)
    started = monotonic()
    last_sent = started
    example: dict[str, Any] | None = None

    async def request(index: int, role: str, read: bool = False) -> None:
        nonlocal last_sent, example
        async with semaphore:
            sent = monotonic()
            last_sent = max(last_sent, sent)
            error_kind: str | None = None
            try:
                client = clients[index]
                response = (
                    await client.get(
                        base + "/api/v1/projects",
                        headers={"Origin": "http://localhost:3000", "X-C11-Load": "1"},
                    )
                    if read
                    else await client.post(
                        base + "/api/v1/screening/text",
                        json=TEXT,
                        headers={"Origin": "http://localhost:3000", "X-C11-Load": "1"},
                    )
                )
                code: int | str = response.status_code
                if code == 429 and example is None:
                    example = {
                        "status": code,
                        "body": response.json(),
                        "headers": dict(response.headers),
                    }
            except httpx.TimeoutException as exc:
                code = "timeout"
                error_kind = type(exc).__name__
            except httpx.TransportError as exc:
                code = "connection_failure"
                error_kind = type(exc).__name__
            records.append(
                {
                    "role": role,
                    "status": code,
                    "sent": sent - started,
                    "latency_ms": (monotonic() - sent) * 1000,
                    "read": read,
                    "error_kind": error_kind,
                }
            )

    tasks: list[asyncio.Task[None]] = []
    aborted = False
    abort_reason: str | None = None
    for tick in range(seconds * 200):
        # Bound both active HTTP work (64) and queued dispatches (another 64).
        if sum(not task.done() for task in tasks) >= 128:
            aborted = True
            abort_reason = "pending_dispatch_ceiling"
            break
        failures = sum(r["status"] in (500, "timeout", "connection_failure") for r in records)
        if failures >= 10:
            aborted = True
            abort_reason = "capacity_or_transport_failures"
            break
        await asyncio.sleep(max(0, started + tick / 200 - monotonic()))
        index = tick % 4 if scenario in ("distributed", "mixed") else 0
        read = scenario == "mixed" and tick % 2 == 0
        tasks.append(asyncio.create_task(request(index, "abusive", read)))
        if tick % 50 == 0:
            # shared-IP scenario intentionally cannot distinguish the legitimate caller.
            tasks.append(
                asyncio.create_task(
                    request(0 if scenario == "shared_ip" else 4, "legitimate", tick % 100 == 0)
                )
            )
    await asyncio.gather(*tasks)
    completed_at = monotonic()
    recovery_start = monotonic()
    recovery: float | None = None
    recovery_failure: str | None = None
    while monotonic() - recovery_start < 3:
        try:
            response = await clients[0].post(base + "/api/v1/screening/text", json=TEXT)
        except httpx.TransportError as exc:
            recovery_failure = type(exc).__name__
            break
        if response.status_code == 200:
            recovery = monotonic() - recovery_start
            break
        await asyncio.sleep(0.1)
    await asyncio.gather(*(client.aclose() for client in clients))
    result: dict[str, Any] = {
        "mode": mode,
        "scenario": scenario,
        "target_abusive_rps": 200,
        "seconds": seconds,
        "safety_aborted": aborted,
        "safety_abort_reason": abort_reason,
        "recovery_failure": recovery_failure,
        "identity": "real socket source IPs 127.0.0.2-5, legitimate .9; shared_ip uses .2",
        "completed_rps": sum(isinstance(r["status"], int) for r in records)
        / (completed_at - started),
        "attempts_finished_rps": len(records) / (completed_at - started),
        "recovery_seconds": recovery,
        "recovery_observation_limit_seconds": 3,
        "example_429": example,
    }
    for role in ("abusive", "legitimate"):
        rows = [r for r in records if r["role"] == role]
        duration = max(r["sent"] for r in rows) - min(r["sent"] for r in rows)
        result[role] = {
            "sent": len(rows),
            "actual_sent_rps": (len(rows) - 1) / duration,
            "status_counts": dict(Counter(str(r["status"]) for r in rows)),
            "transport_error_counts": dict(
                Counter(r["error_kind"] for r in rows if r["error_kind"])
            ),
            "read_status_counts": dict(Counter(str(r["status"]) for r in rows if r["read"])),
            "screen_status_counts": dict(Counter(str(r["status"]) for r in rows if not r["read"])),
            "success_percent": sum(
                isinstance(r["status"], int) and 200 <= r["status"] < 300 for r in rows
            )
            / len(rows)
            * 100,
            "latency_ms": percentiles([r["latency_ms"] for r in rows]),
            "max_scheduling_lag_ms": max(0, (last_sent - started - (seconds - 1 / 200)) * 1000),
        }
    result["records"] = records
    return result


async def run(mode: str, seconds: int, repeat: int) -> None:
    prepare()
    before = integrity()
    runs = []
    unsafe_scenarios: set[str] = set()
    for iteration in range(repeat):
        for scenario in ("single", "distributed", "mixed", "shared_ip"):
            if scenario in unsafe_scenarios:
                continue
            # Bind check: never attach a flood generator to an unrelated existing server.
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 18761))
            receipt = OUT / f"{mode}-{iteration}-{scenario}-process.json"
            receipt.unlink(missing_ok=True)
            receipt.with_suffix(".stop").unlink(missing_ok=True)
            log = (OUT / f"{mode}-{iteration}-{scenario}.log").open("w", encoding="utf-8")
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--server",
                    "--mode",
                    mode,
                    "--receipt",
                    str(receipt),
                ],
                cwd=ROOT,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            try:
                async with httpx.AsyncClient(trust_env=False) as health:
                    for _ in range(100):
                        if process.poll() is not None:
                            raise RuntimeError("Disposable server exited; inspect its local log")
                        try:
                            if (
                                await health.get("http://127.0.0.1:18761/health")
                            ).status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        await asyncio.sleep(0.1)
                    else:
                        raise RuntimeError("Disposable server did not become healthy")
                result = await workload(mode, scenario, seconds, 18761)
                result["iteration"] = iteration
            finally:
                receipt.with_suffix(".stop").touch()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                log.close()
            result["process"] = json.loads(receipt.read_text("utf-8")) if receipt.exists() else None
            runs.append(result)
            if result["safety_aborted"]:
                unsafe_scenarios.add(scenario)
            (OUT / f"{mode}-partial.json").write_text(json.dumps(runs, indent=2), encoding="utf-8")
            print(
                json.dumps(
                    {k: v for k, v in result.items() if k not in ("records", "example_429")}
                ),
                flush=True,
            )
    after = integrity()
    assert before == after, "Fixture or pinned registry changed during HTTP experiment"
    (OUT / f"{mode}.json").write_text(
        json.dumps(
            {
                "fixture": "ARTIFICIAL tiny v1/v2 models and invented project DB; real inference",
                "base_commit": "8c083509e324d76aafc7ee097dc4345a94314afd",
                "runtime": sys.version,
                "recorded_at_utc": datetime.now(UTC).isoformat(),
                "command": sys.argv,
                "benchmark_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "integrity_before": before,
                "integrity_after": after,
                "runs": runs,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("baseline", "shield"), required=True)
    parser.add_argument("--seconds", type=int, choices=range(2, 11), default=4)
    parser.add_argument("--repeat", type=int, choices=range(1, 4), default=2)
    parser.add_argument("--server", action="store_true")
    parser.add_argument("--receipt", type=Path, default=OUT / "process.json")
    args = parser.parse_args()
    if args.server:
        server(args.mode, 18761, args.receipt)
    else:
        asyncio.run(run(args.mode, args.seconds, args.repeat))


if __name__ == "__main__":
    main()
