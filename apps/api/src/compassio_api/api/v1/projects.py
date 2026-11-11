"""Project discovery: search, filter, paginate, detail. Local development only (rights)."""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from compassio_api.api.deps import DataPolicyDep, SessionDep
from compassio_api.api.errors import InvalidQueryError, error_responses
from compassio_api.schemas.data import ProjectDetail, ProjectPage
from compassio_api.services.projects import (
    MAX_PAGE_SIZE,
    ProjectQuery,
    SortKey,
    get_project,
    list_projects,
)

router = APIRouter(prefix="/projects", tags=["projects"])

YearParam = Annotated[int | None, Query(ge=1900, le=2100)]


@router.get(
    "",
    response_model=ProjectPage,
    summary="Search and filter project records (paginated)",
    responses=error_responses(403, 422, 503),
)
def search_projects(
    session: SessionDep,
    policy: DataPolicyDep,
    page: Annotated[int, Query(ge=1, le=100_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 25,
    q: Annotated[
        str | None,
        Query(min_length=1, max_length=200, description="Case-insensitive literal text search"),
    ] = None,
    country: Annotated[str | None, Query(pattern=r"^[A-Z]{3}$", description="ISO3")] = None,
    sector: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    source: Annotated[str | None, Query(pattern=r"^[a-z0-9_]{1,80}$")] = None,
    year_from: YearParam = None,
    year_to: YearParam = None,
    climate_related: Annotated[
        bool | None,
        Query(description="Filter on the research Rio-marker annotation (AidData records only)"),
    ] = None,
    sort: SortKey = "id",
) -> ProjectPage:
    if year_from is not None and year_to is not None and year_from > year_to:
        raise InvalidQueryError("invalid_year_range", "year_from must be <= year_to")
    query = ProjectQuery(
        page=page,
        page_size=page_size,
        q=q.strip() if q and q.strip() else None,
        country=country,
        sector=sector,
        source=source,
        year_from=year_from,
        year_to=year_to,
        climate_related=climate_related,
        sort=sort,
    )
    return list_projects(session, policy, query)


@router.get(
    "/{project_id}",
    response_model=ProjectDetail,
    summary="One project record with source, annotations, finance, warnings and links",
    responses=error_responses(403, 404, 503),
)
def project_detail(
    session: SessionDep,
    policy: DataPolicyDep,
    project_id: Annotated[str, Path(min_length=3, max_length=240)],
) -> ProjectDetail:
    return get_project(session, policy, project_id)
