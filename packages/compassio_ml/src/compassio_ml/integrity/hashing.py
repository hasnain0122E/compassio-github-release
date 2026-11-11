"""SHA-256 hashing of source files.

Files are opened read-only in binary mode and streamed in chunks, so large raw
datasets are never loaded fully into memory and are never modified.
"""

import hashlib
from pathlib import Path

DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MiB


def sha256_file(path: str | Path, *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """Return the lowercase hexadecimal SHA-256 digest of the file at ``path``.

    Raises:
        FileNotFoundError: ``path`` does not exist.
        IsADirectoryError: ``path`` is a directory.
        ValueError: ``chunk_size`` is not positive.
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got {chunk_size}")

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Cannot hash missing file: {file_path}")
    if file_path.is_dir():
        # Checked explicitly: on Windows, opening a directory raises
        # PermissionError rather than IsADirectoryError.
        raise IsADirectoryError(f"Cannot hash a directory: {file_path}")

    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()
