"""Centralized, typed API configuration.

Values are read from environment variables prefixed with ``COMPASSIO_`` (and an
optional ``.env`` file in the working directory). See ``.env.example``.
"""

from functools import lru_cache
from typing import Annotated, Final, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PRODUCT_NAME: Final = "Compassio"
PRODUCT_TAGLINE: Final = "Give Funding a Better Direction."
PRODUCT_CATEGORY: Final = "Climate Funding Intelligence"
API_V1_PREFIX: Final = "/api/v1"

DEFAULT_CORS_ORIGINS: Final = ("http://localhost:3000", "http://127.0.0.1:3000")
# Relative to the working directory (run commands from the repository root). Git-ignored.
DEFAULT_DATABASE_URL: Final = "sqlite:///data/db/compassio_dev.sqlite"

AccessMode = Literal["local_development", "hackathon_event", "public"]


class Settings(BaseSettings):
    """API runtime settings."""

    model_config = SettingsConfigDict(
        env_prefix="COMPASSIO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    # Comma-separated in the environment, e.g.
    # COMPASSIO_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
    cors_origins: Annotated[tuple[str, ...], NoDecode] = DEFAULT_CORS_ORIGINS
    # SQLAlchemy URL. SQLite (default, local) or PostgreSQL (`postgresql+psycopg://...`, driver
    # not yet installed; see docs/architecture/database_design.md). Never commit credentials.
    database_url: str = DEFAULT_DATABASE_URL
    # Source-rights access mode (docs/security/source_rights_access_policy.md):
    #   local_development: registered source records may be inspected on this machine.
    #   public: only sources whose rights_status is permitted* (none today) are served.
    #   hackathon_event: Task 009 event mode (docs/hackathon/data_permission_scope.md): the
    #     sources named by COMPASSIO_EVENT_AUTHORIZATION, loopback clients only, time-boxed.
    # environment=production ALWAYS behaves as "public" (fails closed), whatever this says.
    source_data_access: AccessMode = "public"
    # Key of an entry in event_authorizations_path; required for hackathon_event.
    event_authorization: str | None = None
    event_authorizations_path: str = "configs/event_data_authorizations.yaml"

    # --- Task 009 hardening ----------------------------------------------------------
    # Larger request bodies are rejected with 413 before parsing (screening text is <= ~21 KB).
    max_request_body_bytes: int = Field(default=262_144, ge=1_024, le=10_485_760)
    # Per-client screening requests per minute (in-process, single worker). 0 disables.
    screening_rate_limit_per_minute: int = Field(default=60, ge=0, le=10_000)
    # C11 challenge policy v1; opt-in only. Replaces the Task 009 limiter when enabled.
    c11_enabled: bool = False
    # Separate demonstration adapter; normal screening contracts stay raw.
    c09_enabled: bool = False
    c11_screen_rate: float = Field(default=2, gt=0, le=100, allow_inf_nan=False)
    c11_screen_burst: int = Field(default=6, ge=1, le=100)
    c11_read_rate: float = Field(default=10, gt=0, le=1000, allow_inf_nan=False)
    c11_read_burst: int = Field(default=20, ge=1, le=1000)
    c11_global_screen_rate: float = Field(default=20, gt=0, le=1000, allow_inf_nan=False)
    c11_global_screen_burst: int = Field(default=40, ge=1, le=1000)
    c11_global_read_rate: float = Field(default=50, gt=0, le=1000, allow_inf_nan=False)
    c11_global_read_burst: int = Field(default=50, ge=1, le=1000)
    c11_max_keys: int = Field(default=1024, ge=2, le=100_000)
    c11_idle_seconds: float = Field(default=120, gt=0, le=3600, allow_inf_nan=False)
    # Load and hash-verify the authorized models at startup instead of on the first request.
    preload_models: bool = False

    # --- Task 007 inference ------------------------------------------------------------
    inference_registry_path: str = "configs/inference_models.yaml"
    inference_root: str = "."  # base for artifact_dir entries in the registry
    trusted_registry_path: str = "configs/trusted_model_releases.json"
    # Opt-in authorized local demonstration: ML v2 becomes the default engine. Effective ONLY
    # with environment=development and local source-data access (never in production/test).
    ml_v2_local_demo: bool = False
    # Separate store for saved screenings and review decisions (not the project database).
    review_database_url: str = "sqlite:///data/db/compassio_reviews.sqlite"
    # Writes (saving a screening, recording a review) require this token in the
    # X-Compassio-Review-Token header. Unset = all writes disabled.
    review_api_token: SecretStr | None = None

    @property
    def inference_authorized(self) -> bool:
        """Model screening is local-only until a public prediction service is approved."""
        return self.effective_source_access in ("local_development", "hackathon_event")

    @property
    def ml_v2_demo_active(self) -> bool:
        return (
            self.ml_v2_local_demo
            and self.environment == "development"
            and (self.inference_authorized)
        )

    @field_validator("database_url")
    @classmethod
    def _supported_database(cls, url: str) -> str:
        if not url.startswith(("sqlite:///", "postgresql://", "postgresql+")):
            raise ValueError("database_url must be a sqlite:/// or postgresql URL")
        return url

    @property
    def effective_source_access(self) -> AccessMode:
        """Production can never run in local-inspection mode."""
        return "public" if self.environment == "production" else self.source_data_access

    @model_validator(mode="after")
    def _c11_valid_expiry(self) -> "Settings":
        if self.c11_idle_seconds < max(
            self.c11_screen_burst / self.c11_screen_rate,
            self.c11_read_burst / self.c11_read_rate,
        ):
            raise ValueError("C11 idle expiry must permit complete peer token refill")
        return self

    @model_validator(mode="after")
    def _event_mode_needs_authorization(self) -> "Settings":
        if self.effective_source_access == "hackathon_event" and not self.event_authorization:
            raise ValueError(
                "COMPASSIO_SOURCE_DATA_ACCESS=hackathon_event requires "
                "COMPASSIO_EVENT_AUTHORIZATION (an entry of event_authorizations_path)"
            )
        return self

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @field_validator("cors_origins")
    @classmethod
    def _reject_unsafe_origins(cls, origins: tuple[str, ...]) -> tuple[str, ...]:
        for origin in origins:
            if origin == "*":
                raise ValueError("wildcard CORS origin '*' is not allowed; list origins explicitly")
            if not origin.startswith(("http://", "https://")):
                raise ValueError(f"CORS origin must start with http:// or https://: {origin!r}")
            if origin.endswith("/"):
                raise ValueError(f"CORS origin must not end with '/': {origin!r}")
        return origins


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings (cached)."""
    return Settings()
