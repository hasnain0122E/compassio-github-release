"""Task 008 helpers on top of the PROTECTED ``services.finance`` module (which stays unchanged:
it is hash-pinned in ``configs/task006_integration_reference.json``).

* ``metric_statement`` selects a registered metric's candidate rows with the SAME filters as
  ``services.finance._trends`` (equality is enforced by tests comparing insight totals with
  ``/analytics/trends`` totals).
* ``exclusion_reason`` is ``services.finance._exclusion_reason`` itself (no second rule set).
* ``safe_total`` is the only summation path: ``compassio_ml.finance.aggregate``, returning
  ``total=None`` + reason when a sum would misrepresent the amounts (never 0).
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select

from compassio_api.db.models import FinancialObservation, ProjectCountry
from compassio_api.services.finance import Metric, _exclusion_reason
from compassio_ml.finance import (
    AggregationError,
    AmountLevel,
    AmountUnit,
    FlowKind,
    MonetaryAmount,
    PriceBasis,
    aggregate,
)


def metric_statement(
    metric: Metric,
    country: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> Any:
    """Candidate observation rows for ``metric`` (identical filters to the trends query)."""
    obs = FinancialObservation
    stmt = select(
        obs.observation_key,
        obs.project_id,
        obs.country_iso3,
        obs.amount,
        obs.value_status,
        obs.unit,
        obs.currency,
        obs.price_basis,
        obs.effective_year,
        obs.multi_country,
        obs.estimated,
        obs.recommended_for_aggregates,
    ).where(
        obs.source_id == metric.source_id,
        obs.flow_kind == metric.flow_kind,
        obs.level == metric.level,
        obs.price_basis == metric.price_basis,
    )
    if metric.components == "country_breakdown":
        stmt = stmt.where(obs.financing_type == "country_breakdown")
    elif metric.components == "instrument_lines":
        stmt = stmt.where(
            obs.is_component.is_(True),
            or_(obs.financing_type.is_(None), obs.financing_type != "country_breakdown"),
        )
    else:
        stmt = stmt.where(obs.is_component.is_(False))
    if country is not None and metric.components == "country_breakdown":
        stmt = stmt.where(obs.country_iso3 == country)
    elif country is not None:
        stmt = stmt.where(
            obs.project_id.in_(
                select(ProjectCountry.project_id).where(ProjectCountry.iso3 == country)
            )
        )
    if year_from is not None:
        stmt = stmt.where(obs.effective_year >= year_from)
    if year_to is not None:
        stmt = stmt.where(obs.effective_year <= year_to)
    return stmt


def exclusion_reason(metric: Metric, row: Any) -> str | None:
    """The protected per-row rule used by every metric total (``services.finance``)."""
    return _exclusion_reason(metric, row)


def metric_amount(metric: Metric, row: Any) -> MonetaryAmount:
    """Same construction as the trends total (single-country rows only reach this point)."""
    return MonetaryAmount(
        source_id=metric.source_id,
        source_record_id=row.observation_key,
        flow_kind=FlowKind(metric.flow_kind),
        level=AmountLevel(metric.level),
        value=row.amount,
        unit=AmountUnit(row.unit or "units"),
        currency=row.currency or metric.currency,
        price_basis=PriceBasis(row.price_basis),
        date_meaning=metric.year_basis,
        multi_country=False,
        estimated=row.estimated,
    )


@dataclass(frozen=True, slots=True)
class SafeTotal:
    total: Decimal | None
    summed_records: int
    missing_value_records: int
    estimated_records: int
    reason: str | None


def safe_total(amounts: list[MonetaryAmount]) -> SafeTotal:
    """``aggregate`` with the API convention: unsafe or empty -> ``total=None`` + reason."""
    if not amounts:
        return SafeTotal(None, 0, 0, 0, "No observations to sum.")
    try:
        result = aggregate(amounts)
    except AggregationError as exc:
        return SafeTotal(None, 0, 0, 0, str(exc))
    if result.summed_records == 0:
        return SafeTotal(
            None,
            0,
            result.missing_value_records,
            0,
            "No amount is reported (not treated as zero).",
        )
    return SafeTotal(
        result.total_in_units,
        result.summed_records,
        result.missing_value_records,
        result.estimated_records,
        None,
    )
