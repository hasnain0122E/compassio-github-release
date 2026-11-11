"""Load each registered source into string-typed DataFrames via the safety layer.

No type coercion happens here: every cell is the source's text (or ``None``) so
that the audit can report what is actually in the file.
"""

import csv
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from xml.etree.ElementTree import Element

import pandas as pd

from compassio_ml.data.layout import DataLayout, MissingSourceDataError
from compassio_ml.safety.archive import inspect_zip, read_zip_member
from compassio_ml.safety.spreadsheet import WorkbookSource, list_sheets, read_sheet
from compassio_ml.safety.xml import iter_xml_elements


def table_to_frame(source: WorkbookSource, sheet: str) -> pd.DataFrame:
    table = read_sheet(source, sheet)
    return pd.DataFrame(table.rows, columns=list(table.header), dtype=object)


def single_file(directory: Path, suffix: str, source_id: str) -> Path:
    if not directory.is_dir():
        raise MissingSourceDataError(
            f"Required source '{source_id}' folder not found: {directory}. "
            "Copy the original file into data/raw/<source_id>/."
        )
    matches = sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == suffix)
    if len(matches) != 1:
        raise MissingSourceDataError(
            f"Expected exactly one {suffix} file for source '{source_id}' in {directory}, "
            f"found {len(matches)}"
        )
    return matches[0]


def zip_member_by_suffix(archive: Path, suffix: str, *, contains: str = "") -> str:
    names = [
        m.name
        for m in inspect_zip(archive)
        if not m.is_dir and not m.is_junk and m.suffix == suffix and contains in m.name
    ]
    if len(names) != 1:
        raise ValueError(
            f"Expected one {suffix} member containing {contains!r} in {archive}: {names}"
        )
    return names[0]


@dataclass(frozen=True, slots=True)
class AdbFrames:
    activities: pd.DataFrame
    transactions: pd.DataFrame
    policy_markers: pd.DataFrame
    sectors: pd.DataFrame
    generated_datetime: str | None
    iati_version: str | None


def _text(element: Element, path: str) -> str | None:
    found = element.find(path)
    return found.text if found is not None else None


def _code(element: Element, path: str) -> str | None:
    found = element.find(path)
    return found.get("code") if found is not None else None


def load_adb_iati(path: Path) -> AdbFrames:
    """Parse IATI activities and their nested transactions/markers/sectors."""
    activities: list[dict[str, str | int | None]] = []
    transactions: list[dict[str, str | None]] = []
    markers: list[dict[str, str | None]] = []
    sectors: list[dict[str, str | None]] = []
    root_attrs: dict[str, str] = {}

    with path.open("rb") as handle:
        head = handle.read(4096).decode("utf-8", "replace")
    if "<iati-activities" in head:
        fragment = head.split("<iati-activities", 1)[1].split(">", 1)[0]
        for key in ("generated-datetime", "version"):
            marker = f'{key}="'
            if marker in fragment:
                root_attrs[key] = fragment.split(marker, 1)[1].split('"', 1)[0]

    for act in iter_xml_elements(path, "iati-activity"):
        identifier = _text(act, "iati-identifier")
        default_currency = act.get("default-currency")
        dates = {d.get("type"): d.get("iso-date") for d in act.findall("activity-date")}
        activities.append(
            {
                "iati_identifier": identifier,
                "title": _text(act, "title/narrative"),
                "description": _text(act, "description/narrative"),
                "activity_status": _code(act, "activity-status"),
                "default_currency": default_currency,
                "last_updated": act.get("last-updated-datetime"),
                "hierarchy": act.get("hierarchy"),
                "recipient_countries": "|".join(
                    c.get("code") or "" for c in act.findall("recipient-country")
                ),
                "planned_start": dates.get("1"),
                "actual_start": dates.get("2"),
                "planned_end": dates.get("3"),
                "actual_end": dates.get("4"),
                "document_links": len(act.findall("document-link")),
                "default_finance_type": _code(act, "default-finance-type"),
            }
        )
        for tx in act.findall("transaction"):
            ttype = tx.find("transaction-type")
            value = tx.find("value")
            tdate = tx.find("transaction-date")
            transactions.append(
                {
                    "iati_identifier": identifier,
                    "transaction_type": ttype.get("code") if ttype is not None else None,
                    "value": value.text if value is not None else None,
                    "value_currency": value.get("currency") if value is not None else None,
                    "default_currency": default_currency,
                    "value_date": value.get("value-date") if value is not None else None,
                    "transaction_date": tdate.get("iso-date") if tdate is not None else None,
                }
            )
        for pm in act.findall("policy-marker"):
            markers.append(
                {
                    "iati_identifier": identifier,
                    "vocabulary": pm.get("vocabulary"),
                    "code": pm.get("code"),
                    "significance": pm.get("significance"),
                }
            )
        for sec in act.findall("sector"):
            sectors.append(
                {
                    "iati_identifier": identifier,
                    "vocabulary": sec.get("vocabulary"),
                    "code": sec.get("code"),
                    "percentage": sec.get("percentage"),
                }
            )

    return AdbFrames(
        activities=pd.DataFrame(activities, dtype=object),
        transactions=pd.DataFrame(transactions, dtype=object),
        policy_markers=pd.DataFrame(markers, dtype=object),
        sectors=pd.DataFrame(sectors, dtype=object),
        generated_datetime=root_attrs.get("generated-datetime"),
        iati_version=root_attrs.get("version"),
    )


def load_csv(path: Path) -> pd.DataFrame:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = [[cell if cell != "" else None for cell in row] for row in reader]
    widths = {len(r) for r in rows}
    if widths and widths != {len(header)}:
        raise ValueError(
            f"{path.name}: rows have {sorted(widths)} fields, header has {len(header)}"
        )
    return pd.DataFrame(rows, columns=header, dtype=object)


@dataclass
class SourceData:
    """Lazily loaded frames for every source, shared by all audit steps in one run."""

    layout: DataLayout

    def raw_dir(self, source_id: str) -> Path:
        return self.layout.raw / source_id

    # -- research paper -------------------------------------------------------------
    @cached_property
    def research_archive(self) -> Path:
        return single_file(self.raw_dir("research_paper"), ".zip", "research_paper")

    @cached_property
    def research_climate(self) -> pd.DataFrame:
        member = zip_member_by_suffix(self.research_archive, ".xlsx", contains="Climate_Finance")
        data = read_zip_member(self.research_archive, member)
        sheets = list_sheets(data)
        return table_to_frame(data, sheets[0])

    @cached_property
    def research_sdg(self) -> dict[str, pd.DataFrame]:
        member = zip_member_by_suffix(self.research_archive, ".xlsx", contains="SDG")
        data = read_zip_member(self.research_archive, member)
        return {sheet: table_to_frame(data, sheet) for sheet in list_sheets(data)}

    # -- AidData --------------------------------------------------------------------
    @cached_property
    def aiddata_archive(self) -> Path:
        return single_file(self.raw_dir("aiddata"), ".zip", "aiddata")

    @cached_property
    def aiddata_workbook_bytes(self) -> bytes:
        member = zip_member_by_suffix(self.aiddata_archive, ".xlsx")
        return read_zip_member(self.aiddata_archive, member)

    @cached_property
    def aiddata(self) -> pd.DataFrame:
        return table_to_frame(self.aiddata_workbook_bytes, "GCDF_3.0")

    @cached_property
    def aiddata_sheets(self) -> list[str]:
        return list_sheets(self.aiddata_workbook_bytes)

    # -- ADB IATI -------------------------------------------------------------------
    @cached_property
    def adb(self) -> AdbFrames:
        return load_adb_iati(single_file(self.raw_dir("adb_pakistan"), ".xml", "adb_pakistan"))

    # -- GCF ------------------------------------------------------------------------
    def _single_sheet(self, source_id: str) -> pd.DataFrame:
        path = single_file(self.raw_dir(source_id), ".xlsx", source_id)
        sheets = list_sheets(path)
        if len(sheets) != 1:
            raise ValueError(f"{path.name}: expected one sheet, found {sheets}")
        return table_to_frame(path, sheets[0])

    @cached_property
    def gcf_projects(self) -> pd.DataFrame:
        return self._single_sheet("gcf_projects")

    @cached_property
    def gcf_readiness(self) -> pd.DataFrame:
        return self._single_sheet("gcf_readiness")

    @cached_property
    def gcf_countries(self) -> pd.DataFrame:
        return self._single_sheet("gcf_countries")

    @cached_property
    def gcf_historical(self) -> pd.DataFrame:
        archive = single_file(self.raw_dir("gcf_historical"), ".zip", "gcf_historical")
        data = read_zip_member(archive, zip_member_by_suffix(archive, ".xlsx"))
        return table_to_frame(data, "Portfolio")

    @cached_property
    def gcf_historical_header_raw(self) -> list[str]:
        """Original Portfolio header (before de-duplication) to report duplicate names."""
        archive = single_file(self.raw_dir("gcf_historical"), ".zip", "gcf_historical")
        data = read_zip_member(archive, zip_member_by_suffix(archive, ".xlsx"))
        return [c for c in read_sheet(data, "Portfolio").header if "__dup" in c]

    # -- Climate Funds Update -------------------------------------------------------
    @cached_property
    def cfu_path(self) -> Path:
        return single_file(self.raw_dir("climate_funds_update"), ".xlsx", "climate_funds_update")

    @cached_property
    def cfu(self) -> dict[str, pd.DataFrame]:
        return {sheet: table_to_frame(self.cfu_path, sheet) for sheet in list_sheets(self.cfu_path)}

    # -- Climate Project Explorer ---------------------------------------------------
    @cached_property
    def cpe(self) -> pd.DataFrame:
        return load_csv(
            single_file(
                self.raw_dir("climate_project_explorer"), ".csv", "climate_project_explorer"
            )
        )
