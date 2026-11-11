"""Combined backend/ML integration boundaries. All constructed records are ARTIFICIAL."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from compassio_api.cli import db_cli
from compassio_api.core.config import Settings
from compassio_api.db.migrate import upgrade
from compassio_api.db.models import Base, Source
from compassio_api.db.session import create_read_engine, create_write_engine
from compassio_api.main import create_app
from compassio_api.services.access import resolve_policy
from compassio_api.staging.registry import BACKEND_SOURCES
from compassio_ml.data.layout import DataLayout
from compassio_ml.external.development import ForbiddenPoolError, load_development_pool
from compassio_ml.external.paths import UnsafePathError, V2Paths
from compassio_ml.external.registry import load_registry
from compassio_ml.external.rights import Use, load_rights

REPO = Path(__file__).resolve().parents[1]


def combined(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> V2Paths:
    repo = tmp_path / "example_combined"
    monkeypatch.setenv("COMPASSIO_DATA_ROOT", str(repo / "data"))
    monkeypatch.setenv("COMPASSIO_V1_PROJECT_ROOT", str(repo))
    monkeypatch.delenv("COMPASSIO_V2_OUTPUT_ROOT", raising=False)
    monkeypatch.delenv("COMPASSIO_V2_EXTERNAL_INPUT_ROOT", raising=False)
    return V2Paths.from_env(repo)


def test_combined_outputs_and_legacy_root_selection_are_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = combined(tmp_path, monkeypatch)
    legacy = tmp_path / "example_legacy_data"
    monkeypatch.setenv("COMPASSIO_DATA_DIR", str(legacy))
    assert DataLayout.from_env().root == legacy
    assert paths.v1_project_root == paths.repo_root
    assert paths.input_data_root == paths.repo_root / "data"
    assert paths.writable(paths.datasets / "example" / "a.json").is_relative_to(paths.output_root)
    assert Settings(_env_file=None).database_url == "sqlite:///data/db/compassio_dev.sqlite"


@pytest.mark.parametrize(
    "relative",
    [
        "data/raw",
        "data/processed",
        "data/manifests",
        "data/interim",
        "data/raw_db",
        "data/db",
        "models",
        "experiments",
        "apps",
    ],
)
def test_combined_configuration_never_admits_protected_output_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    paths = combined(tmp_path, monkeypatch)
    monkeypatch.setenv("COMPASSIO_V2_OUTPUT_ROOT", str(paths.repo_root / relative))
    with pytest.raises(UnsafePathError):
        V2Paths.from_env(paths.repo_root)
    with pytest.raises(UnsafePathError):
        paths.writable(paths.repo_root / relative / "example_file")


def test_existing_external_inputs_cannot_be_written_or_used_as_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = combined(tmp_path, monkeypatch)
    external = tmp_path / "example_ml_checkout" / "external_raw"
    external.mkdir(parents=True)
    monkeypatch.setenv("COMPASSIO_V2_EXTERNAL_INPUT_ROOT", str(external))
    paths = V2Paths.from_env(paths.repo_root)
    assert paths.external_raw == external.resolve()
    with pytest.raises(UnsafePathError):
        paths.writable(paths.external_raw / "example_source/new/raw.xml")
    monkeypatch.setenv("COMPASSIO_V2_OUTPUT_ROOT", str(external))
    with pytest.raises(UnsafePathError):
        V2Paths.from_env(paths.repo_root)


@pytest.mark.parametrize("relative", ["data/raw_db", "data/db"])
def test_backend_paths_forbidden_even_without_v1_input_environment(
    tmp_path: Path, relative: str
) -> None:
    paths = V2Paths(tmp_path, tmp_path / "out", None, None)
    with pytest.raises(UnsafePathError):
        paths.readable(tmp_path / relative / "example.json")


def test_backend_snapshot_cannot_be_selected_as_external_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = combined(tmp_path, monkeypatch)
    forbidden = paths.repo_root / "data/raw_db"
    forbidden.mkdir(parents=True)
    monkeypatch.setenv("COMPASSIO_V2_EXTERNAL_INPUT_ROOT", str(forbidden))
    with pytest.raises(UnsafePathError):
        V2Paths.from_env(paths.repo_root)


def test_three_source_registries_and_ai_permissions_remain_independent() -> None:
    canonical = json.loads((REPO / "data/manifests/source_manifest.json").read_text("utf-8"))
    canonical_ids = {e["source_id"] for e in canonical["entries"]}
    external = load_registry(REPO / "configs/external_sources_v2.yaml")
    assert "gcf_api_projects" in BACKEND_SOURCES
    assert "gcf_api_projects" not in canonical_ids
    with pytest.raises(KeyError):
        external.get("gcf_api_projects")
    rights = load_rights(REPO / "configs/ml_rights_eligibility_v2.yaml")
    for source in (
        "gcf_api_projects",
        "gcf_api_snapshot_backend",
        "gcf_project_pages",
        "example_unknown",
    ):
        assert not any(rights.permitted(source, use) for use in Use)
    assert rights.permitted("iati_fcdo", Use.TRAINING)
    assert rights.permitted("iati_ec_intpa", Use.TRAINING)
    assert (
        json.loads((REPO / "configs/ai_assessment_permissions_v2.json").read_text("utf-8"))["runs"]
        == {}
    )


def test_combined_loader_still_refuses_external_evaluation(tmp_path: Path) -> None:
    paths = V2Paths(REPO, tmp_path, None, None)
    with pytest.raises(ForbiddenPoolError):
        load_development_pool(paths, "example", partitions=["external_test_candidate"])
    with pytest.raises(ForbiddenPoolError):
        load_development_pool(paths, "../sealed_external_test/example")


def test_display_access_is_not_training_or_ai_permission(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'example_rights.sqlite').as_posix()}"
    engine = create_write_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for source_id, tier in (
            ("gcf_api_projects", "standard"),
            ("gcf_historical", "restricted_internal"),
        ):
            session.add(
                Source(
                    source_id=source_id,
                    name="example_source",
                    publisher="example_publisher",
                    file_relpath="example.json",
                    file_sha256="0" * 64,
                    rights_status="not_reviewed",
                    observation_type="example_type",
                    synced_at=datetime.now(UTC),
                    source_registry="backend_staging",
                    access_tier=tier,
                )
            )
        session.commit()
        local = resolve_policy(session, "local_development")
        assert local.allows("gcf_api_projects")
        assert not local.allows("gcf_historical")
        assert not resolve_policy(session, "public").allows("gcf_api_projects")
    engine.dispose()
    rights = load_rights(REPO / "configs/ml_rights_eligibility_v2.yaml")
    assert not rights.permitted("gcf_api_projects", Use.TRAINING)
    with TestClient(
        create_app(
            Settings(
                _env_file=None,
                database_url=url,
                environment="production",
                source_data_access="local_development",
            )
        )
    ) as client:
        assert client.get("/api/v1/documents").status_code == 403
        assert client.get("/api/v1/analytics/gcf-timeline").status_code == 403


@pytest.mark.parametrize("command", [["status"], ["verify"], ["report", "reconciliation"]])
def test_verification_cli_cannot_open_a_write_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: list[str]
) -> None:
    database = tmp_path / "example_readonly.sqlite"
    url = f"sqlite:///{database.as_posix()}"
    upgrade(url)
    before = hashlib.sha256(database.read_bytes()).hexdigest()

    def deny_write(_: str) -> None:
        raise AssertionError("Read command opened a write engine")

    monkeypatch.setattr(db_cli, "create_write_engine", deny_write)
    # Empty artificial DB correctly fails audited counts; status/reconciliation succeed.
    assert db_cli.main(["--database-url", url, *command]) == (1 if command == ["verify"] else 0)
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    engine = create_read_engine(url)
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar() == "0003"
        )
    engine.dispose()


def test_frozen_sources_labels_finance_and_release_code_match_checkpoint() -> None:
    pins = json.loads((REPO / "configs/task006_integration_reference.json").read_text("utf-8"))
    for relative, expected in pins["protected_text_sha256"].items():
        actual = hashlib.sha256((REPO / relative).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        assert actual == expected, relative


def test_combined_outputs_cannot_target_another_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = combined(tmp_path, monkeypatch)
    monkeypatch.setenv(
        "COMPASSIO_V2_OUTPUT_ROOT", str(tmp_path / "example_other_checkout" / "data")
    )
    with pytest.raises(UnsafePathError):
        V2Paths.from_env(paths.repo_root)


def test_retrieval_verifier_accepts_readonly_source_root_outside_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from compassio_ml.cli import v2_cli

    external = tmp_path / "example_input"
    retrieval = external / "example_source" / "example_retrieval"
    retrieval.mkdir(parents=True)
    (retrieval / "retrieval_manifest.json").write_text('{"files": []}', encoding="utf-8")
    paths = V2Paths(tmp_path / "repo", tmp_path / "repo/out", None, None, external)
    paths.check_separation()
    monkeypatch.setattr(v2_cli, "_paths", lambda: paths)
    assert v2_cli.main(["verify-retrievals"]) == 0
    assert "external_raw/example_source/example_retrieval: OK" in capsys.readouterr().out
