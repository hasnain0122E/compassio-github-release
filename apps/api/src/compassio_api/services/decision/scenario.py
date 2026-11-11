"""Hypothetical budget scenario planner (compassio-scenario-1.0.0).

A planning simulation over user-selected records: weights x budget, exact ``Decimal``
water-filling under per-project / sector / country caps, then deterministic rounding to 0.01 of
the budget unit. ``allocated_total + unallocated == budget`` holds exactly by construction.

It never claims that money is available, that a record can receive an allocation, or anything
about returns, costs, emissions or eligibility: historical figures are shown only as context.
"""

import hashlib
import json
from collections import defaultdict
from decimal import ROUND_DOWN, Decimal, localcontext
from typing import Literal

from sqlalchemy.orm import Session

from compassio_api.schemas.data import AccessNotice
from compassio_api.schemas.decision import (
    SUPPORTED_OBJECTIVES,
    UNSUPPORTED_OBJECTIVES,
    Allocation,
    FinancialFact,
    ProjectEvidence,
    ScenarioRequest,
    ScenarioResponse,
)
from compassio_api.services.access import AccessPolicy
from compassio_api.services.cache import data_version
from compassio_api.services.decision.errors import DecisionInputError
from compassio_api.services.decision.evidence import (
    CLOSED_STATUSES,
    build_evidence,
    load_projects,
)
from compassio_api.services.decision.methodology import SCENARIO_VERSION
from compassio_api.services.decision.prioritize import components, score

CENT = Decimal("0.01")
SIX_DP = Decimal("0.000001")
MAX_ROUNDS = 1_000
UNIT_SCALE = {"units": Decimal(1), "thousands": Decimal(1_000), "millions": Decimal(1_000_000)}
DISCLOSURES = [
    "HYPOTHETICAL PLANNING SIMULATION: not a statement that funding is available or that any "
    "record can receive the suggested amount.",
    "Records are historical; Compassio holds no data on currently open funding opportunities.",
    "No returns, project costs, emission reductions, climate-risk reduction or financing "
    "eligibility are estimated or implied.",
    "Historical figures are shown for context only; they are not costs or funding needs.",
    "No currency conversion is applied between the budget and any recorded figure.",
]
Status = Literal["allocated", "partially_allocated", "infeasible"]


def _country_group(ev: ProjectEvidence) -> str:
    if ev.multi_country:
        return "multi-country (not attributable)"
    isos = sorted({c.iso3 for c in ev.countries if c.iso3})
    return isos[0] if len(isos) == 1 else "(no mapped country)"


def _sector_group(ev: ProjectEvidence) -> str:
    # Case-insensitive, like sector_priorities matching ("Energy" == "ENERGY").
    return ev.sector.name.casefold() if ev.sector else "(no sector stated)"


def _weights(req: ScenarioRequest, evs: list[ProjectEvidence]) -> dict[str, tuple[Decimal, str]]:
    out: dict[str, tuple[Decimal, str]] = {}
    lowered = {k.casefold(): (k, v) for k, v in req.sector_priorities.items()}
    for ev in evs:
        if req.method == "equal":
            out[ev.project_id] = (Decimal(1), "equal weight")
        elif req.method == "sector_priority":
            sector = ev.sector.name if ev.sector else None
            hit = lowered.get(sector.casefold()) if sector else None
            if hit is not None:
                out[ev.project_id] = (hit[1], f"sector priority for '{hit[0]}'")
            else:
                out[ev.project_id] = (
                    req.unlisted_sector_weight,
                    "unlisted sector weight" + ("" if sector else " (no sector stated)"),
                )
        else:
            value, _ = score(components(ev, req.priority_weights, [], []), "score_zero")
            out[ev.project_id] = (value, f"priority score {value}")
    return out


def _group_sums(groups: dict[str, str], alloc: dict[str, Decimal]) -> dict[str, Decimal]:
    sums: dict[str, Decimal] = defaultdict(Decimal)
    for p, amount in alloc.items():
        sums[groups[p]] += amount
    return sums


def _validate(req: ScenarioRequest) -> None:
    if req.objective not in SUPPORTED_OBJECTIVES:
        reason = UNSUPPORTED_OBJECTIVES.get(
            req.objective, "This objective is not defined by the scenario methodology."
        )
        raise DecisionInputError(
            "objective_not_supported",
            f"Objective '{req.objective}' cannot be supported: {reason} Supported objectives: "
            f"{', '.join(SUPPORTED_OBJECTIVES)}.",
        )
    cons = req.constraints
    if (
        cons.min_per_project is not None
        and cons.max_per_project is not None
        and cons.min_per_project > cons.max_per_project
    ):
        raise DecisionInputError("invalid_constraints", "min_per_project exceeds max_per_project")
    if req.method == "sector_priority" and not req.sector_priorities:
        raise DecisionInputError(
            "missing_sector_priorities", "method 'sector_priority' needs sector_priorities"
        )


def plan(session: Session, policy: AccessPolicy, req: ScenarioRequest) -> ScenarioResponse:
    _validate(req)
    evs = build_evidence(session, policy, load_projects(session, policy, req.project_ids))
    budget = req.budget.amount
    unit_label = f"{req.budget.currency} ({req.budget.unit})"
    weights = _weights(req, evs)
    sector = {ev.project_id: _sector_group(ev) for ev in evs}
    country = {ev.project_id: _country_group(ev) for ev in evs}
    ids = [ev.project_id for ev in evs]
    cons = req.constraints
    arithmetic = [f"Budget B = {budget} {unit_label}; {len(ids)} selected records."]
    feasibility: list[str] = []
    binding: dict[str, set[str]] = defaultdict(set)
    status: Status = "allocated"

    with localcontext() as ctx:
        ctx.prec = 50
        floor = cons.min_per_project or Decimal(0)
        cap = cons.max_per_project
        caps: list[tuple[dict[str, str], Decimal, str]] = []
        if cons.max_share_per_sector is not None:
            caps.append((sector, budget * cons.max_share_per_sector, "max_share_per_sector"))
        if cons.max_share_per_country is not None:
            caps.append((country, budget * cons.max_share_per_country, "max_share_per_country"))

        if floor * len(ids) > budget:
            status = "infeasible"
            alloc = {p: Decimal(0) for p in ids}
            remaining = budget
            feasibility.append(
                f"Infeasible: {len(ids)} x min_per_project {floor} = {floor * len(ids)} exceeds "
                f"the budget {budget}. Nothing is allocated."
            )
        else:
            alloc = {p: floor for p in ids}
            remaining = budget - floor * len(ids)
            if floor:
                binding_note = f"Step 1: minimum {floor} to each record; remaining {remaining}."
                arithmetic.append(binding_note)
                for p in ids:
                    binding[p].add("min_per_project")
            active = {p for p in ids if weights[p][0] > 0}
            for p in sorted(set(ids) - active):
                feasibility.append(f"{p}: weight 0 ({weights[p][1]}); receives only the minimum.")
            rounds = 0
            while remaining > 0 and active and rounds < MAX_ROUNDS:
                rounds += 1
                total_w = sum((weights[p][0] for p in active), Decimal(0))
                tentative = {p: remaining * weights[p][0] / total_w for p in active}
                factor = Decimal(1)
                if cap is not None:
                    for p in active:
                        factor = min(factor, (cap - alloc[p]) / tentative[p])
                for groups, gcap, _name in caps:
                    used = _group_sums(groups, alloc)
                    extra: dict[str, Decimal] = defaultdict(Decimal)
                    for p in active:
                        extra[groups[p]] += tentative[p]
                    for g, add in extra.items():
                        factor = min(factor, max(Decimal(0), gcap - used[g]) / add)
                factor = max(Decimal(0), factor)
                spent = Decimal(0)
                for p in active:
                    alloc[p] += tentative[p] * factor
                    spent += tentative[p] * factor
                arithmetic.append(
                    f"Round {rounds}: share {remaining:.6f} by weight over {len(active)} records "
                    f"(sum of weights {total_w}); scale {min(factor, Decimal(1)):.6f}; "
                    f"placed {spent:.6f}."
                )
                if factor >= 1:
                    remaining = Decimal(0)
                    break
                remaining -= spent
                saturated: set[str] = set()
                if cap is not None:
                    for p in active:
                        if alloc[p] >= cap:
                            saturated.add(p)
                            binding[p].add("max_per_project")
                for groups, gcap, name in caps:
                    used = _group_sums(groups, alloc)
                    for p in active:
                        if used[groups[p]] >= gcap:
                            saturated.add(p)
                            binding[p].add(f"{name} ({groups[p]})")
                if not saturated:  # defensive: no further progress possible
                    break
                active -= saturated

        # Deterministic rounding: round every allocation down to 0.01, then give whole cents to
        # the largest fractional remainders (ties by id) without breaking any cap.
        rounded = {p: a.quantize(CENT, rounding=ROUND_DOWN) for p, a in alloc.items()}
        # Exactly what was placed (the 50-digit sum of the shares can fall a hair short).
        target = (budget - remaining).quantize(CENT, rounding=ROUND_DOWN)
        cents = int((target - sum(rounded.values(), Decimal(0))) / CENT)
        given = 0
        for p in sorted(ids, key=lambda q: (-(alloc[q] - rounded[q]), q)):
            if given >= cents:
                break
            if cap is not None and rounded[p] + CENT > cap:
                continue
            if any(_group_sums(g, rounded)[g[p]] + CENT > gcap for g, gcap, _ in caps):
                continue
            rounded[p] += CENT
            given += 1
        allocated = sum(rounded.values(), Decimal(0))
        unallocated = budget - allocated

    arithmetic.append(
        f"Rounding: allocations rounded down to 0.01; {given} cent(s) redistributed by largest "
        "remainder (ties by project id)."
    )
    arithmetic.append(f"Result: allocated {allocated} + unallocated {unallocated} = {budget}.")
    if status != "infeasible" and unallocated >= CENT:
        status = "partially_allocated"
        feasibility.append(
            f"{unallocated} {unit_label} could not be allocated within the constraints "
            "(caps or zero weights)."
        )
    for name in req.sector_priorities:
        if not any(name.casefold() == s.casefold() for s in sector.values()):
            feasibility.append(f"Sector priority '{name}' matches no selected record's sector.")

    allocations: list[Allocation] = []
    for ev in evs:
        p = ev.project_id
        refs = [f for f in ev.headline_facts if f.is_funding_flow]
        allocations.append(
            Allocation(
                project_id=p,
                title=ev.title,
                source_id=ev.source.source_id,
                sector=ev.sector.name if ev.sector else None,
                country_group=country[p],
                weight=weights[p][0],
                weight_basis=weights[p][1],
                allocation=rounded[p],
                share_of_budget=(rounded[p] / budget).quantize(SIX_DP),
                binding_constraints=sorted(binding[p]),
                reference_facts=refs,
                warnings=_warnings(ev, rounded[p], req, refs),
            )
        )
    request_hash = hashlib.sha256(
        json.dumps(req.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    result_hash = hashlib.sha256(
        json.dumps(
            {
                "methodology": SCENARIO_VERSION,
                "status": status,
                "unallocated": str(unallocated),
                "allocations": [[a.project_id, str(a.allocation)] for a in allocations],
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return ScenarioResponse(
        scenario_label=req.scenario_label,
        status=status,
        budget=req.budget,
        allocated_total=allocated,
        unallocated=unallocated,
        conservation_check=f"{allocated} + {unallocated} = {allocated + unallocated} "
        f"({'equals' if allocated + unallocated == budget else 'DOES NOT EQUAL'} the budget)",
        allocations=allocations,
        arithmetic=arithmetic,
        feasibility_warnings=feasibility,
        assumptions=[
            f"Weights: {req.method} ({SCENARIO_VERSION}).",
            f"All amounts are in {unit_label} as entered; no conversion or inflation adjustment.",
            "Sector caps and priorities compare the source's sector names case-insensitively "
            "(vocabularies still differ by source); country caps use the single mapped "
            "country, and multi-country records form their own group (no country share is "
            "invented).",
            "Allocations are rounded down to 0.01 of the budget unit; leftover cents go to the "
            "largest remainders (ties by project id).",
        ],
        disclosures=DISCLOSURES,
        methodology_version=SCENARIO_VERSION,
        request_sha256=request_hash,
        result_sha256=result_hash,
        data_version=list(data_version(session)),
        access=AccessNotice(mode=policy.mode, notice=policy.notice),
    )


def _warnings(
    ev: ProjectEvidence, amount: Decimal, req: ScenarioRequest, refs: list[FinancialFact]
) -> list[str]:
    out: list[str] = []
    in_units = amount * UNIT_SCALE[req.budget.unit]
    reported = [f for f in refs if f.amount_in_units is not None]
    if not reported:
        out.append("No historical funding figure is recorded for this record.")
    same = [f for f in reported if f.currency == req.budget.currency]
    if reported and not same:
        out.append(
            f"No recorded figure is in {req.budget.currency}; no conversion is applied, so the "
            "allocation cannot be compared with the record's history."
        )
    for f in same:
        if f.amount_in_units is not None and in_units > f.amount_in_units:
            out.append(
                f"Hypothetical allocation exceeds the recorded {f.financial_meaning} "
                f"({f.amount_in_units} {f.currency}, {f.price_basis}); historical figures are "
                "not costs or funding needs."
            )
            break
    statuses = [ev.source_status]
    if ev.verified_approval is not None:
        statuses.append(ev.verified_approval.project_status)
    closed = [x for x in statuses if x and x.strip().lower() in CLOSED_STATUSES]
    if closed:
        out.append(f"Status '{closed[0]}': the activity may be finished or closed.")
    if ev.multi_country:
        out.append("Multi-country record: the allocation is not attributable to one country.")
    if ev.source.source_id == "gcf_readiness":
        out.append("Readiness grant record: capacity support, not a funded project.")
    out.append("Whether this record can receive new funding is not determinable from the data.")
    return out
