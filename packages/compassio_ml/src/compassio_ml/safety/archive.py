"""Read-only ZIP inspection with traversal, corruption and ZIP-bomb protection.

Archives are never extracted to disk. Members are validated from the central
directory, CRC-checked, and individual members are read into memory only after
passing size limits.
"""

import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# macOS resource forks and Finder metadata: harmless, never data.
_JUNK_PREFIXES = ("__MACOSX/",)
_JUNK_NAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})


class UnsafeArchiveError(ValueError):
    """The archive contains a member that could escape extraction or exhaust resources."""


class CorruptArchiveError(ValueError):
    """The file is not a readable ZIP archive or fails its CRC check."""


@dataclass(frozen=True, slots=True)
class ArchiveLimits:
    """Resource limits applied before any member is read."""

    max_members: int = 10_000
    max_total_uncompressed_bytes: int = 2 * 1024**3  # 2 GiB
    max_member_uncompressed_bytes: int = 1024**3  # 1 GiB
    max_compression_ratio: float = 200.0
    # Ratios of tiny members (e.g. a 6 KiB .DS_Store) are meaningless.
    ratio_check_min_bytes: int = 1024 * 1024


@dataclass(frozen=True, slots=True)
class ArchiveMember:
    name: str
    uncompressed_bytes: int
    compressed_bytes: int
    is_dir: bool
    is_junk: bool
    crc32: int

    @property
    def suffix(self) -> str:
        return PurePosixPath(self.name).suffix.lower()


def _unsafe_name_reason(name: str) -> str | None:
    if "\x00" in name:
        return "contains a NUL byte"
    normalized = name.replace("\\", "/")
    if normalized.startswith("/"):
        return "is an absolute path"
    if len(normalized) >= 2 and normalized[1] == ":":
        return "has a drive letter"
    if any(part == ".." for part in normalized.split("/")):
        return "contains '..' (path traversal)"
    return None


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    return info.create_system == 3 and stat.S_ISLNK(mode)


def _is_junk(name: str) -> bool:
    return name.startswith(_JUNK_PREFIXES) or PurePosixPath(name).name in _JUNK_NAMES


def inspect_zip(path: str | Path, limits: ArchiveLimits | None = None) -> list[ArchiveMember]:
    """Validate a ZIP archive and return its members without extracting anything.

    Raises:
        FileNotFoundError: ``path`` does not exist.
        CorruptArchiveError: not a ZIP, unreadable central directory, or CRC failure.
        UnsafeArchiveError: traversal/absolute/symlink/encrypted members or limit breaches.
    """
    lim = limits or ArchiveLimits()
    archive_path = Path(path)
    if not archive_path.is_file():
        raise FileNotFoundError(f"Archive not found: {archive_path}")
    if not zipfile.is_zipfile(archive_path):
        raise CorruptArchiveError(f"Not a ZIP archive (bad signature): {archive_path}")

    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            _check_members(infos, lim, archive_path)
            bad_member = archive.testzip()
    except zipfile.BadZipFile as exc:
        raise CorruptArchiveError(f"Corrupt ZIP archive {archive_path}: {exc}") from exc
    if bad_member is not None:
        raise CorruptArchiveError(f"CRC check failed for member {bad_member!r} in {archive_path}")

    return [
        ArchiveMember(
            name=info.filename,
            uncompressed_bytes=info.file_size,
            compressed_bytes=info.compress_size,
            is_dir=info.is_dir(),
            is_junk=_is_junk(info.filename),
            crc32=info.CRC,
        )
        for info in infos
    ]


def _check_members(infos: list[zipfile.ZipInfo], lim: ArchiveLimits, archive_path: Path) -> None:
    if len(infos) > lim.max_members:
        raise UnsafeArchiveError(
            f"{archive_path} has {len(infos)} members (limit {lim.max_members})"
        )
    total = 0
    for info in infos:
        reason = _unsafe_name_reason(info.filename)
        if reason:
            raise UnsafeArchiveError(f"Member {info.filename!r} in {archive_path} {reason}")
        if _is_symlink(info):
            raise UnsafeArchiveError(f"Member {info.filename!r} in {archive_path} is a symlink")
        if info.flag_bits & 0x1:
            raise UnsafeArchiveError(f"Member {info.filename!r} in {archive_path} is encrypted")
        if info.file_size > lim.max_member_uncompressed_bytes:
            raise UnsafeArchiveError(
                f"Member {info.filename!r} expands to {info.file_size} bytes "
                f"(limit {lim.max_member_uncompressed_bytes})"
            )
        if info.file_size >= lim.ratio_check_min_bytes:
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > lim.max_compression_ratio:
                raise UnsafeArchiveError(
                    f"Member {info.filename!r} compression ratio {ratio:.0f} exceeds "
                    f"{lim.max_compression_ratio:.0f} (possible ZIP bomb)"
                )
        total += info.file_size
        if total > lim.max_total_uncompressed_bytes:
            raise UnsafeArchiveError(
                f"{archive_path} expands beyond {lim.max_total_uncompressed_bytes} bytes"
            )


def read_zip_member(path: str | Path, member: str, limits: ArchiveLimits | None = None) -> bytes:
    """Return one validated member's bytes, read into memory (never written to disk)."""
    members = {m.name: m for m in inspect_zip(path, limits)}
    if member not in members:
        raise KeyError(f"Member {member!r} not found in {path}")
    if members[member].is_dir:
        raise IsADirectoryError(f"Member {member!r} in {path} is a directory")
    with zipfile.ZipFile(path) as archive:
        return archive.read(member)
