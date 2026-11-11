"""Financial summaries that are mathematically valid by construction.

Every total goes through ``compassio_ml.finance.aggregate`` (one flow kind, level, currency and
price basis; no aggregates, no multi-country values, no duplicate project keys). Each metric is
**single-source**, so GCF and CFU amounts are never added together. Rows that cannot be summed
are excluded *and counted*; a year that cannot be computed is returned as ``unavailable`` with
the reason -- never as zero.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from compassio_api.db.models import FinancialObservation, ProjectCountry
from compassio_api.schemas.data import AccessNotice, MetricOut, TrendPoint, TrendsResponse
from compassio_api.services.access import AccessPolicy, SourceRightsNotClearedError
from compassio_api.services.cache import cached
from compassio_ml.finance import (
    AggregationError,
    AmountLevel,
    AmountUnit,
    FlowKind,
    MonetaryAmount,
    PriceBasis,
    aggregate,
)

DISCLAIMERS: tuple[str, ...] = (
    "Amounts are as published by the source; commitments, approvals and disbursements are "
    "different things and are never added together.",
    "Historical finance is not evidence of project success, environmental benefit or "
    "financial return.",
    "An approved or funded project is not necessarily open to new funding.",
    "Multi-country amounts are whole-project values.",
    "No currency conversion has been applied unless labelled 'AidData constant 2021 USD'.",
)

FLOW_LABELS = {
    "commitment": "Commitment",
    "pledge": "Pledge (a promise, not a commitment)",
    "approval": "Approval",
    "disbursement": "Disbursement",
    "repayment_principal": "Principal repayment (inflow to the lender; not funding)",
    "repayment_interest": "Interest payment (inflow to the lender; not funding)",
    "gcf_financing": "GCF financing approved (excludes co-finance)",
    "co_financing": "Co-financing",
    "total_project_cost": "Total project cost",
    "readiness_grant": "Readiness grant",
    "deposit": "Deposit into a fund",
}


def metric_label(flow_kind: str, level: str, is_component: bool) -> str:
    label = FLOW_LABELS.get(flow_kind, flow_kind)
    suffix = f" ({level.replace('_', ' ')} level)"
    if is_component:
        suffix += ", instrument component of the stated total"
    return label + suffix


@dataclass(frozen=True, slots=True)
class Metric:
    metric_id: str
    label: str
    source_id: str
    flow_kind: str
    level: str
    currency: str | None
    price_basis: str
    unit_label: str | None
    year_basis: str
    is_funding: bool
    description: str
    limitations: tuple[str, ...]
    require_recommended: bool = False
    unavailable_reason: str | None = None
    # Which rows form the series: stated totals only, instrument lines, or the source's own
    # per-country breakdown lines.
    components: str = "exclude"
    recommended_reason: str = "not_recommended_for_aggregates"
    deduplication_policy: str = (
        "Single source; one observation per published amount (unique source + key); "
        "instrument components never added to stated totals."
    )

    def out(self) -> MetricOut:
        return MetricOut(
            metric_id=self.metric_id,
            label=self.label,
            source_id=self.source_id,
            flow_kind=self.flow_kind,
            level=self.level,
            currency=self.currency,
            price_basis=self.price_basis,
            year_basis=self.year_basis,
            is_funding=self.is_funding,
            description=self.description,
            limitations=list(self.limitations),
            deduplication_policy=self.deduplication_policy,
            row_selection=self.components,
        )


METRICS: dict[str, Metric] = {
    m.metric_id: m
    for m in (
        Metric(
            "aiddata_commitments_constant_2021_usd",
            "Chinese official finance commitments (AidData constant 2021 USD)",
            "aiddata",
            "commitment",
            "project",
            "USD",
            "constant_2021_usd",
            "USD (AidData constant 2021)",
            "AidData commitment year",
            True,
            "AidData commitments by commitment year in AidData's own constant-2021-USD "
            "conversion, restricted to records AidData recommends for aggregates.",
            (
                "Pledges, umbrella agreements and records AidData does not recommend for "
                "aggregates are excluded (counted).",
                "Regional / multi-country records are excluded from totals (counted).",
                "A commitment is not a disbursement and not evidence of impact.",
            ),
            require_recommended=True,
        ),
        Metric(
            "cfu_approvals_usd",
            "Climate fund approvals (Climate Funds Update, nominal USD)",
            "climate_funds_update",
            "approval",
            "project",
            "USD",
            "nominal",
            "USD",
            "CFU approval year",
            True,
            "Total approved funding per CFU project row by approval year (instrument components "
            "excluded so the total is not double counted).",
            (
                "CFU includes GCF projects that are also in the GCF export; never add this to "
                "GCF figures.",
                "Rows without an approval year are excluded (counted).",
                "Multi-country / global rows are excluded from totals (counted).",
            ),
        ),
        Metric(
            "adb_commitments_usd",
            "ADB Pakistan commitments (IATI transaction type 2, USD)",
            "adb_pakistan",
            "commitment",
            "transaction",
            "USD",
            "nominal",
            "USD",
            "IATI transaction date (year)",
            True,
            "Sum of ADB commitment transactions by transaction year.",
            ("Commitments are not disbursements; repayments are reported separately.",),
        ),
        Metric(
            "adb_disbursements_usd",
            "ADB Pakistan disbursements (IATI transaction type 3, USD)",
            "adb_pakistan",
            "disbursement",
            "transaction",
            "USD",
            "nominal",
            "USD",
            "IATI transaction date (year)",
            True,
            "Sum of ADB disbursement transactions (including published reversals) by year.",
            ("Includes negative reversal transactions as published.",),
        ),
        Metric(
            "adb_principal_repayments_usd",
            "ADB Pakistan principal repayments (inflow to ADB; NOT funding)",
            "adb_pakistan",
            "repayment_principal",
            "transaction",
            "USD",
            "nominal",
            "USD",
            "IATI transaction date (year)",
            False,
            "Principal repaid to ADB by year. This is money returned to the lender.",
            ("Never shown or added as funding.",),
        ),
        Metric(
            "gcf_financing",
            "GCF financing approved (GCF export)",
            "gcf_projects",
            "gcf_financing",
            "project",
            None,
            "unspecified",
            None,
            "none (export has board-meeting codes, not dates)",
            True,
            "GCF 'FA Financing' per funded project.",
            ("Currency and unit are not stated in the export; no date is published.",),
            unavailable_reason=(
                "The GCF export states no currency or unit for 'FA Financing' and publishes no "
                "approval date, so no dated or summed series can be computed. See the "
                "gcf_api_* metrics (official GCF API snapshot, currency stated per line)."
            ),
        ),
        Metric(
            "gcf_api_gcf_funding_by_country_usd",
            "GCF funding by approval year, from GCF's own per-country breakdown (USD)",
            "gcf_api_projects",
            "gcf_financing",
            "project",
            "USD",
            "nominal",
            "USD",
            "GCF Board approval year (API ApprovalDate)",
            True,
            "Sum of GCF's published per-country GCF financing lines (currency stated) by "
            "approval year. With a country filter, only that country's published lines count, "
            "so multi-country projects contribute GCF's own country figure, never the whole "
            "project.",
            (
                "Only projects whose country lines sum exactly to GCF's published total are "
                "included; others are excluded and counted.",
                "Approval is not disbursement and not an open funding opportunity.",
                "Backend staging source (API snapshot), rights not reviewed.",
            ),
            require_recommended=True,
            components="country_breakdown",
            recommended_reason="country_lines_inconsistent_with_published_total",
            deduplication_policy=(
                "One row per published country line; lines are GCF's own split of the project "
                "total, so a project is counted once across its countries. Projects whose lines do "
                "not reproduce the published total are excluded."
            ),
        ),
        Metric(
            "gcf_api_gcf_funding_usd",
            "GCF funding by approval year, from GCF's funding lines by instrument (USD)",
            "gcf_api_projects",
            "gcf_financing",
            "project",
            "USD",
            "nominal",
            "USD",
            "GCF Board approval year (API ApprovalDate)",
            True,
            "Sum of GCF-source funding lines (grants, loans, equity, ...) in USD by approval year.",
            (
                "Only projects whose GCF lines are all USD and sum exactly to the published total "
                "are included (guards against lines re-listed under later Board meetings).",
                "Multi-country projects are whole-project lines and are excluded (counted); use "
                "gcf_api_gcf_funding_by_country_usd for a complete series.",
                "EUR lines are never converted.",
            ),
            require_recommended=True,
            components="instrument_lines",
            recommended_reason="funding_lines_inconsistent_with_published_total",
            deduplication_policy=(
                "One row per published funding line (budget id + Board meeting); identical repeats "
                "stored once; inconsistent line sets excluded."
            ),
        ),
        Metric(
            "gcf_api_disbursements_usd",
            "GCF disbursements by effective year (USD lines)",
            "gcf_api_projects",
            "disbursement",
            "transaction",
            "USD",
            "nominal",
            "USD",
            "GCF disbursement effective date (API DateEffective)",
            True,
            "Sum of GCF disbursement transactions stated in USD, by year.",
            (
                "EUR disbursements are excluded (counted), never converted.",
                "Multi-country projects are excluded (counted) with a country filter or without.",
            ),
            deduplication_policy="One row per published disbursement id.",
        ),
        Metric(
            "gcf_readiness_grants",
            "GCF readiness grants (readiness export)",
            "gcf_readiness",
            "readiness_grant",
            "project",
            None,
            "unspecified",
            None,
            "readiness approval date",
            True,
            "GCF readiness 'Financing' per grant.",
            ("Currency and unit are not stated in the readiness export.",),
            unavailable_reason=(
                "The readiness export states no currency or unit for 'Financing', and the GCF "
                "API offers no readiness endpoint to verify it, so no total is computed."
            ),
        ),
    )
}


class UnknownMetricError(LookupError):
    pass


def trends(
    session: Session,
    policy: AccessPolicy,
    metric_id: str,
    country: str | None,
    year_from: int | None,
    year_to: int | None,
) -> TrendsResponse:
    """Validated, cached entry point (cache keyed on data version, mode and visible sources)."""
    metric = METRICS.get(metric_id)
    if metric is None:
        raise UnknownMetricError(metric_id)
    if not policy.allows(metric.source_id):
        raise SourceRightsNotClearedError(
            f"source '{metric.source_id}' may not be served in the current access mode"
        )
    key = (
        "trends",
        metric_id,
        country,
        year_from,
        year_to,
        policy.mode,
        tuple(sorted(policy.visible_source_ids)),
    )
    return cached(
        session, key, lambda: _trends(session, policy, metric_id, country, year_from, year_to)
    )


def _trends(
    session: Session,
    policy: AccessPolicy,
    metric_id: str,
    country: str | None,
    year_from: int | None,
    year_to: int | None,
) -> TrendsResponse:
    metric = METRICS.get(metric_id)
    if metric is None:
        raise UnknownMetricError(metric_id)
    if not policy.allows(metric.source_id):
        raise SourceRightsNotClearedError(
            f"source '{metric.source_id}' may not be served in the current access mode"
        )
    access = AccessNotice(mode=policy.mode, notice=policy.notice)

    def respond(
        points: list[TrendPoint],
        reason: str | None,
        undated: int = 0,
        outside: dict[str, int] | None = None,
    ) -> TrendsResponse:
        return TrendsResponse(
            metric=metric.out(),
            status="available" if points else "unavailable",
            unavailable_reason=None if points else reason,
            country=country,
            year_from=year_from,
            year_to=year_to,
            points=points,
            undated_records=undated,
            excluded_outside_rules=outside or {},
            aggregation_limitations=list(metric.limitations),
            disclaimers=list(DISCLAIMERS),
            access=access,
        )

    if metric.unavailable_reason is not None:
        return respond([], metric.unavailable_reason)

    obs = FinancialObservation
    stmt = select(
        obs.observation_key,
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

    by_year: dict[int, list[MonetaryAmount]] = defaultdict(list)
    excluded: dict[int, Counter[str]] = defaultdict(Counter)
    outside: Counter[str] = Counter()
    undated = 0
    for row in session.execute(stmt):
        year = row.effective_year
        if year is None:
            undated += 1
            continue
        reason = _exclusion_reason(metric, row)
        if reason is not None:
            excluded[year][reason] += 1
            outside[reason] += 1
            continue
        by_year[year].append(
            MonetaryAmount(
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
        )
    points: list[TrendPoint] = []
    for year in sorted(set(by_year) | set(excluded)):
        amounts = by_year.get(year, [])
        points.append(_point(year, amounts, excluded.get(year, Counter()), metric))
    return respond(points, "No dated observations match these filters.", undated, dict(outside))


def _exclusion_reason(metric: Metric, row: Any) -> str | None:
    """Why an observation cannot enter this metric's total (``None`` = it can)."""
    if row.value_status in {"invalid", "unparseable"}:
        return f"amount_{row.value_status}"
    if metric.require_recommended and row.recommended_for_aggregates is not True:
        return metric.recommended_reason
    if row.multi_country:
        return "multi_country_whole_project_value"
    if row.value_status == "reported" and row.currency != metric.currency:
        return "currency_unknown_or_different"
    if row.value_status == "reported" and row.unit is None:
        return "unit_unknown"
    return None


def _point(
    year: int, amounts: list[MonetaryAmount], excluded: Counter[str], metric: Metric
) -> TrendPoint:
    if not amounts:
        return TrendPoint(
            year=year,
            status="unavailable",
            total=None,
            unit=None,
            summed_records=0,
            missing_value_records=0,
            estimated_records=0,
            excluded_records=dict(excluded),
            unavailable_reason="Every observation for this year was excluded by the rules.",
        )
    try:
        result = aggregate(amounts)
    except AggregationError as exc:
        return TrendPoint(
            year=year,
            status="unavailable",
            total=None,
            unit=None,
            summed_records=0,
            missing_value_records=0,
            estimated_records=0,
            excluded_records=dict(excluded),
            unavailable_reason=str(exc),
        )
    if result.summed_records == 0:
        return TrendPoint(
            year=year,
            status="unavailable",
            total=None,
            unit=None,
            summed_records=0,
            missing_value_records=result.missing_value_records,
            estimated_records=0,
            excluded_records=dict(excluded),
            unavailable_reason="No amount is reported for this year (not treated as zero).",
        )
    return TrendPoint(
        year=year,
        status="available",
        total=result.total_in_units,
        unit=metric.unit_label,
        summed_records=result.summed_records,
        missing_value_records=result.missing_value_records,
        estimated_records=result.estimated_records,
        excluded_records=dict(excluded),
        unavailable_reason=None,
    )
