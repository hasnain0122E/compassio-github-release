"""The web app's TypeScript API types are generated from the live OpenAPI schema and fresh."""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _generator() -> object:
    spec = importlib.util.spec_from_file_location(
        "generate_api_types", REPO / "scripts" / "generate_api_types.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_types_match_the_current_openapi_schema() -> None:
    gen = _generator()
    expected = gen.render(gen.current_schema())  # type: ignore[attr-defined]
    committed = (REPO / "apps/web/src/lib/api-types.ts").read_text(encoding="utf-8")

    assert committed == expected, "run: uv run python scripts/generate_api_types.py"
    assert "export interface ScreeningResponse" in committed


def test_committed_openapi_document_is_fresh() -> None:
    gen = _generator()
    expected = gen.render_openapi(gen.current_schema())  # type: ignore[attr-defined]
    committed = (REPO / "docs/api/openapi.json").read_text(encoding="utf-8")

    assert committed == expected, "run: uv run python scripts/generate_api_types.py"
    assert '"/api/v1/decision/scenarios"' in committed
