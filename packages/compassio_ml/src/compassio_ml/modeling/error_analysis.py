"""Validation-only error analysis for a benchmark winner (Task 004.5).

Reads ``winner_validation_predictions.parquet`` from a run directory, verifies that every record
belongs to the protocol's *validation* partition (no test row can enter), joins descriptive
fields, and assigns deterministic, documented error tags. Nothing here changes a model,
threshold or split.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from compassio_ml.modeling.features import keyword_hits
from compassio_ml.modeling.frozen import PROTOCOL_COLUMN

ANALYSIS_COLUMNS = (
    "record_id",
    "title_clean",
    "description_clean",
    "sector_name",
    "flow_type",
    "commitment_year",
    "recipient_iso3",
    "is_pakistan",
    "rio_overall",
    "rio_mitigation",
    "rio_adaptation",
    "retrospective_text_warning",
    "retrospective_signals",
    "label_revealing_terms",
)
SHORT_DESCRIPTION_CHARS = (
    300  # roughly the lower quartile of research descriptions (Task 002: Q1 391)
)


class NotValidationDataError(ValueError):
    """The predictions contain records outside the validation partition."""


def outcome(y_true: int, pred: int) -> str:
    return {(1, 1): "TP", (0, 1): "FP", (1, 0): "FN", (0, 0): "TN"}[(int(y_true), int(pred))]


def error_tags(row: Mapping[Any, Any]) -> list[str]:
    """Descriptive tags for one FN/FP. Tags are evidence categories, not causes."""
    tags: list[str] = []
    sector = str(row.get("sector_name") or "")
    desc_len = len(str(row.get("description_clean") or ""))
    hits = int(row.get("keyword_hits") or 0)
    if row["outcome"] == "FN":
        mitigation = int(row.get("rio_mitigation") or 0)
        adaptation = int(row.get("rio_adaptation") or 0)
        if adaptation > 0 and mitigation == 0:
            tags.append("adaptation_only_label")
        elif mitigation > 0 and adaptation == 0:
            tags.append("mitigation_only_label")
        else:
            tags.append("mitigation_and_adaptation_label")
        tags.append(
            "significant_not_principal"
            if int(row.get("rio_overall") or 0) == 1
            else "principal_objective"
        )
        tags.append("energy_sector" if sector == "ENERGY" else "non_energy_sector")
        if hits == 0:
            tags.append("no_climate_keyword")
    elif row["outcome"] == "FP":
        tags.append("energy_sector" if sector == "ENERGY" else "non_energy_sector")
        if hits > 0:
            tags.append("climate_keyword_present")
        if bool(row.get("label_revealing_terms")):
            tags.append("explicit_climate_vocabulary")
    else:
        return tags
    if desc_len < SHORT_DESCRIPTION_CHARS:
        tags.append("short_description")
    if bool(row.get("retrospective_text_warning")):
        tags.append("retrospective_wording")
    return tags


@dataclass
class ErrorAnalysis:
    records: pd.DataFrame
    tag_summary: pd.DataFrame
    sector_summary: pd.DataFrame


def load_validation_predictions(
    run_dir: Path, table_path: Path, membership_path: Path, protocol: str = "primary"
) -> pd.DataFrame:
    predictions = pd.read_parquet(run_dir / "winner_validation_predictions.parquet")
    split_column = PROTOCOL_COLUMN[protocol]
    membership = pd.read_parquet(membership_path, columns=["record_id", split_column])
    split_of = dict(zip(membership["record_id"], membership[split_column], strict=True))
    outside = sorted({r for r in predictions["record_id"] if split_of.get(r) != "validation"})
    if outside:
        raise NotValidationDataError(
            f"{len(outside)} prediction records are not in the {protocol} validation partition"
        )
    ids = set(predictions["record_id"])
    table = pd.read_parquet(table_path, columns=list(ANALYSIS_COLUMNS))
    table = table[table["record_id"].isin(ids)]  # validation rows only
    return predictions.merge(table, on="record_id", how="left", validate="one_to_one")


def load_final_test_predictions(
    final_dir: Path, table_path: Path, membership_path: Path, protocol: str
) -> pd.DataFrame:
    """POST-HOC only: read predictions written by a COMPLETED one-shot final evaluation.

    Never used to change a model, threshold or split (Task 005 rule).
    """
    import json

    record = json.loads((final_dir / "test_access.json").read_text(encoding="utf-8"))
    if record.get("status") != "completed" or record.get("protocol") != protocol:
        raise NotValidationDataError("final evaluation for this protocol is not completed")
    predictions = pd.read_parquet(final_dir / "test_predictions.parquet").rename(
        columns={"pred": "pred_at_selected_threshold"}
    )
    split_column = PROTOCOL_COLUMN[protocol]
    membership = pd.read_parquet(membership_path, columns=["record_id", split_column])
    split_of = dict(zip(membership["record_id"], membership[split_column], strict=True))
    if any(split_of.get(r) != "test" for r in predictions["record_id"]):
        raise NotValidationDataError("final predictions contain records outside the test partition")
    table = pd.read_parquet(table_path, columns=list(ANALYSIS_COLUMNS))
    table = table[table["record_id"].isin(set(predictions["record_id"]))]
    return predictions.merge(table, on="record_id", how="left", validate="one_to_one")


def analyse(frame: pd.DataFrame) -> ErrorAnalysis:
    df = frame.copy()
    df["outcome"] = [
        outcome(y, p) for y, p in zip(df["y_true"], df["pred_at_selected_threshold"], strict=True)
    ]
    texts = (df["title_clean"].fillna("") + " " + df["description_clean"].fillna("")).tolist()
    df["keyword_hits"] = [keyword_hits(t) for t in texts]
    df["description_chars"] = df["description_clean"].fillna("").str.len()
    df["title_chars"] = df["title_clean"].fillna("").str.len()
    df["error_tags"] = ["|".join(error_tags(r)) for r in df.to_dict(orient="records")]

    rows = []
    for kind in ("FN", "FP"):
        sub = df[df["outcome"] == kind]
        counts: dict[str, int] = {}
        for tags in sub["error_tags"]:
            for tag in filter(None, str(tags).split("|")):
                counts[tag] = counts.get(tag, 0) + 1
        for tag, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            rows.append(
                {
                    "outcome": kind,
                    "tag": tag,
                    "records": n,
                    "share_of_outcome": round(n / len(sub), 4) if len(sub) else 0.0,
                }
            )
    tag_summary = pd.DataFrame(rows)

    positives = df[df["y_true"] == 1]
    sector = (
        positives.groupby(positives["sector_name"].fillna("(missing)"))
        .agg(positives=("record_id", "size"), tp=("outcome", lambda s: int((s == "TP").sum())))
        .assign(
            fn=lambda d: d["positives"] - d["tp"],
            recall=lambda d: (d["tp"] / d["positives"]).round(3),
        )
        .sort_values(["positives"], ascending=False)
        .reset_index()
        .rename(columns={"sector_name": "sector"})
    )
    return ErrorAnalysis(records=df, tag_summary=tag_summary, sector_summary=sector)


def top_terms(model: object, k: int = 30) -> pd.DataFrame:
    """Largest positive/negative coefficients of a TF-IDF linear pipeline (LR or LinearSVC)."""
    steps = getattr(model, "named_steps", None)
    if steps is None or "tfidf" not in steps or not hasattr(steps["clf"], "coef_"):
        raise TypeError("top_terms needs a fitted Pipeline(tfidf, linear classifier)")
    names = np.asarray(steps["tfidf"].get_feature_names_out())
    coef = np.asarray(steps["clf"].coef_).ravel()
    order = np.argsort(coef)
    rows = [
        {
            "direction": "towards_climate",
            "rank": i + 1,
            "term": names[j],
            "coefficient": round(float(coef[j]), 4),
        }
        for i, j in enumerate(order[::-1][:k])
    ]
    rows += [
        {
            "direction": "against_climate",
            "rank": i + 1,
            "term": names[j],
            "coefficient": round(float(coef[j]), 4),
        }
        for i, j in enumerate(order[:k])
    ]
    return pd.DataFrame(rows)
