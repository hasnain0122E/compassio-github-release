"""Product metadata endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from compassio_api import __version__
from compassio_api.core.config import (
    PRODUCT_CATEGORY,
    PRODUCT_NAME,
    PRODUCT_TAGLINE,
    Settings,
    get_settings,
)
from compassio_api.schemas import MetaResponse

router = APIRouter(tags=["meta"])


@router.get("/meta", response_model=MetaResponse, summary="Product name, tagline and API version")
def meta(settings: Annotated[Settings, Depends(get_settings)]) -> MetaResponse:
    return MetaResponse(
        product_name=PRODUCT_NAME,
        tagline=PRODUCT_TAGLINE,
        category=PRODUCT_CATEGORY,
        api_version=__version__,
        environment=settings.environment,
    )
