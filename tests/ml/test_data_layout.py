from pathlib import Path

import pytest

from compassio_ml.data import (
    DATA_DIR_ENV_VAR,
    DataLayout,
    MissingSourceDataError,
    require_source_file,
)


def test_layout_stage_directories(tmp_path: Path) -> None:
    layout = DataLayout(tmp_path)

    assert layout.raw == tmp_path / "raw"
    assert layout.interim == tmp_path / "interim"
    assert layout.processed == tmp_path / "processed"
    assert layout.manifests == tmp_path / "manifests"


def test_layout_from_env_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DATA_DIR_ENV_VAR, str(tmp_path))

    assert DataLayout.from_env().root == tmp_path


def test_layout_from_env_falls_back_to_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(DATA_DIR_ENV_VAR, raising=False)

    assert DataLayout.from_env(default=tmp_path).root == tmp_path


def test_layout_from_env_falls_back_to_cwd_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(DATA_DIR_ENV_VAR, raising=False)
    monkeypatch.chdir(tmp_path)

    assert DataLayout.from_env().root == tmp_path / "data"


def test_require_source_file_returns_existing_file(tmp_path: Path) -> None:
    source = tmp_path / "raw" / "export.csv"
    source.parent.mkdir()
    source.write_text("id\n", encoding="utf-8")

    assert require_source_file(source) == source


def test_missing_source_file_raises_with_guidance(tmp_path: Path) -> None:
    missing = tmp_path / "raw" / "gcf_funded_projects.csv"

    with pytest.raises(MissingSourceDataError) as excinfo:
        require_source_file(missing, source_id="gcf_funded_projects")

    message = str(excinfo.value)
    assert "gcf_funded_projects" in message
    assert "was not found" in message
    assert "data/raw/" in message
    assert "synthetic" in message


def test_missing_source_error_is_a_file_not_found_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        require_source_file(tmp_path / "absent.xml")


def test_directory_is_not_accepted_as_source_file(tmp_path: Path) -> None:
    with pytest.raises(MissingSourceDataError, match="is a directory"):
        require_source_file(tmp_path)
