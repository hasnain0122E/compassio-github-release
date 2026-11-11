from pathlib import Path

import pytest
from pydantic import ValidationError

from compassio_api.core.config import DEFAULT_CORS_ORIGINS, Settings


def make_settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_defaults_are_local_development(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("COMPASSIO_ENVIRONMENT", "COMPASSIO_LOG_LEVEL", "COMPASSIO_CORS_ORIGINS"):
        monkeypatch.delenv(name, raising=False)

    settings = make_settings()

    assert settings.environment == "development"
    assert settings.log_level == "info"
    assert settings.cors_origins == DEFAULT_CORS_ORIGINS
    assert "*" not in settings.cors_origins


def test_cors_origins_parsed_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPASSIO_CORS_ORIGINS", " http://localhost:3000 , https://app.test ,")

    assert make_settings().cors_origins == ("http://localhost:3000", "https://app.test")


def test_environment_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPASSIO_ENVIRONMENT", "production")

    assert make_settings().environment == "production"


def test_env_file_is_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COMPASSIO_LOG_LEVEL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("COMPASSIO_LOG_LEVEL=debug\n", encoding="utf-8")

    settings = Settings(_env_file=env_file)

    assert settings.log_level == "debug"


@pytest.mark.parametrize(
    "origins",
    ["*", "http://localhost:3000,*", "localhost:3000", "http://localhost:3000/"],
)
def test_unsafe_or_malformed_cors_origins_rejected(
    origins: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COMPASSIO_CORS_ORIGINS", origins)

    with pytest.raises(ValidationError):
        make_settings()


def test_invalid_environment_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(environment="staging")


def test_settings_are_immutable() -> None:
    settings = make_settings()

    with pytest.raises(ValidationError):
        settings.environment = "production"  # type: ignore[misc]
