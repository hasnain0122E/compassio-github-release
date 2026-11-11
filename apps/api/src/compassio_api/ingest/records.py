"""Source-neutral records produced by the per-source builders (pure; no database access).

Every amount passes through ``compassio_ml.finance.MonetaryAmount`` validation when its unit and
currency are known; an amount that the contract rejects is stored as ``invalid`` (never coerced).
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

if TYPE_CHECKING:
    import pandas as pd

from compassio_ml.finance import AmountLevel, AmountUnit, FlowKind, MonetaryAmount, PriceBasis


@dataclass(frozen=True, slots=True)
class CountryRec:
    name: str
    iso3: str | None
    method: str


@dataclass(frozen=True, slots=True)
class AnnotationRec:
    annotation_source_id: str
    scheme: str
    kind: str  # research_annotation | source_classification
    provenance: str
    overall: int | None = None
    mitigation: int | None = None
    adaptation: int | None = None
    is_climate_related: bool | None = None
    label: str | None = None
    raw_value: str | None = None


@dataclass(frozen=True, slots=True)
class WarningRec:
    code: str
    message: str
    field: str | None = None


@dataclass(frozen=True, slots=True)
class ObservationRec:
    key: str
    flow_kind: str
    level: str
    amount: Decimal | None
    raw_value: str | None
    value_status: str  # reported | not_reported | unparseable | invalid
    unit: str | None
    currency: str | None
    unit_status: str
    price_basis: str
    date_meaning: str
    source_reference: str
    multi_country: bool
    effective_date: date | None = None
    effective_year: int | None = None
    financing_type: str | None = None
    is_component: bool = False
    estimated: bool | None = None
    recommended_for_aggregates: bool | None = None
    country_iso3: str | None = None  # only for source-published per-country breakdowns


@dataclass(slots=True)
class ProjectRec:
    source_id: str
    source_project_id: str
    record_level: str
    title: str
    source_reference: str
    description: str | None = None
    recipient_label: str | None = None
    region: str | None = None
    multi_country: bool = False
    sector_name: str | None = None
    sector_code: str | None = None
    sector_vocabulary: str | None = None
    year: int | None = None
    year_type: str | None = None
    date_value: date | None = None
    date_precision: str | None = None
    date_estimated: bool | None = None
    status: str | None = None
    group_key: str | None = None
    group_meaning: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    countries: list[CountryRec] = field(default_factory=list)
    annotations: list[AnnotationRec] = field(default_factory=list)
    observations: list[ObservationRec] = field(default_factory=list)
    warnings: list[WarningRec] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.source_id}:{self.source_project_id}"

    def warn(self, code: str, message: str, field_name: str | None = None) -> None:
        if all(w.code != code for w in self.warnings):
            self.warnings.append(WarningRec(code, message, field_name))

    def content_sha256(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, default=_json_default)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _json_default(value: object) -> str:
    if isinstance(value, Decimal | date):
        return str(value)
    raise TypeError(f"not serialisable: {type(value).__name__}")


# --------------------------------------------------------------------------- parsing helpers
def blank(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and value != value:  # NaN
        return True
    return isinstance(value, str) and value.strip() in {"", "None", "nan", "NaN"}


def text_or_none(value: object) -> str | None:
    return None if blank(value) else str(value).strip()


def parse_decimal(value: object) -> tuple[Decimal | None, str]:
    """Return (amount, value_status). Blank -> not_reported; garbage -> unparseable."""
    if blank(value):
        return None, "not_reported"
    # Floats: shortest round-trip text of the stored double (exactly what the file held).
    text = repr(value) if isinstance(value, float) else str(value).strip().replace(",", "")
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None, "unparseable"
    if not amount.is_finite():
        return None, "unparseable"
    return amount, "reported"


def parse_iso_date(value: object) -> date | None:
    text = text_or_none(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def validated(observation: ObservationRec) -> ObservationRec:
    """Run the finance contract's validators; mark violations as ``invalid``."""
    if observation.value_status != "reported" or observation.unit is None:
        return observation
    try:
        MonetaryAmount(
            source_id="ingest_validation",
            source_record_id=observation.key,
            flow_kind=FlowKind(observation.flow_kind),
            level=AmountLevel(observation.level),
            value=observation.amount,
            unit=AmountUnit(observation.unit),
            currency=observation.currency,
            price_basis=PriceBasis(observation.price_basis),
            date_meaning=observation.date_meaning,
            multi_country=observation.multi_country,
            estimated=observation.estimated,
        )
    except ValidationError:
        return _replace(observation, amount=None, value_status="invalid")
    return observation


def _replace(observation: ObservationRec, **changes: Any) -> ObservationRec:
    values = asdict(observation)
    values.update(changes)
    return ObservationRec(**values)


def frame_rows(frame: "pd.DataFrame") -> list[dict[str, Any]]:
    """DataFrame rows as ``str``-keyed dicts (typed for the builders)."""
    return [{str(k): v for k, v in row.items()} for row in frame.to_dict(orient="records")]
