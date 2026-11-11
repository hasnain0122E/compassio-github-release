"""Project search, filtering, pagination and detail (indexed SQL; never loads the table)."""

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import func, literal_column, or_, select, text
from sqlalchemy.orm import Session, selectinload

from compassio_api.db.models import (
    ClimateAnnotation,
    Project,
    ProjectCountry,
    ProjectRelationship,
    Source,
)
from compassio_api.schemas.data import (
    AccessNotice,
    AnnotationOut,
    CountryOut,
    GroupOut,
    ObservationOut,
    PageMeta,
    ProjectDetail,
    ProjectPage,
    ProjectSummary,
    RelationshipOut,
    SourceRef,
    WarningOut,
)
from compassio_api.services.access import AccessPolicy
from compassio_api.services.discovery import documents_for, enrichments_for
from compassio_api.services.finance import DISCLAIMERS, metric_label
from compassio_api.services.text import escape_like

RIO_SCHEME = "rio_marker_qi_et_al_2026"
MAX_PAGE_SIZE = 100
TRIGRAM_MIN = 3  # FTS5 trigram needs >= 3 characters; shorter queries scan
EXCERPT = 280
GROUP_MEMBERS_SHOWN = 50

SortKey = Literal["id", "-id", "year", "-year", "title", "-title"]
SORT_OPTIONS: tuple[str, ...] = ("id", "-id", "year", "-year", "title", "-title")


class ProjectNotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class ProjectQuery:
    page: int = 1
    page_size: int = 25
    q: str | None = None
    country: str | None = None
    sector: str | None = None
    source: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    climate_related: bool | None = None
    sort: SortKey = "id"

    def applied(self) -> dict[str, Any]:
        keys = ("q", "country", "sector", "source", "year_from", "year_to", "climate_related")
        return {k: getattr(self, k) for k in keys if getattr(self, k) is not None}


def _contains(column: Any, pattern: str, dialect: str) -> Any:
    """Literal, case-insensitive containment. SQLite's LIKE is already ASCII case-insensitive
    (and ``ilike`` would wrap both sides in lower(), defeating the planner); PostgreSQL uses
    ILIKE. The pattern is always a bound parameter."""
    if dialect == "postgresql":
        return column.ilike(pattern, escape="\\")
    return column.like(pattern, escape="\\")


def _conditions(query: ProjectQuery, policy: AccessPolicy, dialect: str) -> list[Any]:
    conds: list[Any] = [Project.source_id.in_(sorted(policy.visible_source_ids))]
    if query.source is not None:
        conds.append(Project.source_id == query.source)
    if query.country is not None:
        conds.append(
            Project.id.in_(
                select(ProjectCountry.project_id).where(ProjectCountry.iso3 == query.country)
            )
        )
    if query.sector is not None:
        conds.append(Project.sector_name == query.sector)
    if query.year_from is not None:
        conds.append(Project.year >= query.year_from)
    if query.year_to is not None:
        conds.append(Project.year <= query.year_to)
    if query.climate_related is not None:
        conds.append(
            Project.id.in_(
                select(ClimateAnnotation.project_id).where(
                    ClimateAnnotation.scheme == RIO_SCHEME,
                    ClimateAnnotation.is_climate_related.is_(query.climate_related),
                    ClimateAnnotation.annotation_source_id.in_(sorted(policy.visible_source_ids)),
                )
            )
        )
    if query.q:
        text_query = query.q.strip()
        if dialect == "sqlite" and len(text_query) >= TRIGRAM_MIN:
            # Index pre-filter only (FTS5 trigram = case-insensitive substring candidates).
            # The literal LIKE below still decides every match, so results are unchanged.
            phrase = '"' + text_query.replace('"', '""') + '"'
            conds.append(
                literal_column("projects.rowid").in_(
                    text("SELECT rowid FROM projects_fts WHERE projects_fts MATCH :fts").bindparams(
                        fts=phrase
                    )
                )
            )
        pattern = f"%{escape_like(text_query)}%"
        conds.append(
            or_(
                _contains(Project.title, pattern, dialect),
                _contains(Project.description, pattern, dialect),
            )
        )
    return conds


def _order(sort: SortKey) -> list[Any]:
    column = {"id": Project.id, "year": Project.year, "title": Project.title}[sort.lstrip("-")]
    primary = column.desc() if sort.startswith("-") else column.asc()
    if column is not Project.id:
        primary = primary.nulls_last()
    return [primary, Project.id.asc()]  # id = deterministic tie-breaker


def _annotations(project: Project, policy: AccessPolicy) -> list[AnnotationOut]:
    return [
        AnnotationOut(
            scheme=a.scheme,
            kind="research_annotation"
            if a.kind == "research_annotation"
            else "source_classification",
            annotation_source_id=a.annotation_source_id,
            is_model_prediction=False,
            overall=a.overall,
            mitigation=a.mitigation,
            adaptation=a.adaptation,
            is_climate_related=a.is_climate_related,
            label=a.label,
            raw_value=a.raw_value,
            provenance=a.provenance,
        )
        for a in project.annotations
        if policy.allows(a.annotation_source_id)
    ]


def _countries(project: Project) -> list[CountryOut]:
    return [
        CountryOut(country_name=c.country_name, iso3=c.iso3, mapping_method=c.mapping_method)
        for c in project.countries
    ]


def _excerpt(text: str | None) -> str | None:
    if text is None or len(text) <= EXCERPT:
        return text
    return text[:EXCERPT].rstrip() + "…"


def list_projects(session: Session, policy: AccessPolicy, query: ProjectQuery) -> ProjectPage:
    conds = _conditions(query, policy, session.get_bind().dialect.name)
    # Deferred join: page over ids only (cheap), with the total from the same scan; then load
    # the page's rows and their children in two batched queries (no N+1).
    page_ids = session.execute(
        select(Project.id, func.count().over())
        .where(*conds)
        .order_by(*_order(query.sort))
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    if page_ids:
        total = int(page_ids[0][1])
    else:
        total = int(session.scalar(select(func.count(Project.id)).where(*conds)) or 0)
    ids = [row[0] for row in page_ids]
    loaded = {
        p.id: p
        for p in session.scalars(
            select(Project)
            .where(Project.id.in_(ids))
            .options(selectinload(Project.countries), selectinload(Project.annotations))
        )
    }
    rows = [loaded[i] for i in ids]
    items = [
        ProjectSummary(
            id=p.id,
            source_id=p.source_id,
            source_project_id=p.source_project_id,
            record_level=p.record_level,
            title=p.title,
            description_excerpt=_excerpt(p.description),
            countries=_countries(p),
            multi_country=p.multi_country,
            region=p.region,
            sector_name=p.sector_name,
            year=p.year,
            year_type=p.year_type,
            status=p.status,
            climate_annotations=_annotations(p, policy),
        )
        for p in rows
    ]
    total_pages = (total + query.page_size - 1) // query.page_size
    empty: str | None = None
    if total == 0:
        empty = "No project records match these filters."
    elif not items:
        empty = f"Page {query.page} is beyond the last page ({total_pages})."
    return ProjectPage(
        items=items,
        pagination=PageMeta(
            page=query.page, page_size=query.page_size, total_items=total, total_pages=total_pages
        ),
        applied_filters=query.applied(),
        sort=query.sort,
        access=AccessNotice(mode=policy.mode, notice=policy.notice),
        empty_result_message=empty,
    )


def get_project(session: Session, policy: AccessPolicy, project_id: str) -> ProjectDetail:
    project = session.scalar(
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.countries),
            selectinload(Project.annotations),
            selectinload(Project.observations),
            selectinload(Project.warnings),
        )
    )
    # A project from a source that may not be served is indistinguishable from a missing one.
    if project is None or not policy.allows(project.source_id):
        raise ProjectNotFoundError(project_id)
    source = session.get_one(Source, project.source_id)
    return ProjectDetail(
        id=project.id,
        source=SourceRef(
            source_id=source.source_id,
            name=source.name,
            publisher=source.publisher,
            rights_status=source.rights_status,
            reference_url=source.reference_url,
        ),
        source_project_id=project.source_project_id,
        record_level=project.record_level,
        title=project.title,
        description=project.description,
        recipient_label=project.recipient_label,
        countries=_countries(project),
        multi_country=project.multi_country,
        region=project.region,
        sector_name=project.sector_name,
        sector_code=project.sector_code,
        sector_vocabulary=project.sector_vocabulary,
        year=project.year,
        year_type=project.year_type,
        date_value=project.date_value,
        date_precision=project.date_precision,
        date_estimated=project.date_estimated,
        status=project.status,
        source_reference=project.source_reference,
        attributes=project.attributes,
        climate_annotations=_annotations(project, policy),
        financial_observations=[
            ObservationOut(
                observation_key=o.observation_key,
                flow_kind=o.flow_kind,
                metric_label=metric_label(o.flow_kind, o.level, o.is_component),
                level=o.level,
                financing_type=o.financing_type,
                is_component=o.is_component,
                amount=o.amount,
                raw_value=o.raw_value,
                value_status=o.value_status,  # type: ignore[arg-type]
                unit=o.unit,
                currency=o.currency,
                unit_status=o.unit_status,
                price_basis=o.price_basis,
                effective_date=o.effective_date,
                effective_year=o.effective_year,
                date_meaning=o.date_meaning,
                multi_country=o.multi_country,
                estimated=o.estimated,
                recommended_for_aggregates=o.recommended_for_aggregates,
                source_reference=o.source_reference,
            )
            for o in project.observations
            if policy.allows(o.source_id)  # e.g. API lines on an export row
        ],
        data_quality_warnings=[
            WarningOut(code=w.code, field=w.field, message=w.message) for w in project.warnings
        ],
        group=_group(session, policy, project),
        relationships=_relationships(session, policy, project.id),
        disclaimers=list(DISCLAIMERS),
        access=AccessNotice(mode=policy.mode, notice=policy.notice),
        enrichments=enrichments_for(session, policy, project.id),
        documents=documents_for(session, policy, project.id),
    )


def _group(session: Session, policy: AccessPolicy, project: Project) -> GroupOut | None:
    if project.group_key is None:
        return None
    members = select(Project.id).where(
        Project.group_key == project.group_key,
        Project.source_id.in_(sorted(policy.visible_source_ids)),
    )
    count = int(session.scalar(select(func.count()).select_from(members.subquery())) or 0)
    ids = session.scalars(members.order_by(Project.id).limit(GROUP_MEMBERS_SHOWN)).all()
    return GroupOut(
        group_key=project.group_key,
        meaning=project.group_meaning,
        member_count=count,
        member_ids=list(ids),
    )


def _relationships(
    session: Session, policy: AccessPolicy, project_id: str
) -> list[RelationshipOut]:
    out: list[RelationshipOut] = []
    for direction, mine, other in (
        ("outgoing", ProjectRelationship.from_project_id, ProjectRelationship.to_project_id),
        ("incoming", ProjectRelationship.to_project_id, ProjectRelationship.from_project_id),
    ):
        rows = session.execute(
            select(ProjectRelationship, Project.source_id, Project.title)
            .join(Project, Project.id == other)
            .where(mine == project_id)
            .order_by(other)
        ).all()
        for rel, other_source, other_title in rows:
            if not policy.allows(other_source):
                continue
            out.append(
                RelationshipOut(
                    direction="outgoing" if direction == "outgoing" else "incoming",
                    other_project_id=rel.to_project_id
                    if direction == "outgoing"
                    else rel.from_project_id,
                    other_source_id=other_source,
                    other_title=other_title,
                    relation_type=rel.relation_type,
                    status=rel.status,
                    method=rel.method,
                    evidence=rel.evidence,
                    human_reviewed=rel.human_reviewed,
                )
            )
    return out
