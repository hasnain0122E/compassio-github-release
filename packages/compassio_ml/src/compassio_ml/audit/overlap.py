"""Cross-source overlap investigation. Nothing is merged.

Status vocabulary:
  * ``same_record_stable_id``   - shared stable identifier; same record re-published.
  * ``same_record_text_differs`` - stable id matches but a text field differs.
  * ``probable_match_reference_code`` - a source reference code (e.g. FP085) appears in text.
  * ``possible_match_requires_review`` - normalized names agree; NOT proof of identity.
  * ``related_not_same`` - linked records (e.g. tranches) that must stay distinct.
  * ``summary`` - aggregate statement about the relation.
"""

import re
from dataclasses import dataclass, field

import pandas as pd

from compassio_ml.audit.inspectors import adb_project_number
from compassio_ml.audit.loaders import SourceData
from compassio_ml.audit.models import OverlapRow
from compassio_ml.data.inventory import Inventory
from compassio_ml.data.parsing import normalize_text, split_country_list

_GCF_REF = re.compile(r"\b(FP|SAP)[ -]?0*(\d{1,3})\b")


def gcf_refs_in_text(text: str | None) -> set[str]:
    """Extract GCF reference codes such as FP085 / SAP024 from free text."""
    if not text:
        return set()
    return {f"{p}{int(n):03d}" for p, n in _GCF_REF.findall(text.upper())}


@dataclass
class OverlapResult:
    rows: list[OverlapRow] = field(default_factory=list)
    facts: dict[str, object] = field(default_factory=dict)

    def add(self, *args: str) -> None:
        keys = (
            "left_source",
            "left_key",
            "right_source",
            "right_key",
            "match_method",
            "status",
            "evidence",
        )
        self.rows.append(OverlapRow(**dict(zip(keys, args, strict=True))))


def _research_vs_aiddata(data: SourceData, out: OverlapResult) -> None:
    cf, ad = data.research_climate, data.aiddata
    left, right = set(cf["AidData_Record_ID"]), set(ad["AidData Record ID"])
    j = cf.merge(
        ad, left_on="AidData_Record_ID", right_on="AidData Record ID", suffixes=("", "_ad")
    )
    comparisons = {
        "Title": "Title_ad",
        "Description": "Description_ad",
        "Commitment_Year": "Commitment Year",
        "Recipient": "Recipient_ad",
        "Sector_Name": "Sector Name",
        "Flow_Type": "Flow Type",
    }
    equal = {
        k: int((j[k].fillna("").str.strip() == j[v].fillna("").str.strip()).sum())
        for k, v in comparisons.items()
    }
    normalized_equal = {
        k: int((j[k].map(normalize_text) == j[v].map(normalize_text)).sum())
        for k in ("Title", "Description")
        for v in [comparisons[k]]
    }
    ra = pd.to_numeric(j["Amount_Constant_USD_2021"], errors="coerce")
    aa = pd.to_numeric(j["Amount (Constant USD 2021)"], errors="coerce")
    within_cent = int((((ra - aa).abs() <= 0.0051) | (ra.isna() & aa.isna())).sum())
    summary: dict[str, object] = {
        "research_ids": len(left),
        "aiddata_ids": len(right),
        "matched": len(left & right),
        "research_only": len(left - right),
        "aiddata_only": len(right - left),
        "field_exact_equal": equal,
        "field_normalized_equal": normalized_equal,
        "amount_equal_within_half_cent": within_cent,
    }
    out.facts["research_vs_aiddata"] = summary
    out.add(
        "research_paper",
        "*",
        "aiddata",
        "*",
        "AidData_Record_ID == AidData Record ID",
        "summary",
        f"{len(left & right)} of {len(left)} research rows matched; {len(right - left)} AidData "
        f"rows unmatched; amounts equal within $0.005 for {within_cent}",
    )
    truncated = 0
    for col in ("Title", "Description"):
        diff = j[j[col].fillna("").str.strip() != j[comparisons[col]].fillna("").str.strip()]
        for _, row in diff.sort_values("AidData_Record_ID", key=lambda s: s.astype(int)).iterrows():
            ours, theirs = str(row[col] or ""), str(row[comparisons[col]] or "")
            if len(ours) == 255 and theirs.startswith(ours):
                truncated += 1
                evidence = f"{col} truncated to 255 characters (AidData has {len(theirs)})"
            elif normalize_text(ours) == normalize_text(theirs):
                evidence = f"{col} differs only in whitespace/punctuation/case"
            else:
                evidence = f"{col} differs in content"
            rid = str(row["AidData_Record_ID"])
            out.add(
                "research_paper",
                rid,
                "aiddata",
                rid,
                "AidData_Record_ID",
                "same_record_text_differs",
                evidence,
            )
    summary["text_truncated_to_255"] = truncated


def _aiddata_packages(data: SourceData, out: OverlapResult) -> None:
    ad = data.aiddata
    parents = ad["AidData Parent ID"].dropna()
    counts = parents.value_counts()
    out.add(
        "aiddata",
        "*",
        "aiddata",
        "*",
        "AidData Parent ID",
        "related_not_same",
        f"{int((counts > 1).sum())} linked packages, {int(counts[counts > 1].sum())} records",
    )


def _inventory_copies(inventory: Inventory, out: OverlapResult) -> None:
    groups = inventory.duplicate_hash_groups
    out.facts["duplicate_file_hash_groups"] = [list(g) for g in groups]
    out.add(
        "(all)",
        "*",
        "(all)",
        "*",
        "SHA-256 of raw files",
        "summary",
        f"{len(inventory.records)} files, {inventory.distinct_file_count} distinct hashes, "
        f"{len(groups)} duplicate-content groups",
    )


def _gcf_projects_vs_historical(data: SourceData, out: OverlapResult) -> None:
    gp, gh = data.gcf_projects, data.gcf_historical
    gh = gh[gh["Ref_N"].notna()]
    current = dict(zip(gp["Ref #"], gp["Theme"], strict=True))
    hist = dict(zip(gh["Ref_N"].str.strip(), gh["Theme"], strict=True))
    matched = sorted(set(current) & set(hist), key=lambda r: (r[:2], int(re.sub(r"\D", "", r))))
    theme_equal = sum(current[r] == hist[r] for r in matched)
    out.facts["gcf_projects_vs_historical"] = {
        "historical_refs": len(hist),
        "matched": len(matched),
        "historical_only": sorted(set(hist) - set(current)),
        "theme_equal": theme_equal,
    }
    out.add(
        "gcf_projects",
        "*",
        "gcf_historical",
        "*",
        "Ref # == Ref_N",
        "summary",
        f"{len(matched)} of {len(hist)} historical refs found in current export; theme equal for "
        f"{theme_equal}",
    )
    for ref in matched:
        out.add(
            "gcf_projects",
            ref,
            "gcf_historical",
            ref,
            "Ref # == Ref_N",
            "same_record_stable_id",
            "theme equal"
            if current[ref] == hist[ref]
            else f"theme {current[ref]!r} vs {hist[ref]!r}",
        )
    for ref in sorted(set(hist) - set(current)):
        out.add(
            "gcf_historical",
            ref,
            "gcf_projects",
            "",
            "Ref_N",
            "summary",
            "Historical ref absent from current export (withdrawn/renumbered? needs review)",
        )


def _gcf_vs_cfu(data: SourceData, out: OverlapResult) -> None:
    gp = data.gcf_projects
    cfu = data.cfu["Projects"]
    gcf_rows = cfu[cfu["Fund"].fillna("").str.contains("GCF")]
    names = dict(zip(gp["Ref #"], gp["Project Name"], strict=True))
    by_ref: dict[str, list[int]] = {}
    for idx, name in zip(gcf_rows.index, gcf_rows["Name of Project"], strict=True):
        for ref in gcf_refs_in_text(name):
            by_ref.setdefault(ref, []).append(int(idx))
    by_name: dict[str, list[int]] = {}
    for idx, name in zip(gcf_rows.index, gcf_rows["Name of Project"], strict=True):
        stripped = _GCF_REF.sub(" ", str(name or "").upper())
        by_name.setdefault(normalize_text(stripped), []).append(int(idx))

    ref_matched = name_only = multi = 0
    for ref in gp["Ref #"]:
        hits = by_ref.get(ref, [])
        method = "GCF reference code in CFU 'Name of Project'"
        status = "probable_match_reference_code"
        if not hits:
            hits = by_name.get(normalize_text(names[ref]), [])
            method = "normalized project name (reference code removed)"
            status = "possible_match_requires_review"
            name_only += bool(hits)
        else:
            ref_matched += 1
        multi += len(hits) > 1
        for idx in hits:
            row = cfu.loc[idx]
            same_name = normalize_text(_GCF_REF.sub(" ", str(row["Name of Project"]).upper())) == (
                normalize_text(names[ref])
            )
            out.add(
                "gcf_projects",
                ref,
                "climate_funds_update",
                f"Projects!row{idx + 2}",
                method,
                status,
                f"CFU fund {row['Fund']!r}, country {row['Country']!r}, approved "
                f"{row['Approved year']}; name {'matches' if same_name else 'differs'}"
                + (
                    "; several CFU rows for this project (e.g. per country)"
                    if len(hits) > 1
                    else ""
                ),
            )
    unmatched_cfu_refs = sorted(set(by_ref) - set(gp["Ref #"]))
    out.facts["gcf_projects_vs_cfu"] = {
        "cfu_gcf_rows": len(gcf_rows),
        "cfu_gcf_rows_excluding_irm_readiness": int((~gcf_rows["Fund"].str.contains("IRM")).sum()),
        "cfu_rows_with_gcf_ref_code": sum(len(v) for v in by_ref.values()),
        "distinct_ref_codes_in_cfu": len(by_ref),
        "gcf_projects_matched_by_ref_code": ref_matched,
        "gcf_projects_matched_by_name_only": name_only,
        "gcf_projects_with_multiple_cfu_rows": multi,
        "cfu_ref_codes_not_in_gcf_export": unmatched_cfu_refs,
    }
    out.add(
        "gcf_projects",
        "*",
        "climate_funds_update",
        "*",
        "reference code, then name",
        "summary",
        f"{ref_matched} of {len(gp)} GCF projects found in CFU by reference code, {name_only} more "
        f"by name only; {len(unmatched_cfu_refs)} CFU reference codes absent from the GCF export",
    )


def _readiness_vs_cfu(data: SourceData, out: OverlapResult) -> None:
    gr = data.gcf_readiness
    cfu = data.cfu["Projects"]
    irm = cfu[cfu["Fund"].fillna("").str.contains("GCF")]
    keys = {
        (normalize_text(n), normalize_text(c))
        for n, c in zip(irm["Name of Project"], irm["Country"], strict=True)
    }
    hits = sum(
        (normalize_text(t), normalize_text(c)) in keys
        for t, c in zip(gr["Project Title"], gr["Country"], strict=True)
    )
    out.facts["gcf_readiness_vs_cfu"] = {"readiness_rows": len(gr), "title_and_country_match": hits}
    out.add(
        "gcf_readiness",
        "*",
        "climate_funds_update",
        "*",
        "normalized title + country",
        "summary",
        f"{hits} of {len(gr)} readiness rows have a CFU GCF row with the same title and country "
        "(possible matches; readiness titles are generic, e.g. 'NDA Strengthening')",
    )


def _cpe_vs_gcf(data: SourceData, out: OverlapResult) -> None:
    cpe, gp = data.cpe, data.gcf_projects
    gcf_names = {normalize_text(n): r for r, n in zip(gp["Ref #"], gp["Project Name"], strict=True)}
    gcf_refs = set(gp["Ref #"])
    families = cpe[cpe["Source"] == "GCF"].groupby("Family URL")
    by_ref = by_name = 0
    for url, docs in families:
        refs: set[str] = set()
        for col in ("Family Name", "Document Title", "Family Summary"):
            for text in docs[col].fillna(""):
                refs |= gcf_refs_in_text(text)
        refs &= gcf_refs
        name = docs["Family Name"].iloc[0]
        name_ref = gcf_names.get(normalize_text(name))
        for ref in sorted(refs):
            by_ref += 1
            out.add(
                "climate_project_explorer",
                str(url),
                "gcf_projects",
                ref,
                "GCF reference code found in CPE family/document text",
                "probable_match_reference_code",
                f"family {str(name)[:60]!r}" + ("; name also matches" if name_ref == ref else ""),
            )
        if name_ref and name_ref not in refs:
            by_name += 1
            out.add(
                "climate_project_explorer",
                str(url),
                "gcf_projects",
                name_ref,
                "normalized family name == GCF project name",
                "possible_match_requires_review",
                f"family {str(name)[:60]!r}",
            )
    out.facts["cpe_vs_gcf"] = {
        "cpe_gcf_families": families.ngroups,
        "matched_by_reference_code": by_ref,
        "matched_by_name_only": by_name,
    }
    out.add(
        "climate_project_explorer",
        "*",
        "gcf_projects",
        "*",
        "reference code / name",
        "summary",
        f"{families.ngroups} CPE GCF families; {by_ref} reference-code, {by_name} name-only links",
    )


def _adb_titles(data: SourceData, out: OverlapResult) -> None:
    acts = data.adb.activities
    acts = acts.assign(
        _proj=acts["iati_identifier"].map(adb_project_number), _t=acts["title"].map(normalize_text)
    )
    cross = 0
    for _title, grp in acts.groupby("_t"):
        if len(grp) < 2:
            continue
        projects = sorted(set(grp["_proj"].dropna()))
        status = "related_not_same"
        if len(projects) > 1:
            cross += 1
        out.add(
            "adb_pakistan",
            "|".join(sorted(grp["iati_identifier"])),
            "adb_pakistan",
            "|".join(projects),
            "identical normalized title",
            status,
            f"{len(grp)} instruments share title {str(grp['title'].iloc[0])[:60]!r} across "
            f"{len(projects)} project number(s)",
        )
    out.facts["adb_title_groups_spanning_projects"] = cross

    gp = data.gcf_projects
    gp_pk = gp[gp["Countries"].map(lambda c: "Pakistan" in split_country_list(c))]
    adb_names = {
        normalize_text(t): i for t, i in zip(acts["title"], acts["iati_identifier"], strict=True)
    }
    for ref, name, entity in zip(
        gp_pk["Ref #"], gp_pk["Project Name"], gp_pk["Entity"], strict=True
    ):
        hit = adb_names.get(normalize_text(name))
        if hit or entity == "ADB":
            out.add(
                "gcf_projects",
                ref,
                "adb_pakistan",
                hit or "",
                "GCF Pakistan project with Entity == ADB, or same normalized title",
                "possible_match_requires_review",
                f"GCF {name[:60]!r} (entity {entity}); "
                + (
                    "same title in ADB IATI"
                    if hit
                    else "no same-title ADB activity; ADB "
                    "co-financing may be reported under a different title"
                ),
            )


_RELATIONS = (
    (("research_paper", "aiddata"), _research_vs_aiddata),
    (("aiddata",), _aiddata_packages),
    (("gcf_projects", "gcf_historical"), _gcf_projects_vs_historical),
    (("gcf_projects", "climate_funds_update"), _gcf_vs_cfu),
    (("gcf_readiness", "climate_funds_update"), _readiness_vs_cfu),
    (("climate_project_explorer", "gcf_projects"), _cpe_vs_gcf),
    (("adb_pakistan", "gcf_projects"), _adb_titles),
)


def investigate_overlap(data: SourceData, inventory: Inventory) -> OverlapResult:
    """Run every relation whose sources are all present; record skipped ones."""
    out = OverlapResult()
    _inventory_copies(inventory, out)
    present = {r.source_id for r in inventory.records if r.error is None}
    skipped = []
    for needed, relation in _RELATIONS:
        if set(needed) <= present:
            relation(data, out)
        else:
            skipped.append(relation.__name__.strip("_"))
    out.facts["skipped_relations"] = skipped
    return out
