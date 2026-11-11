"""Source-specific counting, filtering and issue logic over ARTIFICIAL frames.

Values are invented examples that exercise code paths only. They are not, and must
never be reported as, observations from any real source.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path

import pandas as pd
import pytest

from compassio_ml.audit.inspectors import (
    adb_project_number,
    inspect_adb,
    inspect_cfu,
    inspect_cpe,
    inspect_gcf_projects,
    inspect_gcf_readiness,
    inspect_research,
)
from compassio_ml.audit.loaders import SourceData, load_adb_iati, load_csv
from compassio_ml.audit.overlap import OverlapResult, _gcf_vs_cfu, gcf_refs_in_text
from compassio_ml.audit.research_audit import mentions_year_after
from compassio_ml.data.layout import DataLayout, MissingSourceDataError


def frame(rows: Sequence[Mapping[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows, dtype=object)


def data_with(tmp_path: Path, **frames: object) -> SourceData:
    data = SourceData(DataLayout(tmp_path))
    for name, value in frames.items():
        data.__dict__[name] = value  # pre-populate cached_property slots
    return data


def research_row(
    rid: str, recipient: str, marker: str | None, **extra: object
) -> dict[str, object]:
    row: dict[str, object] = {
        "ID": rid,
        "AidData_Record_ID": rid,
        "Commitment_Year": "2010",
        "Implementation_Start_Year": None,
        "Completion_Year": None,
        "Recipient": recipient,
        "Sector_Name": "EXAMPLE SECTOR",
        "Title": f"Example title {rid}",
        "Description": f"Example description {rid}",
        "Amount_Constant_USD_2021": "100",
        "Grant_Element_OECD_Cash-Flow": None,
        "rio_marker": marker,
    }
    row.update(extra)
    return row


def test_research_counts_labels_and_pakistan(tmp_path: Path) -> None:
    cf = frame(
        [
            research_row("1", "Pakistan", "2,2,0"),
            research_row("2", "Pakistan", "0,0,0"),
            research_row("3", "Kenya", "1,0,1", Amount_Constant_USD_2021=None),
            research_row("4", "Kenya", "0,0,0", Description="Example description 1"),
            research_row("5", "Pakistan ", None),
        ]
    )

    audit = inspect_research(data_with(tmp_path, research_climate=cf))

    assert audit.facts["records"] == 5
    assert audit.facts["climate_positive"] == 2
    assert audit.facts["climate_negative"] == 2
    assert audit.facts["label_missing_or_invalid"] == 1
    assert audit.facts["pakistan_records"] == 3  # whitespace-insensitive match
    assert audit.facts["pakistan_climate_positive"] == 1
    issue_ids = {i.issue_id for i in audit.issues}
    assert "research_rio_marker_missing_or_invalid" in issue_ids
    dup = next(i for i in audit.issues if i.issue_id == "research_duplicate_descriptions")
    assert dup.affected_records == 2
    amount = next(i for i in audit.issues if i.issue_id == "research_amount_missing")
    assert amount.affected_records == 1


def test_research_duplicate_ids_counted(tmp_path: Path) -> None:
    cf = frame([research_row("1", "Kenya", "0,0,0"), research_row("1", "Kenya", "0,0,0")])

    audit = inspect_research(data_with(tmp_path, research_climate=cf))

    assert audit.coverage[0].duplicate_id_rows == 2
    assert audit.facts["aiddata_id_unique"] is False


def test_gcf_projects_pakistan_single_and_multi_country(tmp_path: Path) -> None:
    gp = frame(
        [
            {
                "Ref #": "FP901",
                "Modality": "PAP",
                "Project Name": "Example A",
                "Countries": "Pakistan",
                "BM": "B.40",
                "Theme": "Adaptation",
                "FA Financing": "100",
            },
            {
                "Ref #": "FP902",
                "Modality": "PAP",
                "Project Name": "Example B",
                "Countries": "India, Pakistan, Nepal",
                "BM": "B.41",
                "Theme": "Mitigation",
                "FA Financing": "300",
            },
            {
                "Ref #": "SAP903",
                "Modality": "SAP",
                "Project Name": "Example C",
                "Countries": "Kenya",
                "BM": "B.9",
                "Theme": "Adaptation",
                "FA Financing": "not reported",
            },
        ]
    )

    audit = inspect_gcf_projects(data_with(tmp_path, gcf_projects=gp))

    assert audit.pakistan[0].records == 2
    assert "1 single-country, 1 multi-country" in audit.pakistan[0].notes
    assert audit.facts["pakistan_single_country_refs"] == ["FP901"]
    assert audit.facts["board_meetings"] == ["B.9", "B.40", "B.41"]
    assert audit.year2026[0].records is None  # no dates in file: undeterminable, not zero
    assert any(i.issue_id.endswith("_unparseable") for i in audit.issues)


def test_gcf_readiness_dates_duplicates_and_placeholders(tmp_path: Path) -> None:
    rows: list[dict[str, object]] = [
        {
            "Ref #": "EX-RS-001",
            "Activity": "Example",
            "Project Title": "T1",
            "Country": "Pakistan",
            "Status": "Closed",
            "Approved Date": "May 1, 2015",
            "Financing": "300000",
        },
        {
            "Ref #": "Shared",
            "Activity": None,
            "Project Title": "T2",
            "Country": "Kenya",
            "Status": "Cancelled",
            "Approved Date": "Jan 2, 2026",
            "Financing": "1",
        },
        {
            "Ref #": "Shared",
            "Activity": None,
            "Project Title": "T3",
            "Country": "Chile",
            "Status": "Disbursed",
            "Approved Date": "Feb 3, 2020",
            "Financing": "37000",
        },
    ]

    audit = inspect_gcf_readiness(data_with(tmp_path, gcf_readiness=frame(rows)))

    cov = audit.coverage[0]
    assert (cov.earliest, cov.latest) == ("2015-05-01", "2026-01-02")
    assert cov.records_dated_2026 == 1
    assert cov.pakistan_records == 1
    assert audit.facts["placeholder_financing_le_1"] == 1
    assert audit.facts["ref_duplicate_rows"] == 2


def test_adb_parser_and_transaction_semantics(tmp_path: Path, example_xml_text: str) -> None:
    path = tmp_path / "example.xml"
    path.write_text(example_xml_text, encoding="utf-8")
    adb = load_adb_iati(path)

    audit = inspect_adb(data_with(tmp_path, adb=adb))

    assert len(adb.activities) == 3
    assert len(adb.transactions) == 5
    assert adb.iati_version == "2.03"
    assert audit.facts["project_numbers"] == 2
    by_type = audit.facts["transactions_by_type"]
    assert isinstance(by_type, dict)
    assert by_type["3 Disbursement"]["count"] == 2
    assert by_type["3 Disbursement"]["negative_values"] == 1
    assert by_type["99 UNKNOWN"]["count"] == 1
    issue_ids = {i.issue_id for i in audit.issues}
    assert "adb_unknown_transaction_type" in issue_ids
    missing_ccy = next(i for i in audit.issues if i.issue_id == "adb_transaction_missing_currency")
    assert missing_ccy.affected_records == 1  # third activity has no default-currency
    shared = next(i for i in audit.issues if i.issue_id == "adb_shared_titles_across_instruments")
    assert shared.affected_records == 2
    actual_start_2026 = next(
        r for r in audit.year2026 if r.date_field.startswith("activity-date type 2")
    )
    assert actual_start_2026.records == 1


def test_adb_project_number() -> None:
    assert adb_project_number("XM-DAC-46004-37218-013-LN2202") == "37218-013"
    assert adb_project_number("OTHER-ID") is None
    assert adb_project_number(None) is None


def test_cfu_pakistan_and_missing_years(tmp_path: Path) -> None:
    projects = frame(
        [
            {
                "Fund": "Example Fund (GCF-1)",
                "Country": "Pakistan",
                "Name of Project": "(FP901) A",
                "Theme/Objective": "Adaptation",
                "Summary": None,
                "Approved year": "2019",
                "Amount of Funding Approved (USD millions)": "10",
                "Disbursed (USD millions)": " ",
                "Concessional loan": None,
                "Grant": "10",
                "Guarantee": None,
                "Equity": None,
            },
            {
                "Fund": "Other Fund",
                "Country": "Regional - South Asia",
                "Name of Project": "B",
                "Theme/Objective": "Multiple foci",
                "Summary": "Example",
                "Approved year": None,
                "Amount of Funding Approved (USD millions)": "2",
                "Disbursed (USD millions)": "1",
                "Concessional loan": None,
                "Grant": "2",
                "Guarantee": None,
                "Equity": None,
            },
        ]
    )
    sheets = {
        "Projects": projects,
        "Pledges": frame(
            [
                {
                    "Fund": "F",
                    "Pledged (USD million current)": "1",
                    "Deposited (USD million current)": "1",
                }
            ]
        ),
        "Fund Status": frame([{"Fund": None, "Pledge (USD mn)": "3"}]),
    }

    audit = inspect_cfu(data_with(tmp_path, cfu=sheets))

    assert audit.pakistan[0].records == 1
    assert audit.facts["south_asia_regional_rows"] == 1
    assert audit.facts["approved_year_missing"] == 1
    assert audit.facts["whitespace_only_disbursed"] == 1
    assert audit.facts["gcf_fund_rows"] == 1
    assert "cfu_fund_status_unnamed_row" in {i.issue_id for i in audit.issues}


def test_cpe_counts_families_not_documents(tmp_path: Path) -> None:
    def doc(family: str, doc_id: str, geo: str, pub: str) -> dict[str, object]:
        return {
            "Family Name": f"Example {family}",
            "Family Summary": "<p>x</p>",
            "Family Publication Date": pub,
            "Family URL": f"https://example.invalid/{family}",
            "Document Title": "Doc",
            "Document URL": f"https://example.invalid/d/{doc_id}",
            "Document Content URL": f"https://example.invalid/c/{doc_id}",
            "Document Type": None,
            "Geographies": geo,
            "Source": "GCF",
        }

    cpe = frame(
        [
            doc("a", "1", "PAK", "2026-01-01T00:00:00+00:00"),
            doc("a", "2", "PAK", "2026-01-01T00:00:00+00:00"),
            doc("b", "3", "IND;PAK", "2025-01-01T00:00:00+00:00"),
            doc("c", "4", "KEN", "2024-01-01T00:00:00+00:00"),
        ]
    )

    audit = inspect_cpe(data_with(tmp_path, cpe=cpe))

    assert audit.primary_record_count == 3
    assert audit.pakistan[0].records == 2  # families a and b
    assert audit.year2026[0].records == 1  # family a only
    assert audit.coverage[0].record_count == 4  # documents


def test_gcf_reference_codes_and_cfu_matching(tmp_path: Path) -> None:
    assert gcf_refs_in_text("(FP085) Example; see SAP 24 and fp7") == {"FP085", "SAP024", "FP007"}
    assert gcf_refs_in_text(None) == set()

    gp = frame(
        [
            {"Ref #": "FP901", "Project Name": "Example Resilience"},
            {"Ref #": "FP902", "Project Name": "Example Solar"},
        ]
    )
    cfu = frame(
        [
            {
                "Fund": "Example (GCF-1)",
                "Country": "Pakistan",
                "Name of Project": "(FP901) Renamed",
                "Approved year": "2019",
                "Summary": None,
            },
            {
                "Fund": "Example (GCF-1)",
                "Country": "Kenya",
                "Name of Project": "Example Solar",
                "Approved year": "2020",
                "Summary": None,
            },
        ]
    )
    out = OverlapResult()

    _gcf_vs_cfu(data_with(tmp_path, gcf_projects=gp, cfu={"Projects": cfu}), out)

    statuses = {(r.left_key, r.status) for r in out.rows if r.status != "summary"}
    assert statuses == {
        ("FP901", "probable_match_reference_code"),
        ("FP902", "possible_match_requires_review"),
    }


def test_later_year_mentions() -> None:
    assert mentions_year_after("Completed in 2015 after delays", 2012)
    assert not mentions_year_after("Signed in 2012", 2012)


def test_csv_loader_rejects_ragged_rows(tmp_path: Path) -> None:
    path = tmp_path / "example.csv"
    path.write_text("a,b\n1,2\n3\n", encoding="utf-8")

    with pytest.raises(ValueError, match="fields"):
        load_csv(path)


def test_loader_reports_missing_source_folder(tmp_path: Path) -> None:
    data = SourceData(DataLayout(tmp_path))

    with pytest.raises(MissingSourceDataError, match="gcf_projects"):
        _ = data.gcf_projects
