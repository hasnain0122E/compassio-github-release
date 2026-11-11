"""Registry of expected sources: curated, human-reviewable metadata.

``confirmed_facts`` are statements verified by inspecting the file bytes in Task 002.
``assumptions`` are plausible but unverified (e.g. inferred from a filename) and
must not be presented as facts. Measured values (hash, size, counts) are *not*
stored here; they come from the inventory and inspection commands.
"""

from dataclasses import dataclass, field

from compassio_ml.data.formats import FileFormat


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    source_id: str
    title: str
    publisher: str
    expected_format: FileFormat
    unit_of_observation: str
    critical: bool
    # Exact URL the file was downloaded from; only when actually recorded.
    source_url: str | None = None
    # Publisher landing/record page. NOT evidence of the exact download location.
    reference_url: str | None = None
    # Published licence or terms text noted for later human review. Not an authorization.
    license_notes: str | None = None
    related_sources: tuple[str, ...] = ()
    confirmed_facts: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = field(default=())


SOURCES: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        source_id="research_paper",
        title=(
            "A Benchmark Dataset of Chinese Development Finance with Climate Relevance and "
            "SDG Annotations from 2000-2021 (Scientific Data, 2026) - data files"
        ),
        publisher="Qi, Tang, Zhang, Wang & Qian (Scientific Data 13, 277, 2026), via Figshare",
        expected_format=FileFormat.ZIP,
        unit_of_observation="one AidData GCDF 3.0 project/activity record (AidData_Record_ID)",
        critical=True,
        reference_url="https://doi.org/10.6084/m9.figshare.30015124",
        license_notes=(
            "Figshare API (api.figshare.com/v2/articles/30015124, checked 2026-11-09) lists the "
            "item licence as CC0 (creativecommons.org/publicdomain/zero/1.0). The article itself "
            "(doi:10.1038/s41597-026-06605-9) is CC BY 4.0. Cite the paper. Not human-reviewed."
        ),
        related_sources=("aiddata",),
        confirmed_facts=(
            "Archive contains exactly two workbooks: Chinese_Climate_Finance_2000-2021.xlsx "
            "and Chinese_Development_Finance_SDG_Categorizations_2000-2021.xlsx",
            "Both workbooks are byte-identical to Figshare item 30015124 version 1 (MD5 "
            "7fd6e1d1459c1aac2fe32694010053cf and 488f213db78985973051e81e7fd639b9 match the "
            "Figshare API, checked 2026-11-09); Figshare published date 2026-02-20",
            "Every AidData_Record_ID in both workbooks exists in AidData GCDF 3.0",
            "rio_marker order is (Overall, Mitigation, Adaptation) per the paper's Table 1 "
            "header; scores 0/1/2 = not targeted/significant/principal per Methods, Data processing",
            "Research workbook text fields are truncated at 255 characters (Title 12 rows, "
            "Funding_Agencies 7, Funding_Agencies_Type 1) relative to AidData",
        ),
        assumptions=(
            "The local ZIP wrapper (30015124.zip) bundles the Figshare files at download time; "
            "its own bytes are not published by Figshare",
        ),
        limitations=(
            "The paper states inter-annotator agreement statistics are included in the final "
            "dataset, but no agreement column exists in either workbook",
            "Labels are the authors' annotations, cross-verified with ClimateBERT per the paper; "
            "they are not independent ground truth",
        ),
    ),
    SourceDefinition(
        source_id="aiddata",
        title="AidData's Global Chinese Development Finance Dataset, Version 3.0",
        publisher="AidData (William & Mary)",
        reference_url=(
            "https://www.aiddata.org/data/"
            "aiddatas-global-chinese-development-finance-dataset-version-3-0"
        ),
        license_notes=(
            "Workbook 'License' sheet: Open Data Commons Attribution License (ODC-By 1.0); "
            "attribution to AidData required and the licence must be stated on redistribution. "
            "The dataset web page (checked 2026-11-09) states no licence and names two works as "
            "the official citation. Not human-reviewed."
        ),
        expected_format=FileFormat.ZIP,
        unit_of_observation="one Chinese official-sector project/activity commitment record",
        critical=True,
        related_sources=("research_paper",),
        confirmed_facts=(
            "Workbook 'Contents' sheet states release date November 07, 2023",
            "Workbook 'License' sheet states Open Data Commons Attribution License (ODC-By 1.0)",
            "'Guide' sheet states 20,985 records, 17,957 recommended for aggregates",
            "The AidData dataset page offers a download with the identical filename "
            "AidDatas_Global_Chinese_Development_Finance_Dataset_Version_3_0.zip (checked "
            "2026-11-09); the page gives 'Date Published November 6, 2023'",
        ),
        assumptions=(),
        limitations=(
            "Descriptions are retrospective summaries that may include implementation outcomes",
            "Archive contains macOS metadata (__MACOSX, .DS_Store) which is ignored",
        ),
    ),
    SourceDefinition(
        source_id="adb_pakistan",
        title="Asian Development Bank IATI activities - Pakistan",
        publisher="Asian Development Bank (IATI reporting-org XM-DAC-46004)",
        reference_url="https://data.adb.org/dataset/adb-projects-pakistan",
        license_notes=(
            "Not verified: the reference page returned HTTP 403 to automated access on "
            "2026-11-09. ADB data terms must be reviewed by a person."
        ),
        expected_format=FileFormat.XML,
        unit_of_observation="one IATI activity (an ADB loan/grant financing instrument)",
        critical=False,
        related_sources=("gcf_projects", "climate_project_explorer"),
        confirmed_facts=(
            "IATI standard version 2.03; generated-datetime 2026-10-21T16:49:28+08:00",
            "All activities report recipient-country PK and default-currency USD",
        ),
        assumptions=("Download URL not recorded",),
        limitations=(
            "Policy markers use ADB's own vocabulary (99) without significance scores; they "
            "are not OECD Rio markers",
        ),
    ),
    SourceDefinition(
        source_id="gcf_projects",
        title="Green Climate Fund Open Data Library - funded projects export",
        publisher="Green Climate Fund",
        reference_url="https://data.greenclimate.fund/public/data/projects",
        license_notes="GCF Terms and conditions (greenclimate.fund/terms-and-conditions, read 2026-11-09): use for private study, research, teaching and non-commercial purposes encouraged; commercial use, redistribution or derivatives for commercial purposes need prior written consent; attribution 'First published by the Green Climate Fund' with a link; no implied endorsement. Not a legal review.",
        expected_format=FileFormat.XLSX,
        unit_of_observation="one GCF funded project (FP/SAP reference number)",
        critical=True,
        related_sources=("gcf_historical", "climate_funds_update", "climate_project_explorer"),
        confirmed_facts=("Single sheet 'Sheet 1'; reference numbers are FPnnn/SAPnnn",),
        assumptions=(
            "Filename suffix 1794139775112 read as an epoch-milliseconds export timestamp "
            "(2026-11-08T12:09:35Z)",
            "'FA Financing' is GCF funding in USD (column header states no unit)",
        ),
        limitations=(
            "Workbook properties show it was written by openpyxl and all cells are text; the "
            "bytes may not be the publisher's original export",
            "No approval date column; only board meeting code (BM)",
        ),
    ),
    SourceDefinition(
        source_id="gcf_readiness",
        title="Green Climate Fund Open Data Library - readiness activities export",
        publisher="Green Climate Fund",
        reference_url="https://data.greenclimate.fund/public/data/readiness",
        license_notes="GCF Terms and conditions (greenclimate.fund/terms-and-conditions, read 2026-11-09): use for private study, research, teaching and non-commercial purposes encouraged; commercial use, redistribution or derivatives for commercial purposes need prior written consent; attribution 'First published by the Green Climate Fund' with a link; no implied endorsement. Not a legal review.",
        expected_format=FileFormat.XLSX,
        unit_of_observation="one readiness grant/activity row (Ref # is not unique)",
        critical=False,
        related_sources=("climate_funds_update", "gcf_countries"),
        assumptions=(
            "Filename suffix read as export timestamp 2026-11-08T12:06:19Z",
            "'Financing' is USD (column header states no unit)",
        ),
        limitations=(
            "Written by openpyxl; all cells text",
            "Cancelled grants carry placeholder Financing values (e.g. 1)",
        ),
    ),
    SourceDefinition(
        source_id="gcf_countries",
        title="Green Climate Fund Open Data Library - country summary export",
        publisher="Green Climate Fund",
        reference_url="https://data.greenclimate.fund/public/data/countries",
        license_notes="GCF Terms and conditions (greenclimate.fund/terms-and-conditions, read 2026-11-09): use for private study, research, teaching and non-commercial purposes encouraged; commercial use, redistribution or derivatives for commercial purposes need prior written consent; attribution 'First published by the Green Climate Fund' with a link; no implied endorsement. Not a legal review.",
        expected_format=FileFormat.XLSX,
        unit_of_observation="one country (aggregate of readiness and funded-activity counts/amounts)",
        critical=False,
        related_sources=("gcf_projects", "gcf_readiness"),
        assumptions=("Filename suffix read as export timestamp 2026-11-08T12:06:10Z",),
        limitations=(
            "Aggregates: must never be summed with project-level amounts",
            "Written by openpyxl; all cells text",
        ),
    ),
    SourceDefinition(
        source_id="climate_funds_update",
        title="Climate Funds Update - website master workbook 2025",
        publisher="Climate Funds Update (ODI / Heinrich Boll Stiftung)",
        reference_url="https://climatefundsupdate.org/data-dashboard/",
        license_notes=(
            "The data dashboard (checked 2026-11-09) links an Excel file named "
            "CFU-Website-Master-2025.xlsx and shows '(c) Copyright Climate Funds Update 2026'; "
            "no licence or reuse terms are stated. Terms must be reviewed by a person."
        ),
        expected_format=FileFormat.XLSX,
        unit_of_observation="Projects sheet: one fund-approved project row; Pledges: one "
        "contributor pledge; Fund Status: one fund",
        critical=True,
        related_sources=("gcf_projects", "gcf_readiness"),
        confirmed_facts=(
            "Sheets: 'Fund Status', 'Pledges', 'Projects'",
            "The CFU data dashboard links a download with the identical filename "
            "CFU-Website-Master-2025.xlsx (checked 2026-11-09)",
        ),
        assumptions=("Publisher attribution from the filename; download URL not recorded",),
        limitations=(
            "Workbook author metadata names an individual, not the publisher; provenance of the "
            "copy should be confirmed",
            "Amounts are USD millions",
        ),
    ),
    SourceDefinition(
        source_id="climate_project_explorer",
        title="Climate Project Explorer - search results export",
        publisher="Climate Project Explorer (climateprojectexplorer.org)",
        expected_format=FileFormat.CSV,
        unit_of_observation="one document; documents are grouped into project 'families'",
        critical=False,
        reference_url="https://climateprojectexplorer.org",
        license_notes="Not checked in Task 003. Terms must be reviewed by a person.",
        related_sources=("gcf_projects", "adb_pakistan"),
        confirmed_facts=(
            "Family and document URLs in the file are on climateprojectexplorer.org",
            "Rows cover funds GCF, GEF, AF and CIF",
        ),
        assumptions=("Export reflects one search query whose parameters were not recorded",),
        limitations=(
            "No financial fields",
            "Family Publication Date is the publication date on the explorer, not an approval date",
        ),
    ),
    SourceDefinition(
        source_id="gcf_historical",
        title="T20 GCF portfolio co-financing database V2.1 (historical research dataset)",
        publisher="Research authors (archive mjcszv9t52-1)",
        expected_format=FileFormat.ZIP,
        unit_of_observation="one GCF funded project (Ref_N) with co-financing breakdown",
        critical=False,
        related_sources=("gcf_projects",),
        confirmed_facts=(
            "Workbook properties: created 2020-03-25, modified 2020-03-26",
            "'TO READ' sheet states Total Project Financing is in USD thousands",
        ),
        assumptions=("Archive name suggests a Mendeley Data dataset id; URL not recorded",),
        limitations=(
            "'TO READ' describes Project Name, Date of Approval and Country columns that are "
            "absent from the Portfolio sheet",
            "Duplicate column headers in the Portfolio sheet",
        ),
    ),
)

SOURCES_BY_ID: dict[str, SourceDefinition] = {s.source_id: s for s in SOURCES}
