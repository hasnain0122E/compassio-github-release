"""Historical funding intelligence (Task 008): grouped totals, institutions, approved vs
disbursed, climate distributions, country profile and source coverage.

Every money figure: one registered metric (one source, flow kind, level, currency, price basis)
-> ``services.finance.metric_statement`` rows -> ``exclusion_reason`` -> ``safe_total``
(``compassio_ml.finance.aggregate``). Excluded rows are counted by reason; unsafe totals are null.
"""

from collections import Counter, defaultdict
from collections.abc import Callable
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from compassio_api.db.models import (
    ClimateAnnotation,
    FinancialObservation,
    ImportRun,
    Project,
    ProjectCountry,
    ProjectEnrichment,
    Source,
)
from compassio_api.schemas.data import AccessNotice
from compassio_api.schemas.decision import (
    ApprovedDisbursedResponse,
    ApprovedDisbursedSource,
    ClimateDistribution,
    ClimateDistributionResponse,
    CountryMetricSummary,
    CountryProfileResponse,
    CoverageResponse,
    DistributionBucket,
    GroupedFundingResponse,
    GroupedTotal,
    InstitutionCount,
    InstitutionGroup,
    InstitutionsResponse,
    MetricDeclaration,
    SourceCount,
    SourceCoverage,
)
from compassio_api.services.access import AccessPolicy, SourceRightsNotClearedError
from compassio_api.services.cache import cached, data_version
from compassio_api.services.decision.evidence import INSTITUTION_FIELDS, PUBLISHER_IS_FUNDER
from compassio_api.services.decision.methodology import DECISION_DISCLAIMERS
from compassio_api.services.finance import (
    DISCLAIMERS,
    METRICS,
    Metric,
    UnknownMetricError,
)
from compassio_api.services.finance_rows import (
    exclusion_reason,
    metric_amount,
    metric_statement,
    safe_total,
)
from compassio_api.services.projects import RIO_SCHEME
from compassio_ml.finance import AmountLevel, AmountUnit, FlowKind, MonetaryAmount, PriceBasis

MEANING_BY_FLOW = {
    "commitment": "historical commitments (not disbursements)",
    "approval": "approved funding (not necessarily disbursed)",
    "gcf_financing": "GCF financing approved by the Board (excludes co-financing)",
    "disbursement": "disbursed funds as published",
    "repayment_principal": "principal repaid to the lender (NOT funding)",
    "repayment_interest": "interest paid to the lender (NOT funding)",
    "pledge": "pledges (promises, not commitments)",
    "readiness_grant": "readiness grants (capacity support)",
}


def _access(policy: AccessPolicy) -> AccessNotice:
    return AccessNotice(mode=policy.mode, notice=policy.notice)


def _metric(policy: AccessPolicy, metric_id: str) -> Metric:
    metric = METRICS.get(metric_id)
    if metric is None:
        raise UnknownMetricError(metric_id)
    if not policy.allows(metric.source_id):
        raise SourceRightsNotClearedError(
            f"source '{metric.source_id}' may not be served in the current access mode"
        )
    return metric


def declaration(metric: Metric, universe: str, excluded: dict[str, int]) -> MetricDeclaration:
    return MetricDeclaration(
        metric_id=metric.metric_id,
        label=metric.label,
        universe=universe,
        financial_meaning=MEANING_BY_FLOW.get(metric.flow_kind, metric.flow_kind),
        source_id=metric.source_id,
        flow_kind=metric.flow_kind,
        level=metric.level,
        currency=metric.currency,
        price_basis=metric.price_basis,
        unit=f"units of {metric.currency}" if metric.currency else None,
        year_basis=metric.year_basis,
        is_funding=metric.is_funding,
        known_exclusions=list(metric.limitations),
        excluded_records=dict(sorted(excluded.items())),
    )


def _single_countries(
    session: Session, source_ids: list[str]
) -> tuple[dict[str, str], dict[str, str]]:
    """(project id -> ISO3 for records with exactly one mapped country, ISO3 -> name)."""
    rows = session.execute(
        select(ProjectCountry.project_id, ProjectCountry.iso3, ProjectCountry.country_name)
        .join(Project, Project.id == ProjectCountry.project_id)
        .where(Project.source_id.in_(source_ids), ProjectCountry.iso3.is_not(None))
    ).all()
    per: dict[str, set[str]] = defaultdict(set)
    names: dict[str, str] = {}
    for pid, iso3, name in rows:
        if iso3 is None:
            continue
        per[pid].add(iso3)
        names.setdefault(iso3, name)
    return {pid: next(iter(s)) for pid, s in per.items() if len(s) == 1}, names


def _project_sources(metric: Metric) -> list[str]:
    # API lines (gcf_api_projects) are attached to the GCF export's project rows.
    return ["gcf_projects"] if metric.source_id == "gcf_api_projects" else [metric.source_id]


def funding_by(
    session: Session,
    policy: AccessPolicy,
    metric_id: str,
    dimension: Literal["country", "sector"],
    year_from: int | None,
    year_to: int | None,
    limit: int,
) -> GroupedFundingResponse:
    metric = _metric(policy, metric_id)
    key = (
        "funding_by",
        metric_id,
        dimension,
        year_from,
        year_to,
        limit,
        policy.mode,
        tuple(sorted(policy.visible_source_ids)),
    )
    return cached(
        session,
        key,
        lambda: _funding_by(session, policy, metric, dimension, year_from, year_to, limit),
    )


def _funding_by(
    session: Session,
    policy: AccessPolicy,
    metric: Metric,
    dimension: Literal["country", "sector"],
    year_from: int | None,
    year_to: int | None,
    limit: int,
) -> GroupedFundingResponse:
    universe = (
        f"{metric.description} Grouped by {dimension}; years "
        f"{year_from or 'all'}-{year_to or 'all'}; undated rows excluded (counted)."
    )
    if metric.unavailable_reason is not None:
        return GroupedFundingResponse(
            dimension=dimension,
            status="unavailable",
            unavailable_reason=metric.unavailable_reason,
            declaration=declaration(metric, universe, {}),
            year_from=year_from,
            year_to=year_to,
            groups=[],
            groups_total=0,
            groups_shown=0,
            disclaimers=list(DISCLAIMERS),
            access=_access(policy),
        )
    sources = _project_sources(metric)
    labels: dict[str, str] = {}
    if dimension == "country":
        assign, labels = _single_countries(session, sources)
    else:
        assign = {
            pid: str(sector)
            for pid, sector in session.execute(
                select(Project.id, Project.sector_name).where(
                    Project.source_id.in_(sources), Project.sector_name.is_not(None)
                )
            )
        }
    groups: dict[str, list[MonetaryAmount]] = defaultdict(list)
    excluded: Counter[str] = Counter()
    for row in session.execute(metric_statement(metric, None, year_from, year_to)):
        if row.effective_year is None:
            excluded["undated"] += 1
            continue
        reason = exclusion_reason(metric, row)
        if reason is not None:
            excluded[reason] += 1
            continue
        if dimension == "country" and metric.components == "country_breakdown":
            group = row.country_iso3
        else:
            group = assign.get(row.project_id)
        if group is None:
            excluded[
                "country_not_attributable" if dimension == "country" else "sector_not_stated"
            ] += 1
            continue
        groups[group].append(metric_amount(metric, row))
    out: list[GroupedTotal] = []
    for group, amounts in groups.items():
        t = safe_total(amounts)
        out.append(
            GroupedTotal(
                key=group,
                label=labels.get(group, group),
                status="available" if t.total is not None else "unavailable",
                total=t.total,
                summed_records=t.summed_records,
                missing_value_records=t.missing_value_records,
                estimated_records=t.estimated_records,
                unavailable_reason=t.reason,
            )
        )
    out.sort(key=lambda g: (g.total is None, -(g.total or Decimal(0)), g.key))
    return GroupedFundingResponse(
        dimension=dimension,
        status="available" if out else "unavailable",
        unavailable_reason=None if out else f"No observation can be attributed to a {dimension}.",
        declaration=declaration(metric, universe, dict(excluded)),
        year_from=year_from,
        year_to=year_to,
        groups=out[:limit],
        groups_total=len(out),
        groups_shown=min(limit, len(out)),
        disclaimers=list(DISCLAIMERS),
        access=_access(policy),
    )


def _country_projects(iso3: str | None) -> Any:
    return select(ProjectCountry.project_id).where(ProjectCountry.iso3 == iso3)


def institutions(
    session: Session, policy: AccessPolicy, country: str | None, limit: int
) -> InstitutionsResponse:
    key = ("institutions", country, limit, policy.mode, tuple(sorted(policy.visible_source_ids)))
    return cached(session, key, lambda: _institutions(session, policy, country, limit))


def _institutions(
    session: Session, policy: AccessPolicy, country: str | None, limit: int
) -> InstitutionsResponse:
    groups: list[InstitutionGroup] = []
    publishers = {s.source_id: s.publisher for s in session.scalars(select(Source))}
    for source_id in sorted(set(INSTITUTION_FIELDS) | set(PUBLISHER_IS_FUNDER)):
        if not policy.allows(source_id):
            continue
        stmt = select(Project.attributes).where(Project.source_id == source_id)
        if country is not None:
            stmt = stmt.where(Project.id.in_(_country_projects(country)))
        attrs = [a or {} for a in session.scalars(stmt)]
        if source_id in PUBLISHER_IS_FUNDER:
            groups.append(
                InstitutionGroup(
                    source_id=source_id,
                    role=PUBLISHER_IS_FUNDER[source_id],
                    field="publisher",
                    institutions=[
                        InstitutionCount(institution=publishers[source_id], projects=len(attrs))
                    ]
                    if attrs
                    else [],
                    distinct_institutions=1 if attrs else 0,
                    projects_without_institution=0,
                    projects=len(attrs),
                )
            )
        for field, role in INSTITUTION_FIELDS.get(source_id, ()):
            counts: Counter[str] = Counter()
            missing = 0
            for a in attrs:
                value = a.get(field)
                if isinstance(value, str) and value.strip():
                    counts[value.strip()] += 1
                else:
                    missing += 1
            ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
            groups.append(
                InstitutionGroup(
                    source_id=source_id,
                    role=role,
                    field=field,
                    institutions=[
                        InstitutionCount(institution=k, projects=v) for k, v in ranked[:limit]
                    ],
                    distinct_institutions=len(counts),
                    projects_without_institution=missing,
                    projects=len(attrs),
                )
            )
    return InstitutionsResponse(
        universe="Project records of each visible source"
        + (f" with a mapped country {country}" if country else ""),
        country=country,
        measure="project_record_count",
        groups=groups,
        note="Counts of records naming each institution, exactly as the source spells it "
        "(no name merging). Roles differ by source: an implementer is not a funder. No money "
        "is summed here.",
        access=_access(policy),
    )


# --------------------------------------------------------------- approved vs disbursed
_PairSpec = tuple[str, str, Callable[[Any], bool], str, Callable[[Any], bool], str, str, list[str]]
PAIR_SPECS: dict[str, _PairSpec] = {
    "climate_funds_update": (
        "approval",
        "Approved funding per CFU project (stated total, instrument components excluded)",
        lambda r: not r.is_component,
        "disbursement",
        lambda r: not r.is_component,
        "Disbursed to date as reported by CFU (stated total)",
        "climate_funds_update",
        [
            "CFU reports cumulative disbursement at its own update; timing differs by fund.",
            "Project-level USD as published (CFU units: millions, converted with the unit "
            "scale only).",
        ],
    ),
    "gcf_api_projects": (
        "gcf_financing",
        "GCF financing approved (sum of the project's USD funding lines)",
        lambda r: r.is_component and r.financing_type != "country_breakdown",
        "disbursement",
        lambda r: True,
        "GCF disbursement transactions (USD)",
        "gcf_projects",
        [
            "Projects with any non-USD line or lines inconsistent with the published total "
            "are excluded (counted), never converted.",
            "Disbursement lags approval by years; a low ratio is not under-performance.",
        ],
    ),
    "adb_pakistan": (
        "commitment",
        "ADB commitment transactions (IATI type 2) per financing instrument",
        lambda r: True,
        "disbursement",
        lambda r: True,
        "ADB disbursement transactions (IATI type 3, incl. published reversals)",
        "adb_pakistan",
        ["ADB publishes commitments, not approvals; repayments are excluded (not funding)."],
    ),
}


def _reported(per: dict[str, dict[str, list[Any]]], bad: set[str], flow: str) -> set[str]:
    """Records (not excluded) with at least one REPORTED amount of ``flow``."""
    return {
        pid
        for pid, flows in per.items()
        if pid not in bad and any(r.value_status == "reported" for r in flows.get(flow, []))
    }


def _pair_total(source_id: str, flow: str, level: str, rows: list[Any]) -> Decimal | None:
    amounts = [
        MonetaryAmount(
            source_id=source_id,
            source_record_id=r.observation_key,
            flow_kind=FlowKind(flow),
            level=AmountLevel(level),
            value=r.amount if r.value_status == "reported" else None,
            unit=AmountUnit(r.unit or "units"),
            currency=r.currency or "USD",
            price_basis=PriceBasis(r.price_basis),
            date_meaning=r.date_meaning,
            estimated=r.estimated,
        )
        for r in rows
    ]
    return safe_total(amounts).total


def approved_vs_disbursed(
    session: Session, policy: AccessPolicy, country: str | None
) -> ApprovedDisbursedResponse:
    key = ("approved_vs_disbursed", country, policy.mode, tuple(sorted(policy.visible_source_ids)))
    return cached(session, key, lambda: _approved_vs_disbursed(session, policy, country))


def _approved_vs_disbursed(
    session: Session, policy: AccessPolicy, country: str | None
) -> ApprovedDisbursedResponse:
    out: list[ApprovedDisbursedSource] = []
    for source_id, spec in PAIR_SPECS.items():
        a_flow, a_meaning, a_sel, d_flow, d_sel, d_meaning, proj_source, limits = spec
        if not policy.allows(source_id) or not policy.allows(proj_source):
            continue
        obs = FinancialObservation
        stmt = (
            select(
                obs.project_id,
                obs.observation_key,
                obs.flow_kind,
                obs.level,
                obs.amount,
                obs.value_status,
                obs.unit,
                obs.currency,
                obs.price_basis,
                obs.is_component,
                obs.financing_type,
                obs.recommended_for_aggregates,
                obs.estimated,
                obs.date_meaning,
                Project.multi_country,
            )
            .join(Project, Project.id == obs.project_id)
            .where(obs.source_id == source_id, obs.flow_kind.in_([a_flow, d_flow]))
        )
        if country is not None:
            stmt = stmt.where(
                obs.project_id.in_(_country_projects(country)), Project.multi_country.is_(False)
            )
        per: dict[str, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))
        excluded: Counter[str] = Counter()
        bad: set[str] = set()
        for r in session.execute(stmt):
            selected = a_sel(r) if r.flow_kind == a_flow else d_sel(r)
            if not selected:
                continue
            per[r.project_id][r.flow_kind].append(r)
            reason = None
            if r.multi_country:
                reason = "multi_country_whole_project_value"
            elif r.value_status in {"invalid", "unparseable"}:
                reason = f"amount_{r.value_status}"
            elif r.value_status == "reported" and r.currency != "USD":
                reason = "currency_not_usd_or_unknown"
            elif (
                source_id == "gcf_api_projects"
                and r.flow_kind == a_flow
                and (r.recommended_for_aggregates is not True)
            ):
                reason = "funding_lines_inconsistent_with_published_total"
            if reason is not None:
                bad.add(r.project_id)
                excluded[reason] += 1

        with_a = _reported(per, bad, a_flow)
        with_d = _reported(per, bad, d_flow)
        paired = sorted(with_a & with_d)

        levels = {f: {r.level for p in paired for r in per[p][f]} for f in (a_flow, d_flow)}
        approved = (
            _pair_total(
                source_id, a_flow, levels[a_flow].pop(), [r for p in paired for r in per[p][a_flow]]
            )
            if len(levels[a_flow]) == 1
            else None
        )
        disbursed = (
            _pair_total(
                source_id, d_flow, levels[d_flow].pop(), [r for p in paired for r in per[p][d_flow]]
            )
            if len(levels[d_flow]) == 1
            else None
        )
        ratio = (
            (disbursed / approved).quantize(Decimal("0.0001"))
            if approved and disbursed is not None
            else None
        )
        out.append(
            ApprovedDisbursedSource(
                source_id=source_id,
                approval_meaning=a_meaning,
                disbursement_meaning=d_meaning,
                currency="USD",
                universe="Records of this source that report BOTH figures in USD (paired); "
                "multi-country records excluded" + (f"; mapped to {country}" if country else ""),
                projects_with_approval=len(with_a),
                projects_with_disbursement=len(with_d),
                paired_projects=len(paired),
                approved_total_paired=approved,
                disbursed_total_paired=disbursed,
                disbursed_to_approved_ratio=ratio,
                excluded_projects={k: v for k, v in sorted(excluded.items())},
                limitations=limits,
            )
        )
    return ApprovedDisbursedResponse(
        country=country, sources=out, disclaimers=list(DISCLAIMERS), access=_access(policy)
    )


# -------------------------------------------------------------------- climate distribution
def _rio_bucket(m: int | None, a: int | None) -> str:
    m, a = m or 0, a or 0
    if m and a:
        return "mitigation and adaptation"
    if m:
        return "mitigation only"
    if a:
        return "adaptation only"
    return "not climate-related"


def climate_distribution(
    session: Session, policy: AccessPolicy, country: str | None
) -> ClimateDistributionResponse:
    key = ("climate_distribution", country, policy.mode, tuple(sorted(policy.visible_source_ids)))
    return cached(session, key, lambda: _climate_distribution(session, policy, country))


def _climate_distribution(
    session: Session, policy: AccessPolicy, country: str | None
) -> ClimateDistributionResponse:
    ann = ClimateAnnotation
    stmt = (
        select(
            ann.scheme,
            ann.annotation_source_id,
            ann.kind,
            ann.mitigation,
            ann.adaptation,
            ann.overall,
            ann.label,
        )
        .join(Project, Project.id == ann.project_id)
        .where(
            ann.annotation_source_id.in_(sorted(policy.visible_source_ids)),
            Project.source_id.in_(sorted(policy.visible_source_ids)),
        )
    )
    if country is not None:
        stmt = stmt.where(ann.project_id.in_(_country_projects(country)))
    buckets: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    for scheme, src, kind, m, a, overall, label in session.execute(stmt):
        if scheme == RIO_SCHEME:
            buckets[(scheme + ":objective", src, kind)][_rio_bucket(m, a)] += 1
            strength = {2: "principal", 1: "significant"}.get(overall or 0, "not climate-related")
            buckets[(scheme + ":strength", src, kind)][strength] += 1
        else:
            buckets[(scheme, src, kind)][label or "(no label)"] += 1
    meanings = {
        RIO_SCHEME + ":objective": "Qi et al. 2026 Rio-marker research labels: which climate "
        "objective is marked (AidData records).",
        RIO_SCHEME + ":strength": "Highest Rio marker: principal (2) or significant (1).",
        "cfu_theme_objective": "Climate Funds Update theme / objective as published.",
        "gcf_theme": "GCF theme as published.",
        "gcf_readiness_activity": "GCF readiness activity type (capacity support).",
    }
    dists = [
        ClimateDistribution(
            scheme=scheme,
            annotation_source_id=src,
            kind="research_annotation"
            if kind == "research_annotation"
            else "source_classification",
            meaning=meanings.get(scheme, scheme),
            buckets=[
                DistributionBucket(label=k, projects=v)
                for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
            projects_annotated=sum(c.values()),
        )
        for (scheme, src, kind), c in sorted(buckets.items())
    ]
    return ClimateDistributionResponse(
        country=country,
        measure="project_record_count",
        distributions=dists,
        statement="Counts of records by climate label or classification. Labels describe "
        "stated purpose; they are not measured climate outcomes. Labels are kept as published "
        "(no merging of spellings).",
        access=_access(policy),
    )


# -------------------------------------------------------------------------------- coverage
def coverage(session: Session, policy: AccessPolicy) -> CoverageResponse:
    key = ("coverage", policy.mode, tuple(sorted(policy.visible_source_ids)))
    return cached(session, key, lambda: _coverage(session, policy))


def _coverage(session: Session, policy: AccessPolicy) -> CoverageResponse:
    projects = {
        s: (n, lo, hi)
        for s, n, lo, hi in session.execute(
            select(
                Project.source_id, func.count(), func.min(Project.year), func.max(Project.year)
            ).group_by(Project.source_id)
        )
    }
    obs = FinancialObservation
    observations = {
        s: (n, int(rep or 0))
        for s, n, rep in session.execute(
            select(
                obs.source_id,
                func.count(),
                func.sum(case((obs.value_status == "reported", 1), else_=0)),
            ).group_by(obs.source_id)
        )
    }
    imports = {
        s: t
        for s, t in session.execute(
            select(ImportRun.source_key, func.max(ImportRun.finished_at))
            .where(ImportRun.status == "completed")
            .group_by(ImportRun.source_key)
        )
    }
    # A source's rows may be written by an import with another key (AidData rows come from the
    # research_paper import). Freshness = latest completed run of any key that wrote its rows.
    writer_keys: dict[str, set[str]] = defaultdict(set)
    for source_id, run_key in session.execute(
        select(Project.source_id, ImportRun.source_key)
        .join(ImportRun, ImportRun.id == Project.import_run_id)
        .distinct()
    ):
        writer_keys[source_id].add(run_key)
    for source_id, keys in writer_keys.items():
        times = [t for k in keys | {source_id} if (t := imports.get(k)) is not None]
        if times:
            imports[source_id] = max(times)
    snapshots: dict[str, list[str]] = defaultdict(list)
    for s, snap in session.execute(
        select(ProjectEnrichment.source_id, ProjectEnrichment.snapshot_id).distinct()
    ):
        snapshots[s].append(snap)
    out = []
    for src in session.scalars(select(Source).order_by(Source.source_id)):
        if not policy.allows(src.source_id):
            continue
        n, lo, hi = projects.get(src.source_id, (0, None, None))
        o, rep = observations.get(src.source_id, (0, 0))
        out.append(
            SourceCoverage(
                source_id=src.source_id,
                name=src.name,
                publisher=src.publisher,
                rights_status=src.rights_status,
                access_tier=src.access_tier,
                served_in_current_mode=True,
                version_info=src.version_info,
                project_rows=n,
                financial_observation_rows=o,
                reported_amount_rows=rep,
                min_year=lo,
                max_year=hi,
                last_completed_import=imports.get(src.source_id),
                snapshot_ids=sorted(snapshots.get(src.source_id, [])),
            )
        )
    return CoverageResponse(
        data_version=list(data_version(session)), sources=out, access=_access(policy)
    )


# --------------------------------------------------------------------------- country profile
def country_profile(session: Session, policy: AccessPolicy, iso3: str) -> CountryProfileResponse:
    key = ("country_profile", iso3, policy.mode, tuple(sorted(policy.visible_source_ids)))
    return cached(session, key, lambda: _country_profile(session, policy, iso3))


def _country_profile(session: Session, policy: AccessPolicy, iso3: str) -> CountryProfileResponse:
    visible = sorted(policy.visible_source_ids)
    counts = [
        SourceCount(
            source_id=s,
            single_country_projects=int(single or 0),
            multi_country_projects_including_country=int(multi or 0),
        )
        for s, single, multi in session.execute(
            select(
                Project.source_id,
                func.sum(case((Project.multi_country.is_(False), 1), else_=0)),
                func.sum(case((Project.multi_country.is_(True), 1), else_=0)),
            )
            .where(Project.id.in_(_country_projects(iso3)), Project.source_id.in_(visible))
            .group_by(Project.source_id)
            .order_by(Project.source_id)
        )
    ]
    summaries: list[CountryMetricSummary] = []
    for metric in METRICS.values():
        if not policy.allows(metric.source_id):
            continue
        universe = f"{metric.description} Restricted to {iso3}; all years; undated excluded."
        if metric.unavailable_reason is not None:
            summaries.append(
                CountryMetricSummary(
                    declaration=declaration(metric, universe, {}),
                    status="unavailable",
                    all_years_total=None,
                    summed_records=0,
                    first_year=None,
                    last_year=None,
                    unavailable_reason=metric.unavailable_reason,
                )
            )
            continue
        amounts: list[MonetaryAmount] = []
        years: list[int] = []
        excluded: Counter[str] = Counter()
        for row in session.execute(metric_statement(metric, iso3)):
            if row.effective_year is None:
                excluded["undated"] += 1
                continue
            reason = exclusion_reason(metric, row)
            if reason is not None:
                excluded[reason] += 1
                continue
            amounts.append(metric_amount(metric, row))
            years.append(row.effective_year)
        t = safe_total(amounts)
        summaries.append(
            CountryMetricSummary(
                declaration=declaration(metric, universe, dict(excluded)),
                status="available" if t.total is not None else "unavailable",
                all_years_total=t.total,
                summed_records=t.summed_records,
                first_year=min(years, default=None),
                last_year=max(years, default=None),
                unavailable_reason=t.reason,
            )
        )
    sectors = session.execute(
        select(Project.sector_name, func.count())
        .where(
            Project.id.in_(_country_projects(iso3)),
            Project.source_id.in_(visible),
            Project.sector_name.is_not(None),
        )
        .group_by(Project.sector_name)
        .order_by(func.count().desc(), Project.sector_name)
        .limit(10)
    ).all()
    return CountryProfileResponse(
        country=iso3,
        project_counts=counts,
        metrics=summaries,
        top_sectors=[DistributionBucket(label=str(s), projects=n) for s, n in sectors],
        climate=_climate_distribution(session, policy, iso3),
        country_aggregates_endpoint=f"/api/v1/analytics/country-aggregates?iso3={iso3}",
        disclaimers=list(DISCLAIMERS) + list(DECISION_DISCLAIMERS[:2]),
        access=_access(policy),
    )
