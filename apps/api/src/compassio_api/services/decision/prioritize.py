"""Transparent, rule-based prioritization for further due diligence (compassio-priority-1.0.0).

Each component is computed from the same ``ProjectEvidence`` the API returns, so every score is
traceable to displayed fields. Arithmetic is exact ``Decimal``; ties break by project id.
A high rank means "worth reviewing under the chosen criteria" -- never financially attractive,
eligible for new funding or environmentally effective.
"""

import hashlib
import json
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from compassio_api.db.models import Project
from compassio_api.schemas.data import AccessNotice, PageMeta
from compassio_api.schemas.decision import (
    FinancialFact,
    PrioritizeRequest,
    PrioritizeResponse,
    PriorityItem,
    PriorityWeights,
    ProjectEvidence,
    RelevanceDistinction,
    ScoreComponent,
)
from compassio_api.services.access import AccessPolicy
from compassio_api.services.cache import cached, data_version
from compassio_api.services.decision.errors import DecisionInputError
from compassio_api.services.decision.evidence import build_evidence, load_projects
from compassio_api.services.decision.methodology import DECISION_DISCLAIMERS, PRIORITY_VERSION
from compassio_api.services.projects import ProjectQuery, _conditions

MAX_CANDIDATES = 2_000
CHUNK = 500
FOUR_DP = Decimal("0.0001")
UNCERTAINTY_CODES = frozenset(
    {
        "commitment_date_estimated",
        "amount_estimated",
        "not_recommended_for_aggregates",
        "country_not_attributable",
        "retrospective_description",
        "currency_and_unit_not_stated",
    }
)
INTERPRETATION = (
    "Ranked for further due diligence under the selected criteria only. A high rank is not a "
    "statement of financial attractiveness, eligibility for new funding or environmental "
    "effectiveness."
)


def _component(
    criterion: str, weight: Decimal, value: Decimal | None, evidence: str, requested: bool = True
) -> ScoreComponent:
    if not requested:
        return ScoreComponent(
            criterion=criterion,
            weight=weight,
            value=None,
            status="not_requested",
            contribution=Decimal(0),
            evidence=evidence,
        )
    if value is None:
        return ScoreComponent(
            criterion=criterion,
            weight=weight,
            value=None,
            status="not_available",
            contribution=Decimal(0),
            evidence=evidence,
        )
    return ScoreComponent(
        criterion=criterion,
        weight=weight,
        value=value,
        status="applied",
        contribution=(weight * value).quantize(FOUR_DP),
        evidence=evidence,
    )


def components(
    ev: ProjectEvidence,
    weights: PriorityWeights,
    sectors_of_interest: list[str],
    countries_of_interest: list[str],
) -> list[ScoreComponent]:
    out: list[ScoreComponent] = []
    cr = ev.climate_relevance
    climate = {
        "research_annotation_climate_related": Decimal(1),
        "listed_by_climate_fund": Decimal(1),
        "research_annotation_not_climate_related": Decimal(0),
    }.get(cr.status)
    out.append(
        _component(
            "climate_relevance",
            weights.climate_relevance,
            climate,
            f"{cr.status}: {cr.basis} (label, not impact)",
        )
    )

    c = ev.completeness
    fields = {
        "description": c.has_description,
        "sector": c.has_sector,
        "year": c.has_year,
        "mapped country": c.has_mapped_country,
        "source status": c.has_source_status,
        "institution": c.has_institution,
    }
    present = [k for k, v in fields.items() if v]
    out.append(
        _component(
            "evidence_completeness",
            weights.evidence_completeness,
            (Decimal(len(present)) / Decimal(len(fields))).quantize(FOUR_DP),
            f"{len(present)}/{len(fields)} present"
            + (
                f"; missing: {', '.join(k for k, v in fields.items() if not v)}"
                if len(present) < len(fields)
                else ""
            ),
        )
    )

    funding = [f for f in ev.headline_facts if f.is_funding_flow and f.amount is not None]
    complete = [f for f in funding if f.currency and (f.year is not None or f.first_year)]
    if complete:
        value, why = (
            Decimal(1),
            f"{complete[0].meaning_label}: {complete[0].amount} "
            f"{complete[0].unit} {complete[0].currency}",
        )
    elif funding:
        value, why = Decimal("0.5"), f"{funding[0].meaning_label}: amount without currency/date"
    else:
        value, why = Decimal(0), "no reported funding amount (repayments ignored)"
    out.append(_component("funding_completeness", weights.funding_completeness, value, why))

    if sectors_of_interest:
        sector = ev.sector.name if ev.sector else None
        terms = [t.casefold() for t in sectors_of_interest]
        if sector is None:
            out.append(
                _component(
                    "sector_match", weights.sector_match, None, "no sector stated by the source"
                )
            )
        else:
            hit = next((t for t in terms if t in sector.casefold()), None)
            out.append(
                _component(
                    "sector_match",
                    weights.sector_match,
                    Decimal(1 if hit else 0),
                    f"sector '{sector}'"
                    + (f" contains '{hit}'" if hit else " matches no requested term"),
                )
            )
    else:
        out.append(
            _component(
                "sector_match", weights.sector_match, None, "no sector requested", requested=False
            )
        )

    if countries_of_interest:
        isos = {x.iso3 for x in ev.countries if x.iso3}
        wanted = set(countries_of_interest)
        if not isos:
            out.append(
                _component("country_match", weights.country_match, None, "no mapped country")
            )
        elif isos & wanted and not ev.multi_country:
            out.append(
                _component(
                    "country_match",
                    weights.country_match,
                    Decimal(1),
                    f"single-country record in {sorted(isos & wanted)[0]}",
                )
            )
        elif isos & wanted:
            out.append(
                _component(
                    "country_match",
                    weights.country_match,
                    Decimal("0.5"),
                    "multi-country record including "
                    f"{', '.join(sorted(isos & wanted))} (no country share)",
                )
            )
        else:
            out.append(
                _component(
                    "country_match",
                    weights.country_match,
                    Decimal(0),
                    f"countries {', '.join(sorted(isos))} not requested",
                )
            )
    else:
        out.append(
            _component(
                "country_match",
                weights.country_match,
                None,
                "no country requested",
                requested=False,
            )
        )

    deterministic = [
        d for d in ev.documents if d.verification_state == "deterministic_identifier_match"
    ]
    if deterministic or (c.has_documents and not ev.documents):
        doc_value, doc_why = (
            Decimal(1),
            (
                f"{len(deterministic)} deterministic document link(s)"
                if deterministic
                else "IATI document links listed by the source"
            ),
        )
    elif ev.documents:
        doc_value, doc_why = Decimal("0.5"), f"{len(ev.documents)} candidate link(s) need review"
    else:
        doc_value, doc_why = Decimal(0), "no linked documents"
    out.append(_component("documentation", weights.documentation, doc_value, doc_why))

    codes = sorted({w.code for w in ev.data_quality_warnings} & UNCERTAINTY_CODES)
    out.append(
        _component(
            "review_uncertainty",
            weights.review_uncertainty,
            min(Decimal(1), (Decimal(len(codes)) / Decimal(3))).quantize(FOUR_DP),
            f"uncertainty warnings: {', '.join(codes) if codes else 'none'}",
        )
    )
    return out


def score(comps: list[ScoreComponent], policy_missing: str) -> tuple[Decimal, Decimal]:
    total_w = Decimal(0)
    total_c = Decimal(0)
    for comp in comps:
        if comp.status == "applied" or (
            comp.status == "not_available" and policy_missing == "score_zero"
        ):
            total_w += comp.weight
            total_c += comp.contribution
    if total_w == 0:
        return Decimal(0).quantize(FOUR_DP), total_w
    return (total_c / total_w).quantize(FOUR_DP, rounding=ROUND_HALF_EVEN), total_w


def _candidate_ids(session: Session, policy: AccessPolicy, req: PrioritizeRequest) -> list[str]:
    f = req.filters
    if f.year_from is not None and f.year_to is not None and f.year_from > f.year_to:
        raise DecisionInputError("invalid_year_range", "year_from must be <= year_to")
    if f.project_ids:
        if len(set(f.project_ids)) != len(f.project_ids):
            raise DecisionInputError("duplicate_project_ids", "filters.project_ids must be unique")
        return sorted(p.id for p in load_projects(session, policy, f.project_ids))
    if f.source is not None and not policy.allows(f.source):
        raise DecisionInputError(
            "unknown_or_restricted_source",
            f"source '{f.source}' is not available in this access mode",
        )
    query = ProjectQuery(
        q=f.q,
        country=f.country,
        sector=f.sector,
        source=f.source,
        year_from=f.year_from,
        year_to=f.year_to,
    )
    dialect = session.get_bind().dialect.name
    conds = _conditions(query, policy, dialect)
    count = int(session.scalar(select(func.count()).select_from(Project).where(*conds)) or 0)
    if count > MAX_CANDIDATES:
        raise DecisionInputError(
            "candidate_set_too_large",
            f"{count} records match; narrow the filters to at most {MAX_CANDIDATES} "
            "(e.g. country, source, sector, years or a search term).",
        )
    return list(session.scalars(select(Project.id).where(*conds).order_by(Project.id)))


def _canonical(req: PrioritizeRequest) -> dict[str, Any]:
    data: dict[str, Any] = req.model_dump(mode="json", exclude={"page", "page_size"})
    return data


def _funding_basis(funding: list[FinancialFact]) -> str:
    if not funding:
        return "No reported funding amount in the stored sources."
    f = funding[0]
    currency = f.currency or "(currency not stated)"
    return f"{f.financial_meaning} {f.amount} {f.unit or ''} {currency} from {f.source_id}"


def _ranked(session: Session, policy: AccessPolicy, req: PrioritizeRequest) -> list[PriorityItem]:
    ids = _candidate_ids(session, policy, req)
    applied = {k: v for k, v in req.filters.model_dump(exclude_none=True).items()}
    items: list[PriorityItem] = []
    for start in range(0, len(ids), CHUNK):
        chunk = ids[start : start + CHUNK]
        for ev in build_evidence(session, policy, load_projects(session, policy, chunk)):
            comps = components(ev, req.weights, req.sectors_of_interest, req.countries_of_interest)
            value, weight_total = score(comps, req.missing_component_policy)
            funding = [f for f in ev.headline_facts if f.is_funding_flow and f.amount is not None]
            items.append(
                PriorityItem(
                    rank=0,
                    project_id=ev.project_id,
                    title=ev.title,
                    source_id=ev.source.source_id,
                    score=value,
                    components=comps,
                    applied_weight_total=weight_total,
                    distinctions=RelevanceDistinction(
                        matched_filters=applied,
                        has_documented_historical_funding=bool(funding),
                        documented_funding_basis=_funding_basis(funding),
                    ),
                    interpretation=INTERPRETATION,
                )
            )
    items.sort(key=lambda i: (-i.score, i.project_id))
    return [i.model_copy(update={"rank": n}) for n, i in enumerate(items, start=1)]


def prioritize(
    session: Session, policy: AccessPolicy, req: PrioritizeRequest
) -> PrioritizeResponse:
    if sum(req.weights.model_dump().values()) == 0:
        raise DecisionInputError("no_criteria_weighted", "At least one weight must be above 0.")
    canonical = _canonical(req)
    version = list(data_version(session))
    key = (
        "prioritize",
        json.dumps(canonical, sort_keys=True),
        policy.mode,
        tuple(sorted(policy.visible_source_ids)),
    )
    ranked = cached(session, key, lambda: _ranked(session, policy, req))
    fingerprint = hashlib.sha256(
        json.dumps(
            {"methodology": PRIORITY_VERSION, "request": canonical, "data_version": version},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    start = (req.page - 1) * req.page_size
    total = len(ranked)
    return PrioritizeResponse(
        items=ranked[start : start + req.page_size],
        pagination=PageMeta(
            page=req.page,
            page_size=req.page_size,
            total_items=total,
            total_pages=max(1, -(-total // req.page_size)),
        ),
        candidates=total,
        methodology_version=PRIORITY_VERSION,
        ranking_fingerprint=fingerprint,
        data_version=version,
        disclaimers=list(DECISION_DISCLAIMERS),
        access=AccessNotice(mode=policy.mode, notice=policy.notice),
    )
