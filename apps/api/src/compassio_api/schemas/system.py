"""Schemas for service-level (non-domain) endpoints."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Liveness status of the API process."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]
    service: str
    version: str


class MetaResponse(BaseModel):
    """Product identity and API version."""

    model_config = ConfigDict(frozen=True)

    product_name: str
    tagline: str
    category: str
    api_version: str
    environment: str
