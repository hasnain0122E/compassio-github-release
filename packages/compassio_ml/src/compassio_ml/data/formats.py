"""File-format detection from content signatures (not just extensions)."""

import zipfile
from enum import StrEnum
from pathlib import Path

_SNIFF_BYTES = 64 * 1024


class FileFormat(StrEnum):
    ZIP = "zip"
    XLSX = "xlsx"
    XML = "xml"
    CSV = "csv"


class UnsupportedFormatError(ValueError):
    """The file's extension or content is not an accepted source format."""


def detect_format(path: str | Path) -> FileFormat:
    """Return the verified format of ``path``.

    Both the extension and the content must agree; mismatches are refused so a
    renamed file cannot slip through as a different format.

    Raises:
        FileNotFoundError: the file does not exist.
        UnsupportedFormatError: unknown extension, macro-enabled workbook, or content mismatch.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Source file not found: {file_path}")
    suffix = file_path.suffix.lower()
    with file_path.open("rb") as handle:
        head = handle.read(_SNIFF_BYTES)

    if suffix in {".xlsm", ".xlsb", ".xls"}:
        raise UnsupportedFormatError(
            f"{file_path.name}: {suffix} workbooks are not accepted "
            "(macro-enabled or legacy binary); obtain an .xlsx export"
        )
    if suffix == ".zip":
        if not head.startswith(b"PK\x03\x04"):
            raise UnsupportedFormatError(f"{file_path.name}: .zip extension but no ZIP signature")
        return FileFormat.ZIP
    if suffix == ".xlsx":
        if not head.startswith(b"PK\x03\x04") or not _is_ooxml_workbook(file_path):
            raise UnsupportedFormatError(f"{file_path.name}: .xlsx extension but not a workbook")
        return FileFormat.XLSX
    if suffix == ".xml":
        if not head.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"<"):
            raise UnsupportedFormatError(f"{file_path.name}: .xml extension but not XML content")
        return FileFormat.XML
    if suffix == ".csv":
        if b"\x00" in head:
            raise UnsupportedFormatError(f"{file_path.name}: .csv contains NUL bytes (binary?)")
        try:
            head.decode("utf-8")
        except UnicodeDecodeError as exc:
            # A multi-byte character may straddle the sniff boundary; accept that only.
            if exc.start < len(head) - 4:
                raise UnsupportedFormatError(f"{file_path.name}: .csv is not UTF-8") from exc
        return FileFormat.CSV
    raise UnsupportedFormatError(
        f"{file_path.name}: unsupported extension {suffix or '(none)'}; "
        "accepted: .zip, .xlsx, .xml, .csv"
    )


def _is_ooxml_workbook(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in names and "xl/workbook.xml" in names
