"""IATI activity files via the official IATI Registry (publisher-hosted XML).

The IATI Datastore v3 API requires a subscription key (HTTP 401 without one, observed); no key
was supplied, so it is not used. The IATI Registry's CKAN-compatible API is open and lists each
publisher's own activity files with a per-dataset licence, which is the route used here.

Unit of observation: one IATI activity (``iati-identifier``); ``hierarchy`` 1 = programme,
2 = component. Components link to programmes through ``related-activity type=1``.

Label category B: DAC policy markers (vocabulary 1) code 6 = climate change mitigation, code 7 =
climate change adaptation, significance 0 = not targeted, 1 = significant, 2 = principal,
**reported by the publishing donor**. A marker present with significance 0 is an explicit
donor-reported "not targeted"; a marker that is absent is unknown, never a negative.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element

from compassio_ml.external.records import (
    CandidateRecord,
    SectorFamily,
    TextTiming,
    dac_sector_family,
    primary_family,
)
from compassio_ml.external.registry import RetrievalRun, read_retrieval_manifest
from compassio_ml.safety.xml import iter_xml_elements

REGISTRY_SEARCH = (
    "https://iatiregistry.org/api/3/action/package_search?q=publisher_iati_id:{pid}&rows={rows}"
)


@dataclass(frozen=True)
class IatiPublisher:
    """One IATI publisher retrieved through the IATI Registry."""

    source_id: str
    name: str
    iati_id: str
    dataset_pattern: re.Pattern[str]
    registry_rows: int
    max_file_bytes: int
    max_total_bytes: int
    document_url_template: str | None = None  # "{id}" -> iati-identifier
    terms_urls: dict[str, str] = field(default_factory=dict)


FCDO = IatiPublisher(
    source_id="iati_fcdo",
    name="UK Foreign, Commonwealth and Development Office (IATI publisher GB-GOV-1)",
    iati_id="GB-GOV-1",
    # FCDO's main programme files; BBC WS, British Council, CSSF, ... are left out.
    dataset_pattern=re.compile(r"^fcdo-set-\d+$"),
    registry_rows=100,
    max_file_bytes=30 * 1024 * 1024,
    max_total_bytes=350 * 1024 * 1024,
    document_url_template="https://devtracker.fcdo.gov.uk/projects/{id}",
)
EC_INTPA = IatiPublisher(
    source_id="iati_ec_intpa",
    name="European Commission - DG International Partnerships (IATI publisher XI-IATI-EC_INTPA)",
    iati_id="XI-IATI-EC_INTPA",
    dataset_pattern=re.compile(r"^ec-intpa-[a-z0-9-]+$"),
    registry_rows=200,
    max_file_bytes=30 * 1024 * 1024,
    max_total_bytes=200 * 1024 * 1024,
    terms_urls={"commission_legal_notice.html": "https://commission.europa.eu/legal-notice_en"},
)
PUBLISHERS = {p.source_id: p for p in (FCDO, EC_INTPA)}
# Backward-compatible aliases for the FCDO source.
SOURCE_ID = FCDO.source_id
PUBLISHER = FCDO.name
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
RIO_CODES = {"6": "mitigation", "7": "adaptation"}
VALID_SIGNIFICANCE = {"0", "1", "2"}
_WB_CODE = re.compile(r"\bP\d{6}\b")
_GCF_CODE = re.compile(r"\b(FP|SAP)(\d{3})\b")


def _is_activity_file(dataset: dict[str, Any]) -> bool:
    extras = {e.get("key"): e.get("value") for e in dataset.get("extras") or []}
    return str(extras.get("filetype", "activity")) == "activity"


def acquire(run: RetrievalRun, publisher: IatiPublisher = FCDO) -> list[str]:
    notes: list[str] = []
    for name, url in publisher.terms_urls.items():
        run.fetch(url, name, max_bytes=5 * 1024 * 1024, role="terms")
    index = run.fetch(
        REGISTRY_SEARCH.format(pid=publisher.iati_id, rows=publisher.registry_rows),
        "registry_datasets.json",
        max_bytes=5 * 1024 * 1024,
        role="index",
    )
    if index is None:
        return ["IATI Registry dataset list failed; nothing downloaded"]
    payload = json.loads(index.path.read_text(encoding="utf-8"))
    results = payload["result"]["results"]
    if int(payload["result"].get("count", len(results))) > len(results):
        notes.append(f"registry reports more datasets than returned ({len(results)})")
    datasets = [
        d for d in results if publisher.dataset_pattern.match(d["name"]) and _is_activity_file(d)
    ]
    total = 0
    selected: list[dict[str, Any]] = []
    for dataset in sorted(datasets, key=lambda d: str(d["name"])):
        resource = dataset["resources"][0]
        size = int(resource.get("size") or 0)
        if size > publisher.max_file_bytes or total + size > publisher.max_total_bytes:
            notes.append(f"skipped {dataset['name']}: size {size} exceeds bound")
            continue
        total += size
        selected.append(dataset)
    run.parameters = {
        "publisher": publisher.iati_id,
        "dataset_pattern": publisher.dataset_pattern.pattern,
        "licences": sorted({str(d.get("license_id")) for d in selected}),
        "datasets": [d["name"] for d in selected],
        "declared_total_bytes": total,
    }
    for dataset in selected:
        resource = dataset["resources"][0]
        run.fetch(
            str(resource["url"]),
            f"{dataset['name']}.xml",
            max_bytes=publisher.max_file_bytes,
            role="data",
        )
    notes.append(f"registry listed {len(datasets)} matching datasets; fetched {len(selected)}")
    return notes


def _narrative(element: Element | None) -> str | None:
    if element is None:
        return None
    texts = [(n.get(XML_LANG), (n.text or "").strip()) for n in element.findall("narrative")]
    texts = [(lang, t) for lang, t in texts if t]
    if not texts:
        return None
    for lang, text in texts:
        if lang in (None, "en", "EN"):
            return text
    return texts[0][1]


def _float(value: str | None) -> float:
    try:
        return float(value) if value else 0.0
    except ValueError:
        return 0.0


def parse_activity(activity: Element) -> dict[str, Any]:
    """Extract only the fields used downstream from one ``iati-activity`` element."""
    descriptions: dict[str, str] = {}
    for desc in activity.findall("description"):
        kind = desc.get("type") or "1"
        text = _narrative(desc)
        if text and kind not in descriptions:
            descriptions[kind] = text
    markers: dict[str, str] = {}
    other_markers: list[str] = []
    for marker in activity.findall("policy-marker"):
        vocab = marker.get("vocabulary") or "1"
        code = marker.get("code") or ""
        if vocab == "1" and code in RIO_CODES:
            markers[RIO_CODES[code]] = marker.get("significance") or ""
        elif vocab == "1":
            other_markers.append(code)
    sectors: list[tuple[str, float]] = []
    for sector in activity.findall("sector"):
        vocab = sector.get("vocabulary") or "1"
        code = sector.get("code") or ""
        if vocab in ("1", "2") and code:
            sectors.append((code, _float(sector.get("percentage")) or 100.0))
    countries = [
        (c.get("code") or "", _float(c.get("percentage")))
        for c in activity.findall("recipient-country")
        if c.get("code")
    ]
    dates = {
        d.get("type") or "": d.get("iso-date") or "" for d in activity.findall("activity-date")
    }
    status = activity.find("activity-status")
    return {
        "id": (activity.findtext("iati-identifier") or "").strip(),
        "hierarchy": activity.get("hierarchy") or "1",
        "last_updated": activity.get("last-updated-datetime"),
        "title": _narrative(activity.find("title")),
        "descriptions": descriptions,
        "markers": markers,
        "other_dac_markers": sorted(set(other_markers)),
        "sectors": sectors,
        "countries": countries,
        "dates": dates,
        "status": status.get("code") if status is not None else None,
        "parents": sorted(
            {
                r.get("ref") or ""
                for r in activity.findall("related-activity")
                if r.get("type") == "1" and r.get("ref")
            }
        ),
        "participating_orgs": sorted(
            {o.get("ref") or "" for o in activity.findall("participating-org") if o.get("ref")}
        ),
        "document_links": len(activity.findall("document-link")),
    }


def _significance(value: str | None) -> int | None:
    return int(value) if value in VALID_SIGNIFICANCE else None


def to_candidate(
    parsed: dict[str, Any],
    *,
    retrieval_id: str,
    raw_file: str,
    raw_sha256: str,
    publisher: IatiPublisher = FCDO,
    file_url: str | None = None,
) -> CandidateRecord:
    descriptions: dict[str, str] = parsed["descriptions"]
    # 1 = general, 2 = objectives. Target groups (3) and other types are excluded.
    description = " ".join(descriptions[k] for k in ("1", "2") if k in descriptions) or None
    weights: dict[SectorFamily, float] = {}
    for code, pct in parsed["sectors"]:
        fam = dac_sector_family(code)
        weights[fam] = weights.get(fam, 0.0) + pct
    markers: dict[str, str] = parsed["markers"]
    mit = _significance(markers.get("mitigation"))
    ada = _significance(markers.get("adaptation"))
    if mit is not None and ada is not None:
        marker_status = "explicit_both"
    elif mit is not None or ada is not None:
        marker_status = "explicit_partial"
    else:
        marker_status = "absent"
    invalid = {k: v for k, v in markers.items() if v not in VALID_SIGNIFICANCE}
    status = parsed["status"]
    timing = (
        TextTiming.PRE_APPROVAL_PIPELINE if status == "1" else TextTiming.PUBLISHER_CURRENT_SNAPSHOT
    )
    text = f"{parsed['title'] or ''} {description or ''}"
    refs = sorted(
        {f"worldbank_projects:{c}" for c in _WB_CODE.findall(text)}
        | {f"gcf_project_pages:{m.group(1)}{m.group(2)}" for m in _GCF_CODE.finditer(text)}
    )
    dates: dict[str, str] = parsed["dates"]
    return CandidateRecord(
        source_id=publisher.source_id,
        publisher=publisher.name,
        source_record_id=parsed["id"],
        retrieval_id=retrieval_id,
        raw_file=raw_file,
        raw_file_sha256=raw_sha256,
        document_url=(
            publisher.document_url_template.format(id=parsed["id"])
            if publisher.document_url_template
            else file_url
        ),
        title=parsed["title"],
        description=description,
        text_type="iati_activity_description",
        country_iso3=sorted({f"ISO2:{c}" for c, _ in parsed["countries"]}),
        sector_codes=sorted({c for c, _ in parsed["sectors"]}),
        sector_families=sorted(f.value for f in weights),
        sector_family=primary_family(weights).value,
        approval_date=None,
        start_date=dates.get("2") or dates.get("1"),
        end_date=dates.get("4") or dates.get("3"),
        last_updated=parsed["last_updated"],
        text_date=None,
        text_date_basis="IATI description as published at retrieval (activity "
        f"last-updated {parsed['last_updated'] or 'unknown'}); original drafting date unknown",
        text_timing=timing.value,
        status=status,
        hierarchy=parsed["hierarchy"],
        parent_ids=[f"{publisher.source_id}:{p}" for p in parsed["parents"]],
        cross_references=refs,
        label_category="B_donor_reported_rio" if marker_status != "absent" else "none",
        donor_rio_mitigation=mit,
        donor_rio_adaptation=ada,
        donor_marker_status=marker_status,
        extra={
            "invalid_rio_significance": invalid,
            "other_dac_markers": parsed["other_dac_markers"],
            "participating_orgs": parsed["participating_orgs"],
            "document_links": parsed["document_links"],
            "description_types": sorted(descriptions),
        },
    )


def parse_retrieval(directory: Path, publisher: IatiPublisher = FCDO) -> list[CandidateRecord]:
    manifest = read_retrieval_manifest(directory)
    retrieval_id = str(manifest["retrieval_id"])
    seen: dict[str, CandidateRecord] = {}
    duplicates = 0
    for entry in manifest["files"]:
        if entry.get("role") != "data":
            continue
        for activity in iter_xml_elements(directory / str(entry["file"]), "iati-activity"):
            parsed = parse_activity(activity)
            if not parsed["id"]:
                continue
            if parsed["id"] in seen:
                duplicates += 1
                continue
            seen[parsed["id"]] = to_candidate(
                parsed,
                retrieval_id=retrieval_id,
                raw_file=str(entry["file"]),
                raw_sha256=str(entry["sha256"]),
                publisher=publisher,
                file_url=str(entry.get("final_url") or ""),
            )
    for record in seen.values():
        record.extra["file_level_duplicate_ids_seen"] = duplicates
    return list(seen.values())
