"""Source inspection reports, the machine-readable coverage/readiness report and the
time-of-description audit. Every number is computed from the build outputs; nothing is typed in.

"Verified labels" means **human-adjudicated** labels only. Donor-reported markers (category B)
are counted as *source-reported* labels, never as verified ground truth.
"""

import json
from pathlib import Path
from typing import Any, cast

import pandas as pd

from compassio_ml.external.partition import (
    ALL_PARTITIONS,
    EXTERNAL,
    TRAIN,
    VALID,
    sample_size_table,
)
from compassio_ml.external.registry import read_retrieval_manifest

PRIORITY_FAILURE_SECTORS = (
    "agriculture_forestry_fishing",
    "water_sanitation_waste",
    "disaster_risk_and_emergency",
    "transport",
    "urban_development",
    "health",
    "environment_ecosystems",
    "multisector_other",
)


def _vc(series: pd.Series) -> dict[str, int]:
    return {str(k): int(v) for k, v in series.value_counts(dropna=False).items()}


def _donor(frame: pd.DataFrame) -> pd.DataFrame:
    explicit = frame[frame["donor_marker_status"] == "explicit_both"]
    return explicit.assign(
        pos=explicit["donor_rio_overall"] > 0,
        ada=explicit["donor_rio_adaptation"] > 0,
        mit=explicit["donor_rio_mitigation"] > 0,
        ada_only=(explicit["donor_rio_adaptation"] > 0) & (explicit["donor_rio_mitigation"] == 0),
    )


def inspect_source(frame: pd.DataFrame, retrieval_dir: Path) -> dict[str, Any]:
    manifest = read_retrieval_manifest(retrieval_dir)
    years = pd.to_datetime(frame["approval_date"].fillna(frame["start_date"]), errors="coerce")
    report: dict[str, Any] = {
        "source_id": manifest["source_id"],
        "publisher": manifest["publisher"],
        "retrieval_id": manifest["retrieval_id"],
        "files": len(manifest["files"]),
        "bytes": sum(int(f["bytes"]) for f in manifest["files"]),
        "failures": manifest["failures"],
        "terms_files": [
            {"file": f["file"], "sha256": f["sha256"], "url": f["final_url"]}
            for f in manifest["files"]
            if f.get("role") == "terms"
        ],
        "records": len(frame),
        "records_with_title": int(frame["title_clean"].notna().sum()),
        "records_missing_description": int(frame["description_clean"].isna().sum()),
        "records_with_usable_text": int(frame["has_usable_text"].sum()),
        "description_chars_quantiles": {
            str(q): float(frame["description_chars"].quantile(q)) for q in (0.1, 0.5, 0.9)
        },
        "pakistan_records": int(frame["is_pakistan"].sum()),
        "multi_country_records": int(frame["multi_country"].sum()),
        "unresolved_country_codes": int(frame["country_iso3"].str.contains("ISO2:").sum()),
        "countries": len({c for s in frame["country_iso3"] for c in s.split(";") if c}),
        "year_range": [int(years.dt.year.min()), int(years.dt.year.max())]
        if years.notna().any()
        else None,
        "status": _vc(frame["status"]),
        "sector_family": _vc(frame["sector_family"]),
        "label_category": _vc(frame["label_category"]),
        "text_timing": _vc(frame["text_timing"]),
        "v2_partition": _vc(frame["v2_partition"]),
        "project_families": int(frame["project_family_id"].nunique()),
        "partition_groups": int(frame["partition_group_id"].nunique()),
    }
    if "hierarchy" in frame and frame["hierarchy"].notna().any():
        report["hierarchy"] = _vc(frame["hierarchy"])
    if (frame["donor_marker_status"] != "absent").any():
        report["donor_marker_status"] = _vc(frame["donor_marker_status"])
        donor = _donor(frame)
        counts = donor.groupby(["donor_rio_mitigation", "donor_rio_adaptation"]).size()
        report["donor_rio_crosstab_mitigation_x_adaptation"] = {
            "x".join(str(int(v)) for v in cast(tuple[Any, ...], key)): int(n)
            for key, n in counts.items()
        }
    if frame["gcf_theme"].notna().any():
        report["gcf_theme"] = _vc(frame["gcf_theme"])
    if (frame["wb_climate_themes"] != "").any():
        report["wb_climate_themes"] = _vc(frame["wb_climate_themes"])
    return report


def overlap_summary(links: pd.DataFrame) -> dict[str, Any]:
    def src(series: pd.Series) -> pd.Series:
        return series.str.split(":", n=1).str[0]

    frame = links.assign(left_source=src(links["left_id"]), right_source=src(links["right_id"]))
    frame = frame[frame["relation"] != "v1_leakage_group"]
    frame = frame.assign(
        pair=[
            " <-> ".join(sorted((a, b)))
            for a, b in zip(frame["left_source"], frame["right_source"], strict=True)
        ]
    )
    out: dict[str, Any] = {}
    for strength, part in frame.groupby("strength"):
        counts = part.groupby(["relation", "pair"]).size()
        out[str(strength)] = {
            " | ".join(str(v) for v in cast(tuple[Any, ...], key)): int(n)
            for key, n in counts.items()
        }
    return out


def timing_audit(external: pd.DataFrame) -> dict[str, Any]:
    out: dict[str, Any] = {
        "definitions": {
            "commitment_date": "Date funds were committed. Not available in the acquired external "
            "sources (World Bank reports approval, not commitment, dates).",
            "approval_date": "World Bank boardapprovaldate; GCF Board meeting date (BMDate). IATI "
            "activity files carry no approval date.",
            "document_creation_date": "Date the text was written. Unknown for all acquired text "
            "except where a dated document row exists (GCF funding "
            "proposal), which is recorded but not the text used.",
            "latest_update_date": "IATI last-updated-datetime; GCF ODL ProjectLastModifiedOn.",
            "evaluation_date": "Retrieval timestamp in each retrieval manifest.",
        }
    }
    for source_id, frame in external.groupby("source_id"):
        extra = frame["extra"].map(lambda s: json.loads(s) if s else {})
        entry: dict[str, Any] = {
            "text_timing": _vc(frame["text_timing"]),
            "with_approval_date": int(frame["approval_date"].notna().sum()),
            "with_last_updated": int(frame["last_updated"].notna().sum()),
            "with_verified_text_date": int(frame["text_date"].notna().sum()),
        }
        if source_id == "gcf_project_pages":
            entry["with_dated_approved_funding_proposal"] = int(
                extra.map(lambda e: bool(e.get("approved_funding_proposal_date"))).sum()
            )
            entry["with_funding_proposal_received_date"] = int(
                extra.map(lambda e: bool(e.get("funding_proposal_received"))).sum()
            )
        out[str(source_id)] = entry
    out["conclusion"] = (
        "No acquired text has a verified authoring date. Only World Bank Pipeline projects and "
        "IATI status-1 activities are verifiably pre-approval/pre-implementation at retrieval. "
        "Approval-time forecasting validity cannot be claimed for the other records."
    )
    return out


def sector_label_table(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    donor = _donor(frame)
    for family, part in frame.groupby("sector_family"):
        d = donor[donor["sector_family"] == family]
        rows.append(
            {
                "sector_family": str(family),
                "records": len(part),
                "usable_text": int(part["has_usable_text"].sum()),
                "donor_explicit_markers": len(d),
                "donor_positive_any": int(d["pos"].sum()),
                "donor_adaptation_positive": int(d["ada"].sum()),
                "donor_adaptation_only": int(d["ada_only"].sum()),
                "donor_mitigation_positive": int(d["mit"].sum()),
                "donor_explicit_not_targeted": int((~d["pos"]).sum()),
                "no_source_label": int((part["donor_marker_status"] == "absent").sum()),
            }
        )
    return sorted(rows, key=lambda r: -int(r["records"]))


def coverage_report(
    external: pd.DataFrame,
    aiddata_roles: pd.DataFrame,
    links: pd.DataFrame,
    pilot: pd.DataFrame | None,
    human_verified: int,
    registry_access: dict[str, str],
) -> dict[str, Any]:
    usable = external[external["has_usable_text"]]
    labelled = usable[usable["donor_marker_status"] == "explicit_both"]
    donor = _donor(labelled)
    pools: dict[str, Any] = {}
    for pool in sorted(ALL_PARTITIONS):
        part = usable[usable["v2_partition"] == pool]
        d = donor[donor["v2_partition"] == pool]
        pools[pool] = {
            "external_records_usable_text": len(part),
            "by_source": _vc(part["source_id"]),
            "donor_labelled": len(d),
            "donor_positive": int(d["pos"].sum()),
            "donor_non_energy_positive": int((d["pos"] & ~d["is_energy_sector"]).sum()),
            "donor_adaptation_positive": int(d["ada"].sum()),
            "donor_adaptation_only": int(d["ada_only"].sum()),
            "donor_explicit_not_targeted": int((~d["pos"]).sum()),
            "pakistan": int(part["is_pakistan"].sum()),
            "aiddata_records": int((aiddata_roles["v2_partition"] == pool).sum()),
        }
    suspected = links[links["strength"] == "suspected_requires_review"]
    sealed = usable[usable["v2_partition"] == EXTERNAL]
    observed_verified = {
        s: 0
        for s in (
            "non_energy_positives",
            "adaptation_only_positives",
            "energy_positives",
            "predicted_positives",
            "negatives",
            "pakistan_positives",
        )
    }
    return {
        "report_version": "v2_coverage_v1",
        "label_terms": {
            "verified_labels": "human-adjudicated (category E) labels only",
            "donor_labelled": "category B donor-reported Rio markers (explicit, both codes); "
            "source-reported, not verified",
        },
        "source_access": registry_access,
        "records_acquired": _vc(external["source_id"]),
        "records_with_usable_text": _vc(usable["source_id"]),
        "records_with_verified_labels": human_verified,
        "records_requiring_human_review": {
            "external_test_pilot_items": 0 if pilot is None else len(pilot),
            "reviews_required_per_item": 2,
            "external_test_candidate_pool_usable": len(sealed),
        },
        "donor_reported_labels": {
            "records": len(donor),
            "positive_any": int(donor["pos"].sum()),
            "non_energy_positive": int((donor["pos"] & ~donor["is_energy_sector"]).sum()),
            "adaptation_positive": int(donor["ada"].sum()),
            "adaptation_only": int(donor["ada_only"].sum()),
            "mitigation_positive": int(donor["mit"].sum()),
            "explicit_not_targeted_negative_controls": int((~donor["pos"]).sum()),
        },
        "unlabelled_records_not_counted_as_negative": int(
            (usable["donor_marker_status"] == "absent").sum()
        ),
        "pakistan_records": _vc(external[external["is_pakistan"]]["source_id"]),
        "independent_publishers": sorted(external["publisher"].unique().tolist()),
        "possible_duplicates": {
            "suspected_pairs_requiring_review": len(suspected),
            "by_relation": _vc(suspected["relation"]),
            "evidence_backed_overlap": overlap_summary(links).get("evidence_backed", {}),
        },
        "rights": {
            "rights_status_all_sources": sorted(external["rights_status"].unique().tolist()),
            "restrictions": [
                "GCF pages and backend API snapshot: ai-train=no; restricted for training, "
                "automated evaluation and human-review worksheets pending reviewed permission",
                "FCDO IATI: registry licence uk-ogl (OGL v3) - attribution required; not "
                "human-reviewed",
                "World Bank: terms page retrieved, not human-reviewed",
                "EC INTPA: EU-owned content CC BY 4.0 notice; attribution required; "
                "third-party content may need separate clearance; not human-reviewed",
                "All v2 data stay local and git-ignored until review",
            ],
        },
        "document_timing": {k: _vc(v["text_timing"]) for k, v in external.groupby("source_id")},
        "pools": pools,
        "failure_case_sectors_training_and_validation": [
            r
            for r in sector_label_table(usable[usable["v2_partition"].isin([TRAIN, VALID])])
            if r["sector_family"] in PRIORITY_FAILURE_SECTORS
        ],
        "pilot_strata": {}
        if pilot is None
        else {
            str(k): {
                "sampled": len(g),
                "pakistan": int(g["is_pakistan"].sum()),
                "population": int(g["stratum_population"].iloc[0]),
            }
            for k, g in pilot.groupby("stratum")
        },
        "sample_size_policy": sample_size_table(observed_verified),
    }


def write_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
