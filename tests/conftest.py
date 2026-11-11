"""Shared pytest fixtures.

Fixtures here never fabricate project or climate-finance observations; they
only construct application objects and temporary files for unit tests.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from compassio_api.core.config import Settings
from compassio_api.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    # _env_file=None isolates tests from a developer's local .env file.
    return Settings(_env_file=None, environment="test")


@pytest.fixture
def client(test_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(test_settings)) as test_client:
        yield test_client
