"""Repository data-directory layout and explicit handling of missing source files.

Source datasets are not committed to Git. Code that needs one must call
:func:`require_source_file`, which fails loudly with instructions instead of
silently substituting other data.
"""

import os
from dataclasses import dataclass
from pathlib import Path

DATA_DIR_ENV_VAR = "COMPASSIO_DATA_DIR"


class MissingSourceDataError(FileNotFoundError):
    """A required source data file is not present locally."""


@dataclass(frozen=True, slots=True)
class DataLayout:
    """Locations of the data stages under a single data root."""

    root: Path

    @classmethod
    def from_env(cls, default: Path | None = None) -> "DataLayout":
        """Build a layout from ``COMPASSIO_DATA_DIR``, else ``default``, else ``./data``."""
        configured = os.environ.get(DATA_DIR_ENV_VAR)
        if configured:
            return cls(Path(configured))
        return cls(default if default is not None else Path.cwd() / "data")

    @property
    def raw(self) -> Path:
        """Immutable source files exactly as acquired."""
        return self.root / "raw"

    @property
    def interim(self) -> Path:
        """Intermediate, reproducibly derived files."""
        return self.root / "interim"

    @property
    def processed(self) -> Path:
        """Final derived datasets used for modelling and the product."""
        return self.root / "processed"

    @property
    def manifests(self) -> Path:
        """Committed provenance manifests describing the source files."""
        return self.root / "manifests"


def require_source_file(path: str | Path, *, source_id: str | None = None) -> Path:
    """Return ``path`` if it is an existing regular file, else raise.

    Raises:
        MissingSourceDataError: the file does not exist or is not a regular file.
    """
    file_path = Path(path)
    if file_path.is_file():
        return file_path

    label = f"source '{source_id}'" if source_id else "source file"
    reason = "is a directory, not a file" if file_path.is_dir() else "was not found"
    raise MissingSourceDataError(
        f"Required {label} {reason}: {file_path}. "
        "Copy the original downloaded file into data/raw/ and register it in "
        "data/manifests/ (see docs/data/data_contracts.md). "
        "Do not substitute synthetic or re-downloaded data without approval."
    )
