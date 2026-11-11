"""End-to-end research dataset construction (Task 003). Read-only on data/raw.

Outputs (all git-ignored, all regenerable):

* data/processed/research_projects.parquet           cleaned table, one row per record
* data/processed/research_text_originals.parquet     immutable source text (both copies)
* data/processed/research_split_membership_v1.parquet split membership per protocol
* artifacts/research_v1/*                             reports, checksums, metadata
"""

import csv
import hashlib
import json
import platform
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from compassio_ml.audit.loaders import SourceData
from compassio_ml.data.inventory import build_inventory
from compassio_ml.data.layout import DataLayout, MissingSourceDataError
from compassio_ml.data.manifest import SourceManifest
from compassio_ml.data.manifest_io import manifest_path, validate_manifest
from compassio_ml.research.dataset import (
    ELIGIBLE,
    assign_eligibility,
    build_research_table,
    conflicting_description_groups,
    join_research_aiddata,
)
from compassio_ml.research.grouping import RELATIONS, GroupInput, build_groups
from compassio_ml.research.splits import (
    EXCLUDED_PK_GROUP_MATE,
    SplitConfig,
    build_membership,
    check_disjoint,
    load_split_config,
    order_key,
)

DEFAULT_CONFIG = Path("configs") / "research_split_v1.yaml"
DEFAULT_REPORT_DIR = Path("artifacts") / "research_v1"
SPLIT_COLUMNS = ("split_primary", "split_chronological", "split_pakistan_holdout")


class PipelineError(RuntimeError):
    """A precondition for building the research dataset failed."""


@dataclass
class BuildResult:
    table: pd.DataFrame
    originals: pd.DataFrame
    membership: pd.DataFrame
    reports: dict[str, list[dict[str, object]]]
    summary: dict[str, object]


# ---------------------------------------------------------------------------- helpers
def _verified_hashes(layout: DataLayout) -> dict[str, str]:
    report = validate_manifest(layout, build_inventory(layout))
    if not report.ok:
        raise PipelineError(
            "Source manifest validation failed; refusing to build:\n  " + "\n  ".join(report.errors)
        )
    manifest = SourceManifest.model_validate_json(manifest_path(layout).read_text(encoding="utf-8"))
    hashes = {e.source_id: e.sha256 for e in manifest.entries}
    for needed in ("research_paper", "aiddata"):
        if needed not in hashes:
            raise MissingSourceDataError(f"Source '{needed}' is not registered in the manifest")
    return hashes


def _rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    return [{str(k): v for k, v in r.items()} for r in frame.to_dict(orient="records")]


def _share(n: int, d: int) -> float:
    return round(n / d, 6) if d else 0.0


# ---------------------------------------------------------------------------- grouping
def add_groups(table: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, list[tuple[str, ...]]]]:
    def opt(value: object) -> str | None:
        return None if value is None or value is pd.NA else str(value)

    inputs = [
        GroupInput(
            record_id=str(r["record_id"]),
            parent_id=opt(r["parent_id"]),
            title=opt(r["title_clean"]),
            description=opt(r["description_clean"]),
            recipient=opt(r["recipient"]),
        )
        for r in table.to_dict(orient="records")
    ]
    result = build_groups(inputs, RELATIONS)
    sizes = Counter(result.group_of.values())
    out = table.assign(
        leakage_group_id=table["record_id"].map(result.group_of),
        leakage_group_size=table["record_id"].map(lambda r: sizes[result.group_of[r]]),
    )
    return out, result.relation_groups


def _leakage_report(
    table: pd.DataFrame, relation_groups: dict[str, list[tuple[str, ...]]], config: SplitConfig
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    sizes = table.groupby("leakage_group_id").agg(
        size=("record_id", "size"),
        recipients=("recipient_iso3", "nunique"),
        years=("commitment_year", "nunique"),
        year_min=("commitment_year", "min"),
        year_max=("commitment_year", "max"),
        positives=("is_climate_related", "sum"),
        pakistan=("is_pakistan", "sum"),
        sectors=("sector_name", "nunique"),
    )
    multi = sizes[sizes["size"] > 1]
    by_relation_multi = {r: len(relation_groups.get(r, [])) for r in RELATIONS}

    # Records that would leak under an ordinary record-level random split.
    fr = dict(config.primary.fractions)
    names = sorted(fr)
    eligible = table[table["eligibility_status"] == ELIGIBLE]
    ordered = sorted(eligible["record_id"], key=lambda r: order_key(config.seed, "naive", r))
    cut1 = int(len(ordered) * fr[names[0]])
    cut2 = cut1 + int(len(ordered) * fr[names[1]])
    naive = {
        r: (names[0] if i < cut1 else names[1] if i < cut2 else names[2])
        for i, r in enumerate(ordered)
    }
    naive_split = eligible.assign(_s=eligible["record_id"].map(naive))
    spread = naive_split.groupby("leakage_group_id")["_s"].nunique()
    leaky_groups = set(spread[spread > 1].index)
    leaky_records = int(naive_split["leakage_group_id"].isin(leaky_groups).sum())

    size_dist = Counter(sizes["size"].tolist())
    summary: dict[str, object] = {
        "records": len(table),
        "groups": len(sizes),
        "singleton_groups": int((sizes["size"] == 1).sum()),
        "multi_record_groups": len(multi),
        "records_in_multi_record_groups": int(multi["size"].sum()),
        "largest_group_size": int(sizes["size"].max()),
        "relation_edge_groups": by_relation_multi,
        "relation_edge_group_records": {
            r: sum(len(g) for g in relation_groups.get(r, [])) for r in RELATIONS
        },
        "groups_spanning_multiple_recipients": int((multi["recipients"] > 1).sum()),
        "groups_spanning_multiple_years": int((multi["years"] > 1).sum()),
        "groups_spanning_multiple_sectors": int((multi["sectors"] > 1).sum()),
        "groups_with_mixed_labels": int(
            ((multi["positives"] > 0) & (multi["positives"] < multi["size"])).sum()
        ),
        "records_without_parent_id": int(table["parent_id"].isna().sum()),
        "naive_random_split_leaking_records": leaky_records,
        "naive_random_split_leaking_groups": len(leaky_groups),
        "group_size_distribution": {str(k): v for k, v in sorted(size_dist.items())},
    }
    largest = sizes.sort_values(["size", "leakage_group_id"], ascending=[False, True]).head(25)
    largest_rows = [
        {"leakage_group_id": str(gid), **{str(k): int(v) for k, v in r.items()}}
        for gid, r in largest.iterrows()
    ]
    dist_rows: list[dict[str, object]] = [
        {"group_size": k, "groups": v, "records": k * v} for k, v in sorted(size_dist.items())
    ]
    return summary, largest_rows, dist_rows


# ---------------------------------------------------------------------------- reports
def _conflict_review(table: pd.DataFrame) -> list[dict[str, object]]:
    groups = conflicting_description_groups(table)
    by_id = table.set_index("record_id")
    rows: list[dict[str, object]] = []
    compare = [
        "title_clean",
        "recipient_iso3",
        "commitment_year",
        "sector_name",
        "flow_type",
        "amount_original_src",
        "amount_currency",
        "funding_agencies",
        "status",
    ]
    for key in sorted(groups, key=lambda k: groups[k][0]):
        members = groups[key]
        sub = by_id.loc[members]
        differs = [c for c in compare if sub[c].astype(str).nunique() > 1]
        gid = "d_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
        for r in sub.reset_index().to_dict(orient="records"):
            rid = r["record_id"]
            rows.append(
                {
                    "description_group": gid,
                    "group_size": len(members),
                    "record_id": rid,
                    "rio_marker_src": r["rio_marker_src"],
                    "is_climate_related": bool(r["is_climate_related"]),
                    "commitment_year": int(r["commitment_year"]),
                    "recipient_iso3": r["recipient_iso3"],
                    "sector_name": r["sector_name"],
                    "flow_type": r["flow_type"],
                    "fields_differing_within_group": "|".join(differs),
                    "title_clean": r["title_clean"],
                    "review_status": "pending_human_review",
                }
            )
    return rows


def _eligibility_report(table: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for status, sub in table.groupby("eligibility_status", sort=True):
        reasons = sub["exclusion_reasons"].replace("", "(none)")
        for reason, rs in sub.groupby(reasons, sort=True):
            rows.append(
                {
                    "eligibility_status": status,
                    "reasons": reason,
                    "records": len(rs),
                    "climate_related": int(rs["is_climate_related"].fillna(False).sum()),
                    "pakistan": int(rs["is_pakistan"].sum()),
                    "pakistan_climate_related": int(
                        (rs["is_pakistan"] & rs["is_climate_related"].fillna(False)).sum()
                    ),
                }
            )
    return rows


COMPLETENESS_FIELDS = (
    "record_id",
    "title_clean",
    "description_clean",
    "parent_id",
    "commitment_year",
    "recipient",
    "sector_name",
    "rio_marker_src",
    "amount_original",
    "amount_currency",
    "amount_constant_usd_2021",
)


def _completeness(table: pd.DataFrame) -> list[dict[str, object]]:
    breakdowns = {
        "all": pd.Series("all", index=table.index),
        "is_climate_related": table["is_climate_related"].astype(str),
        "is_pakistan": table["is_pakistan"].astype(str),
        "commitment_year": table["commitment_year"].astype(str),
        "sector_name": table["sector_name"].fillna("(missing)"),
        "recipient_iso3": table["recipient_iso3"].fillna("(missing)"),
    }
    rows: list[dict[str, object]] = []
    for bname, keys in breakdowns.items():
        for bval, idx in table.groupby(keys, sort=True).groups.items():
            sub = table.loc[idx]
            for f in COMPLETENESS_FIELDS:
                present = int(sub[f].notna().sum())
                rows.append(
                    {
                        "breakdown": bname,
                        "value": str(bval),
                        "field": f,
                        "records": len(sub),
                        "present": present,
                        "missing": len(sub) - present,
                        "share_present": _share(present, len(sub)),
                    }
                )
    return rows


def _retrospective_report(table: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    signals = [
        "later_year_mention",
        "completion_language",
        "disbursement_language",
        "status_outcome_language",
    ]
    scopes = {
        "all": table,
        "eligible": table[table["eligibility_status"] == ELIGIBLE],
        "eligible_climate_related": table[
            (table["eligibility_status"] == ELIGIBLE) & table["is_climate_related"].fillna(False)
        ],
        "eligible_pakistan": table[
            (table["eligibility_status"] == ELIGIBLE) & table["is_pakistan"]
        ],
    }
    for scope, sub in scopes.items():
        n = len(sub)
        warn = int(sub["retrospective_text_warning"].sum())
        row: dict[str, object] = {
            "scope": scope,
            "records": n,
            "retrospective_text_warning": warn,
            "share_warning": _share(warn, n),
        }
        for s in signals:
            row[s] = int(
                sub["retrospective_signals"].str.split("|").map(lambda xs, s=s: s in xs).sum()
            )
        row["label_revealing_terms"] = int(sub["label_revealing_terms"].sum())
        rows.append(row)
    for year, sub in table.groupby("commitment_year", sort=True):
        warn = int(sub["retrospective_text_warning"].sum())
        rows.append(
            {
                "scope": f"year={year}",
                "records": len(sub),
                "retrospective_text_warning": warn,
                "share_warning": _share(warn, len(sub)),
            }
        )
    return rows


def _split_summary(membership: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for col in SPLIT_COLUMNS:
        for value, sub in membership.groupby(col, sort=True):
            years = sub["commitment_year"].dropna()
            rows.append(
                {
                    "protocol": col.removeprefix("split_"),
                    "split": value,
                    "records": len(sub),
                    "groups": int(sub["leakage_group_id"].nunique()),
                    "climate_related": int(sub["is_climate_related"].fillna(False).sum()),
                    "positive_share": _share(
                        int(sub["is_climate_related"].fillna(False).sum()), len(sub)
                    ),
                    "pakistan": int((sub["recipient_iso3"] == "PAK").fillna(False).sum()),
                    "year_min": int(years.min()) if len(years) else None,
                    "year_max": int(years.max()) if len(years) else None,
                }
            )
    return rows


def _pakistan_coverage(membership: pd.DataFrame, energy: str) -> list[dict[str, object]]:
    pk = membership[(membership["recipient_iso3"] == "PAK").fillna(False).astype(bool)]
    rows: list[dict[str, object]] = []
    for col in SPLIT_COLUMNS:
        for value, sub in pk.groupby(col, sort=True):
            for stratum, ss in (
                ("all", sub),
                (energy, sub[sub["sector_name"] == energy]),
                (f"non-{energy}", sub[sub["sector_name"] != energy]),
            ):
                rows.append(
                    {
                        "protocol": col.removeprefix("split_"),
                        "split": value,
                        "sector_stratum": stratum,
                        "records": len(ss),
                        "climate_related": int(ss["is_climate_related"].fillna(False).sum()),
                        "groups": int(ss["leakage_group_id"].nunique()),
                    }
                )
    excluded = membership[membership["split_pakistan_holdout"] == EXCLUDED_PK_GROUP_MATE]
    rows.append(
        {
            "protocol": "pakistan_holdout",
            "split": EXCLUDED_PK_GROUP_MATE,
            "sector_stratum": "all (non-Pakistan records)",
            "records": len(excluded),
            "climate_related": int(excluded["is_climate_related"].fillna(False).sum()),
            "groups": int(excluded["leakage_group_id"].nunique()),
        }
    )
    return rows


# ---------------------------------------------------------------------------- build
def build(layout: DataLayout, config_path: Path = DEFAULT_CONFIG) -> BuildResult:
    hashes = _verified_hashes(layout)
    config = load_split_config(config_path)
    data = SourceData(layout)
    joined, join_report = join_research_aiddata(data.research_climate, data.aiddata)
    table, originals = build_research_table(joined, hashes["research_paper"], hashes["aiddata"])
    table = assign_eligibility(table)
    table, relation_groups = add_groups(table)
    membership = build_membership(table, config)

    violations = {c: check_disjoint(membership, c) for c in SPLIT_COLUMNS}
    if any(violations.values()):
        raise PipelineError(f"Group leakage across splits: {violations}")
    pk_rows_in_training = int(
        (
            membership["split_pakistan_holdout"].isin(["train", "validation"])
            & (membership["recipient_iso3"] == "PAK").fillna(False)
        ).sum()
    )
    if pk_rows_in_training:
        raise PipelineError("Pakistan records found in Pakistan-holdout training/validation")

    leakage_summary, largest, dist = _leakage_report(table, relation_groups, config)
    conflict_rows = _conflict_review(table)
    status_counts = table["eligibility_status"].value_counts().to_dict()
    summary: dict[str, object] = {
        "split_version": config.version,
        "seed": config.seed,
        "join": join_report.as_dict(),
        "rows": len(table),
        "eligibility": {str(k): int(v) for k, v in sorted(status_counts.items())},
        "climate_related": int(table["is_climate_related"].fillna(False).sum()),
        "pakistan": int(table["is_pakistan"].sum()),
        "rio_overall_is_max_all_rows": bool(table["rio_overall_is_max"].fillna(False).all()),
        "cleaning_step_counts": {
            col: dict(
                sorted(Counter(s for v in table[col] for s in (v.split("|") if v else [])).items())
            )
            for col in ("title_cleaning_steps", "description_cleaning_steps")
        },
        "research_title_differs": int(table["research_title_differs"].sum()),
        "research_title_truncated_255": int(table["research_title_truncated_255"].sum()),
        "research_description_differs": int(table["research_description_differs"].sum()),
        "conflicting_description_groups": len({r["description_group"] for r in conflict_rows}),
        "conflicting_description_records": len(conflict_rows),
        "leakage": leakage_summary,
        "disjointness_violations": {c: len(v) for c, v in violations.items()},
        "pakistan_rows_in_holdout_training": pk_rows_in_training,
    }
    reports = {
        "eligibility_report": _eligibility_report(table),
        "conflicting_label_review": conflict_rows,
        "leakage_largest_groups": largest,
        "leakage_group_size_distribution": dist,
        "split_summary": _split_summary(membership),
        "pakistan_split_coverage": _pakistan_coverage(
            membership, config.pakistan_holdout.report_strata["sector_energy"]
        ),
        "retrospective_warning_report": _retrospective_report(table),
        "field_completeness": _completeness(table),
    }
    return BuildResult(table, originals, membership, reports, summary)


# ---------------------------------------------------------------------------- write
def _write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(frame, preserve_index=False)
    table = table.replace_schema_metadata({b"compassio": b"research_v1"})
    pq.write_table(table, path, compression="zstd", write_statistics=True)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    columns: list[str] = []
    for row in rows:
        columns += [k for k in row if k not in columns]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if v is None else v) for k, v in row.items()})


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_outputs(result: BuildResult, processed_dir: Path, report_dir: Path) -> dict[str, str]:
    report_dir.mkdir(parents=True, exist_ok=True)
    data_files = {
        "research_projects.parquet": result.table,
        "research_text_originals.parquet": result.originals,
        "research_split_membership_v1.parquet": result.membership,
    }
    written: list[Path] = []
    for name, frame in data_files.items():
        path = processed_dir / name
        _write_parquet(frame, path)
        written.append(path)
    for name, rows in result.reports.items():
        path = report_dir / f"{name}.csv"
        _write_csv(path, rows)
        written.append(path)
    summary_path = report_dir / "build_summary.json"
    summary_path.write_text(
        json.dumps(result.summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    written.append(summary_path)

    checksums = {p.name: _sha256(p) for p in written}
    (report_dir / "checksums.json").write_text(
        json.dumps(checksums, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (report_dir / "pipeline_metadata.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "python": platform.python_version(),
                "packages": {
                    p: version(p)
                    for p in ("compassio-ml", "pandas", "pyarrow", "openpyxl", "pyyaml")
                },
                "deterministic_outputs": sorted(checksums),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return checksums
