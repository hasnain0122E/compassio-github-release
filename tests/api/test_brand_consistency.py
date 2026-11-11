"""The web app duplicates the API's product strings until generated types exist
(see packages/shared/README.md). This test keeps the two copies identical."""

import re
from pathlib import Path

from compassio_api.core.config import PRODUCT_CATEGORY, PRODUCT_NAME, PRODUCT_TAGLINE

BRAND_TS = Path(__file__).resolve().parents[2] / "apps" / "web" / "src" / "lib" / "brand.ts"


def _ts_constants() -> dict[str, str]:
    text = BRAND_TS.read_text(encoding="utf-8")
    return dict(re.findall(r'export const (\w+) = "([^"]*)";', text))


def test_official_tagline_is_exact() -> None:
    assert PRODUCT_TAGLINE == "Give Funding a Better Direction."


def test_web_brand_strings_match_api() -> None:
    constants = _ts_constants()

    assert constants == {
        "PRODUCT_NAME": PRODUCT_NAME,
        "PRODUCT_TAGLINE": PRODUCT_TAGLINE,
        "PRODUCT_CATEGORY": PRODUCT_CATEGORY,
    }
