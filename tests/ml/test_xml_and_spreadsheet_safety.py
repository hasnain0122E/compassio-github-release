"""Safe XML parsing and read-only spreadsheet access. Artificial inputs only."""

import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from compassio_ml.safety import (
    InvalidXMLError,
    MacroEnabledWorkbookError,
    iter_xml_elements,
    list_sheets,
    read_sheet,
)

MakeXlsx = Callable[[str, dict[str, list[list[object]]]], Path]


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "example.xml"
    path.write_text(text, encoding="utf-8")
    return path


def test_iterates_matching_elements(tmp_path: Path) -> None:
    path = write(tmp_path, "<root><item id='1'/><other/><item id='2'/></root>")

    ids = [element.get("id") for element in iter_xml_elements(path, "item")]

    assert ids == ["1", "2"]


def test_malformed_xml_raises(tmp_path: Path) -> None:
    path = write(tmp_path, "<root><item></root>")

    with pytest.raises(InvalidXMLError, match="Malformed"):
        list(iter_xml_elements(path, "item"))


def test_entity_expansion_rejected(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
        "<r><item>&b;</item></r>",
    )

    with pytest.raises(InvalidXMLError, match="Forbidden"):
        list(iter_xml_elements(path, "item"))


def test_external_entity_rejected(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        "<r><item>&x;</item></r>",
    )

    with pytest.raises(InvalidXMLError):
        list(iter_xml_elements(path, "item"))


def test_missing_xml_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        list(iter_xml_elements(tmp_path / "absent.xml", "item"))


def test_read_sheet_returns_strings_and_drops_empty_rows(make_xlsx: MakeXlsx) -> None:
    path = make_xlsx(
        "example.xlsx",
        {
            "Data": [
                ["Ref #", "Amount", "Flag", "When"],
                ["EX1", 25000000, True, None],
                [None, None, None, None],
                ["EX2", 12.5, False, "2000-01-01"],
            ]
        },
    )

    table = read_sheet(path, "Data")

    assert table.header == ("Ref #", "Amount", "Flag", "When")
    assert table.rows == [("EX1", "25000000", "TRUE", None), ("EX2", "12.5", "FALSE", "2000-01-01")]


def test_duplicate_headers_are_disambiguated(make_xlsx: MakeXlsx) -> None:
    path = make_xlsx("example.xlsx", {"Data": [["a", "b", "a", "a"], [1, 2, 3, 4]]})

    assert read_sheet(path, "Data").header == ("a", "b", "a__dup1", "a__dup2")


def test_unnamed_empty_columns_dropped(make_xlsx: MakeXlsx) -> None:
    path = make_xlsx("example.xlsx", {"Data": [["a", None, "b"], [1, None, 2]]})

    assert read_sheet(path, "Data").header == ("a", "b")


def test_list_sheets_and_missing_sheet(make_xlsx: MakeXlsx) -> None:
    path = make_xlsx("example.xlsx", {"First": [["a"]], "Second": [["b"]]})

    assert list_sheets(path) == ["First", "Second"]
    with pytest.raises(KeyError, match="Third"):
        read_sheet(path, "Third")


def test_workbook_from_bytes(make_xlsx: MakeXlsx) -> None:
    path = make_xlsx("example.xlsx", {"S": [["a"], ["x"]]})

    assert read_sheet(path.read_bytes(), "S").rows == [("x",)]


def test_macro_enabled_workbook_refused(tmp_path: Path) -> None:
    path = tmp_path / "example.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
        archive.writestr("xl/vbaProject.bin", b"\x00example")

    with pytest.raises(MacroEnabledWorkbookError):
        read_sheet(path, "Sheet1")
