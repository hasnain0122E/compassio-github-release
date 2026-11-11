"""Format detection and strict value parsing. Artificial inputs only."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from compassio_ml.data.formats import FileFormat, UnsupportedFormatError, detect_format
from compassio_ml.data.parsing import (
    GCF_DATE_FORMATS,
    normalize_text,
    parse_amount,
    parse_date,
    parse_iso_datetime_date,
    parse_year,
    series_key,
    split_codes,
    split_country_list,
)
from compassio_ml.research.labels import parse_rio_marker

MakeXlsx = Callable[[str, dict[str, list[list[object]]]], Path]
MakeZip = Callable[[str, dict[str, bytes]], Path]


def test_detects_each_supported_format(
    tmp_path: Path, make_xlsx: MakeXlsx, make_zip: MakeZip
) -> None:
    csv_file = tmp_path / "example.csv"
    csv_file.write_text("a,b\n1,2\n", encoding="utf-8")
    xml_file = tmp_path / "example.xml"
    xml_file.write_bytes(b"\xef\xbb\xbf<?xml version='1.0'?><r/>")

    assert detect_format(make_zip("example.zip", {"x.txt": b"x"})) is FileFormat.ZIP
    assert detect_format(make_xlsx("example.xlsx", {"S": [["a"]]})) is FileFormat.XLSX
    assert detect_format(csv_file) is FileFormat.CSV
    assert detect_format(xml_file) is FileFormat.XML


@pytest.mark.parametrize("name", ["example.txt", "example.pdf", "example", "example.json"])
def test_unsupported_extension_refused(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.write_text("x", encoding="utf-8")

    with pytest.raises(UnsupportedFormatError, match="unsupported extension"):
        detect_format(path)


@pytest.mark.parametrize("name", ["example.xlsm", "example.xls", "example.xlsb"])
def test_macro_or_legacy_workbooks_refused(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.write_bytes(b"PK\x03\x04example")

    with pytest.raises(UnsupportedFormatError, match="not accepted"):
        detect_format(path)


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("example.zip", b"plain text"),
        ("example.xlsx", b"plain text"),
        ("example.xml", b"not xml"),
        ("example.csv", b"a,b\x00\n"),
    ],
)
def test_extension_content_mismatch_refused(tmp_path: Path, name: str, content: bytes) -> None:
    path = tmp_path / name
    path.write_bytes(content)

    with pytest.raises(UnsupportedFormatError):
        detect_format(path)


def test_zip_renamed_to_xlsx_refused(make_zip: MakeZip) -> None:
    archive = make_zip("example.zip", {"x.txt": b"x"})
    renamed = archive.with_suffix(".xlsx")
    archive.rename(renamed)

    with pytest.raises(UnsupportedFormatError, match="not a workbook"):
        detect_format(renamed)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        detect_format(tmp_path / "absent.csv")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("25000000", Decimal("25000000")),
        ("57619101.519999996", Decimal("57619101.519999996")),
        ("1,234.50", Decimal("1234.50")),
        ("$300000", Decimal("300000")),
        ("-50", Decimal("-50")),
        (None, None),
        ("", None),
        ("   ", None),
        ("nan", None),
    ],
)
def test_parse_amount(raw: str | None, expected: Decimal | None) -> None:
    assert parse_amount(raw) == expected


@pytest.mark.parametrize("raw", ["USD 220 000,00", "ten", "inf", "-Infinity", "NaN0", "12 34"])
def test_parse_amount_rejects_non_numeric(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_amount(raw)


def test_parse_year() -> None:
    assert parse_year("2021") == 2021
    assert parse_year("2016.0") == 2016
    assert parse_year(" ") is None
    with pytest.raises(ValueError):
        parse_year("20x1")
    with pytest.raises(ValueError):
        parse_year("1800")


def test_parse_gcf_date_format() -> None:
    assert parse_date("May 1, 2015", GCF_DATE_FORMATS) == date(2015, 5, 1)
    assert parse_date("Jun 11, 2015", GCF_DATE_FORMATS) == date(2015, 6, 11)
    with pytest.raises(ValueError):
        parse_date("2015-05-01", GCF_DATE_FORMATS)


def test_parse_iso_datetime_date() -> None:
    assert parse_iso_datetime_date("2026-10-05T00:00:00+00:00") == date(2026, 10, 5)
    assert parse_iso_datetime_date("2021-04-25T00:00:00") == date(2021, 4, 25)
    assert parse_iso_datetime_date("2021-04-25") == date(2021, 4, 25)
    assert parse_iso_datetime_date(None) is None
    with pytest.raises(ValueError):
        parse_iso_datetime_date("25/04/2021")


def test_text_normalization_and_series_key() -> None:
    assert normalize_text("  Café: Solar-Power   PROJECT ") == "cafe solar power project"
    assert series_key("Example Programme - Tranche 1") == series_key("Example Programme Tranche 2")
    assert series_key("Example Programme") != series_key("Other Programme")


def test_country_and_code_lists() -> None:
    assert split_country_list("Kenya, Rwanda, Dominican Republic (the)") == [
        "Kenya",
        "Rwanda",
        "Dominican Republic (the)",
    ]
    assert split_country_list(None) == []
    assert split_codes("PAK;IND|BGD, NPL") == ["PAK", "IND", "BGD", "NPL"]


@pytest.mark.parametrize(
    ("raw", "overall", "second", "third"),
    [("0,0,0", 0, 0, 0), ("2,2,1", 2, 2, 1), (" 1, 0, 1 ", 1, 0, 1)],
)
def test_parse_rio_marker(raw: str, overall: int, second: int, third: int) -> None:
    marker = parse_rio_marker(raw)

    assert marker is not None
    assert (marker.rio_overall, marker.rio_mitigation, marker.rio_adaptation) == (
        overall,
        second,
        third,
    )
    assert marker.is_climate_related is (overall > 0)
    assert marker.overall_is_max


def test_rio_marker_missing_and_invalid() -> None:
    assert parse_rio_marker(None) is None
    assert parse_rio_marker("  ") is None
    for bad in ("1,1", "1,1,1,1", "a,b,c", "3,0,0", "1;0;1"):
        with pytest.raises(ValueError):
            parse_rio_marker(bad)
    marker = parse_rio_marker("1,2,0")
    assert marker is not None and not marker.overall_is_max
