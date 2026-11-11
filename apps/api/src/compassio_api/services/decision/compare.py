"""Side-by-side comparison of selected projects (no invented totals, no double counting)."""

from collections import defaultdict

from sqlalchemy.orm import Session

from compassio_api.schemas.data import AccessNotice
from compassio_api.schemas.decision import (
    CompareResponse,
    ComparisonCell,
    ComparisonGroup,
    DuplicateWarning,
    EvidenceResponse,
    FinancialFact,
)
from compassio_api.services.access import AccessPolicy
from compassio_api.services.decision.evidence import build_evidence, load_projects
from compassio_api.services.decision.methodology import COMPARISON_VERSION, DECISION_DISCLAIMERS
from compassio_api.services.finance_rows import safe_total
from compassio_ml.finance import AmountLevel, AmountUnit, FlowKind, MonetaryAmount, PriceBasis


def _amount(fact: FinancialFact, project_key: str) -> MonetaryAmount:
    level = AmountLevel(fact.level) if fact.fact_type == "source_reported" else AmountLevel.PROJECT
    return MonetaryAmount(
        source_id=fact.source_id,
        source_record_id=fact.fact_id,
        project_key=project_key,
        flow_kind=FlowKind(fact.flow_kind),
        # A derived per-record transaction sum is one figure per record (project level).
        level=level,
        value=fact.amount_in_units,
        unit=AmountUnit.UNITS,
        currency=fact.currency,
        price_basis=PriceBasis(fact.price_basis),
        date_meaning=fact.date_meaning,
        multi_country=fact.multi_country,
        estimated=fact.estimated,
    )


def _clusters(links: dict[str, set[str]], ids: list[str]) -> dict[str, str]:
    """project id -> cluster key (smallest id among linked selected projects)."""
    parent = {i: i for i in ids}

    def find(x: str) -> str:
        while parent[x] != x:
            x = parent[x]
        return x

    for a, others in links.items():
        for b in others:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    return {i: find(i) for i in ids}


def _shares_package(ids: list[str], package_of: dict[str, str]) -> bool:
    keys = [package_of[i] for i in ids if i in package_of]
    return len(keys) != len(set(keys))


def evidence(session: Session, policy: AccessPolicy, project_id: str) -> EvidenceResponse:
    project = build_evidence(session, policy, load_projects(session, policy, [project_id]))[0]
    return EvidenceResponse(
        project=project,
        methodology_version=COMPARISON_VERSION,
        disclaimers=list(DECISION_DISCLAIMERS),
        access=AccessNotice(mode=policy.mode, notice=policy.notice),
    )


def compare(session: Session, policy: AccessPolicy, project_ids: list[str]) -> CompareResponse:
    projects = build_evidence(session, policy, load_projects(session, policy, project_ids))
    selected = set(project_ids)
    links = {
        p.project_id: {r.project_id for r in p.linked_records if r.project_id in selected}
        for p in projects
    }
    cluster = _clusters(links, project_ids)
    warnings: list[DuplicateWarning] = []
    seen: set[tuple[str, str]] = set()
    for p in projects:
        for r in p.linked_records:
            pair = tuple(sorted((p.project_id, r.project_id)))
            if r.project_id in selected and pair not in seen:
                seen.add((pair[0], pair[1]))
                warnings.append(
                    DuplicateWarning(
                        project_ids=list(pair),
                        relation_type=r.relation_type,
                        verification_state=r.verification_state,
                        message="These records are linked as probably the same real-world "
                        "project in different sources; their amounts are never added.",
                    )
                )

    packages: dict[str, list[str]] = defaultdict(list)
    for p in projects:
        if p.group_key is not None:
            packages[p.group_key].append(p.project_id)
    for key, members in sorted(packages.items()):
        if len(members) > 1:
            warnings.append(
                DuplicateWarning(
                    project_ids=sorted(members),
                    relation_type="same_source_record_group",
                    verification_state="source_published_group",
                    message=f"Related records in the same source group ({key}). The source "
                    "publishes them as one package; Compassio does not add their amounts "
                    "because a package total may double count or omit package-level figures.",
                )
            )

    package_of = {p.project_id: p.group_key for p in projects if p.group_key is not None}
    by_key: dict[str, dict[str, list[FinancialFact]]] = defaultdict(lambda: defaultdict(list))
    for p in projects:
        for f in p.headline_facts:
            by_key[f.comparability_key][p.project_id].append(f)

    groups: list[ComparisonGroup] = []
    for key in sorted(by_key):
        cells_by_project = by_key[key]
        first = next(iter(cells_by_project.values()))[0]
        cells = [
            ComparisonCell(project_id=pid, facts=cells_by_project.get(pid, []))
            for pid in project_ids
        ]
        reason: str | None = None
        total = None
        summed = missing = 0
        present = [c for c in cells if c.facts]
        if len(present) < 2:
            reason = "Fewer than two selected projects report this figure; nothing to compare."
        elif any(len(c.facts) > 1 for c in present):
            reason = "A project has several figures of this kind; choose one before summing."
        elif any(c.facts[0].recommended_for_aggregates is False for c in present):
            reason = (
                "The source does not recommend at least one of these figures for aggregates "
                "(e.g. an umbrella agreement or pledge); no total is computed."
            )
        elif _shares_package([c.project_id for c in present], package_of):
            reason = (
                "At least two of these records belong to the same source record group (for "
                "example an AidData parent package); their amounts are not added "
                "(see duplicate_warnings)."
            )
        elif first.currency is None:
            reason = "The source states no currency or unit for this figure; it cannot be summed."
        else:
            result = safe_total([_amount(c.facts[0], cluster[c.project_id]) for c in present])
            total, reason = result.total, result.reason
            summed, missing = result.summed_records, result.missing_value_records
        groups.append(
            ComparisonGroup(
                comparability_key=key,
                source_id=first.source_id,
                flow_kind=first.flow_kind,
                financial_meaning=first.financial_meaning,
                meaning_label=first.meaning_label,
                level=first.level,
                currency=first.currency,
                price_basis=first.price_basis,
                cells=cells,
                selection_total=total,
                selection_total_status="available" if total is not None else "unavailable",
                selection_summed_records=summed,
                selection_missing_records=missing,
                selection_total_reason=None if total is not None else reason,
                selection_total_meaning="Sum of these historical figures for the selected "
                "records only, in units of the stated currency. Not available funding, not a "
                "country or fund total.",
            )
        )
    indicators = projects[0].completeness.model_dump(exclude={"missing"}).keys()
    matrix = {
        name: {p.project_id: bool(getattr(p.completeness, name)) for p in projects}
        for name in indicators
    }
    return CompareResponse(
        projects=projects,
        comparable_groups=groups,
        duplicate_warnings=warnings,
        field_matrix=matrix,
        methodology_version=COMPARISON_VERSION,
        disclaimers=list(DECISION_DISCLAIMERS),
        access=AccessNotice(mode=policy.mode, notice=policy.notice),
    )
