import importlib
import re
from importlib.metadata import requires, version

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "compassio_ml",
        "compassio_ml.integrity",
        "compassio_ml.integrity.cli",
        "compassio_ml.data",
        "compassio_api",
        "compassio_api.main",
    ],
)
def test_modules_import(module: str) -> None:
    importlib.import_module(module)


def test_package_versions_match_distribution_metadata() -> None:
    import compassio_api
    import compassio_ml

    assert compassio_ml.__version__ == version("compassio-ml")
    assert compassio_api.__version__ == version("compassio-api")


def test_ml_package_does_not_depend_on_http_layer() -> None:
    """The ML package must stay independent of the API (one-way dependency)."""
    names = {
        re.split(r"[\s<>=!~;\[(]", req, maxsplit=1)[0].lower()
        for req in requires("compassio-ml") or []
    }

    assert "pydantic" in names  # sanity check that parsing worked
    assert names.isdisjoint({"fastapi", "starlette", "uvicorn", "compassio-api"})
