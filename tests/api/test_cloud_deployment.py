"""Cloud deployment boundaries, tested without provider credentials or uploads."""

import importlib.util
import io
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from compassio_api.core.config import Settings
from compassio_api.main import create_app

ROOT = Path(__file__).resolve().parents[2]


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "infra" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_production_hides_interactive_api_docs() -> None:
    with TestClient(create_app(Settings(_env_file=None, environment="production"))) as client:
        assert client.get("/health").status_code == 200
        for route in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(route).status_code == 404


@pytest.mark.parametrize(
    "origin",
    [
        "http://judge.example",
        "https://judge.example/path",
        "https://user@judge.example",
        "https://*.example",
        "https://judge.example?secret=value",
    ],
)
def test_cloud_launcher_rejects_unsafe_origins(
    origin: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COMPASSIO_ENVIRONMENT", "production")
    monkeypatch.setenv("COMPASSIO_CORS_ORIGINS", origin)
    with pytest.raises(ValueError):
        load("start_api").command()


def test_cloud_launch_is_single_worker_without_proxy_trust(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPASSIO_ENVIRONMENT", "production")
    monkeypatch.setenv("COMPASSIO_CORS_ORIGINS", "https://judge.example")
    monkeypatch.setenv("PORT", "9123")
    command = load("start_api").command()
    assert command[0] == sys.executable
    assert command[command.index("--port") + 1] == "9123"
    assert command[command.index("--workers") + 1] == "1"
    assert "--no-proxy-headers" in command


def test_no_network_without_transfer_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load("provision_runtime")
    approval = tmp_path / "approval.json"
    approval.write_text("{}")
    monkeypatch.setattr(module, "build_opener", lambda *_: pytest.fail("network before approval"))
    with pytest.raises(ValueError, match="approval"):
        module.provision(tmp_path / "runtime", tmp_path / "missing.json", approval)


def test_existing_canonical_runtime_is_verified_without_download(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load("provision_runtime")
    if not all((ROOT / rel).exists() for rel in module.ARTIFACTS):
        pytest.skip("canonical runtime absent")
    approval = tmp_path / "approval.json"
    # Test receipt is temporary and used only for a no-network, no-write local verification.
    approval.write_text(
        json.dumps(
            {
                "cloud_transfer_approved": True,
                "evidence_reference": "unit-test-only",
                "reviewed_by": "test",
                "approved_provider": "test",
            }
        )
    )
    downloads = tmp_path / "downloads.json"
    downloads.write_text(
        json.dumps({rel: "https://unused.example/file" for rel in module.ARTIFACTS})
    )

    class Offline:
        def open(self, *args: object, **kwargs: object) -> None:
            pytest.fail("existing canonical files must not be downloaded")

    monkeypatch.setattr(module, "build_opener", lambda *_: Offline())
    module.provision(ROOT, downloads, approval)


def test_corrupt_download_is_never_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load("provision_runtime")
    approval = tmp_path / "approval.json"
    approval.write_text(
        json.dumps(
            {
                "cloud_transfer_approved": True,
                "evidence_reference": "unit-test-only",
                "reviewed_by": "test",
                "approved_provider": "test",
            }
        )
    )
    downloads = tmp_path / "downloads.json"
    downloads.write_text(
        json.dumps({rel: "https://unused.example/file" for rel in module.ARTIFACTS})
    )

    class CorruptResponse(io.BytesIO):
        status = 200

    class CorruptTransport:
        def open(self, *args: object, **kwargs: object) -> CorruptResponse:
            return CorruptResponse(b"deliberately invalid artifact bytes")

    monkeypatch.setattr(module, "build_opener", lambda *_: CorruptTransport())
    root = tmp_path / "runtime"
    with pytest.raises(ValueError, match="checksum mismatch"):
        module.provision(root, downloads, approval)
    assert not any(path.is_file() for path in root.rglob("*"))
