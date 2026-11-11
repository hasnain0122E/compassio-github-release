"""Documents, enrichment views, data-quality / completeness, GCF timeline, country aggregates,
relationship summaries. All filtered by the rights policy; aggregates via grouped SQL."""

from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from compassio_api.core.provenance import ENRICHMENT_PRECEDENCE as PRECEDENCE
from compassio_api.db.models import (
    CountryAggregate,
    DataQualityWarning,
    Document,
    DocumentLink,
    FinancialObservation,
    Project,
    ProjectCountry,
    ProjectEnrichment,
    ProjectRelationship,
    RecordGroup,
    Source,
)
from compassio_api.schemas.data import (
    AccessNotice,
    DocumentLinkOut,
    DocumentOut,
    EnrichmentOut,
    PageMeta,
    TrendPoint,
)
from compassio_api.schemas.discovery import (
    CountryAggregateOut,
    CountryAggregatesResponse,
    DataQualityResponse,
    DocumentPage,
    FieldCoverage,
    FinancingCompletenessResponse,
    FlowCompleteness,
    GcfTimelineResponse,
    MeasureMeta,
    RelationshipSummaryResponse,
    RelationshipSummaryRow,
    SourceQuality,
    TimelinePoint,
)
from compassio_api.services.access import AccessPolicy, SourceRightsNotClearedError
from compassio_api.services.cache import cached
from compassio_api.services.finance import DISCLAIMERS, METRICS
from compassio_api.services.finance import trends as metric_trends
from compassio_api.services.text import escape_like

API_SOURCE = "gcf_api_projects"
CPE_SOURCE = "climate_project_explorer"
DOC_RIGHTS = (
    "Catalogue metadata only. Linked documents belong to their publishers; Compassio does not "
    "store or redistribute them. Rights not reviewed."
)
COUNT_DEDUP = "Counts of distinct rows of one source; no cross-source addition."


def _access(policy: AccessPolicy) -> AccessNotice:
    return AccessNotice(mode=policy.mode, notice=policy.notice)


def _source_names(session: Session) -> dict[str, tuple[str, str]]:
    return {
        s.source_id: (s.name, s.observation_type) for s in session.scalars(select(Source)).all()
    }


# ----------------------------------------------------------------------------- per project
def enrichments_for(session: Session, policy: AccessPolicy, project_id: str) -> list[EnrichmentOut]:
    rows = session.scalars(
        select(ProjectEnrichment)
        .where(ProjectEnrichment.project_id == project_id)
        .order_by(ProjectEnrichment.source_id)
    ).all()
    return [
        EnrichmentOut(
            source_id=e.source_id,
            snapshot_id=e.snapshot_id,
            relation_type=e.relation_type,
            match_method=e.match_method,
            match_evidence=e.match_evidence,
            verification_state=e.verification_state,
            review_status=e.review_status,
            last_verified_on=e.last_verified_on,
            official_url=e.official_url,
            approval_date=e.approval_date,
            approval_date_type=e.approval_date_type,
            approval_status=e.approval_status,
            project_status=e.project_status,
            status_as_of=e.status_as_of,
            status_as_of_meaning=e.status_as_of_meaning,
            values=e.values,
            conflicts=e.conflicts,
            precedence=PRECEDENCE,
        )
        for e in rows
        if policy.allows(e.source_id)
    ]


def _document_out(doc: Document, linked: list[str]) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        source_id=doc.source_id,
        title=doc.title,
        family_name=doc.family_name,
        document_type=doc.document_type,
        publisher_fund=doc.publisher_fund,
        document_date=doc.document_date,
        document_date_type=doc.document_date_type,
        geographies=list(doc.geographies),
        languages=doc.languages,
        catalogue_url=doc.catalogue_url,
        content_url=doc.content_url,
        linked_project_ids=linked,
        rights_notice=DOC_RIGHTS,
    )


def documents_for(session: Session, policy: AccessPolicy, project_id: str) -> list[DocumentLinkOut]:
    rows = session.execute(
        select(DocumentLink, Document)
        .join(Document, Document.id == DocumentLink.document_id)
        .where(DocumentLink.project_id == project_id)
        .order_by(Document.document_date.desc(), Document.id)
    ).all()
    return [
        DocumentLinkOut(
            document=_document_out(doc, [project_id]),
            relation_type=link.relation_type,
            match_method=link.match_method,
            match_evidence=link.match_evidence,
            verification_state=link.verification_state,
            review_status=link.review_status,
            last_verified_on=link.last_verified_on,
        )
        for link, doc in rows
        if policy.allows(doc.source_id)
    ]


# -------------------------------------------------------------------------------- documents
def list_documents(
    session: Session,
    policy: AccessPolicy,
    *,
    page: int,
    page_size: int,
    project_id: str | None,
    fund: str | None,
    q: str | None,
    linked_only: bool,
) -> DocumentPage:
    if not policy.allows(CPE_SOURCE):
        raise SourceRightsNotClearedError("document catalogue source may not be served")
    conds: list[Any] = [Document.source_id.in_(sorted(policy.visible_source_ids))]
    if project_id is not None:
        conds.append(
            Document.id.in_(
                select(DocumentLink.document_id).where(DocumentLink.project_id == project_id)
            )
        )
    if linked_only:
        conds.append(Document.id.in_(select(DocumentLink.document_id)))
    if fund is not None:
        conds.append(Document.publisher_fund == fund)
    if q:
        pattern = f"%{escape_like(q.strip())}%"
        conds.append(
            or_(
                Document.title.like(pattern, escape="\\"),
                Document.family_name.like(pattern, escape="\\"),
            )
        )
    total = int(session.scalar(select(func.count(Document.id)).where(*conds)) or 0)
    docs = session.scalars(
        select(Document)
        .where(*conds)
        .order_by(Document.document_date.desc().nulls_last(), Document.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    links: dict[str, list[str]] = defaultdict(list)
    for doc_id, proj in session.execute(
        select(DocumentLink.document_id, DocumentLink.project_id)
        .where(DocumentLink.document_id.in_([d.id for d in docs]))
        .order_by(DocumentLink.project_id)
    ):
        links[doc_id].append(proj)
    pages = (total + page_size - 1) // page_size
    return DocumentPage(
        items=[_document_out(d, links.get(d.id, [])) for d in docs],
        pagination=PageMeta(page=page, page_size=page_size, total_items=total, total_pages=pages),
        applied_filters={
            k: v
            for k, v in {
                "project_id": project_id,
                "fund": fund,
                "q": q,
                "linked_only": linked_only,
            }.items()
            if v not in (None, False)
        },
        access=_access(policy),
        empty_result_message=None
        if docs
        else ("No documents match these filters." if total == 0 else "Page beyond the last page."),
    )


# ---------------------------------------------------------------------------- data quality
QUALITY_FIELDS: tuple[tuple[str, Any], ...] = (
    ("description", Project.description),
    ("year", Project.year),
    ("date_value", Project.date_value),
    ("sector_name", Project.sector_name),
    ("status", Project.status),
    ("region", Project.region),
)


def data_quality(session: Session, policy: AccessPolicy) -> DataQualityResponse:
    return cached(
        session,
        ("data_quality", policy.mode, tuple(sorted(policy.visible_source_ids))),
        lambda: _data_quality(session, policy),
    )


def _data_quality(session: Session, policy: AccessPolicy) -> DataQualityResponse:
    visible = sorted(policy.visible_source_ids)
    names = _source_names(session)
    columns = [func.count(col) for _, col in QUALITY_FIELDS]
    rows = session.execute(
        select(Project.source_id, func.min(Project.record_level), func.count(), *columns)
        .where(Project.source_id.in_(visible))
        .group_by(Project.source_id)
        .order_by(Project.source_id)
    ).all()
    iso = dict(
        session.execute(
            select(Project.source_id, func.count(func.distinct(ProjectCountry.project_id)))
            .join(ProjectCountry, ProjectCountry.project_id == Project.id)
            .where(Project.source_id.in_(visible), ProjectCountry.iso3.is_not(None))
            .group_by(Project.source_id)
        ).all()
    )
    warnings: dict[str, Counter[str]] = defaultdict(Counter)
    for source_id, code, n in session.execute(
        select(Project.source_id, DataQualityWarning.code, func.count())
        .join(Project, Project.id == DataQualityWarning.project_id)
        .where(Project.source_id.in_(visible))
        .group_by(Project.source_id, DataQualityWarning.code)
    ):
        warnings[source_id][code] = int(n)
    out: list[SourceQuality] = []
    for row in rows:
        source_id, level, total = row[0], row[1], int(row[2])
        fields = [
            FieldCoverage(field=name, present=int(row[3 + i]), missing=total - int(row[3 + i]))
            for i, (name, _) in enumerate(QUALITY_FIELDS)
        ]
        mapped = int(iso.get(source_id, 0))
        fields.append(FieldCoverage(field="country_iso3", present=mapped, missing=total - mapped))
        out.append(
            SourceQuality(
                source_id=source_id,
                record_level=level,
                rows=total,
                fields=fields,
                top_warnings=dict(warnings[source_id].most_common(10)),
                meta=MeasureMeta(
                    dataset=names.get(source_id, (source_id, ""))[0],
                    source_id=source_id,
                    unit_of_observation=names.get(source_id, ("", level))[1],
                    measure="records with / without each field",
                    currency=None,
                    unit="records",
                    date_meaning=None,
                    missing_count=0,
                    excluded_count=0,
                    deduplication_policy=COUNT_DEDUP,
                ),
            )
        )
    return DataQualityResponse(sources=out, access=_access(policy))


def financing_completeness(session: Session, policy: AccessPolicy) -> FinancingCompletenessResponse:
    return cached(
        session,
        ("financing_completeness", policy.mode, tuple(sorted(policy.visible_source_ids))),
        lambda: _financing_completeness(session, policy),
    )


def _financing_completeness(
    session: Session, policy: AccessPolicy
) -> FinancingCompletenessResponse:
    visible = sorted(policy.visible_source_ids)
    names = _source_names(session)
    obs = FinancialObservation

    def count_if(condition: Any) -> Any:
        return func.sum(case((condition, 1), else_=0))

    rows = session.execute(
        select(
            obs.source_id,
            obs.flow_kind,
            func.count(),
            count_if(obs.value_status == "reported"),
            count_if(obs.value_status == "not_reported"),
            count_if(obs.value_status == "unparseable"),
            count_if(obs.value_status == "invalid"),
            count_if((obs.value_status == "reported") & obs.currency.is_(None)),
            count_if((obs.value_status == "reported") & obs.unit.is_(None)),
            count_if(obs.is_component.is_(True)),
        )
        .where(obs.source_id.in_(visible))
        .group_by(obs.source_id, obs.flow_kind)
        .order_by(obs.source_id, obs.flow_kind)
    ).all()
    flows = [
        FlowCompleteness(
            source_id=s,
            flow_kind=f,
            observations=int(n),
            reported=int(rep or 0),
            not_reported=int(nr or 0),
            unparseable=int(up or 0),
            invalid=int(inv or 0),
            reported_without_currency=int(nocur or 0),
            reported_without_unit=int(nounit or 0),
            component_lines=int(comp or 0),
            meta=MeasureMeta(
                dataset=names.get(s, (s, ""))[0],
                source_id=s,
                unit_of_observation="one published amount (financial observation)",
                measure=f"{f} observations by value status",
                currency=None,
                unit="observations",
                date_meaning=None,
                missing_count=int(nr or 0),
                excluded_count=int(up or 0) + int(inv or 0),
                deduplication_policy="Unique (source, observation key); counts only, no sums.",
            ),
        )
        for s, f, n, rep, nr, up, inv, nocur, nounit, comp in rows
    ]
    return FinancingCompletenessResponse(flows=flows, access=_access(policy))


# ---------------------------------------------------------------------------- GCF timeline
TIMELINE_METRIC = "gcf_api_gcf_funding_by_country_usd"


def gcf_timeline(
    session: Session, policy: AccessPolicy, country: str | None
) -> GcfTimelineResponse:
    if not (policy.allows(API_SOURCE) and policy.allows("gcf_projects")):
        raise SourceRightsNotClearedError("GCF sources may not be served in this mode")
    stmt = (
        select(ProjectEnrichment.approval_date, ProjectEnrichment.project_status)
        .join(Project, Project.id == ProjectEnrichment.project_id)
        .where(ProjectEnrichment.source_id == API_SOURCE, Project.source_id == "gcf_projects")
    )
    if country is not None:
        stmt = stmt.where(
            Project.id.in_(select(ProjectCountry.project_id).where(ProjectCountry.iso3 == country))
        )
    years: dict[int, Counter[str]] = defaultdict(Counter)
    undated = 0
    for approval, status in session.execute(stmt):
        if approval is None:
            undated += 1
            continue
        years[approval.year][status or "not published"] += 1
    funding = metric_trends(session, policy, TIMELINE_METRIC, country, None, None)
    by_year: dict[int, TrendPoint] = {p.year: p for p in funding.points}
    metric = METRICS[TIMELINE_METRIC]
    excluded_total = sum(funding.excluded_outside_rules.values())
    return GcfTimelineResponse(
        country=country,
        points=[
            TimelinePoint(
                year=year,
                projects_approved=sum(years[year].values()),
                by_current_status=dict(years[year]),
                gcf_funding=by_year.get(year),
            )
            for year in sorted(set(years) | set(by_year))
        ],
        projects_without_approval_date=undated,
        projects_meta=MeasureMeta(
            dataset="GCF funded projects export, dated by the GCF API snapshot (matched by code)",
            source_id="gcf_projects + gcf_api_projects",
            unit_of_observation="one GCF funded project (FP/SAP)",
            measure="projects approved per year (current status as published)",
            currency=None,
            unit="projects",
            date_meaning="GCF Board approval date (API ApprovalDate)",
            missing_count=undated,
            excluded_count=0,
            deduplication_policy="One row per GCF reference code (export row); API-only records "
            "are not counted.",
        ),
        funding_meta=MeasureMeta(
            dataset="GCF API snapshot",
            source_id=metric.source_id,
            unit_of_observation="GCF-published per-country financing line",
            measure=metric.label,
            currency="USD",
            unit="USD",
            date_meaning=metric.year_basis,
            missing_count=sum(p.missing_value_records for p in funding.points),
            excluded_count=excluded_total,
            deduplication_policy=metric.deduplication_policy,
        ),
        disclaimers=list(DISCLAIMERS),
        access=_access(policy),
    )


# ------------------------------------------------------------------------- country summaries
AGGREGATE_RULE = (
    "Source-published country-level cumulative figures. They are snapshots, not project rows: "
    "never add them to project-level observations or to each other."
)


def country_aggregates(
    session: Session, policy: AccessPolicy, iso3: str | None
) -> CountryAggregatesResponse:
    if not policy.allows("gcf_countries"):
        raise SourceRightsNotClearedError("gcf_countries may not be served in this mode")
    stmt = select(CountryAggregate).order_by(CountryAggregate.iso3, CountryAggregate.measure)
    if iso3 is not None:
        stmt = stmt.where(CountryAggregate.iso3 == iso3)
    names = _source_names(session)
    return CountryAggregatesResponse(
        items=[
            CountryAggregateOut(
                iso3=a.iso3,
                country_name=a.country_name,
                region=a.region,
                measure=a.measure,
                measure_label=a.measure_label,
                value_kind=a.value_kind,
                amount=a.amount,
                value_status=a.value_status,
                currency=a.currency,
                unit=a.unit,
                snapshot_date=a.snapshot_date,
                meta=MeasureMeta(
                    dataset=names.get(a.source_id, (a.source_id, ""))[0],
                    source_id=a.source_id,
                    unit_of_observation="one country (GCF country summary)",
                    measure=a.measure_label,
                    currency=a.currency,
                    unit=a.unit if a.value_kind == "money" else "count",
                    date_meaning=a.date_meaning,
                    missing_count=0 if a.value_status == "reported" else 1,
                    excluded_count=0,
                    deduplication_policy="Published aggregate; not recomputed or summed.",
                ),
            )
            for a in session.scalars(stmt).all()
        ],
        rule=AGGREGATE_RULE,
        access=_access(policy),
    )


# ---------------------------------------------------------------------- relationship summary
RELATIONSHIP_POLICY = (
    "Links are explicit rows with method, evidence, verification state and review status.",
    "Only stable identifiers or reference codes create links; title similarity never does.",
    "A link never merges records or adds their amounts.",
    "Verification states are categories, not probabilities.",
)


def relationship_summary(session: Session, policy: AccessPolicy) -> RelationshipSummaryResponse:
    visible = sorted(policy.visible_source_ids)
    rows: list[RelationshipSummaryRow] = []
    for t, v, s, a, n in session.execute(
        select(
            ProjectRelationship.relation_type,
            ProjectRelationship.verification_state,
            ProjectRelationship.status,
            ProjectRelationship.asserted_by_source_id,
            func.count(),
        )
        .join(Project, Project.id == ProjectRelationship.from_project_id)
        .where(Project.source_id.in_(visible))
        .group_by(
            ProjectRelationship.relation_type,
            ProjectRelationship.verification_state,
            ProjectRelationship.status,
            ProjectRelationship.asserted_by_source_id,
        )
    ):
        rows.append(
            RelationshipSummaryRow(
                relation_type=t,
                table="project_relationships",
                verification_state=v,
                status=s,
                links=int(n),
                asserted_by_source_id=a,
            )
        )
    for t, v, a, n in session.execute(
        select(
            DocumentLink.relation_type,
            DocumentLink.verification_state,
            DocumentLink.asserted_by_source_id,
            func.count(),
        )
        .where(DocumentLink.asserted_by_source_id.in_(visible))
        .group_by(
            DocumentLink.relation_type,
            DocumentLink.verification_state,
            DocumentLink.asserted_by_source_id,
        )
    ):
        rows.append(
            RelationshipSummaryRow(
                relation_type=t,
                table="document_links",
                verification_state=v,
                status=None,
                links=int(n),
                asserted_by_source_id=a,
            )
        )
    for t, v, s, n in session.execute(
        select(
            ProjectEnrichment.relation_type,
            ProjectEnrichment.verification_state,
            ProjectEnrichment.source_id,
            func.count(),
        )
        .where(ProjectEnrichment.source_id.in_(visible))
        .group_by(
            ProjectEnrichment.relation_type,
            ProjectEnrichment.verification_state,
            ProjectEnrichment.source_id,
        )
    ):
        rows.append(
            RelationshipSummaryRow(
                relation_type=t,
                table="project_enrichments",
                verification_state=v,
                status="same_record_stable_id",
                links=int(n),
                asserted_by_source_id=s,
            )
        )
    for t, v, s, n in session.execute(
        select(
            RecordGroup.member_relation_type,
            RecordGroup.verification_state,
            RecordGroup.source_id,
            func.sum(RecordGroup.member_count),
        )
        .where(RecordGroup.source_id.in_(visible))
        .group_by(
            RecordGroup.member_relation_type, RecordGroup.verification_state, RecordGroup.source_id
        )
    ):
        rows.append(
            RelationshipSummaryRow(
                relation_type=t,
                table="record_groups",
                verification_state=v,
                status="related_not_same",
                links=int(n or 0),
                asserted_by_source_id=s,
            )
        )
    return RelationshipSummaryResponse(
        rows=rows, policy=list(RELATIONSHIP_POLICY), access=_access(policy)
    )
