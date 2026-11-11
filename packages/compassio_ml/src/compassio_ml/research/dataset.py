"""Construction of the cleaned research table (one row per AidData record).

The research climate workbook and AidData GCDF 3.0 describe the *same* 20,985 records. They
are joined one-to-one on ``AidData_Record_ID`` == ``AidData Record ID`` (exact string match,
both keys verified unique). They are never stacked.

Text policy: the cleaned title/description are derived from the **AidData** originals, which
are the upstream, untruncated text (12 research titles are cut at 255 characters, and one
research description lost the word "null"). Both originals are kept in the auxiliary
``research_text_originals`` table, and rows whose research copy differs are flagged.
"""

import hashlib
from collections import Counter
from dataclasses import dataclass, field

import pandas as pd

from compassio_ml.audit.loaders import SourceData
from compassio_ml.data.parsing import (
    normalize_text,
    parse_amount,
    parse_iso_datetime_date,
    parse_year,
)
from compassio_ml.research.labels import parse_rio_marker
from compassio_ml.research.retrospective import diagnose
from compassio_ml.research.text import clean_text, word_count

# Minimum usable description for supervised text classification. The shortest observed
# description is 68 characters; the threshold exists so that future data is not silently
# treated as a negative when its text is too thin to judge.
MIN_DESCRIPTION_CHARS = 40
MIN_DESCRIPTION_WORDS = 6

COMPARED_FIELDS = {
    "Commitment_Year": "Commitment Year",
    "Recipient": "Recipient",
    "Recipient_Region": "Recipient Region",
    "Sector_Name": "Sector Name",
    "Flow_Type": "Flow Type",
    "Funding_Agencies": "Funding Agencies",
    "Funding_Agencies_Type": "Funding Agencies Type",
    "Title": "Title",
    "Description": "Description",
}


class JoinIntegrityError(ValueError):
    """The research/AidData join violated a one-to-one requirement."""


@dataclass
class JoinReport:
    research_rows: int
    aiddata_rows: int
    research_key_unique: bool
    aiddata_key_unique: bool
    matched: int
    research_only: list[str]
    aiddata_only: list[str]
    joined_rows: int
    field_mismatches: dict[str, int] = field(default_factory=dict)
    amount_mismatches_over_half_cent: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "research_rows": self.research_rows,
            "aiddata_rows": self.aiddata_rows,
            "research_key_unique": self.research_key_unique,
            "aiddata_key_unique": self.aiddata_key_unique,
            "matched": self.matched,
            "research_only": self.research_only,
            "aiddata_only": self.aiddata_only,
            "joined_rows": self.joined_rows,
            "field_mismatches_exact": self.field_mismatches,
            "amount_mismatches_over_half_cent": self.amount_mismatches_over_half_cent,
        }


def _missing(value: object) -> bool:
    return value is None or value is pd.NA or (isinstance(value, float) and value != value)


def _s(value: object) -> str | None:
    if _missing(value):
        return None
    text = str(value)
    return text if text.strip() != "" else None


def _yes(value: object) -> bool | None:
    text = _s(value)
    if text is None:
        return None
    lowered = text.strip().lower()
    if lowered in {"yes", "true"}:
        return True
    if lowered in {"no", "false"}:
        return False
    raise ValueError(f"Expected Yes/No, got {text!r}")


def sha256_text(value: str | None) -> str | None:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value is not None else None


def join_research_aiddata(
    research: pd.DataFrame, aiddata: pd.DataFrame
) -> tuple[pd.DataFrame, JoinReport]:
    """Exact one-to-one join on the AidData record id. Raises on any non-unique key."""
    rkey, akey = research["AidData_Record_ID"].map(_s), aiddata["AidData Record ID"].map(_s)
    report = JoinReport(
        research_rows=len(research),
        aiddata_rows=len(aiddata),
        research_key_unique=bool(rkey.notna().all() and rkey.is_unique),
        aiddata_key_unique=bool(akey.notna().all() and akey.is_unique),
        matched=0,
        research_only=sorted(set(rkey.dropna()) - set(akey.dropna())),
        aiddata_only=sorted(set(akey.dropna()) - set(rkey.dropna())),
        joined_rows=0,
    )
    if not report.research_key_unique or not report.aiddata_key_unique:
        dup_r = [k for k, n in Counter(rkey.dropna()).items() if n > 1][:5]
        dup_a = [k for k, n in Counter(akey.dropna()).items() if n > 1][:5]
        raise JoinIntegrityError(
            f"Join keys must be present and unique (research dups {dup_r}, aiddata dups {dup_a})"
        )
    left = research.assign(_key=rkey)
    right = aiddata.assign(_key=akey).add_prefix("ad::").rename(columns={"ad::_key": "_key"})
    joined = left.merge(right, on="_key", how="inner", validate="one_to_one")
    report.matched = len(joined)
    report.joined_rows = len(joined)
    for rcol, acol in COMPARED_FIELDS.items():
        report.field_mismatches[rcol] = int(
            (joined[rcol].map(_s).fillna("") != joined[f"ad::{acol}"].map(_s).fillna("")).sum()
        )
    ra = pd.to_numeric(joined["Amount_Constant_USD_2021"], errors="coerce")
    aa = pd.to_numeric(joined["ad::Amount (Constant USD 2021)"], errors="coerce")
    report.amount_mismatches_over_half_cent = int(
        (~(((ra - aa).abs() <= 0.0051) | (ra.isna() & aa.isna()))).sum()
    )
    return joined, report


def _parse_float(value: object) -> float | None:
    amount = parse_amount(_s(value))
    return float(amount) if amount is not None else None


def build_research_table(
    joined: pd.DataFrame, research_sha256: str, aiddata_sha256: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (research_projects, research_text_originals)."""
    rows: list[dict[str, object]] = []
    originals: list[dict[str, object]] = []
    for rec in joined.to_dict(orient="records"):
        record_id = str(rec["_key"])
        title_src = _s(rec["ad::Title"])
        desc_src = _s(rec["ad::Description"])
        title = clean_text(title_src)
        desc = clean_text(desc_src)
        research_title, research_desc = _s(rec["Title"]), _s(rec["Description"])

        label_error: str | None = None
        try:
            marker = parse_rio_marker(_s(rec["rio_marker"]))
        except ValueError as exc:
            marker, label_error = None, str(exc)
        year_src = _s(rec["ad::Commitment Year"])
        try:
            year = parse_year(year_src)
            year_error = None
        except ValueError as exc:
            year, year_error = None, str(exc)
        commit_date = parse_iso_datetime_date(_s(rec["ad::Commitment Date (MM/DD/YYYY)"]))
        amount_src = _s(rec["ad::Amount (Original Currency)"])
        currency = _s(rec["ad::Original Currency"])
        flags = diagnose(desc.value, year)

        rows.append(
            {
                "record_id": record_id,
                "research_row_id": _s(rec["ID"]),
                "source_ids": "research_paper|aiddata",
                "research_file_sha256": research_sha256,
                "aiddata_file_sha256": aiddata_sha256,
                # --- text (cleaned, derived from AidData originals) ---
                "title_clean": title.value,
                "description_clean": desc.value,
                "title_cleaning_steps": "|".join(title.steps),
                "description_cleaning_steps": "|".join(desc.steps),
                "title_source_sha256": sha256_text(title_src),
                "description_source_sha256": sha256_text(desc_src),
                "description_chars": len(desc.value or ""),
                "description_words": word_count(desc.value),
                "research_title_differs": (research_title or "") != (title_src or ""),
                "research_title_truncated_255": bool(
                    research_title
                    and title_src
                    and len(research_title) == 255
                    and title_src.startswith(research_title)
                    and len(title_src) > 255
                ),
                "research_description_differs": (research_desc or "") != (desc_src or ""),
                # --- context (source values) ---
                "recipient": _s(rec["ad::Recipient"]),
                "recipient_iso3": _s(rec["ad::Recipient ISO-3"]),
                "recipient_region": _s(rec["ad::Recipient Region"]),
                "is_pakistan": _s(rec["ad::Recipient ISO-3"]) == "PAK",
                "commitment_year_src": year_src,
                "commitment_year": year,
                "commitment_year_error": year_error,
                "commitment_date": commit_date.isoformat() if commit_date else None,
                "commitment_date_estimated": _yes(rec["ad::Commitment Date Estimated"]),
                "sector_code": _s(rec["ad::Sector Code"]),
                "sector_name": _s(rec["ad::Sector Name"]),
                "flow_type": _s(rec["ad::Flow Type"]),
                "flow_type_simplified": _s(rec["ad::Flow Type Simplified"]),
                "flow_class": _s(rec["ad::Flow Class"]),
                "intent": _s(rec["ad::Intent"]),
                "status": _s(rec["ad::Status"]),
                "funding_agencies": _s(rec["ad::Funding Agencies"]),
                "funding_agencies_type": _s(rec["ad::Funding Agencies Type"]),
                "recommended_for_aggregates": _yes(rec["ad::Recommended For Aggregates"]),
                "umbrella": _yes(rec["ad::Umbrella"]),
                "parent_id": _s(rec["ad::AidData Parent ID"]),
                # --- finance (commitment values as published; never imputed) ---
                "amount_original_src": amount_src,
                "amount_original": _parse_float(amount_src),
                "amount_currency": currency,
                "amount_unit": "units of amount_currency" if amount_src else None,
                "amount_constant_usd_2021": _parse_float(rec["ad::Amount (Constant USD 2021)"]),
                "amount_kind": "commitment_or_pledge (AidData definition)",
                "amount_estimated": _yes(rec["ad::Amount Estimated"]),
                # --- label (authors' annotation) ---
                "rio_marker_src": _s(rec["rio_marker"]),
                "rio_overall": marker.rio_overall if marker else None,
                "rio_mitigation": marker.rio_mitigation if marker else None,
                "rio_adaptation": marker.rio_adaptation if marker else None,
                "rio_overall_is_max": marker.overall_is_max if marker else None,
                "is_climate_related": marker.is_climate_related if marker else None,
                "label_error": label_error,
                # --- retrospective diagnostic (warnings, never exclusions) ---
                "retrospective_text_warning": flags.retrospective_text_warning,
                "retrospective_signals": "|".join(flags.signals),
                "label_revealing_terms": flags.label_revealing_terms,
            }
        )
        originals.append(
            {
                "record_id": record_id,
                "title_aiddata_src": title_src,
                "description_aiddata_src": desc_src,
                "title_research_src": research_title,
                "description_research_src": research_desc,
            }
        )
    table = _typed(pd.DataFrame(rows, dtype=object))
    text = _typed(pd.DataFrame(originals, dtype=object))
    order = table["record_id"].astype(int).argsort(kind="stable")
    text_order = text["record_id"].astype(int).argsort(kind="stable")
    return (
        table.iloc[order].reset_index(drop=True),
        text.iloc[text_order].reset_index(drop=True),
    )


INT_COLUMNS = frozenset(
    {
        "commitment_year",
        "rio_overall",
        "rio_mitigation",
        "rio_adaptation",
        "description_chars",
        "description_words",
    }
)
FLOAT_COLUMNS = frozenset({"amount_original", "amount_constant_usd_2021"})
BOOL_COLUMNS = frozenset(
    {
        "research_title_differs",
        "research_title_truncated_255",
        "research_description_differs",
        "is_pakistan",
        "commitment_date_estimated",
        "recommended_for_aggregates",
        "umbrella",
        "amount_estimated",
        "rio_overall_is_max",
        "is_climate_related",
        "retrospective_text_warning",
        "label_revealing_terms",
    }
)


def _typed(frame: pd.DataFrame) -> pd.DataFrame:
    """Explicit nullable dtypes so missing values stay <NA> (never NaN-as-truthy)."""
    out: dict[str, pd.Series] = {}
    for col in frame.columns:
        if col in INT_COLUMNS:
            out[col] = frame[col].astype("Int64")
        elif col in FLOAT_COLUMNS:
            out[col] = frame[col].astype("Float64")
        elif col in BOOL_COLUMNS:
            out[col] = frame[col].astype("boolean")
        else:
            out[col] = frame[col].astype("string")
        out[col].name = col
    return pd.DataFrame(out)


ELIGIBLE = "eligible"
QUARANTINED = "quarantined"
ANALYTICS_ONLY = "analytics_only"


def conflicting_description_groups(table: pd.DataFrame) -> dict[str, list[str]]:
    """Normalized-description groups whose members carry different binary labels."""
    keyed = table.assign(
        _k=table["description_clean"].map(lambda v: normalize_text(None if _missing(v) else str(v)))
    )
    keyed = keyed[(keyed["_k"] != "") & keyed["is_climate_related"].notna()]
    out: dict[str, list[str]] = {}
    for key, grp in keyed.groupby("_k"):
        if len(grp) > 1 and grp["is_climate_related"].nunique() > 1:
            out[str(key)] = sorted(grp["record_id"], key=int)
    return out


def assign_eligibility(table: pd.DataFrame) -> pd.DataFrame:
    """Add ``eligibility_status`` and ``exclusion_reasons``; nothing is dropped."""
    conflicts = conflicting_description_groups(table)
    conflicted = {rid for members in conflicts.values() for rid in members}
    statuses: list[str] = []
    reasons: list[str] = []
    for raw in table.to_dict(orient="records"):
        rec = {k: (None if _missing(v) else v) for k, v in raw.items()}
        quarantine: list[str] = []
        analytics: list[str] = []
        if rec["label_error"] or rec["rio_marker_src"] is None:
            quarantine.append("invalid_or_missing_rio_marker")
        elif rec["rio_overall_is_max"] is False:
            quarantine.append("rio_overall_not_max_of_components")
        if rec["record_id"] in conflicted:
            quarantine.append("conflicting_label_same_description")
        if rec["commitment_year"] is None:
            quarantine.append("invalid_commitment_year")
        if (
            rec["description_clean"] is None
            or int(str(rec["description_chars"])) < MIN_DESCRIPTION_CHARS
            or int(str(rec["description_words"])) < MIN_DESCRIPTION_WORDS
        ):
            analytics.append("insufficient_description")
        if quarantine:
            statuses.append(QUARANTINED)
        elif analytics:
            statuses.append(ANALYTICS_ONLY)
        else:
            statuses.append(ELIGIBLE)
        reasons.append("|".join(quarantine + analytics))
    return table.assign(
        eligibility_status=pd.array(statuses, dtype="string"),
        exclusion_reasons=pd.array(reasons, dtype="string"),
    )


def load_joined(data: SourceData) -> tuple[pd.DataFrame, JoinReport]:
    return join_research_aiddata(data.research_climate, data.aiddata)
