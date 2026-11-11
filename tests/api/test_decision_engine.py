"""Task 008 decision engine on the ARTIFICIAL extended fixture database (logic only).

Expected numbers are derived by hand from the fixture rows in conftest.py (example_* records,
ZZ* countries); none of them is model or real-world evidence.
"""

import hashlib
import random
import sqlite3
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from compassio_api.services.decision import prioritize as prioritize_module

from .conftest import make_client

FP901, FP902 = "gcf_projects:FP901", "gcf_projects:FP902"
CFU_R2, CFU_R3, CFU_R4 = (f"climate_funds_update:projects-r{i}" for i in (2, 3, 4))
ADB1 = "adb_pakistan:XM-DAC-46004-99999-001-LN1"
ADB2 = "adb_pakistan:XM-DAC-46004-99999-001-LN2"


@pytest.fixture
def client(extended_url: str) -> TestClient:
    return make_client(extended_url)


def _group(body: dict[str, Any], key_part: str) -> dict[str, Any]:
    matches = [g for g in body["comparable_groups"] if key_part in g["comparability_key"]]
    assert len(matches) == 1, [g["comparability_key"] for g in body["comparable_groups"]]
    group: dict[str, Any] = matches[0]
    return group


def _evidence(client: TestClient, pid: str) -> dict[str, Any]:
    r = client.get(f"/api/v1/decision/evidence/{pid}")
    assert r.status_code == 200, r.text
    project: dict[str, Any] = r.json()["project"]
    return project


def _table_digest(url: str, table: str) -> str:
    with sqlite3.connect(url.removeprefix("sqlite:///")) as con:
        rows = con.execute(f"select * from {table} order by id").fetchall()
    return hashlib.sha256(repr(rows).encode()).hexdigest()


# ------------------------------------------------------------------------------- evidence
def test_every_flow_kind_is_labelled_with_its_financial_meaning(client: TestClient) -> None:
    pledge = _evidence(client, "aiddata:5")["headline_facts"]
    assert {f["financial_meaning"] for f in pledge} == {"pledge_not_commitment"}
    assert all(f["is_funding_flow"] is False for f in pledge)

    gcf = {(f["source_id"], f["flow_kind"]): f for f in _evidence(client, FP901)["headline_facts"]}
    assert gcf[("gcf_api_projects", "gcf_financing")]["financial_meaning"] == "approval"
    assert gcf[("gcf_api_projects", "co_financing")]["financial_meaning"] == "co_financing"
    assert gcf[("gcf_api_projects", "total_project_cost")]["is_funding_flow"] is False
    # Export and API figures for the same project are separate facts, never merged.
    assert gcf[("gcf_projects", "gcf_financing")]["amount"] == "1000"
    assert gcf[("gcf_api_projects", "gcf_financing")]["currency"] is None

    adb = _evidence(client, ADB1)
    flows = {f["flow_kind"]: f for f in adb["headline_facts"]}
    assert flows["disbursement"]["fact_type"] == "derived_sum_of_source_transactions"
    assert Decimal(flows["disbursement"]["amount"]) == Decimal(390)  # 400 + (-10) reversal
    assert flows["disbursement"]["transactions_summed"] == 2
    repayments = [f for f in adb["headline_facts"] if f["flow_kind"].startswith("repayment")]
    assert repayments and all(f["financial_meaning"] == "repayment_not_funding" for f in repayments)
    assert all(not f["is_funding_flow"] for f in repayments)


def test_units_are_scaled_but_values_stay_exact(client: TestClient) -> None:
    cfu = _evidence(client, CFU_R2)
    approval = next(f for f in cfu["headline_facts"] if f["flow_kind"] == "approval")
    assert approval["amount"] == "1.5" and approval["unit"] == "millions"
    assert Decimal(approval["amount_in_units"]) == Decimal(1_500_000)
    assert [f["financing_type"] for f in cfu["breakdown_facts"]] == ["grant"]


def test_missing_values_are_explicit_nulls_never_zero(client: TestClient) -> None:
    ev = _evidence(client, "aiddata:3")
    assert all(
        f["amount"] is None and f["value_status"] == "not_reported" for f in ev["headline_facts"]
    )
    assert "has_reported_amount" in ev["completeness"]["missing"]
    gcf = _evidence(client, FP901)
    assert gcf["sector"] is None and gcf["year"] is None and gcf["description"] is None


def test_multi_country_records_keep_whole_project_values(client: TestClient) -> None:
    ev = _evidence(client, FP902)
    assert ev["multi_country"] is True
    lines = {
        f["country_iso3"]: f
        for f in ev["breakdown_facts"]
        if f["financing_type"] == "country_breakdown" and f["flow_kind"] == "gcf_financing"
    }
    assert {k: v["amount"] for k, v in lines.items()} == {"ZZA": "1200", "ZZB": "800"}
    assert all(v["country_attribution"] == "source_published_country_line" for v in lines.values())
    headline = [f for f in ev["headline_facts"] if f["flow_kind"] == "gcf_financing"]
    assert all(
        f["country_attribution"] == "whole_project_value_not_attributable_to_one_country"
        for f in headline
    )


def test_evidence_carries_provenance_approval_links_and_documents(client: TestClient) -> None:
    ev = _evidence(client, FP901)
    assert ev["verified_approval"]["approval_date"] == "2016-03-01"
    assert ev["verified_approval"]["verified_by_source_id"] == "gcf_api_projects"
    assert {d["verification_state"] for d in ev["documents"]} == {
        "deterministic_identifier_match",
        "candidate_requires_review",
    }
    assert [r["project_id"] for r in ev["linked_records"]] == [CFU_R2]
    assert ev["current_funding_opportunity"] == "not_determinable"
    assert ev["climate_relevance"]["status"] == "listed_by_climate_fund"
    assert _evidence(client, "aiddata:2")["climate_relevance"]["status"] == (
        "research_annotation_not_climate_related"
    )


# ----------------------------------------------------------------------------- comparison
def test_compatible_figures_are_summed_exactly(client: TestClient) -> None:
    body = client.post(
        "/api/v1/decision/compare", json={"project_ids": ["aiddata:1", "aiddata:2"]}
    ).json()
    nominal = _group(body, "aiddata|commitment|project|USD|nominal")
    constant = _group(body, "aiddata|commitment|project|USD|constant_2021_usd")
    assert Decimal(nominal["selection_total"]) == Decimal("200.20")
    assert Decimal(constant["selection_total"]) == Decimal("400.50")
    assert nominal["selection_summed_records"] == 2


def test_missing_amounts_are_counted_not_added(client: TestClient) -> None:
    body = client.post("/api/v1/decision/compare", json={"project_ids": [ADB1, ADB2]}).json()
    commitment = _group(body, "adb_pakistan|commitment|transaction|USD")
    # ADB1 and ADB2 share one ADB project number: the same-group rule withholds the total.
    assert commitment["selection_total"] is None
    assert "same source record group" in commitment["selection_total_reason"]
    assert any(w["relation_type"] == "same_source_record_group" for w in body["duplicate_warnings"])
    # A not-reported AidData amount states no currency either: shown, never put in a USD total.
    aid = client.post(
        "/api/v1/decision/compare", json={"project_ids": ["aiddata:2", "aiddata:3"]}
    ).json()
    usd = _group(aid, "aiddata|commitment|project|USD|nominal")
    assert [c["project_id"] for c in usd["cells"] if c["facts"]] == ["aiddata:2"]
    assert usd["selection_total"] is None


def test_incompatible_figures_are_shown_separately_without_a_total(client: TestClient) -> None:
    body = client.post(
        "/api/v1/decision/compare", json={"project_ids": ["aiddata:1", "aiddata:5", FP901]}
    ).json()
    keys = {g["comparability_key"] for g in body["comparable_groups"]}
    assert any("|commitment|" in k for k in keys) and any("|pledge|" in k for k in keys)
    for g in body["comparable_groups"]:
        present = [c for c in g["cells"] if c["facts"]]
        assert len(present) == 1 and g["selection_total"] is None
    gcf = _group(body, "gcf_api_projects|gcf_financing|project|currency_not_stated")
    assert gcf["selection_total_status"] == "unavailable"


def test_multi_country_and_unknown_currency_block_totals(client: TestClient) -> None:
    body = client.post(
        "/api/v1/decision/compare", json={"project_ids": ["aiddata:1", "aiddata:4"]}
    ).json()
    nominal = _group(body, "aiddata|commitment|project|USD|nominal")
    assert nominal["selection_total"] is None
    assert "multi-country" in nominal["selection_total_reason"]
    gcf = client.post("/api/v1/decision/compare", json={"project_ids": [FP901, FP902]}).json()
    export = _group(gcf, "gcf_projects|gcf_financing")
    assert export["selection_total"] is None
    assert "currency" in export["selection_total_reason"]


def test_cross_source_matches_are_flagged_and_never_added(client: TestClient) -> None:
    body = client.post("/api/v1/decision/compare", json={"project_ids": [CFU_R2, FP901]}).json()
    assert [w["project_ids"] for w in body["duplicate_warnings"]] == [[CFU_R2, FP901]]
    for g in body["comparable_groups"]:
        assert g["selection_total"] is None  # different sources never share a group


def test_comparison_shows_explicit_missing_information(client: TestClient) -> None:
    body = client.post(
        "/api/v1/decision/compare", json={"project_ids": [FP901, "aiddata:1"]}
    ).json()
    assert body["field_matrix"]["has_sector"] == {FP901: False, "aiddata:1": True}
    assert body["field_matrix"]["has_verified_approval"] == {FP901: True, "aiddata:1": False}


@pytest.mark.parametrize(
    "payload",
    [
        {"project_ids": ["aiddata:1"]},
        {"project_ids": ["aiddata:1", "aiddata:1"]},
        {"project_ids": ["aiddata:1", "aiddata:2"], "x": 1},
    ],
)
def test_compare_input_validation(client: TestClient, payload: dict[str, Any]) -> None:
    assert client.post("/api/v1/decision/compare", json=payload).status_code == 422


def test_unknown_projects_are_404(client: TestClient) -> None:
    r = client.post("/api/v1/decision/compare", json={"project_ids": ["aiddata:1", "aiddata:999"]})
    assert r.status_code == 404 and r.json()["code"] == "project_not_found"


# ------------------------------------------------------------------------------- insights
def test_funding_by_country_uses_single_country_records_only(client: TestClient) -> None:
    r = client.get("/api/v1/analytics/funding-by-country?metric=cfu_approvals_usd").json()
    assert {g["key"]: Decimal(g["total"]) for g in r["groups"]} == {
        "ZZA": Decimal(1_500_000),
        "ZZB": Decimal(250_000),
    }
    assert r["declaration"]["excluded_records"] == {"multi_country_whole_project_value": 1}
    assert r["declaration"]["financial_meaning"].startswith("approved funding")


def test_source_country_lines_are_counted_once_across_countries(client: TestClient) -> None:
    r = client.get(
        "/api/v1/analytics/funding-by-country?metric=gcf_api_gcf_funding_by_country_usd"
    ).json()
    totals = {g["key"]: Decimal(g["total"]) for g in r["groups"]}
    assert totals == {"ZZA": Decimal(2200), "ZZB": Decimal(800)}
    # 1000 (FP901) + 2000 (FP902): the split never exceeds the published project totals.
    assert sum(totals.values()) == Decimal(3000)


def test_funding_by_sector_and_unavailable_metrics(client: TestClient) -> None:
    r = client.get("/api/v1/analytics/funding-by-sector?metric=cfu_approvals_usd").json()
    assert [(g["key"], Decimal(g["total"])) for g in r["groups"]] == [
        ("Example sector", Decimal(1_750_000))
    ]
    gcf = client.get("/api/v1/analytics/funding-by-country?metric=gcf_financing").json()
    assert gcf["status"] == "unavailable" and gcf["groups"] == []
    unknown = client.get("/api/v1/analytics/funding-by-country?metric=example_unknown")
    assert unknown.status_code == 404


def test_approved_vs_disbursed_pairs_only_comparable_records(client: TestClient) -> None:
    body = client.get("/api/v1/analytics/approved-vs-disbursed").json()
    by = {s["source_id"]: s for s in body["sources"]}
    cfu = by["climate_funds_update"]
    assert cfu["paired_projects"] == 1  # r2 only: r3 multi-country, r4 invalid disbursement
    assert Decimal(cfu["approved_total_paired"]) == Decimal(1_500_000)
    assert Decimal(cfu["disbursed_total_paired"]) == Decimal(500_000)
    assert Decimal(cfu["disbursed_to_approved_ratio"]) == Decimal("0.3333")
    gcf = by["gcf_api_projects"]
    assert gcf["paired_projects"] == 1 and Decimal(gcf["disbursed_to_approved_ratio"]) == Decimal(
        "0.4"
    )
    adb = by["adb_pakistan"]
    assert Decimal(adb["approved_total_paired"]) == Decimal(1000)
    assert Decimal(adb["disbursed_total_paired"]) == Decimal(390)


def test_climate_distribution_counts_labels_not_impact(client: TestClient) -> None:
    body = client.get("/api/v1/analytics/climate-distribution").json()
    rio = next(d for d in body["distributions"] if d["scheme"].endswith(":objective"))
    assert sum(b["projects"] for b in rio["buckets"]) == 5
    assert "not measured" in body["statement"]


def test_country_profile_and_coverage(client: TestClient) -> None:
    body = client.get("/api/v1/analytics/country-profile/ZZA").json()
    metric = next(
        m
        for m in body["metrics"]
        if m["declaration"]["metric_id"] == "aiddata_commitments_constant_2021_usd"
    )
    assert Decimal(metric["all_years_total"]) == Decimal("400.50")  # aiddata:1 + aiddata:2
    cov = client.get("/api/v1/analytics/coverage").json()
    assert {s["source_id"] for s in cov["sources"]} >= {"aiddata", "gcf_projects"}
    assert "gcf_historical" not in {s["source_id"] for s in cov["sources"]}


def test_institutions_count_records_by_role(client: TestClient) -> None:
    body = client.get("/api/v1/analytics/institutions").json()
    roles = {(g["source_id"], g["field"]) for g in body["groups"]}
    assert ("gcf_projects", "accredited_entity") in roles
    assert body["measure"] == "project_record_count"


# --------------------------------------------------------------------------- prioritization
PRIORITY = {"filters": {"project_ids": ["aiddata:1", "aiddata:2", "aiddata:5", FP901, CFU_R2]}}


def test_prioritization_is_deterministic_and_decomposed(client: TestClient) -> None:
    first = client.post("/api/v1/decision/prioritize", json=PRIORITY).json()
    second = client.post("/api/v1/decision/prioritize", json=PRIORITY).json()
    assert first["items"] == second["items"]
    assert first["ranking_fingerprint"] == second["ranking_fingerprint"]
    for item in first["items"]:
        applied = [c for c in item["components"] if c["status"] != "not_requested"]
        total = sum((Decimal(c["contribution"]) for c in applied), Decimal(0))
        weights = sum((Decimal(c["weight"]) for c in applied), Decimal(0))
        assert Decimal(item["score"]) == (total / weights).quantize(Decimal("0.0001"))
        assert "not a statement of financial attractiveness" in item["interpretation"]
        assert item["distinctions"]["current_funding_opportunity"] == "not_determinable"
    scores = [(Decimal(i["score"]), i["project_id"]) for i in first["items"]]
    assert scores == sorted(scores, key=lambda s: (-s[0], s[1]))


def test_relevance_funding_and_opportunity_are_distinct(client: TestClient) -> None:
    body = client.post("/api/v1/decision/prioritize", json=PRIORITY).json()
    by = {i["project_id"]: i["distinctions"] for i in body["items"]}
    assert by["aiddata:1"]["has_documented_historical_funding"] is True
    assert by["aiddata:5"]["has_documented_historical_funding"] is False  # pledge only


def test_user_criteria_change_the_ranking_transparently(client: TestClient) -> None:
    only_climate = {
        **PRIORITY,
        "weights": {
            k: 0
            for k in (
                "evidence_completeness",
                "funding_completeness",
                "sector_match",
                "country_match",
                "documentation",
                "review_uncertainty",
            )
        }
        | {"climate_relevance": 1},
    }
    body = client.post("/api/v1/decision/prioritize", json=only_climate).json()
    scores = {i["project_id"]: i["score"] for i in body["items"]}
    assert scores["aiddata:1"] == "1.0000" and scores["aiddata:2"] == "0.0000"
    sector = {**PRIORITY, "sectors_of_interest": ["energy"]}
    comp = next(
        c
        for i in client.post("/api/v1/decision/prioritize", json=sector).json()["items"]
        if i["project_id"] == "aiddata:1"
        for c in i["components"]
        if c["criterion"] == "sector_match"
    )
    assert comp["value"] == "1" and "EXAMPLE ENERGY" in comp["evidence"]


def test_missing_component_policy_is_explicit(client: TestClient) -> None:
    def score(policy: str) -> str:
        body = client.post(
            "/api/v1/decision/prioritize",
            json={
                "filters": {"project_ids": [FP901]},
                "sectors_of_interest": ["energy"],
                "missing_component_policy": policy,
            },
        ).json()
        return str(body["items"][0]["score"])

    assert Decimal(score("exclude_from_denominator")) > Decimal(score("score_zero"))


def test_prioritization_pagination_and_limits(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    page1 = client.post("/api/v1/decision/prioritize", json={**PRIORITY, "page_size": 2}).json()
    page2 = client.post(
        "/api/v1/decision/prioritize", json={**PRIORITY, "page_size": 2, "page": 2}
    ).json()
    assert [i["rank"] for i in page1["items"] + page2["items"]] == [1, 2, 3, 4]
    assert page1["pagination"]["total_items"] == 5
    zero = {**PRIORITY, "weights": {k: 0 for k in PRIORITY_KEYS}}
    assert client.post("/api/v1/decision/prioritize", json=zero).json()["code"] == (
        "no_criteria_weighted"
    )
    monkeypatch.setattr(prioritize_module, "MAX_CANDIDATES", 2)
    r = client.post("/api/v1/decision/prioritize", json={"filters": {"source": "aiddata"}})
    assert r.status_code == 422 and r.json()["code"] == "candidate_set_too_large"


PRIORITY_KEYS = (
    "climate_relevance",
    "evidence_completeness",
    "funding_completeness",
    "sector_match",
    "country_match",
    "documentation",
    "review_uncertainty",
)


# -------------------------------------------------------------------------------- scenarios
def _scenario(client: TestClient, **body: Any) -> dict[str, Any]:
    payload = {
        "budget": {"amount": "100", "currency": "USD"},
        "project_ids": ["aiddata:1", "aiddata:2", CFU_R2],
    } | body
    r = client.post("/api/v1/decision/scenarios", json=payload)
    assert r.status_code == 200, r.text
    data: dict[str, Any] = r.json()
    return data


def test_equal_split_conserves_the_budget_to_the_cent(client: TestClient) -> None:
    s = _scenario(client)
    assert [a["allocation"] for a in s["allocations"]] == ["33.34", "33.33", "33.33"]
    assert Decimal(s["allocated_total"]) + Decimal(s["unallocated"]) == Decimal(100)
    assert s["status"] == "allocated"
    assert s["request_sha256"] == _scenario(client)["request_sha256"]
    assert s["result_sha256"] == _scenario(client)["result_sha256"]


def test_caps_leave_an_explicit_unallocated_remainder(client: TestClient) -> None:
    s = _scenario(client, constraints={"max_per_project": "20"})
    assert [a["allocation"] for a in s["allocations"]] == ["20.00", "20.00", "20.00"]
    assert s["status"] == "partially_allocated" and s["unallocated"] == "40.00"
    assert all("max_per_project" in a["binding_constraints"] for a in s["allocations"])


def test_sector_and_country_caps(client: TestClient) -> None:
    # aiddata:2 and aiddata:3 share 'EXAMPLE SECTOR'; aiddata:1 is 'EXAMPLE ENERGY'.
    s = _scenario(
        client,
        project_ids=["aiddata:1", "aiddata:2", "aiddata:3"],
        constraints={"max_share_per_sector": "0.4"},
    )
    by = {a["project_id"]: a["allocation"] for a in s["allocations"]}
    assert by == {"aiddata:1": "40.00", "aiddata:2": "20.00", "aiddata:3": "20.00"}
    assert s["status"] == "partially_allocated" and s["unallocated"] == "20.00"
    multi = _scenario(
        client, project_ids=["aiddata:1", "aiddata:4"], constraints={"max_share_per_country": "0.5"}
    )
    groups = {a["project_id"]: a["country_group"] for a in multi["allocations"]}
    assert groups["aiddata:4"] == "multi-country (not attributable)"
    assert all(Decimal(a["allocation"]) == Decimal(50) for a in multi["allocations"])


def test_sector_priority_weights_and_unlisted_sectors(client: TestClient) -> None:
    s = _scenario(
        client,
        method="sector_priority",
        sector_priorities={"EXAMPLE ENERGY": "3", "example sector": "1"},
    )
    by = {a["project_id"]: a for a in s["allocations"]}
    assert by["aiddata:1"]["allocation"] == "60.00"  # 3 / (3 + 1 + 1), case-insensitive
    assert by["aiddata:2"]["weight"] == "1"
    only = _scenario(client, method="sector_priority", sector_priorities={"EXAMPLE ENERGY": "3"})
    alloc = {a["project_id"]: a["allocation"] for a in only["allocations"]}
    assert alloc == {"aiddata:1": "100.00", "aiddata:2": "0.00", CFU_R2: "0.00"}
    assert any("weight 0" in w for w in only["feasibility_warnings"])
    missing = client.post(
        "/api/v1/decision/scenarios",
        json={
            "budget": {"amount": "1", "currency": "USD"},
            "project_ids": ["aiddata:1"],
            "method": "sector_priority",
        },
    )
    assert missing.json()["code"] == "missing_sector_priorities"


def test_infeasible_minimums_allocate_nothing(client: TestClient) -> None:
    s = _scenario(client, constraints={"min_per_project": "40"})
    assert s["status"] == "infeasible" and Decimal(s["unallocated"]) == Decimal(100)
    assert all(a["allocation"] == "0" or Decimal(a["allocation"]) == 0 for a in s["allocations"])


@pytest.mark.parametrize(
    "objective", ["maximize_return", "maximize_emission_reductions", "example_invented_objective"]
)
def test_unsupported_objectives_are_rejected(client: TestClient, objective: str) -> None:
    r = client.post(
        "/api/v1/decision/scenarios",
        json={
            "budget": {"amount": "1", "currency": "USD"},
            "project_ids": ["aiddata:1"],
            "objective": objective,
        },
    )
    assert r.status_code == 422 and r.json()["code"] == "objective_not_supported"


def test_scenario_warnings_never_invent_costs_or_eligibility(client: TestClient) -> None:
    s = _scenario(client, budget={"amount": "1000", "currency": "USD"})
    a1 = next(a for a in s["allocations"] if a["project_id"] == "aiddata:1")
    assert any("not costs or funding needs" in w for w in a1["warnings"])
    eur = _scenario(client, budget={"amount": "10", "currency": "EUR"})
    assert any("no conversion" in w for w in eur["allocations"][0]["warnings"])
    assert any("HYPOTHETICAL" in d for d in s["disclosures"])


def test_scenario_conservation_property(client: TestClient) -> None:
    rng = random.Random(8)  # deterministic pseudo-random budgets: logic check only
    for _ in range(25):
        budget = Decimal(rng.randint(1, 10_000_000)) / Decimal(100)
        cap = Decimal(rng.randint(1, 5_000_000)) / Decimal(100)
        s = _scenario(
            client,
            budget={"amount": str(budget), "currency": "USD"},
            method="priority_score",
            constraints={"max_per_project": str(cap)},
        )
        allocs = [Decimal(a["allocation"]) for a in s["allocations"]]
        assert sum(allocs) + Decimal(s["unallocated"]) == budget
        assert all(Decimal(0) <= a <= cap for a in allocs)


# ------------------------------------------------------------------- rights / integrity
SOURCE_DERIVED = [
    ("get", f"/api/v1/decision/evidence/{FP901}", None),
    ("post", "/api/v1/decision/compare", {"project_ids": ["aiddata:1", "aiddata:2"]}),
    ("post", "/api/v1/decision/prioritize", PRIORITY),
    (
        "post",
        "/api/v1/decision/scenarios",
        {"budget": {"amount": "1", "currency": "USD"}, "project_ids": ["aiddata:1"]},
    ),
    ("get", "/api/v1/analytics/funding-by-country?metric=cfu_approvals_usd", None),
    ("get", "/api/v1/analytics/funding-by-sector?metric=cfu_approvals_usd", None),
    ("get", "/api/v1/analytics/institutions", None),
    ("get", "/api/v1/analytics/approved-vs-disbursed", None),
    ("get", "/api/v1/analytics/climate-distribution", None),
    ("get", "/api/v1/analytics/coverage", None),
    ("get", "/api/v1/analytics/country-profile/ZZA", None),
]


@pytest.mark.parametrize(
    "settings", [{"source_data_access": "public"}, {"environment": "production"}]
)
@pytest.mark.parametrize(("method", "path", "body"), SOURCE_DERIVED)
def test_source_derived_routes_fail_closed_without_rights(
    extended_url: str, settings: dict[str, str], method: str, path: str, body: Any
) -> None:
    c = make_client(extended_url, **settings)
    r = c.get(path) if method == "get" else c.post(path, json=body)
    assert r.status_code == 403 and r.json()["code"] == "source_rights_not_cleared"


def test_methodology_is_public_and_versioned(extended_url: str) -> None:
    body = (
        make_client(extended_url, source_data_access="public")
        .get("/api/v1/decision/methodology")
        .json()
    )
    assert body["priority_version"] == "compassio-priority-1.0.0"
    assert body["scenario_version"] == "compassio-scenario-1.0.0"
    assert "maximize_return" in body["unsupported_objectives"]


def test_restricted_records_stay_invisible(client: TestClient, extended_url: str) -> None:
    with sqlite3.connect(extended_url.removeprefix("sqlite:///")) as con:
        hidden = [
            r[0]
            for r in con.execute(
                "select id from projects where source_id = 'gcf_historical' limit 1"
            )
        ]
    pid = hidden[0] if hidden else "gcf_historical:example"
    assert client.get(f"/api/v1/decision/evidence/{pid}").status_code == 404
    assert (
        client.post(
            "/api/v1/decision/compare", json={"project_ids": ["aiddata:1", pid]}
        ).status_code
        == 404
    )


def test_endpoints_never_modify_stored_observations(client: TestClient, extended_url: str) -> None:
    before = _table_digest(extended_url, "financial_observations")
    for method, path, body in SOURCE_DERIVED:
        r = client.get(path) if method == "get" else client.post(path, json=body)
        assert r.status_code == 200, (path, r.text)
    assert _table_digest(extended_url, "financial_observations") == before


@pytest.mark.parametrize("country", ["ZZA", "ZZB", "PAK"])
def test_insight_totals_never_drift_from_trend_totals(client: TestClient, country: str) -> None:
    """finance_rows.metric_statement must select exactly what the protected trends query does."""
    profile = client.get(f"/api/v1/analytics/country-profile/{country}").json()
    for summary in profile["metrics"]:
        metric = summary["declaration"]["metric_id"]
        trend = client.get(f"/api/v1/analytics/trends?metric={metric}&country={country}").json()
        totals = [Decimal(p["total"]) for p in trend["points"] if p["total"] is not None]
        if summary["all_years_total"] is None:
            assert not totals, metric
        else:
            assert Decimal(summary["all_years_total"]) == sum(totals, Decimal(0)), metric
