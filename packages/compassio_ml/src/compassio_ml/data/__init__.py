"""Data-layout conventions, source-file guards and the source manifest model."""

from compassio_ml.data.layout import (
    DATA_DIR_ENV_VAR,
    DataLayout,
    MissingSourceDataError,
    require_source_file,
)
from compassio_ml.data.manifest import RightsStatus, SourceManifest, SourceManifestEntry

__all__ = [
    "DATA_DIR_ENV_VAR",
    "DataLayout",
    "MissingSourceDataError",
    "RightsStatus",
    "SourceManifest",
    "SourceManifestEntry",
    "require_source_file",
]
