"""Common candidate-record schema for external sources, text hashing and sector taxonomy.

A candidate record keeps its source identity (``source_id`` + ``source_record_id``) and the
verbatim parsed text. Source climate indicators are stored in *category-specific* columns
(``donor_rio_*``, ``gcf_theme``, ``wb_climate_themes``) and are never collapsed into one label.
``proposed_rio_*`` are proposals for human review, filled only from donor-reported Rio markers.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from compassio_ml.data.parsing import normalize_text
from compassio_ml.research.text import clean_text

MIN_USABLE_DESCRIPTION_CHARS = 100


class TextTiming(StrEnum):
    """What the text is known to describe in time. ``unknown`` unless verified."""

    PRE_APPROVAL_PIPELINE = "pre_approval_pipeline"  # project not yet approved at retrieval
    APPROVAL_STAGE_SNAPSHOT = "approval_stage_statement_current_snapshot"
    PUBLISHER_CURRENT_SNAPSHOT = "publisher_current_snapshot"
    PORTFOLIO_SUMMARY_UNDATED = "portfolio_summary_undated"
    RETROSPECTIVE = "retrospective"
    UNKNOWN = "unknown"


class SectorFamily(StrEnum):
    ENERGY = "energy"
    TRANSPORT = "transport"
    AGRICULTURE_FORESTRY_FISHING = "agriculture_forestry_fishing"
    WATER_SANITATION_WASTE = "water_sanitation_waste"
    DISASTER_EMERGENCY = "disaster_risk_and_emergency"
    ENVIRONMENT_ECOSYSTEMS = "environment_ecosystems"
    HEALTH = "health"
    EDUCATION = "education"
    GOVERNANCE = "governance_civil_society"
    SOCIAL_PROTECTION = "social_protection_inclusion"
    URBAN = "urban_development"
    INDUSTRY_TRADE = "industry_trade_business"
    FINANCE = "finance"
    COMMUNICATIONS = "communications"
    MULTISECTOR_OTHER = "multisector_other"
    UNKNOWN = "unknown"


# DAC 5-digit purpose codes: exact overrides first, then 3-digit category.
_DAC_EXACT: dict[str, SectorFamily] = {
    "43060": SectorFamily.DISASTER_EMERGENCY,
    "43030": SectorFamily.URBAN,
    "41010": SectorFamily.ENVIRONMENT_ECOSYSTEMS,
}
_DAC_PREFIX: dict[str, SectorFamily] = {
    **dict.fromkeys(("111", "112", "113", "114"), SectorFamily.EDUCATION),
    **dict.fromkeys(("121", "122", "123", "130"), SectorFamily.HEALTH),
    "140": SectorFamily.WATER_SANITATION_WASTE,
    **dict.fromkeys(("151", "152"), SectorFamily.GOVERNANCE),
    "160": SectorFamily.SOCIAL_PROTECTION,
    "210": SectorFamily.TRANSPORT,
    "220": SectorFamily.COMMUNICATIONS,
    **dict.fromkeys(("231", "232", "233", "234", "235", "236"), SectorFamily.ENERGY),
    "240": SectorFamily.FINANCE,
    "250": SectorFamily.INDUSTRY_TRADE,
    **dict.fromkeys(("311", "312", "313"), SectorFamily.AGRICULTURE_FORESTRY_FISHING),
    **dict.fromkeys(("321", "322", "323", "331", "332"), SectorFamily.INDUSTRY_TRADE),
    "410": SectorFamily.ENVIRONMENT_ECOSYSTEMS,
    "430": SectorFamily.MULTISECTOR_OTHER,
    **dict.fromkeys(("720", "730", "740"), SectorFamily.DISASTER_EMERGENCY),
}

# World Bank major-sector code: first letter of codes such as "AAX", "LLX".
_WB_MAJOR: dict[str, SectorFamily] = {
    "A": SectorFamily.AGRICULTURE_FORESTRY_FISHING,
    "B": SectorFamily.GOVERNANCE,
    "C": SectorFamily.COMMUNICATIONS,
    "E": SectorFamily.EDUCATION,
    "F": SectorFamily.FINANCE,
    "H": SectorFamily.HEALTH,
    "J": SectorFamily.SOCIAL_PROTECTION,
    "L": SectorFamily.ENERGY,
    "N": SectorFamily.SOCIAL_PROTECTION,
    "T": SectorFamily.TRANSPORT,
    "W": SectorFamily.WATER_SANITATION_WASTE,
    "Y": SectorFamily.INDUSTRY_TRADE,
}

# GCF ODL "Sector" is public/private; GCF areas are not sectors. GCF records use text-free
# mapping only from explicit page result-area tags when present (see gcf module).


def dac_sector_family(code: str | None) -> SectorFamily:
    if not code:
        return SectorFamily.UNKNOWN
    code = code.strip()
    if code in _DAC_EXACT:
        return _DAC_EXACT[code]
    return _DAC_PREFIX.get(code[:3], SectorFamily.MULTISECTOR_OTHER)


def wb_sector_family(major_code: str | None) -> SectorFamily:
    if not major_code:
        return SectorFamily.UNKNOWN
    return _WB_MAJOR.get(major_code.strip()[:1].upper(), SectorFamily.MULTISECTOR_OTHER)


def primary_family(weights: dict[SectorFamily, float]) -> SectorFamily:
    """Family with the largest share; ``multisector_other`` when no share information
    distinguishes several families; ``unknown`` when empty."""
    if not weights:
        return SectorFamily.UNKNOWN
    if len(weights) == 1:
        return next(iter(weights))
    best = max(weights.values())
    leaders = [fam for fam, w in weights.items() if w == best]
    if best <= 0 or len(leaders) > 1:
        return SectorFamily.MULTISECTOR_OTHER
    return leaders[0]


def text_key(title: str | None, description: str | None) -> str:
    """SHA-256 of normalized title + description (exact-duplicate key across sources)."""
    joined = normalize_text(title) + "\n" + normalize_text(description)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def description_key(description: str | None) -> str | None:
    norm = normalize_text(description)
    if len(norm) < MIN_USABLE_DESCRIPTION_CHARS:
        return None
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


@dataclass
class CandidateRecord:
    source_id: str
    publisher: str
    source_record_id: str
    retrieval_id: str
    raw_file: str
    raw_file_sha256: str
    document_url: str | None
    title: str | None
    description: str | None
    text_type: str
    country_iso3: list[str]
    sector_codes: list[str]
    sector_families: list[str]
    sector_family: str
    approval_date: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    last_updated: str | None = None
    text_date: str | None = None
    text_date_basis: str = "unknown"
    text_timing: str = TextTiming.UNKNOWN.value
    status: str | None = None
    hierarchy: str | None = None
    parent_ids: list[str] = field(default_factory=list)
    cross_references: list[str] = field(default_factory=list)
    label_category: str = "none"
    donor_rio_mitigation: int | None = None
    donor_rio_adaptation: int | None = None
    donor_marker_status: str = "absent"
    gcf_theme: str | None = None
    wb_climate_themes: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    rights_status: str = "not_reviewed"

    @property
    def candidate_id(self) -> str:
        return f"{self.source_id}:{self.source_record_id}"

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        title = clean_text(self.title).value
        desc = clean_text(self.description).value
        row["candidate_id"] = self.candidate_id
        row["title_clean"] = title
        row["description_clean"] = desc
        row["description_chars"] = len(desc or "")
        row["has_usable_text"] = bool(title) and len(desc or "") >= MIN_USABLE_DESCRIPTION_CHARS
        row["text_sha256"] = text_key(title, desc)
        row["description_sha256"] = description_key(desc)
        row["is_pakistan"] = "PAK" in self.country_iso3
        row["multi_country"] = len(self.country_iso3) > 1
        row["is_energy_sector"] = self.sector_family == SectorFamily.ENERGY.value
        if self.donor_rio_mitigation is not None and self.donor_rio_adaptation is not None:
            row["donor_rio_overall"] = max(self.donor_rio_mitigation, self.donor_rio_adaptation)
        else:
            row["donor_rio_overall"] = None
        for key in (
            "country_iso3",
            "sector_codes",
            "sector_families",
            "parent_ids",
            "cross_references",
            "wb_climate_themes",
        ):
            row[key] = ";".join(row[key])
        row["extra"] = json.dumps(self.extra, sort_keys=True, default=str) if self.extra else ""
        return row
