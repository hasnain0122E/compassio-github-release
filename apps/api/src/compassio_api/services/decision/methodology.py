"""Versioned decision-engine methodologies (bump a version whenever behaviour changes)."""

from compassio_api.schemas.decision import (
    SUPPORTED_OBJECTIVES,
    UNSUPPORTED_OBJECTIVES,
    MethodologyResponse,
)
from compassio_api.services.decision.evidence import MEANINGS

COMPARISON_VERSION = "compassio-comparison-1.1.0"
PRIORITY_VERSION = "compassio-priority-1.0.0"
SCENARIO_VERSION = "compassio-scenario-1.0.0"

DECISION_DISCLAIMERS: tuple[str, ...] = (
    "Decision support only: Compassio does not approve, recommend or allocate real funding.",
    "Historical project funding is not a currently available funding opportunity.",
    "Commitments, approvals, disbursements and repayments are different things and are never "
    "added together; repayments are not funding.",
    "Climate-relevance labels are classifications, not measured environmental impact.",
    "No currency conversion or inflation adjustment is applied (AidData constant 2021 USD is "
    "AidData's own published figure).",
    "Multi-country amounts are whole-project values and are never split between countries.",
)

PRIORITY_CRITERIA = {
    "climate_relevance": "1 if a Qi et al. 2026 research annotation marks the record climate-"
    "related or a dedicated climate fund publishes it; 0 if the annotation says not related; "
    "not_available otherwise. A label, not impact.",
    "evidence_completeness": "Share of 6 record fields present: description, sector, year, "
    "mapped country, source status, institution.",
    "funding_completeness": "1 = a reported funding amount with currency and date; 0.5 = an "
    "amount missing currency or date; 0 = no reported funding amount (repayments ignored).",
    "sector_match": "1 if the sector contains any requested sector term (case-insensitive), "
    "else 0; not_requested when no sector is given.",
    "country_match": "1 = single-country record in a requested country; 0.5 = multi-country "
    "record that includes it; 0 otherwise; not_requested when none is given.",
    "documentation": "1 = a deterministic document link or IATI document links; 0.5 = only "
    "candidate links needing review; 0 = none.",
    "review_uncertainty": "Share (capped at 1) of 3 uncertainty warnings present (estimated "
    "dates/amounts, not recommended for aggregates, country not attributable, retrospective "
    "description). Higher = more need for careful human review, not lower quality.",
}

SCENARIO_METHODS = {
    "equal": "Every selected project gets weight 1.",
    "sector_priority": "Weight = the user's priority for the project's sector "
    "(unlisted_sector_weight otherwise).",
    "priority_score": "Weight = the project's deterministic priority score "
    f"({PRIORITY_VERSION}) under the given priority weights.",
}

RULES = [
    "Every money total goes through compassio_ml.finance.aggregate; an unsafe total is null "
    "with a reason, never 0.",
    "Facts are comparable only when source, flow kind, level, currency, price basis and row "
    "selection are all equal (comparability_key).",
    "Cross-source records linked as probably the same project are shown side by side and "
    "never summed.",
    "Records of the same source record group (an AidData parent package or an ADB project "
    "number) are shown side by side and flagged; a comparison never adds their amounts.",
    "Instrument components and source-published country lines are breakdowns, never added to "
    "stated totals.",
    "Missing values are null and listed in completeness.missing; they are never imputed.",
    "Rankings are deterministic (ties broken by project id) and fully decomposed into "
    "components; they are not statements of financial attractiveness, eligibility or impact.",
    "Scenarios are hypothetical: exact Decimal arithmetic, rounded to 0.01 of the budget unit, "
    "allocated + unallocated == budget exactly.",
]

PUBLIC_DISPLAY = {
    "GET /api/v1/decision/methodology": "Safe to display publicly (no source data).",
    "all other decision and analytics endpoints": "Source-derived. Served only when "
    "COMPASSIO_SOURCE_DATA_ACCESS=local_development outside production; in public mode they "
    "return 403 source_rights_not_cleared because no source has a rights clearance yet.",
}


def methodology() -> MethodologyResponse:
    return MethodologyResponse(
        comparison_version=COMPARISON_VERSION,
        priority_version=PRIORITY_VERSION,
        scenario_version=SCENARIO_VERSION,
        priority_criteria=PRIORITY_CRITERIA,
        scenario_methods=SCENARIO_METHODS,
        supported_objectives=list(SUPPORTED_OBJECTIVES),
        unsupported_objectives=dict(UNSUPPORTED_OBJECTIVES),
        financial_meanings={k: f"{v[0]}: {v[2]}" for k, v in sorted(MEANINGS.items())},
        rules=RULES,
        public_display=PUBLIC_DISPLAY,
    )
