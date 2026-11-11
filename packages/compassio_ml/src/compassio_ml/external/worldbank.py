"""World Bank Projects API (v3): bounded acquisition and parsing.

Only an explicit field allow-list is requested, so staff names and IDs returned by ``fl=*``
(``teamleadname``, ``teamleaderupi``) are never collected.

Climate indicator (label category D): ``themev2_level3_exact`` values "Adaptation" /
"Mitigation" when "Climate Change" appears at theme level 2. These are World Bank theme tags
returned **without percentages** by this API; they are not Rio scores, and their absence is not
a negative label.
"""

import json
import re
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from compassio_ml.external.records import (
    CandidateRecord,
    SectorFamily,
    TextTiming,
    primary_family,
    wb_sector_family,
)
from compassio_ml.external.registry import RetrievalRun, read_retrieval_manifest

SOURCE_ID = "worldbank_projects"
PUBLISHER = "World Bank"
API = "https://search.worldbank.org/api/v3/projects"
PAGE_ROWS = 500
MAX_PAGES_PER_COUNTRY = 10
# Pakistan plus comparison countries with large adaptation/agriculture/water portfolios.
DEFAULT_COUNTRIES: tuple[str, ...] = ("PK", "BD", "NP", "LK", "KE", "MZ")
FIELDS: tuple[str, ...] = (
    "id",
    "project_name",
    "pdo",
    "project_abstract",
    "countrycode",
    "countryshortname",
    "boardapprovaldate",
    "closingdate",
    "status",
    "last_stage_reached_name",
    "public_disclosure_date",
    "fiscalyear",
    "major_sectors",
    "sectorcode",
    "themev2_level1_exact",
    "themev2_level2_exact",
    "themev2_level3_exact",
    "projectfinancialtype",
    "totalamt",
    "curr_total_commitment",
    "lendinginstr",
    "prodline",
    "milestones",
)
TERMS_URLS = {
    "terms_of_use_for_datasets.html": "https://www.worldbank.org/en/about/legal/terms-of-use-for-datasets",
}
_GCF_CODE = re.compile(r"\b(FP|SAP)\s?-?(\d{3})\b")
_WB_CODE = re.compile(r"\bP\d{6}\b")


def page_url(country: str, offset: int) -> str:
    return (
        f"{API}?format=json&countrycode_exact={country}&rows={PAGE_ROWS}&os={offset}"
        f"&fl={','.join(FIELDS)}"
    )


def acquire(run: RetrievalRun, countries: Iterable[str] = DEFAULT_COUNTRIES) -> list[str]:
    """Fetch every project page for each country, plus the terms page. Returns notes."""
    notes: list[str] = []
    countries = tuple(countries)
    run.parameters = {"countries": list(countries), "fields": list(FIELDS), "rows": PAGE_ROWS}
    for name, url in TERMS_URLS.items():
        run.fetch(url, name, max_bytes=5 * 1024 * 1024, role="terms")
    for country in countries:
        offset, total, pages = 0, None, 0
        while total is None or offset < total:
            if pages >= MAX_PAGES_PER_COUNTRY:
                notes.append(f"{country}: stopped at page cap {MAX_PAGES_PER_COUNTRY}")
                break
            retrieval = run.fetch(
                page_url(country, offset), f"projects_{country}_{offset:05d}.json", role="data"
            )
            pages += 1
            if retrieval is None:
                notes.append(f"{country}: page at offset {offset} failed; country incomplete")
                break
            payload = json.loads(retrieval.path.read_text(encoding="utf-8"))
            total = int(payload.get("total", 0))
            offset += PAGE_ROWS
        notes.append(f"{country}: API total={total}")
    return notes


def _iso3(codes: list[str]) -> list[str]:
    """ISO2 codes are kept as ``ISO2:XX``; the dataset build resolves them to ISO3."""
    return sorted({f"ISO2:{c}" for c in codes})


def _date(value: Any) -> str | None:
    if not value or not isinstance(value, str):
        return None
    return value[:10]


def _climate_themes(project: dict[str, Any]) -> list[str]:
    level2 = [str(v).strip() for v in project.get("themev2_level2_exact") or []]
    if "Climate Change" not in level2:
        return []
    level3 = {str(v).strip() for v in project.get("themev2_level3_exact") or []}
    return sorted(level3 & {"Adaptation", "Mitigation"})


def _sectors(project: dict[str, Any]) -> tuple[list[str], dict[SectorFamily, float]]:
    codes: list[str] = []
    weights: dict[SectorFamily, float] = {}
    for item in project.get("major_sectors") or []:
        major = item.get("major_sector", {}) if isinstance(item, dict) else {}
        code = str(major.get("major_sector_code") or "")
        if not code:
            continue
        codes.append(code)
        share = 0.0
        for sector in major.get("sectors") or []:
            pct = str(sector.get("sector_percent") or "0")
            share += float(pct) if pct.replace(".", "", 1).isdigit() else 0.0
        family = wb_sector_family(code)
        weights[family] = weights.get(family, 0.0) + share
    return sorted(set(codes)), weights


def _timing(project: dict[str, Any], retrieved: date) -> tuple[str, str]:
    status = str(project.get("status") or "")
    approval = _date(project.get("boardapprovaldate"))
    if status == "Pipeline" and (approval is None or date.fromisoformat(approval) > retrieved):
        return (
            TextTiming.PRE_APPROVAL_PIPELINE.value,
            f"status=Pipeline and board approval {approval or 'unset'} after retrieval "
            f"{retrieved.isoformat()}",
        )
    return (
        TextTiming.APPROVAL_STAGE_SNAPSHOT.value,
        "PDO/abstract as returned by the API at retrieval; may have been revised after "
        "approval; document date not verified",
    )


def parse_retrieval(directory: Path) -> list[CandidateRecord]:
    manifest = read_retrieval_manifest(directory)
    retrieval_id = str(manifest["retrieval_id"])
    by_id: dict[str, CandidateRecord] = {}
    for entry in manifest["files"]:
        if entry.get("role") != "data":
            continue
        path = directory / str(entry["file"])
        retrieved = datetime.fromisoformat(str(entry["retrieved_at"])).astimezone(UTC).date()
        payload = json.loads(path.read_text(encoding="utf-8"))
        projects = payload.get("projects") or {}
        if not isinstance(projects, dict):
            raise ValueError(f"Unexpected 'projects' structure in {path}")
        for pid, project in projects.items():
            if pid in by_id:
                existing = by_id[pid]
                existing.country_iso3 = sorted(
                    set(existing.country_iso3) | set(_iso3(project.get("countrycode") or []))
                )
                continue
            pdo = (project.get("pdo") or "").strip()
            abstract = (project.get("project_abstract") or "").strip()
            description = " ".join(part for part in (pdo, abstract) if part) or None
            codes, weights = _sectors(project)
            timing, basis = _timing(project, retrieved)
            text = f"{project.get('project_name') or ''} {description or ''}"
            refs = sorted(
                {f"gcf_project_pages:{m.group(1)}{m.group(2)}" for m in _GCF_CODE.finditer(text)}
                | {f"worldbank_projects:{c}" for c in _WB_CODE.findall(text) if c != pid}
            )
            by_id[pid] = CandidateRecord(
                source_id=SOURCE_ID,
                publisher=PUBLISHER,
                source_record_id=str(pid),
                retrieval_id=retrieval_id,
                raw_file=str(entry["file"]),
                raw_file_sha256=str(entry["sha256"]),
                document_url=f"https://projects.worldbank.org/en/projects-operations/project-detail/{pid}",
                title=project.get("project_name"),
                description=description,
                text_type="wb_pdo_and_abstract",
                country_iso3=_iso3(project.get("countrycode") or []),
                sector_codes=codes,
                sector_families=sorted(f.value for f in weights),
                sector_family=primary_family(weights).value,
                approval_date=_date(project.get("boardapprovaldate")),
                end_date=_date(project.get("closingdate")),
                text_date=None,
                text_date_basis=basis,
                text_timing=timing,
                status=project.get("status"),
                cross_references=refs,
                label_category="D_world_bank_climate_indicator"
                if _climate_themes(project)
                else "none",
                wb_climate_themes=_climate_themes(project),
                extra={
                    "has_pdo": bool(pdo),
                    "has_abstract": bool(abstract),
                    "last_stage_reached": project.get("last_stage_reached_name"),
                    "public_disclosure_date": project.get("public_disclosure_date"),
                    "theme_level2": sorted(set(project.get("themev2_level2_exact") or [])),
                    "financial_type": project.get("projectfinancialtype"),
                    "commitment_usd": project.get("curr_total_commitment"),
                },
            )
    return list(by_id.values())
