import hashlib
import os
from pathlib import Path

import pytest

from compassio_ml.integrity import sha256_file
from compassio_ml.integrity.cli import main

# Published SHA-256 test vectors (FIPS 180-2 / NIST).
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_empty_file_matches_known_vector(tmp_path: Path) -> None:
    target = tmp_path / "empty.bin"
    target.write_bytes(b"")

    assert sha256_file(target) == EMPTY_SHA256


def test_abc_matches_known_vector(tmp_path: Path) -> None:
    target = tmp_path / "abc.txt"
    target.write_bytes(b"abc")

    assert sha256_file(target) == ABC_SHA256


@pytest.mark.parametrize("chunk_size", [1, 7, 4096, 10_000_000])
def test_digest_is_independent_of_chunk_size(tmp_path: Path, chunk_size: int) -> None:
    payload = bytes(range(256)) * 1000  # 256,000 bytes, spans many chunks
    target = tmp_path / "payload.bin"
    target.write_bytes(payload)

    assert sha256_file(target, chunk_size=chunk_size) == hashlib.sha256(payload).hexdigest()


def test_binary_content_is_not_newline_translated(tmp_path: Path) -> None:
    payload = b"line1\r\nline2\nline3\r"
    target = tmp_path / "crlf.csv"
    target.write_bytes(payload)

    assert sha256_file(target) == hashlib.sha256(payload).hexdigest()


def test_hashing_does_not_modify_file(tmp_path: Path) -> None:
    target = tmp_path / "source.xml"
    target.write_bytes(b"<iati-activities/>")
    fixed_time = 1_600_000_000
    os.utime(target, (fixed_time, fixed_time))
    before = target.stat()

    sha256_file(target)

    after = target.stat()
    assert target.read_bytes() == b"<iati-activities/>"
    assert after.st_size == before.st_size
    assert after.st_mtime_ns == before.st_mtime_ns


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="missing file"):
        sha256_file(tmp_path / "does_not_exist.csv")


def test_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(IsADirectoryError):
        sha256_file(tmp_path)


def test_non_positive_chunk_size_rejected(tmp_path: Path) -> None:
    target = tmp_path / "x.bin"
    target.write_bytes(b"x")

    with pytest.raises(ValueError, match="chunk_size"):
        sha256_file(target, chunk_size=0)


def test_cli_prints_sha256sum_format(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "abc.txt"
    target.write_bytes(b"abc")

    exit_code = main([str(target)])

    assert exit_code == 0
    assert capsys.readouterr().out == f"{ABC_SHA256}  {target}\n"


def test_cli_reports_missing_file_and_continues(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    present = tmp_path / "abc.txt"
    present.write_bytes(b"abc")
    missing = tmp_path / "missing.csv"

    exit_code = main([str(missing), str(present)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "missing.csv" in captured.err
    assert captured.out == f"{ABC_SHA256}  {present}\n"
