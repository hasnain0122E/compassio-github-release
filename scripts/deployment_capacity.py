"""Measure an isolated real API over loopback; never uploads records or enables cloud access.

Run from the repository root with --out artifacts/task013/capacity.json.
Windows RSS is working set; Linux RSS comes from /proc. Neither emulates a Render cgroup.
"""

import argparse
import concurrent.futures
import ctypes
import json
import os
import platform
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from runtime_artifacts import ARTIFACTS, verify  # noqa: E402


def rss(pid: int) -> int:
    if sys.platform == "win32":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in ("peak", "working", "pp", "p", "pnp", "np", "page", "peakpage")
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x410, False, pid)
        try:
            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            query = ctypes.WinDLL("psapi").GetProcessMemoryInfo
            query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            if not handle or not query(handle, ctypes.byref(counters), counters.cb):
                return 0
            return int(counters.working)
        finally:
            if handle:
                kernel.CloseHandle(handle)
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except FileNotFoundError:
        return 0
    return 0


def cpu_seconds(pid: int) -> float:
    if sys.platform == "win32":
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x410, False, pid)
        clocks = [ctypes.c_uint64() for _ in range(4)]
        query = kernel.GetProcessTimes
        query.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(ctypes.c_uint64)] * 4
        try:
            if not handle or not query(handle, *(ctypes.byref(value) for value in clocks)):
                raise RuntimeError("Process CPU timing unavailable")
            return (clocks[2].value + clocks[3].value) / 10_000_000
        finally:
            if handle:
                kernel.CloseHandle(handle)
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")


def request(base: str, path: str, body: bytes | None = None, **headers: str) -> dict:
    start = time.perf_counter()
    req = Request(base + path, data=body, headers=headers)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        response = urlopen(req, timeout=90)
    except HTTPError as exc:
        response = exc
    with response:
        payload = response.read()
        try:
            content = json.loads(payload)
        except ValueError:
            content = {}
        return {
            "status": response.status,
            "seconds": round(time.perf_counter() - start, 4),
            "bytes": len(payload),
            "code": content.get("code"),
            "cors": response.headers.get("Access-Control-Allow-Origin"),
            "retry_after": response.headers.get("Retry-After"),
            "model_hash": content.get("model", {}).get("artifact_sha256"),
            "label_score": content.get("prediction", {}).get("label_score"),
        }


def measure(mode: str) -> dict:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = {k: v for k, v in os.environ.items() if not k.startswith("COMPASSIO_")}
    env.update(
        {
            "COMPASSIO_ENVIRONMENT": mode,
            "COMPASSIO_SOURCE_DATA_ACCESS": "local_development",
            "COMPASSIO_ML_V2_LOCAL_DEMO": "true",
            "COMPASSIO_C11_ENABLED": "true",
            "COMPASSIO_C09_ENABLED": "true",
            "COMPASSIO_CORS_ORIGINS": "https://judge.example",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
    )
    start = time.perf_counter()
    # Windows venv python.exe can be a launcher: measure the interpreter's own PID.
    code = (
        "import os; print(os.getpid(), flush=True); import uvicorn; "
        f"uvicorn.run('compassio_api.main:app', host='127.0.0.1', port={port}, "
        "workers=1, proxy_headers=False, access_log=False)"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=REPO,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    assert proc.stdout is not None
    server_pid = int(proc.stdout.readline().strip())
    samples: list[int] = []
    stop = threading.Event()

    def monitor() -> None:
        while not stop.wait(0.02):
            samples.append(rss(server_pid))

    thread = threading.Thread(target=monitor)
    thread.start()
    try:
        while True:
            try:
                health = request(base, "/health")
                if health["status"] == 200:
                    break
            except (URLError, TimeoutError):
                pass
            if proc.poll() is not None or time.perf_counter() - start > 90:
                raise RuntimeError("API failed to start within 90 seconds")
            time.sleep(0.05)
        report = {
            "startup_seconds": round(time.perf_counter() - start, 4),
            "startup_rss_bytes": rss(server_pid),
            "health": health,
            "startup_cpu_seconds": cpu_seconds(server_pid),
        }
        report["discovery"] = request(base, "/api/v1/projects?country=PAK&page_size=5")
        report["search"] = request(base, "/api/v1/projects?q=solar&page_size=5")
        report["detail"] = request(base, "/api/v1/projects/aiddata:35266")
        for model in ("ml_v1", "ml_v2"):
            cpu_start = cpu_seconds(server_pid)
            body = json.dumps({"title": "Solar power for rural clinics", "model": model}).encode()
            report[model] = [request(base, "/api/v1/screening/text", body) for _ in range(3)]
            report[f"rss_after_{model}"] = rss(server_pid)
            report[f"cpu_seconds_{model}_three_requests"] = cpu_seconds(server_pid) - cpu_start
        report["oversized"] = request(
            base, "/api/v1/screening/text", b"x" * 262145, Origin="https://judge.example"
        )
        report["approved_cors"] = request(base, "/health", Origin="https://judge.example")
        report["unapproved_cors"] = request(base, "/health", Origin="https://unapproved.example")
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            report["concurrent_reads"] = list(
                pool.map(lambda _: request(base, "/api/v1/projects?page_size=5"), range(8))
            )
        report["rss_peak_sampled_bytes"] = max(samples, default=0)
        body = json.dumps({"title": "Solar power for rural clinics", "model": "ml_v2"}).encode()
        report["spoofed_forwarded_screen_burst"] = [
            request(base, "/api/v1/screening/text", body, **{"X-Forwarded-For": f"192.0.2.{n}"})
            for n in range(12)
        ]
        rejected = [r for r in report["spoofed_forwarded_screen_burst"] if r["status"] == 429]
        if rejected:
            time.sleep(float(rejected[-1]["retry_after"]) + 0.2)
            report["limiter_recovery"] = request(base, "/api/v1/screening/text", body)
        return report
    finally:
        stop.set()
        thread.join()
        proc.terminate()
        proc.wait(timeout=15)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not verify(REPO):
        return 1
    result = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "logical_cpus": os.cpu_count(),
        "rss_sample_interval_seconds": 0.02,
        "artifact_bytes": {rel: (REPO / rel).stat().st_size for rel in ARTIFACTS},
    }
    db = REPO / "data/db/compassio_dev.sqlite"
    start = time.perf_counter()
    with sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True) as con:
        result["sqlite_integrity"] = con.execute("pragma integrity_check").fetchone()[0]
        result["sqlite_foreign_key_violations"] = len(
            con.execute("pragma foreign_key_check").fetchall()
        )
    result["sqlite_check_seconds"] = round(time.perf_counter() - start, 4)
    result["production"] = measure("production")
    result["local_development"] = measure("development")
    public, local = result["production"], result["local_development"]
    result["checks_passed"] = (
        result["sqlite_integrity"] == "ok"
        and result["sqlite_foreign_key_violations"] == 0
        and public["discovery"]["status"] == 403
        and local["discovery"]["status"] == 200
        and all(r["status"] == 200 for r in local["concurrent_reads"])
        and all(r["status"] == 403 for key in ("ml_v1", "ml_v2") for r in public[key])
        and all(
            r["status"] == 200
            and r["model_hash"]
            == ARTIFACTS[
                "models/compassio_ccrc_v1/model.joblib"
                if key == "ml_v1"
                else "data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550/model.joblib"
            ][0]
            for key in ("ml_v1", "ml_v2")
            for r in local[key]
        )
        and all(
            mode["oversized"]["status"] == 413
            and mode["oversized"]["cors"] == "https://judge.example"
            and mode["unapproved_cors"]["cors"] is None
            and any(r["status"] == 429 for r in mode["spoofed_forwarded_screen_burst"])
            and mode.get("limiter_recovery", {}).get("status") == expected
            for mode, expected in ((public, 403), (local, 200))
        )
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
