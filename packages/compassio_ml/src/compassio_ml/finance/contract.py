"""Typed monetary amounts with provenance, and the only sanctioned way to add them.

Rules enforced here (docs/architecture/financial_data_contract.md):

* Amounts are only summed within one flow kind, one currency, one price basis and one
  project/transaction level. Commitments + disbursements, GCF financing + co-financing, or
  pledges + approvals are never added.
* Country and fund aggregates are never summed with each other or with project rows.
* Multi-country project amounts are whole-project values; they are never attributed to, or
  summed for, a single country.
* Unknown currency blocks aggregation. No currency conversion or deflation happens here.
* A missing amount is ``None``: excluded and counted, never treated as zero.
* Two amounts for the same real-world project (``project_key``) from different sources are a
  duplicate representation and must be resolved explicitly before summing.
"""

import re
from collections import Counter
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

_ISO_4217 = re.compile(r"^[A-Z]{3}$")


class FlowKind(StrEnum):
    APPROVAL = "approval"
    COMMITMENT = "commitment"
    PLEDGE = "pledge"
    DEPOSIT = "deposit"
    DISBURSEMENT = "disbursement"
    REPAYMENT_PRINCIPAL = "repayment_principal"
    REPAYMENT_INTEREST = "repayment_interest"
    GCF_FINANCING = "gcf_financing"
    CO_FINANCING = "co_financing"
    TOTAL_PROJECT_COST = "total_project_cost"
    READINESS_GRANT = "readiness_grant"


class AmountLevel(StrEnum):
    PROJECT = "project"
    FINANCING_INSTRUMENT = "financing_instrument"  # e.g. one ADB loan/grant (IATI activity)
    TRANSACTION = "transaction"
    COUNTRY_AGGREGATE = "country_aggregate"
    FUND_AGGREGATE = "fund_aggregate"


AGGREGATE_LEVELS = frozenset({AmountLevel.COUNTRY_AGGREGATE, AmountLevel.FUND_AGGREGATE})
# Negative values are legitimate only for transaction-level reversals/cancellations.
NEGATIVE_ALLOWED = frozenset(
    {FlowKind.DISBURSEMENT, FlowKind.REPAYMENT_INTEREST, FlowKind.REPAYMENT_PRINCIPAL}
)


class AmountUnit(StrEnum):
    UNITS = "units"
    THOUSANDS = "thousands"
    MILLIONS = "millions"

    @property
    def scale(self) -> Decimal:
        return {"units": Decimal(1), "thousands": Decimal(1_000), "millions": Decimal(1_000_000)}[
            self.value
        ]


class PriceBasis(StrEnum):
    NOMINAL = "nominal"
    CONSTANT_2021_USD = "constant_2021_usd"  # AidData's published conversion; not re-derived
    UNSPECIFIED = "unspecified"


class MonetaryAmount(BaseModel):
    """One published amount, exactly as the source states it, with provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    project_key: str | None = None  # reviewed cross-source identity, if any
    flow_kind: FlowKind
    level: AmountLevel
    value: Decimal | None  # None = not reported (never zero)
    unit: AmountUnit
    currency: str | None  # ISO 4217 code; None = unknown
    price_basis: PriceBasis = PriceBasis.NOMINAL
    observation_date: date | None = None
    date_meaning: str = Field(min_length=1)  # e.g. "commitment date", "export snapshot"
    multi_country: bool = False
    estimated: bool | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.currency is not None and not _ISO_4217.match(self.currency):
            raise ValueError(f"currency must be an ISO 4217 code or None, got {self.currency!r}")
        if self.value is not None:
            if not self.value.is_finite():
                raise ValueError("value must be finite")
            if self.value < 0 and not (
                self.level is AmountLevel.TRANSACTION and self.flow_kind in NEGATIVE_ALLOWED
            ):
                raise ValueError(
                    f"negative {self.flow_kind} at level {self.level} is not allowed "
                    "(only transaction-level reversals may be negative)"
                )
        if self.price_basis is PriceBasis.CONSTANT_2021_USD and self.currency != "USD":
            raise ValueError("constant_2021_usd amounts must have currency USD")
        return self

    @property
    def value_in_units(self) -> Decimal | None:
        return None if self.value is None else self.value * self.unit.scale


class AggregationError(ValueError):
    """The amounts cannot be added without misrepresenting them."""


class AggregationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    flow_kind: FlowKind
    level: AmountLevel
    currency: str
    price_basis: PriceBasis
    total_in_units: Decimal
    summed_records: int
    missing_value_records: int  # excluded; reported so totals are never read as complete
    estimated_records: int


def aggregate(amounts: list[MonetaryAmount]) -> AggregationResult:
    """Sum amounts only when the result has one unambiguous meaning; otherwise raise."""
    if not amounts:
        raise AggregationError("nothing to aggregate")
    for attribute in ("flow_kind", "level", "currency", "price_basis"):
        values = {getattr(a, attribute) for a in amounts}
        if len(values) > 1:
            raise AggregationError(
                f"cannot add amounts with different {attribute}: {sorted(map(str, values))}"
            )
    first = amounts[0]
    if first.level in AGGREGATE_LEVELS:
        raise AggregationError(f"{first.level} values are already aggregates; do not sum them")
    if first.currency is None:
        raise AggregationError("unknown currency: amounts cannot be summed or converted")
    multi = [a.source_record_id for a in amounts if a.multi_country]
    if multi:
        raise AggregationError(
            f"{len(multi)} multi-country amounts carry whole-project values; they cannot be "
            "summed or attributed to one country"
        )
    keys = Counter(a.project_key for a in amounts if a.project_key)
    duplicated = sorted(k for k, n in keys.items() if n > 1)
    if duplicated:
        raise AggregationError(
            f"duplicate representations of the same project: {duplicated[:5]}; choose one "
            "source per project before summing"
        )
    present = [a for a in amounts if a.value is not None]
    total = sum((a.value_in_units for a in present if a.value_in_units is not None), Decimal(0))
    return AggregationResult(
        flow_kind=first.flow_kind,
        level=first.level,
        currency=first.currency,
        price_basis=first.price_basis,
        total_in_units=total,
        summed_records=len(present),
        missing_value_records=len(amounts) - len(present),
        estimated_records=sum(1 for a in present if a.estimated),
    )
