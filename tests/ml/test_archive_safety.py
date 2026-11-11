"""ZIP safety: traversal, corruption, bombs, symlinks, encryption. Artificial archives only."""

import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from compassio_ml.safety import (
    ArchiveLimits,
    CorruptArchiveError,
    UnsafeArchiveError,
    inspect_zip,
    read_zip_member,
)

MakeZip = Callable[[str, dict[str, bytes]], Path]


def test_valid_archive_lists_members_and_flags_junk(make_zip: MakeZip) -> None:
    archive = make_zip(
        "example.zip",
        {"data/example.csv": b"a,b\n1,2\n", "__MACOSX/._example.csv": b"x", "data/.DS_Store": b"y"},
    )

    members = {m.name: m for m in inspect_zip(archive)}

    assert set(members) == {"data/example.csv", "__MACOSX/._example.csv", "data/.DS_Store"}
    assert not members["data/example.csv"].is_junk
    assert members["__MACOSX/._example.csv"].is_junk
    assert members["data/.DS_Store"].is_junk
    assert members["data/example.csv"].uncompressed_bytes == 8


def test_inspection_does_not_extract_anything(make_zip: MakeZip, tmp_path: Path) -> None:
    archive = make_zip("example.zip", {"inner.txt": b"hello"})
    before = sorted(p.name for p in tmp_path.iterdir())

    inspect_zip(archive)
    assert read_zip_member(archive, "inner.txt") == b"hello"

    assert sorted(p.name for p in tmp_path.iterdir()) == before


@pytest.mark.parametrize(
    "name",
    ["../evil.txt", "safe/../../evil.txt", "/etc/evil", "C:/evil.txt", "..\\evil.txt"],
)
def test_unsafe_member_paths_rejected(tmp_path: Path, name: str) -> None:
    archive = tmp_path / "example.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("ok.txt", b"ok")
        hostile = zipfile.ZipInfo("placeholder")
        hostile.filename = name  # bypass ZipInfo's constructor normalisation
        handle.writestr(hostile, b"evil")

    with pytest.raises(UnsafeArchiveError):
        inspect_zip(archive)


def test_symlink_member_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "example.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        handle.writestr(info, "/etc/passwd")

    with pytest.raises(UnsafeArchiveError, match="symlink"):
        inspect_zip(archive)


def test_encrypted_member_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "example.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("secret.txt", b"example")
    # zipfile cannot write encrypted members, so set the "encrypted" flag bit directly
    # in the local header (offset 6) and the central directory record (offset 8).
    raw = bytearray(archive.read_bytes())
    raw[raw.index(b"PK") + 6] |= 0x1
    raw[raw.index(b"PK") + 8] |= 0x1
    archive.write_bytes(bytes(raw))

    with pytest.raises(UnsafeArchiveError, match="encrypted"):
        inspect_zip(archive)


def test_high_compression_ratio_rejected_as_zip_bomb(make_zip: MakeZip) -> None:
    archive = make_zip("example.zip", {"zeros.bin": b"\x00" * (2 * 1024 * 1024)})

    with pytest.raises(UnsafeArchiveError, match="ZIP bomb"):
        inspect_zip(archive)


def test_total_uncompressed_limit(make_zip: MakeZip) -> None:
    archive = make_zip("example.zip", {"a.txt": b"a" * 600, "b.txt": b"b" * 600})

    with pytest.raises(UnsafeArchiveError, match="expands beyond"):
        inspect_zip(archive, ArchiveLimits(max_total_uncompressed_bytes=1000))


def test_member_count_limit(make_zip: MakeZip) -> None:
    archive = make_zip("example.zip", {f"{i}.txt": b"x" for i in range(5)})

    with pytest.raises(UnsafeArchiveError, match="members"):
        inspect_zip(archive, ArchiveLimits(max_members=4))


def test_non_zip_file_is_corrupt(tmp_path: Path) -> None:
    fake = tmp_path / "example.zip"
    fake.write_bytes(b"this is not a zip archive")

    with pytest.raises(CorruptArchiveError, match="Not a ZIP"):
        inspect_zip(fake)


def test_truncated_archive_is_corrupt(make_zip: MakeZip) -> None:
    archive = make_zip("example.zip", {"inner.txt": b"hello world " * 200})
    data = archive.read_bytes()
    archive.write_bytes(data[: len(data) // 2])

    with pytest.raises(CorruptArchiveError):
        inspect_zip(archive)


def test_crc_mismatch_is_corrupt(tmp_path: Path) -> None:
    archive = tmp_path / "example.zip"
    payload = b"EXAMPLE-PAYLOAD-" * 64
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as handle:
        handle.writestr("inner.txt", payload)
    raw = bytearray(archive.read_bytes())
    offset = raw.index(payload)
    raw[offset + 10] ^= 0xFF
    archive.write_bytes(bytes(raw))

    with pytest.raises(CorruptArchiveError, match="CRC"):
        inspect_zip(archive)


def test_missing_archive_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        inspect_zip(tmp_path / "absent.zip")


def test_read_unknown_member_raises_key_error(make_zip: MakeZip) -> None:
    archive = make_zip("example.zip", {"inner.txt": b"x"})

    with pytest.raises(KeyError):
        read_zip_member(archive, "other.txt")
