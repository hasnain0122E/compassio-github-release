"""Per-project decision evidence: labelled financial facts, provenance, quality, completeness.

Facts are the stored observations, labelled with what they mean financially. The only derived
figures are per-flow sums of one project's *transaction-level* rows (ADB / GCF disbursements),
computed with ``services.finance.safe_total`` (i.e. ``compassio_ml.finance.aggregate``) and
marked ``derived_sum_of_source_transactions``. Components are never added to stated totals.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from compassio_api.db.models import (
    ClimateAnnotation,
    Document,
    DocumentLink,
    FinancialObservation,
    Project,
    ProjectEnrichment,
    ProjectRelationship,
    Source,
)
from compassio_api.schemas.data import AnnotationOut, WarningOut
from compassio_api.schemas.decision import (
    ClimateRelevance,
    Completeness,
    CountryAttribution,
    CountryRef,
    DocumentRef,
    FinancialFact,
    FinancialMeaning,
    InstitutionRef,
    LinkedRecord,
    ProjectEvidence,
    SectorRef,
    SourceInfo,
    VerifiedApproval,
)
from compassio_api.services.access import AccessPolicy
from compassio_api.services.finance import metric_label
from compassio_api.services.finance_rows import SafeTotal, safe_total
from compassio_api.services.projects import RIO_SCHEME, ProjectNotFoundError
from compassio_ml.finance import AmountLevel, AmountUnit, FlowKind, MonetaryAmount, PriceBasis

MEANINGS: dict[str, tuple[FinancialMeaning, bool, str]] = {
    "commitment": ("historical_commitment", True, "Historical commitment (not a disbursement)"),
    "pledge": (
        "pledge_not_commitment",
        False,
        "Pledge: a promise, not a commitment or funding provided",
    ),
    "approval": ("approval", True, "Approved funding (not necessarily disbursed)"),
    "gcf_financing": ("approval", True, "GCF financing approved (excludes co-financing)"),
    "disbursement": ("disbursement", True, "Disbursed funds as published"),
    "repayment_principal": (
        "repayment_not_funding",
        False,
        "Principal repaid to the lender; NOT funding",
    ),
    "repayment_interest": (
        "repayment_not_funding",
        False,
        "Interest paid to the lender; NOT funding",
    ),
    "co_financing": ("co_financing", True, "Co-financing from other financiers (not GCF money)"),
    "total_project_cost": (
        "total_project_cost",
        False,
        "Total project cost as published (not a funding flow)",
    ),
    "readiness_grant": ("readiness_grant", True, "GCF readiness grant (capacity support)"),
    "deposit": ("deposit_into_fund", True, "Deposit into a fund (not project funding)"),
}
INSTITUTION_FIELDS: dict[str, tuple[tuple[str, str], ...]] = {
    "aiddata": (("funding_agencies", "funding agency (as stated by AidData)"),),
    "climate_funds_update": (
        ("fund", "climate fund (funder)"),
        ("implementing_agency", "implementing agency"),
        ("recipient_institution", "recipient institution"),
    ),
    "gcf_projects": (("accredited_entity", "GCF accredited entity (implementer, not funder)"),),
    "gcf_readiness": (("delivery_partner", "readiness delivery partner (not funder)"),),
}
PUBLISHER_IS_FUNDER = {
    "adb_pakistan": "lender / financier (publisher of the record)",
    "gcf_projects": "fund (publisher of the record)",
    "gcf_readiness": "fund (publisher of the record)",
}
CLIMATE_FUND_SOURCES = frozenset({"climate_funds_update", "gcf_projects", "gcf_readiness"})
CLOSED_STATUSES = frozenset(
    {"completion", "completed", "closed", "cancelled", "discontinued", "finalisation", "disbursed"}
)


def flow_meaning(flow_kind: str) -> tuple[FinancialMeaning, bool, str]:
    return MEANINGS.get(flow_kind, ("historical_commitment", True, flow_kind))


def _attribution(project: Project, obs: FinancialObservation | None) -> CountryAttribution:
    if obs is not None and obs.financing_type == "country_breakdown":
        return "source_published_country_line"
    if project.multi_country or (obs is not None and obs.multi_country):
        return "whole_project_value_not_attributable_to_one_country"
    if any(c.iso3 for c in project.countries):
        return "single_country_project"
    return "no_mapped_country"


def _scale(unit: str | None) -> Any:
    return AmountUnit(unit).scale if unit in ("units", "thousands", "millions") else None


def _key(o: FinancialObservation, selection: str) -> str:
    currency = o.currency or "currency_not_stated"
    return f"{o.source_id}|{o.flow_kind}|{o.level}|{currency}|{o.price_basis}|{selection}"


def _fact(project: Project, o: FinancialObservation, selection: str) -> FinancialFact:
    meaning, is_funding, label = flow_meaning(o.flow_kind)
    scale = _scale(o.unit)
    return FinancialFact(
        fact_id=o.observation_key,
        fact_type="source_reported",
        source_id=o.source_id,
        flow_kind=o.flow_kind,
        financial_meaning=meaning,
        is_funding_flow=is_funding,
        meaning_label=f"{label} - {metric_label(o.flow_kind, o.level, o.is_component)}",
        level=o.level,
        financing_type=o.financing_type,
        is_component=o.is_component,
        amount=o.amount,
        amount_in_units=None if o.amount is None or scale is None else o.amount * scale,
        unit=o.unit,
        currency=o.currency,
        price_basis=o.price_basis,
        value_status=o.value_status,
        date=o.effective_date,
        year=o.effective_year,
        date_meaning=o.date_meaning,
        multi_country=o.multi_country or project.multi_country,
        country_iso3=o.country_iso3,
        country_attribution=_attribution(project, o),
        estimated=o.estimated,
        recommended_for_aggregates=o.recommended_for_aggregates,
        comparability_key=_key(o, selection),
        source_reference=o.source_reference,
    )


def _derived(project: Project, rows: list[FinancialObservation]) -> FinancialFact:
    """Sum of one project's transaction rows for one flow/currency/basis (via aggregate)."""
    first = rows[0]
    meaning, is_funding, label = flow_meaning(first.flow_kind)
    years = [r.effective_year for r in rows if r.effective_year is not None]
    total: SafeTotal
    if first.currency is None or first.unit is None:
        total = SafeTotal(None, 0, len(rows), 0, "currency or unit not stated")
    else:
        total = safe_total(
            [
                MonetaryAmount(
                    source_id=r.source_id,
                    source_record_id=r.observation_key,
                    flow_kind=FlowKind(r.flow_kind),
                    level=AmountLevel.TRANSACTION,
                    value=r.amount if r.value_status == "reported" else None,
                    unit=AmountUnit(r.unit or "units"),
                    currency=r.currency,
                    price_basis=PriceBasis(r.price_basis),
                    date_meaning=r.date_meaning,
                    multi_country=False,  # one project's own transactions, not a country split
                    estimated=r.estimated,
                )
                for r in rows
            ]
        )
    return FinancialFact(
        fact_id=f"derived:{first.source_id}:{first.flow_kind}:{first.currency}:{project.id}",
        fact_type="derived_sum_of_source_transactions",
        source_id=first.source_id,
        flow_kind=first.flow_kind,
        financial_meaning=meaning,
        is_funding_flow=is_funding,
        meaning_label=f"{label} - sum of {len(rows)} published transactions for this record",
        level="transaction",
        financing_type=None,
        is_component=False,
        amount=total.total,
        amount_in_units=total.total,
        unit="units" if total.total is not None else first.unit,
        currency=first.currency,
        price_basis=first.price_basis,
        value_status="reported" if total.total is not None else "not_reported",
        date=None,
        year=None,
        date_meaning=f"{first.date_meaning}; spans {min(years, default=None)}-"
        f"{max(years, default=None)}",
        multi_country=project.multi_country,
        country_iso3=None,
        country_attribution=_attribution(project, None),
        estimated=None,
        recommended_for_aggregates=None,
        transactions_summed=total.summed_records,
        first_year=min(years, default=None),
        last_year=max(years, default=None),
        comparability_key=_key(first, "derived_transaction_sum"),
        source_reference=f"{len(rows)} transactions; e.g. {first.source_reference}",
    )


def financial_facts(
    project: Project, policy: AccessPolicy
) -> tuple[list[FinancialFact], list[FinancialFact]]:
    """(headline facts, breakdown facts) from the observations of visible sources."""
    headline: list[FinancialFact] = []
    breakdown: list[FinancialFact] = []
    transactions: dict[tuple[str, str, str | None, str], list[FinancialObservation]] = defaultdict(
        list
    )
    for o in sorted(project.observations, key=lambda x: x.observation_key):
        if not policy.allows(o.source_id):
            continue
        if o.is_component:
            selection = (
                f"country_line:{o.country_iso3}"
                if o.financing_type == "country_breakdown"
                else f"component:{o.financing_type}"
            )
            breakdown.append(_fact(project, o, selection))
        elif o.level == "transaction":
            transactions[(o.source_id, o.flow_kind, o.currency, o.price_basis)].append(o)
        else:
            headline.append(_fact(project, o, "stated_total"))
    for key in sorted(transactions, key=lambda k: tuple(str(x) for x in k)):
        headline.append(_derived(project, transactions[key]))
    return headline, breakdown


def load_projects(session: Session, policy: AccessPolicy, ids: Sequence[str]) -> list[Project]:
    """Projects in request order; any missing or non-visible id -> ProjectNotFoundError."""
    rows = session.scalars(
        select(Project)
        .where(Project.id.in_(list(ids)))
        .options(
            selectinload(Project.countries),
            selectinload(Project.annotations),
            selectinload(Project.observations),
            selectinload(Project.warnings),
        )
    ).all()
    by_id = {p.id: p for p in rows if policy.allows(p.source_id)}
    for pid in ids:
        if pid not in by_id:
            raise ProjectNotFoundError(pid)
    return [by_id[pid] for pid in ids]


def _annotation_out(a: ClimateAnnotation) -> AnnotationOut:
    return AnnotationOut(
        scheme=a.scheme,
        kind="research_annotation" if a.kind == "research_annotation" else "source_classification",
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


def climate_relevance(project: Project, policy: AccessPolicy) -> ClimateRelevance:
    visible = [a for a in project.annotations if policy.allows(a.annotation_source_id)]
    outs = [_annotation_out(a) for a in visible]
    rio = [a for a in visible if a.scheme == RIO_SCHEME and a.is_climate_related is not None]
    if rio:
        related = bool(rio[0].is_climate_related)
        return ClimateRelevance(
            status="research_annotation_climate_related"
            if related
            else "research_annotation_not_climate_related",
            basis=f"Qi et al. 2026 Rio-marker research annotation ({rio[0].label or 'label'})",
            annotations=outs,
        )
    if project.source_id in CLIMATE_FUND_SOURCES:
        theme = next((a.label or a.raw_value for a in visible), None)
        return ClimateRelevance(
            status="listed_by_climate_fund",
            basis=f"Record published by a dedicated climate fund ({project.source_id}); "
            f"source classification: {theme or 'none'}",
            annotations=outs,
        )
    return ClimateRelevance(
        status="no_climate_annotation",
        basis="No research annotation or climate-fund classification is stored",
        annotations=outs,
    )


def institutions(project: Project, source: Source) -> list[InstitutionRef]:
    out: list[InstitutionRef] = []
    if project.source_id in PUBLISHER_IS_FUNDER:
        out.append(
            InstitutionRef(role=PUBLISHER_IS_FUNDER[project.source_id], name=source.publisher)
        )
    attrs = project.attributes or {}
    for field, role in INSTITUTION_FIELDS.get(project.source_id, ()):
        value = attrs.get(field)
        if isinstance(value, str) and value.strip():
            out.append(InstitutionRef(role=role, name=value.strip()))
    return out


class _Batch:
    """Side tables for many projects, loaded once per request."""

    def __init__(self, session: Session, policy: AccessPolicy, ids: list[str]) -> None:
        visible = sorted(policy.visible_source_ids)
        self.sources = {s.source_id: s for s in session.scalars(select(Source))}
        self.approvals: dict[str, VerifiedApproval] = {}
        for e in session.scalars(
            select(ProjectEnrichment)
            .where(ProjectEnrichment.project_id.in_(ids), ProjectEnrichment.source_id.in_(visible))
            .order_by(ProjectEnrichment.project_id, ProjectEnrichment.snapshot_id.desc())
        ):
            if e.project_id in self.approvals or e.approval_date is None:
                continue
            self.approvals[e.project_id] = VerifiedApproval(
                approval_status=e.approval_status,
                approval_date=e.approval_date,
                approval_date_type=e.approval_date_type,
                project_status=e.project_status,
                status_as_of=e.status_as_of,
                verified_by_source_id=e.source_id,
                verification_state=e.verification_state,
                official_url=e.official_url,
            )
        self.links: dict[str, list[LinkedRecord]] = defaultdict(list)
        rels = session.scalars(
            select(ProjectRelationship).where(
                or_(
                    ProjectRelationship.from_project_id.in_(ids),
                    ProjectRelationship.to_project_id.in_(ids),
                )
            )
        ).all()
        others = {r.to_project_id for r in rels} | {r.from_project_id for r in rels}
        meta = {
            p.id: p
            for p in session.execute(
                select(Project.id, Project.source_id, Project.title).where(
                    Project.id.in_(sorted(others))
                )
            )
        }
        for r in sorted(rels, key=lambda x: x.id):
            for mine, other in (
                (r.from_project_id, r.to_project_id),
                (r.to_project_id, r.from_project_id),
            ):
                if mine not in ids or other not in meta or not policy.allows(meta[other].source_id):
                    continue
                self.links[mine].append(
                    LinkedRecord(
                        project_id=other,
                        source_id=meta[other].source_id,
                        title=meta[other].title,
                        relation_type=r.relation_type,
                        status=r.status,
                        verification_state=r.verification_state,
                        human_reviewed=r.human_reviewed,
                        double_counting_rule="Probably the same real-world project in another "
                        "source: compare side by side, never add their amounts.",
                    )
                )
        self.documents: dict[str, list[DocumentRef]] = defaultdict(list)
        for link, doc in session.execute(
            select(DocumentLink, Document)
            .join(Document, Document.id == DocumentLink.document_id)
            .where(DocumentLink.project_id.in_(ids), Document.source_id.in_(visible))
            .order_by(DocumentLink.project_id, Document.id)
        ):
            self.documents[link.project_id].append(
                DocumentRef(
                    document_id=doc.id,
                    title=doc.title,
                    document_type=doc.document_type,
                    verification_state=link.verification_state,
                    catalogue_url=doc.catalogue_url,
                )
            )


def _completeness(
    project: Project,
    headline: list[FinancialFact],
    insts: list[InstitutionRef],
    docs: list[DocumentRef],
    approval: VerifiedApproval | None,
) -> Completeness:
    funding = [f for f in headline if f.is_funding_flow]
    reported = [f for f in funding if f.amount is not None]
    iati_docs = int((project.attributes or {}).get("document_links") or 0)
    flags = {
        "has_description": bool(project.description),
        "has_sector": project.sector_name is not None,
        "has_year": project.year is not None,
        "has_mapped_country": any(c.iso3 for c in project.countries),
        "has_source_status": project.status is not None,
        "has_institution": bool(insts),
        "has_reported_amount": bool(reported),
        "has_amount_with_currency": any(f.currency for f in reported),
        "has_dated_amount": any(f.year is not None or f.first_year is not None for f in reported),
        "has_documents": bool(docs) or iati_docs > 0,
        "has_verified_approval": approval is not None,
    }
    return Completeness(**flags, missing=[k for k, v in flags.items() if not v])


def _limitations(project: Project, headline: list[FinancialFact]) -> list[str]:
    out = [
        "Historical record: not evidence that funding is currently available.",
        "Climate labels are classifications, not measured environmental outcomes.",
    ]
    if project.multi_country:
        out.append("Multi-country record: amounts are whole-project values; no country share.")
    if any(f.currency is None and f.amount is not None for f in headline):
        out.append("Some amounts state no currency or unit in the source; they cannot be summed.")
    if any(f.recommended_for_aggregates is False for f in headline):
        out.append("The source does not recommend some of these amounts for aggregates.")
    if any(f.financial_meaning == "repayment_not_funding" for f in headline):
        out.append("Repayments are money returned to the lender, not funding.")
    if any(f.financial_meaning == "pledge_not_commitment" for f in headline):
        out.append("A pledge is a promise, not a commitment.")
    if project.source_id == "gcf_readiness":
        out.append("Readiness grants support capacity; they are not funded projects.")
    if (project.status or "").strip().lower() in CLOSED_STATUSES:
        out.append(f"Source status '{project.status}': the activity may be finished or closed.")
    return out


def build_evidence(
    session: Session, policy: AccessPolicy, projects: Iterable[Project]
) -> list[ProjectEvidence]:
    projects = list(projects)
    batch = _Batch(session, policy, [p.id for p in projects])
    out: list[ProjectEvidence] = []
    for p in projects:
        source = batch.sources[p.source_id]
        headline, breakdown = financial_facts(p, policy)
        insts = institutions(p, source)
        docs = batch.documents.get(p.id, [])
        approval = batch.approvals.get(p.id)
        countries = sorted(p.countries, key=lambda c: c.position)
        out.append(
            ProjectEvidence(
                project_id=p.id,
                title=p.title,
                source=SourceInfo(
                    source_id=source.source_id,
                    name=source.name,
                    publisher=source.publisher,
                    rights_status=source.rights_status,
                    access_tier=source.access_tier,
                    reference_url=source.reference_url,
                ),
                source_project_id=p.source_project_id,
                record_level=p.record_level,
                description=p.description,
                countries=[
                    CountryRef(
                        country_name=c.country_name, iso3=c.iso3, mapping_method=c.mapping_method
                    )
                    for c in countries
                ],
                multi_country=p.multi_country,
                country_note=(
                    "Multi-country record: amounts are whole-project values and are not "
                    "allocated to any one country."
                    if p.multi_country
                    else "Single recipient as published."
                ),
                sector=SectorRef(
                    name=p.sector_name, code=p.sector_code, vocabulary=p.sector_vocabulary
                )
                if p.sector_name
                else None,
                institutions=insts,
                year=p.year,
                year_type=p.year_type,
                source_status=p.status,
                verified_approval=approval,
                climate_relevance=climate_relevance(p, policy),
                headline_facts=headline,
                breakdown_facts=breakdown,
                linked_records=batch.links.get(p.id, []),
                documents=docs,
                data_quality_warnings=[
                    WarningOut(code=w.code, field=w.field, message=w.message)
                    for w in sorted(p.warnings, key=lambda w: (w.code, w.field or ""))
                ],
                completeness=_completeness(p, headline, insts, docs, approval),
                source_reference=p.source_reference,
                group_key=p.group_key,
                group_meaning=p.group_meaning,
                limitations=_limitations(p, headline),
            )
        )
    return out
