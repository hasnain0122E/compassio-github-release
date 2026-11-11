"""Research-label integrity audit: distributions, consistency, leakage indicators."""

import re
from dataclasses import dataclass, field

import pandas as pd

from compassio_ml.audit.loaders import SourceData
from compassio_ml.audit.models import LabelRow
from compassio_ml.audit.profiling import parse_column
from compassio_ml.data.parsing import normalize_text
from compassio_ml.research.labels import RioMarker, parse_rio_marker

SCORE_MEANING = {
    0: "0 = not targeted (Qi et al. 2026, Methods)",
    1: "1 = significant objective (Qi et al. 2026, Methods)",
    2: "2 = principal objective (Qi et al. 2026, Methods)",
}

# Terms used only to *measure* lexical leakage risk; never as labels.
LEAKAGE_TERMS: dict[str, str] = {
    "climate": r"\bclimat",
    "renewable": r"\brenewabl",
    "solar": r"\bsolar\b",
    "wind power/farm": r"\bwind (?:power|farm|turbine)",
    "hydropower": r"hydropower|hydroelectric|hydro power",
    "emission/low-carbon": r"\bemission|low[- ]carbon",
    "flood": r"\bflood",
    "drought": r"\bdrought",
    "irrigation": r"\birrigat",
    "early warning/meteorology": r"early warning|meteorolog",
    "adaptation": r"\badaptat",
    "mitigation": r"\bmitigat",
}


@dataclass
class ResearchLabelAudit:
    distribution: list[LabelRow] = field(default_factory=list)
    facts: dict[str, object] = field(default_factory=dict)


def _frame_with_labels(cf: pd.DataFrame) -> pd.DataFrame:
    parsed = parse_column(cf["rio_marker"], parse_rio_marker)
    labels: list[RioMarker | None] = parsed.values
    out = cf.copy()
    out["_overall"] = [lab.rio_overall if lab else None for lab in labels]
    out["_second"] = [lab.rio_mitigation if lab else None for lab in labels]
    out["_third"] = [lab.rio_adaptation if lab else None for lab in labels]
    out["_positive"] = [bool(lab and lab.is_climate_related) for lab in labels]
    out["_valid"] = [lab is not None for lab in labels]
    out["_consistent"] = [bool(lab and lab.overall_is_max) for lab in labels]
    out["_pk"] = cf["Recipient"].map(lambda v: isinstance(v, str) and v.strip() == "Pakistan")
    return out


def _rows(
    frame: pd.DataFrame, column: str, label_field: str, meaning: dict[object, str]
) -> list[LabelRow]:
    total = len(frame)
    rows = []
    for value, sub in frame.groupby(column, dropna=False, sort=True):
        rows.append(
            LabelRow(
                label_field=label_field,
                value=str(value),
                records=len(sub),
                share=round(len(sub) / total, 6),
                pakistan_records=int(sub["_pk"].sum()),
                meaning=meaning.get(value, ""),
            )
        )
    return rows


def audit_research_labels(data: SourceData) -> ResearchLabelAudit:
    cf = _frame_with_labels(data.research_climate)
    result = ResearchLabelAudit()
    raw_meaning = {
        v: ("no climate objective in either component" if v == "0,0,0" else "")
        for v in cf["rio_marker"].unique()
    }
    result.distribution += _rows(cf, "rio_marker", "rio_marker (raw)", raw_meaning)
    result.distribution += _rows(cf, "_overall", "rio_overall", SCORE_MEANING)  # type: ignore[arg-type]
    result.distribution += _rows(cf, "_second", "rio_mitigation", SCORE_MEANING)  # type: ignore[arg-type]
    result.distribution += _rows(cf, "_third", "rio_adaptation", SCORE_MEANING)  # type: ignore[arg-type]
    result.distribution += _rows(
        cf,
        "_positive",
        "binary target candidate (overall > 0)",
        {True: "climate-relevant", False: "not climate-relevant"},
    )

    text = (cf["Title"].fillna("") + " " + cf["Description"].fillna("")).str.lower()
    keyword_rows = []
    for name, pattern in LEAKAGE_TERMS.items():
        hit = text.str.contains(pattern, regex=True)
        n = int(hit.sum())
        keyword_rows.append(
            {
                "term": name,
                "records_with_term": n,
                "positive": int((hit & cf["_positive"]).sum()),
                "second_gt0": int((hit & (cf["_second"].fillna(0) > 0)).sum()),
                "third_gt0": int((hit & (cf["_third"].fillna(0) > 0)).sum()),
                "positive_rate": round(float((hit & cf["_positive"]).sum()) / n, 4) if n else None,
            }
        )
    base_rate = float(cf["_positive"].mean())

    norm_desc = cf["Description"].map(normalize_text)
    groups = cf.assign(_k=norm_desc).groupby("_k")
    sizes = groups.size()
    multi = sizes[sizes > 1].index
    conflicting = [k for k in multi if cf.loc[norm_desc == k, "_positive"].nunique() > 1]
    conflict_rows = int(norm_desc.isin(conflicting).sum())

    years = cf["Commitment_Year"].astype(int)
    by_year = (
        cf.assign(_y=years)
        .groupby("_y")
        .agg(records=("_positive", "size"), positive=("_positive", "sum"))
        .reset_index()
    )
    desc_len = cf["Description"].fillna("").str.len()

    sdg = data.research_sdg
    sdg_facts: dict[str, object] = {}
    for sheet, frame in sdg.items():
        aligned = frame["AidData_Record_ID"].tolist() == cf["AidData_Record_ID"].tolist()
        ct = pd.crosstab(frame["SDG13"].astype(int).values, cf["_overall"].values)
        sdg_facts[sheet] = {
            "rows": len(frame),
            "ids_aligned_with_climate_workbook": aligned,
            "description_identical": sum(
                a == b for a, b in zip(frame["Description"], cf["Description"], strict=True)
            ),
            "sdg13_by_overall": {
                f"SDG13={i}": {f"overall={c}": int(ct.loc[i, c]) for c in ct.columns}
                for i in ct.index
            },
            "sdg_list_blank": int(frame.iloc[:, 15].isna().sum()),
            "sdg_list_column": str(frame.columns[15]),
        }

    climate_term = text.str.contains(LEAKAGE_TERMS["climate"], regex=True)
    result.facts.update(
        {
            "records": len(cf),
            "valid_labels": int(cf["_valid"].sum()),
            "overall_equals_max_of_components": int(cf["_consistent"].sum()),
            "positive": int(cf["_positive"].sum()),
            "negative": int((cf["_valid"] & ~cf["_positive"]).sum()),
            "positive_rate": round(base_rate, 6),
            "pakistan": int(cf["_pk"].sum()),
            "pakistan_positive": int((cf["_pk"] & cf["_positive"]).sum()),
            "both_components_nonzero": int(((cf["_second"] > 0) & (cf["_third"] > 0)).sum()),
            "keyword_association": keyword_rows,
            "climate_word_in_text": int(climate_term.sum()),
            "positives_without_climate_word": int((cf["_positive"] & ~climate_term).sum()),
            "duplicate_description_groups": len(multi),
            "duplicate_description_rows": int(norm_desc.isin(multi).sum()),
            "conflicting_label_groups": len(conflicting),
            "conflicting_label_rows": conflict_rows,
            "by_year": by_year.to_dict(orient="records"),
            "description_length": {
                "min": int(desc_len.min()),
                "median": float(desc_len.median()),
                "max": int(desc_len.max()),
                "under_100_chars": int((desc_len < 100).sum()),
            },
            "descriptions_mentioning_later_year": sum(
                mentions_year_after(str(d or ""), int(y))
                for d, y in zip(cf["Description"], cf["Commitment_Year"], strict=True)
            ),
            "positive_descriptions_mentioning_later_year": sum(
                mentions_year_after(str(d or ""), int(y))
                for d, y, p in zip(
                    cf["Description"], cf["Commitment_Year"], cf["_positive"], strict=True
                )
                if p
            ),
            "sdg_workbook": sdg_facts,
            "positive_by_flow_type": {
                str(k): [int(v["_positive"].sum()), len(v)] for k, v in cf.groupby("Flow_Type")
            },
            "positive_by_sector_top": sorted(
                ((str(k), int(v["_positive"].sum()), len(v)) for k, v in cf.groupby("Sector_Name")),
                key=lambda r: -r[1],
            )[:8],
        }
    )
    return result


def mentions_year_after(description: str, commitment_year: int) -> bool:
    """True if the text mentions a calendar year later than the commitment year."""
    years = [int(y) for y in re.findall(r"\b(20[0-3]\d)\b", description)]
    return any(y > commitment_year for y in years)
