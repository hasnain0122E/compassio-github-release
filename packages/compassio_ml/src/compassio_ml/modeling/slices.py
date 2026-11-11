"""Validation subgroup reports. Small slices are reported with their size but metrics suppressed."""

import numpy as np
import pandas as pd

from compassio_ml.modeling.metrics import ranking_metrics, threshold_metrics

YEAR_BANDS = ((2000, 2005), (2006, 2010), (2011, 2015), (2016, 2021))


def _slice_row(
    family: str,
    value: str,
    mask: np.ndarray,
    y: np.ndarray,
    score: np.ndarray,
    pred: np.ndarray,
    min_records: int,
    min_positives: int,
) -> dict[str, object]:
    n, pos = int(mask.sum()), int(y[mask].sum())
    row: dict[str, object] = {
        "slice_family": family,
        "slice": value,
        "records": n,
        "positives": pos,
    }
    if n == 0:
        row["suppressed"] = True
        return row
    # Recall is meaningless without positives; precision needs predicted positives.
    suppressed = n < min_records or pos < min_positives
    row["suppressed"] = suppressed
    tm = threshold_metrics(y[mask], pred[mask])
    row.update({"tp": tm["tp"], "fp": tm["fp"], "fn": tm["fn"], "tn": tm["tn"]})
    if not suppressed:
        row.update({k: tm[k] for k in ("precision", "recall", "f1")})
        row.update(ranking_metrics(y[mask], score[mask]))
    row["false_positive_rate"] = (
        (tm["fp"] / (tm["fp"] + tm["tn"])) if (tm["fp"] + tm["tn"]) else None
    )
    return row


def slice_report(
    meta: pd.DataFrame,
    y: np.ndarray,
    score: np.ndarray,
    pred: np.ndarray,
    *,
    min_records: int,
    min_positives: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    def add(family: str, value: str, mask: np.ndarray | pd.Series) -> None:
        rows.append(
            _slice_row(
                family,
                value,
                np.asarray(mask, dtype=bool),
                y,
                score,
                pred,
                min_records,
                min_positives,
            )
        )

    add("all", "all", np.ones(len(y), dtype=bool))
    # Label slices: recall on positives, false-positive rate on negatives (P/R undefined here).
    for value, label in (("climate_related", 1), ("not_climate_related", 0)):
        mask = y == label
        if not mask.any():
            rows.append(
                {
                    "slice_family": "label",
                    "slice": value,
                    "records": 0,
                    "positives": 0,
                    "suppressed": True,
                }
            )
            continue
        tm = threshold_metrics(y[mask], pred[mask])
        rows.append(
            {
                "slice_family": "label",
                "slice": value,
                "records": int(mask.sum()),
                "positives": int(y[mask].sum()),
                "suppressed": False,
                "tp": tm["tp"],
                "fp": tm["fp"],
                "fn": tm["fn"],
                "tn": tm["tn"],
                "recall": tm["recall"] if label == 1 else None,
                "false_positive_rate": (tm["fp"] / mask.sum())
                if label == 0 and mask.sum()
                else None,
            }
        )
    years = meta["commitment_year"].astype(int).to_numpy()
    for lo, hi in YEAR_BANDS:
        add("commitment_year_band", f"{lo}-{hi}", (years >= lo) & (years <= hi))
    pk = meta["is_pakistan"].fillna(False).astype(bool).to_numpy()
    add("pakistan", "pakistan", pk)
    add("pakistan", "non_pakistan", ~pk)
    energy = (meta["sector_name"].fillna("") == "ENERGY").to_numpy()
    add("sector", "ENERGY", energy)
    add("sector", "non_ENERGY", ~energy)
    for (fam, value), m in (
        (("pakistan_x_sector", "pakistan_ENERGY"), pk & energy),
        (("pakistan_x_sector", "pakistan_non_ENERGY"), pk & ~energy),
    ):
        add(fam, value, m)
    retro = meta["retrospective_text_warning"].fillna(False).astype(bool).to_numpy()
    add("retrospective_text_warning", "warning", retro)
    add("retrospective_text_warning", "no_warning", ~retro)
    amount = meta["amount_original"].notna().to_numpy()
    add("amount", "amount_known", amount)
    add("amount", "amount_missing", ~amount)
    recipients = meta["recipient_iso3"].fillna("(none)").astype(str).to_numpy()
    counts = pd.Series(recipients).value_counts()
    for iso, n in counts.items():
        mask = recipients == iso
        if n >= min_records and int(y[mask].sum()) >= min_positives:
            add("recipient", str(iso), mask)
    return rows
