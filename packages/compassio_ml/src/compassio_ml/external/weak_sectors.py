"""Weak-sector coverage requirements (transport, urban, flood/disaster, agriculture, water,
ecosystems).

Targets are *evaluation* coverage targets, computed with the Wilson sample-size function:
``minimum`` = positives for a 95 % half-width of 0.15 on recall at an assumed 0.75, ``preferred``
= half-width 0.10. They apply separately to the development VALIDATION pool (model selection)
and to the human-verified EXTERNAL TEST. Training counts are reported without a target.
Counts are source-reported labels (A researcher, B donor); human-verified counts are 0 until
frozen review exists. Unlabelled records are never counted as negatives.
"""

import math
from typing import Any

import pandas as pd

from compassio_ml.external.partition import EXTERNAL, TRAIN, VALID, n_for_half_width

WEAK_SECTORS: dict[str, str] = {
    "transport": "Transport",
    "urban_development": "Urban resilience",
    "disaster_risk_and_emergency": "Flood and disaster preparedness",
    "agriculture_forestry_fishing": "Agriculture",
    "water_sanitation_waste": "Water infrastructure",
    "environment_ecosystems": "Ecosystems",
}
AIDDATA_SECTOR_FAMILY: dict[str, str] = {
    "TRANSPORT AND STORAGE": "transport",
    "AGRICULTURE, FORESTRY, FISHING": "agriculture_forestry_fishing",
    "WATER SUPPLY AND SANITATION": "water_sanitation_waste",
    "GENERAL ENVIRONMENTAL PROTECTION": "environment_ecosystems",
    "EMERGENCY RESPONSE": "disaster_risk_and_emergency",
    "RECONSTRUCTION RELIEF AND REHABILITATION": "disaster_risk_and_emergency",
    "DISASTER PREVENTION AND PREPAREDNESS": "disaster_risk_and_emergency",
}
ASSUMED_RECALL = 0.75
MINIMUM_POSITIVES = n_for_half_width(ASSUMED_RECALL, 0.15)
PREFERRED_POSITIVES = n_for_half_width(ASSUMED_RECALL, 0.10)
ASSUMED_PREVALENCE = (0.25, 0.50)  # planning assumptions for review volume; NOT measured


def _donor_counts(frame: pd.DataFrame) -> dict[str, int]:
    labelled = frame[frame["donor_marker_status"] == "explicit_both"]
    pos = labelled["donor_rio_overall"] > 0
    ada_only = (labelled["donor_rio_adaptation"] > 0) & (labelled["donor_rio_mitigation"] == 0)
    return {
        "positive": int(pos.sum()),
        "negative": int((~pos).sum()),
        "adaptation_only": int(ada_only.sum()),
    }


def weak_sector_requirements(external: pd.DataFrame, aiddata: pd.DataFrame) -> list[dict[str, Any]]:
    """``external``: all external records with v2 columns (any partition). ``aiddata``: v1
    research rows with ``sector_name``, ``is_climate_related`` and ``v2_partition``."""
    usable = external[external["has_usable_text"]]
    aid = aiddata.assign(family=aiddata["sector_name"].map(AIDDATA_SECTOR_FAMILY))
    rows: list[dict[str, Any]] = []
    for family, label in WEAK_SECTORS.items():
        part = usable[usable["sector_family"] == family]
        a_fam = aid[aid["family"] == family]
        entry: dict[str, Any] = {"sector_family": family, "label": label}
        for pool in (TRAIN, VALID):
            donor = _donor_counts(part[part["v2_partition"] == pool])
            a_pool = a_fam[a_fam["v2_partition"] == pool]
            entry[pool] = {
                "donor_B": donor,
                "researcher_A": {
                    "positive": int(a_pool["is_climate_related"].sum()),
                    "negative": int((~a_pool["is_climate_related"].astype(bool)).sum()),
                },
                "unlabelled_external": int(
                    (part[part["v2_partition"] == pool]["donor_marker_status"] == "absent").sum()
                ),
            }
        valid_pos = entry[VALID]["donor_B"]["positive"] + entry[VALID]["researcher_A"]["positive"]
        ext = part[part["v2_partition"] == EXTERNAL]
        entry["validation_positive_source_labelled"] = valid_pos
        entry["validation_missing_vs_minimum"] = max(0, MINIMUM_POSITIVES - valid_pos)
        entry["validation_missing_vs_preferred"] = max(0, PREFERRED_POSITIVES - valid_pos)
        entry["external_test"] = {
            "unlabelled_candidates_usable": len(ext),
            "world_bank_climate_tagged": int((ext["wb_climate_themes"] != "").sum()),
            "pakistan": int(ext["is_pakistan"].sum()),
            "human_verified_positive": 0,
            "missing_vs_minimum": MINIMUM_POSITIVES,
            "missing_vs_preferred": PREFERRED_POSITIVES,
            "review_items_needed_for_minimum_at_assumed_prevalence": {
                str(p): math.ceil(MINIMUM_POSITIVES / p) for p in ASSUMED_PREVALENCE
            },
            "candidate_pool_sufficient_for_minimum_at_0.25": len(ext)
            >= math.ceil(MINIMUM_POSITIVES / 0.25),
        }
        rows.append(entry)
    return rows


def summary_targets() -> dict[str, Any]:
    return {
        "assumed_recall": ASSUMED_RECALL,
        "minimum_positives_half_width_0.15": MINIMUM_POSITIVES,
        "preferred_positives_half_width_0.10": PREFERRED_POSITIVES,
        "assumed_prevalence_for_review_volume": list(ASSUMED_PREVALENCE),
        "note": "Targets apply per sector to the validation pool and to the human-verified "
        "external test. Prevalence values are planning assumptions, not measurements.",
    }
