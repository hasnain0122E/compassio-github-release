"""Builders for ARTIFICIAL test fixtures.

Everything produced here is synthetic, tiny and labelled ``example`` so it can
never be mistaken for a research observation. Fixtures exercise parsing and
counting logic only; they must never be used to report coverage or model quality.
"""

import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest
from openpyxl import Workbook

EXAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<iati-activities generated-datetime="2000-01-01T00:00:00+00:00" version="2.03">
  <iati-activity default-currency="USD" hierarchy="1" last-updated-datetime="2000-01-01T00:00:00">
    <iati-identifier>XM-DAC-46004-00001-001-LN0001</iati-identifier>
    <title><narrative>Example Programme - Tranche 1</narrative></title>
    <description><narrative>Example description one.</narrative></description>
    <activity-status code="2"/>
    <activity-date type="1" iso-date="2025-01-01"/>
    <activity-date type="2" iso-date="2026-02-01"/>
    <recipient-country code="PK"/>
    <policy-marker vocabulary="99" code="Example climate priority"/>
    <sector vocabulary="1" code="23210"/>
    <transaction><transaction-type code="2"/><transaction-date iso-date="2026-02-01"/>
      <value value-date="2026-02-01">1000</value></transaction>
    <transaction><transaction-type code="3"/><transaction-date iso-date="2026-03-01"/>
      <value value-date="2026-03-01">-50</value></transaction>
    <transaction><transaction-type code="6"/><transaction-date iso-date="2025-03-01"/>
      <value value-date="2025-03-01">20</value></transaction>
  </iati-activity>
  <iati-activity default-currency="USD" hierarchy="1" last-updated-datetime="2000-01-01T00:00:00">
    <iati-identifier>XM-DAC-46004-00001-001-GRNT0002</iati-identifier>
    <title><narrative>Example Programme - Tranche 1</narrative></title>
    <description><narrative>Example description two.</narrative></description>
    <activity-status code="3"/>
    <activity-date type="1" iso-date="2010-01-01"/>
    <recipient-country code="PK"/>
    <transaction><transaction-type code="99"/><transaction-date iso-date="2011-01-01"/>
      <value value-date="2011-01-01">5</value></transaction>
  </iati-activity>
  <iati-activity hierarchy="1" last-updated-datetime="2000-01-01T00:00:00">
    <iati-identifier>XM-DAC-46004-00002-001-LN0003</iati-identifier>
    <title><narrative>Example Other Project</narrative></title>
    <description><narrative>Example description three.</narrative></description>
    <activity-status code="2"/>
    <recipient-country code="PK"/>
    <transaction><transaction-type code="3"/><transaction-date iso-date="2012-01-01"/>
      <value value-date="2012-01-01">7</value></transaction>
  </iati-activity>
</iati-activities>
"""


def write_xlsx(path: Path, sheets: dict[str, list[list[object]]]) -> Path:
    workbook = Workbook()
    first = True
    for name, rows in sheets.items():
        sheet = workbook.active if first else workbook.create_sheet()
        assert sheet is not None
        sheet.title = name
        first = False
        for row in rows:
            sheet.append(row)
    workbook.save(path)
    return path


def write_zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


MakeXlsx = Callable[[str, dict[str, list[list[object]]]], Path]
MakeZip = Callable[[str, dict[str, bytes]], Path]


@pytest.fixture
def example_xml_text() -> str:
    return EXAMPLE_XML


@pytest.fixture
def make_xlsx(tmp_path: Path) -> MakeXlsx:
    return lambda name, sheets: write_xlsx(tmp_path / name, sheets)


@pytest.fixture
def make_zip(tmp_path: Path) -> MakeZip:
    return lambda name, members: write_zip(tmp_path / name, members)
