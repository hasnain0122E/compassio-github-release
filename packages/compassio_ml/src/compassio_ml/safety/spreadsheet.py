"""Read-only spreadsheet access: no macros, no external links, cached values only.

openpyxl never executes VBA; macro-enabled workbooks are additionally rejected so
they cannot be silently treated as ordinary data. ``keep_links=False`` stops
openpyxl from loading external-workbook link caches, and ``data_only=True`` reads
the values stored in the file rather than formulas.
"""

import io
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import BinaryIO

from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook

WorkbookSource = str | Path | bytes


class MacroEnabledWorkbookError(ValueError):
    """The workbook contains a VBA project and is refused."""


@dataclass(frozen=True, slots=True)
class SheetTable:
    """A worksheet as a header row plus string cells (``None`` for empty)."""

    sheet: str
    header: tuple[str, ...]
    rows: list[tuple[str | None, ...]]


def _as_binary(source: WorkbookSource) -> BinaryIO | str:
    if isinstance(source, bytes):
        return io.BytesIO(source)
    return str(source)


def _reject_macros(source: WorkbookSource) -> None:
    handle = _as_binary(source)
    try:
        with zipfile.ZipFile(handle) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Not a valid .xlsx workbook: {exc}") from exc
    if any(name.lower().endswith("vbaproject.bin") for name in names):
        raise MacroEnabledWorkbookError("Workbook contains a VBA project (macros); refused")


def _open(source: WorkbookSource) -> Workbook:
    _reject_macros(source)
    return load_workbook(
        _as_binary(source), read_only=True, data_only=True, keep_links=False, keep_vba=False
    )


def list_sheets(source: WorkbookSource) -> list[str]:
    workbook = _open(source)
    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()


def _cell_to_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date | time):
        return value.isoformat()
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value)
    return text


def _dedupe_header(raw: tuple[object, ...]) -> tuple[str, ...]:
    seen: dict[str, int] = {}
    header: list[str] = []
    for index, value in enumerate(raw):
        name = str(value).strip() if value is not None else f"__unnamed_{index}"
        if name in seen:
            seen[name] += 1
            name = f"{name}__dup{seen[name]}"
        else:
            seen[name] = 0
        header.append(name)
    return tuple(header)


def read_sheet(source: WorkbookSource, sheet: str, *, header_row: int = 1) -> SheetTable:
    """Read one worksheet as strings.

    Duplicate header names are disambiguated with ``__dupN`` suffixes (and reported
    by callers), fully empty trailing rows and unnamed all-empty columns are dropped.
    """
    workbook = _open(source)
    try:
        if sheet not in workbook.sheetnames:
            raise KeyError(f"Sheet {sheet!r} not found; available: {workbook.sheetnames}")
        worksheet = workbook[sheet]
        rows_iter = worksheet.iter_rows(min_row=header_row, values_only=True)
        try:
            raw_header = next(rows_iter)
        except StopIteration:
            return SheetTable(sheet=sheet, header=(), rows=[])
        header = _dedupe_header(tuple(raw_header))
        rows: list[tuple[str | None, ...]] = []
        for raw in rows_iter:
            cells = tuple(_cell_to_str(v) for v in raw[: len(header)])
            cells = cells + (None,) * (len(header) - len(cells))
            if any(c is not None and c.strip() != "" for c in cells):
                rows.append(cells)
    finally:
        workbook.close()

    keep = [
        i
        for i, name in enumerate(header)
        if not name.startswith("__unnamed_") or any(r[i] is not None for r in rows)
    ]
    return SheetTable(
        sheet=sheet,
        header=tuple(header[i] for i in keep),
        rows=[tuple(r[i] for i in keep) for r in rows],
    )
