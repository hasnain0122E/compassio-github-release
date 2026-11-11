"""Source metadata, available filter values and the coverage overview (grouped SQL counts)."""

from collections import defaultdict

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from compassio_api.db.models import (
    ClimateAnnotation,
    DataQualityWarning,
    FinancialObservation,
    Project,
    ProjectCountry,
    ProjectRelationship,
    Source,
)
from compassio_api.schemas.data import (
    AccessNotice,
    FilterCountry,
    FilterSector,
    FiltersResponse,
    FilterYearRange,
    MetricsResponse,
    OverviewResponse,
    SourceOut,
    SourceOverview,
    SourcesResponse,
)
from compassio_api.services.access import PERMITTED_RIGHTS, AccessPolicy
from compassio_api.services.cache import cached
from compassio_api.services.finance import DISCLAIMERS, METRICS
from compassio_api.services.projects import RIO_SCHEME, SORT_OPTIONS

COUNTING_RULES = (
    "Counts are per source and per unit of observation; rows from different sources are never "
    "added into one project count.",
    "AidData records in one Parent ID package and ADB instruments under one project number are "
    "reported as 'distinct_groups' as well as rows.",
    "CFU rows that cite a GCF reference code are linked to the GCF project, not merged; GCF "
    "projects are counted once, from the GCF export.",
    "Pakistan rows include multi-country projects that list Pakistan; their amounts are "
    "whole-project values.",
)


def _access(policy: AccessPolicy) -> AccessNotice:
    return AccessNotice(mode=policy.mode, notice=policy.notice)


def list_sources(session: Session, policy: AccessPolicy) -> SourcesResponse:
    counts = dict(
        session.execute(select(Project.source_id, func.count()).group_by(Project.source_id)).all()
    )
    sources = session.scalars(select(Source).order_by(Source.source_id)).all()
    return SourcesResponse(
        sources=[
            SourceOut(
                source_id=s.source_id,
                name=s.name,
                publisher=s.publisher,
                version_info=s.version_info,
                file_sha256=s.file_sha256,
                reference_url=s.reference_url,
                rights_status=s.rights_status,
                rights_evidence=s.rights_evidence,
                license_notes=s.license_notes,
                observation_type=s.observation_type,
                audited_record_count=s.audited_record_count,
                imported_project_rows=int(counts.get(s.source_id, 0)),
                served_in_current_mode=policy.allows(s.source_id),
                public_display_permitted=s.rights_status in PERMITTED_RIGHTS,
            )
            for s in sources
        ],
        access=_access(policy),
    )


def _key(policy: AccessPolicy, name: str) -> tuple[str, str, tuple[str, ...]]:
    return (name, policy.mode, tuple(sorted(policy.visible_source_ids)))


def filters(session: Session, policy: AccessPolicy) -> FiltersResponse:
    return cached(session, _key(policy, "filters"), lambda: _filters(session, policy))


def overview(session: Session, policy: AccessPolicy) -> OverviewResponse:
    return cached(session, _key(policy, "overview"), lambda: _overview(session, policy))


def _filters(session: Session, policy: AccessPolicy) -> FiltersResponse:
    visible = sorted(policy.visible_source_ids)
    countries = session.execute(
        select(ProjectCountry.iso3, func.min(ProjectCountry.country_name), func.count())
        .join(Project, Project.id == ProjectCountry.project_id)
        .where(Project.source_id.in_(visible), ProjectCountry.iso3.is_not(None))
        .group_by(ProjectCountry.iso3)
        .order_by(ProjectCountry.iso3)
    ).all()
    sectors = session.execute(
        select(Project.source_id, Project.sector_vocabulary, Project.sector_name, func.count())
        .where(Project.source_id.in_(visible), Project.sector_name.is_not(None))
        .group_by(Project.source_id, Project.sector_vocabulary, Project.sector_name)
        .order_by(Project.source_id, Project.sector_name)
    ).all()
    years = session.execute(
        select(
            Project.source_id,
            func.min(Project.year_type),
            func.min(Project.year),
            func.max(Project.year),
            func.count(Project.year),
            func.count(),
        )
        .where(Project.source_id.in_(visible))
        .group_by(Project.source_id)
        .order_by(Project.source_id)
    ).all()
    present = sorted({row[0] for row in years})
    return FiltersResponse(
        sources=present,
        countries=[FilterCountry(iso3=i, name=n, project_rows=c) for i, n, c in countries if i],
        sectors=[
            FilterSector(source_id=s, sector_vocabulary=v, sector_name=n, project_rows=c)
            for s, v, n, c in sectors
            if n
        ],
        year_ranges=[
            FilterYearRange(
                source_id=s,
                year_type=t,
                min_year=lo,
                max_year=hi,
                rows_with_year=with_year,
                rows_without_year=total - with_year,
            )
            for s, t, lo, hi, with_year, total in years
        ],
        climate_annotation_filter=(
            "climate_related=true|false filters on the Qi et al. 2026 Rio-marker research "
            "annotation (AidData records only). Records without that annotation are excluded "
            "when the filter is set. It is not a Compassio model prediction."
        ),
        sort_options=list(SORT_OPTIONS),
        access=_access(policy),
    )


def metrics(policy: AccessPolicy) -> MetricsResponse:
    return MetricsResponse(
        metrics=[m.out() for m in METRICS.values() if policy.allows(m.source_id)],
        access=_access(policy),
    )


def _overview(session: Session, policy: AccessPolicy) -> OverviewResponse:
    visible = sorted(policy.visible_source_ids)
    base = (
        select(
            Project.source_id,
            func.min(Project.record_level),
            func.count(),
            func.count(func.distinct(func.coalesce(Project.group_key, Project.id))),
            func.count(Project.description),
            func.count(Project.year),
            func.min(Project.year),
            func.max(Project.year),
            func.sum(case((Project.multi_country, 1), else_=0)),
        )
        .where(Project.source_id.in_(visible))
        .group_by(Project.source_id)
        .order_by(Project.source_id)
    )
    pakistan = dict(
        session.execute(
            select(Project.source_id, func.count(func.distinct(Project.id)))
            .join(ProjectCountry, ProjectCountry.project_id == Project.id)
            .where(ProjectCountry.iso3 == "PAK", Project.source_id.in_(visible))
            .group_by(Project.source_id)
        ).all()
    )
    flows: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(dict))
    for source_id, flow, status, count in session.execute(
        select(
            FinancialObservation.source_id,
            FinancialObservation.flow_kind,
            FinancialObservation.value_status,
            func.count(),
        )
        .where(FinancialObservation.source_id.in_(visible))
        .group_by(
            FinancialObservation.source_id,
            FinancialObservation.flow_kind,
            FinancialObservation.value_status,
        )
    ).all():
        flows[source_id][flow][status] = int(count)
    annotations: dict[str, dict[str, int]] = defaultdict(dict)
    for source_id, scheme, flag, count in session.execute(
        select(
            Project.source_id,
            ClimateAnnotation.scheme,
            ClimateAnnotation.is_climate_related,
            func.count(),
        )
        .join(Project, Project.id == ClimateAnnotation.project_id)
        .where(Project.source_id.in_(visible), ClimateAnnotation.annotation_source_id.in_(visible))
        .group_by(Project.source_id, ClimateAnnotation.scheme, ClimateAnnotation.is_climate_related)
    ).all():
        if scheme == RIO_SCHEME:
            key = (
                "unknown"
                if flag is None
                else ("climate_related" if flag else "not_climate_related")
            )
            annotations[source_id][f"{scheme}:{key}"] = int(count)
        else:
            annotations[source_id][scheme] = annotations[source_id].get(scheme, 0) + int(count)
    warnings: dict[str, dict[str, int]] = defaultdict(dict)
    for source_id, code, count in session.execute(
        select(Project.source_id, DataQualityWarning.code, func.count())
        .join(Project, Project.id == DataQualityWarning.project_id)
        .where(Project.source_id.in_(visible))
        .group_by(Project.source_id, DataQualityWarning.code)
        .order_by(func.count().desc())
    ).all():
        warnings[source_id][code] = int(count)
    links = dict(
        session.execute(
            select(ProjectRelationship.status, func.count())
            .join(Project, Project.id == ProjectRelationship.from_project_id)
            .where(Project.source_id.in_(visible))
            .group_by(ProjectRelationship.status)
        ).all()
    )
    return OverviewResponse(
        sources=[
            SourceOverview(
                source_id=s,
                record_level=level,
                project_rows=rows,
                distinct_groups=groups,
                rows_with_description=described,
                rows_with_year=dated,
                min_year=lo,
                max_year=hi,
                multi_country_rows=int(multi or 0),
                pakistan_rows=int(pakistan.get(s, 0)),
                observations_by_flow={k: dict(v) for k, v in flows[s].items()},
                climate_annotations=dict(annotations[s]),
                top_warnings=dict(list(warnings[s].items())[:12]),
            )
            for s, level, rows, groups, described, dated, lo, hi, multi in session.execute(
                base
            ).all()
        ],
        cross_source_links={str(k): int(v) for k, v in links.items()},
        counting_rules=list(COUNTING_RULES),
        disclaimers=list(DISCLAIMERS),
        access=_access(policy),
    )
