"""Issue, check, validate, adjudicate and freeze human-review worksheets.

Layout under ``labeling/<build_id>/``::

    reviewers.template.yaml        placeholder registry (never valid as-is)
    reviewers.yaml                 created by the team: genuine reviewers (git-ignored)
    external_test_pilot_v1/
        reviewer_A.csv, reviewer_B.csv   blind, empty sheets to hand out
        issued_items.parquet             item_id + exact issued text (validation reference)
        worksheet_manifest.json          SHA-256 of every issued sheet
        completed/                       reviewers save completed copies here (same names)
        adjudication/adjudication_sheet.csv            generated after A and B are complete
        adjudication/completed/adjudication_sheet.csv  returned by the adjudicator
    training_label_audit_v1/
        reviewer.csv, issued_items.parquet, worksheet_manifest.json, completed/

Pilot items come only from ``external_test_candidate`` (World Bank; GCF is rights-restricted);
audit items only from ``training_candidate`` donor-labelled records. Nothing here fills a
reviewer, adjudicator or final-label value.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from compassio_ml.external.labeling import (
    ADJUDICATION_CONTEXT_COLUMNS,
    ADJUDICATOR_COLUMNS,
    FINAL_STATUSES,
    LABEL_POLICY_VERSION,
    REVIEWER_COLUMNS,
    REVIEWERS_TEMPLATE,
    WORKSHEET_COLUMNS,
    LabelRecord,
    ReviewerLabel,
    ReviewValidation,
    ReviewWorkflowError,
    agreement,
    build_worksheet,
    cohen_kappa,
    item_id,
    load_reviewers,
    read_sheet,
    validate_completed,
    write_csv,
)
from compassio_ml.external.partition import (
    DEVELOPMENT_PARTITIONS,
    EXTERNAL,
    SEED,
    TRAIN,
    sample_pilot,
)
from compassio_ml.external.paths import V2Paths
from compassio_ml.external.rights import DEFAULT_RIGHTS_CONFIG, Use, load_rights
from compassio_ml.integrity import sha256_file

PILOT = "external_test_pilot_v1"
AUDIT = "training_label_audit_v1"
PILOT_SHEETS = {"reviewer_A.csv": "reviewer_a", "reviewer_B.csv": "reviewer_b"}
AUDIT_SHEETS = {"reviewer.csv": "auditor"}
AUDIT_POSITIVES = 50
AUDIT_NEGATIVES = 50


def _ordered(frame: pd.DataFrame, salt: str) -> pd.DataFrame:
    key = frame["item_id"].map(lambda i: hashlib.sha256(f"{salt}:{i}".encode()).hexdigest())
    return frame.assign(_k=key).sort_values("_k").drop(columns="_k").reset_index(drop=True)


def _write_json(data: Any, path: Path) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")


def _issue(
    directory: Path, items: pd.DataFrame, worksheet: str, sheets: dict[str, str], build_id: str
) -> pd.DataFrame:
    (directory / "completed").mkdir(parents=True, exist_ok=True)
    sheet = build_worksheet(items, worksheet)
    for name in sheets:
        write_csv(_ordered(sheet, name), directory / name)
    issued = sheet[["item_id", "title", "description"]].assign(
        candidate_id=items["candidate_id"].to_numpy()
    )
    issued.to_parquet(directory / "issued_items.parquet", index=False)
    _write_json(
        {
            "worksheet": worksheet,
            "build_id": build_id,
            "label_policy_version": LABEL_POLICY_VERSION,
            "issued_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "items": len(sheet),
            "sheets": {
                name: {"role": role, "sha256": sha256_file(directory / name)}
                for name, role in sheets.items()
            },
            "issued_items_sha256": sha256_file(directory / "issued_items.parquet"),
        },
        directory / "worksheet_manifest.json",
    )
    return sheet


def create_worksheets(paths: V2Paths, build_dir: Path) -> list[str]:
    build_id = build_dir.name
    sealed = paths.writable(paths.sealed / build_id)
    labeling = paths.writable(paths.labeling / build_id)
    pilot_path = sealed / "pilot_v1.parquet"
    if pilot_path.exists():
        raise FileExistsError(f"Pilot already sampled for {build_id}: {pilot_path}")
    pool = pd.read_parquet(sealed / "candidate_pool.parquet")
    candidates = pd.read_parquet(build_dir / "candidates.parquet")
    rights = load_rights(paths.repo_root / DEFAULT_RIGHTS_CONFIG)
    forbidden = {
        str(s)
        for s in set(pool["source_id"]) | set(candidates["source_id"])
        if not rights.permitted(str(s), Use.HUMAN_REVIEW)
    }
    if forbidden:
        raise ReviewWorkflowError(f"Sources not permitted for human review: {sorted(forbidden)}")
    labeling.mkdir(parents=True, exist_ok=True)
    template = labeling / "reviewers.template.yaml"
    if not template.exists():
        template.write_text(REVIEWERS_TEMPLATE, encoding="utf-8")

    pool = pool[pool["has_usable_text"] & (pool["v2_partition"] == EXTERNAL)]
    pilot = sample_pilot(pool, seed=SEED)
    pilot.to_parquet(pilot_path, index=False)
    _issue(labeling / PILOT, pilot, PILOT, PILOT_SHEETS, build_id)

    donor = candidates[
        (candidates["v2_partition"] == TRAIN)
        & candidates["has_usable_text"]
        & (candidates["donor_marker_status"] == "explicit_both")
    ].copy()
    donor["_k"] = donor["candidate_id"].map(
        lambda c: hashlib.sha256(f"{SEED}:audit:{c}".encode()).hexdigest()
    )
    donor = donor.sort_values("_k").drop_duplicates("partition_group_id")
    positives = donor[donor["donor_rio_overall"] > 0]
    positives = pd.concat(
        [positives[~positives["is_energy_sector"]], positives[positives["is_energy_sector"]]]
    ).head(AUDIT_POSITIVES)
    negatives = donor[donor["donor_rio_overall"] == 0].head(AUDIT_NEGATIVES)
    audit = pd.concat([positives, negatives]).drop(columns="_k").reset_index(drop=True)
    _issue(labeling / AUDIT, audit, AUDIT, AUDIT_SHEETS, build_id)
    return [
        f"Pilot: {len(pilot)} items from {len(pool)} usable external-test candidates "
        f"({int(pilot['is_pakistan'].sum())} Pakistan); strata "
        f"{pilot['stratum'].value_counts().to_dict()}",
        f"Pilot sheets: {labeling / PILOT} (reviewer_A.csv, reviewer_B.csv; blind, empty)",
        f"Training-label audit: {len(audit)} items ({len(positives)} donor-positive, "
        f"{len(negatives)} donor-negative; sources {audit['source_id'].value_counts().to_dict()})",
        f"Reviewer registry template: {template}",
        f"Label policy: {LABEL_POLICY_VERSION}. No labels were assigned by code.",
    ]


# ------------------------------------------------------------------ checks
def _sheet_dirs(paths: V2Paths, build_id: str) -> dict[str, tuple[Path, dict[str, str]]]:
    root = paths.labeling / build_id
    return {PILOT: (root / PILOT, PILOT_SHEETS), AUDIT: (root / AUDIT, AUDIT_SHEETS)}


def check_worksheets(paths: V2Paths, build_dir: Path) -> dict[str, Any]:
    """Readiness check of the ISSUED sheets (not of reviews)."""
    build_id = build_dir.name
    membership = pd.read_parquet(build_dir / "partition_membership.parquet")
    role = dict(zip(membership["candidate_id"], membership["v2_partition"], strict=True))
    source = dict(zip(membership["candidate_id"], membership["source_id"], strict=True))
    consumed = set(membership.loc[membership["v1_consumed_test"].astype(bool), "candidate_id"])
    report: dict[str, Any] = {"build_id": build_id, "errors": []}
    errors: list[str] = report["errors"]
    rights = load_rights(paths.repo_root / DEFAULT_RIGHTS_CONFIG)
    allowed = {PILOT: {EXTERNAL}, AUDIT: set(DEVELOPMENT_PARTITIONS)}
    for worksheet, (directory, sheets) in _sheet_dirs(paths, build_id).items():
        manifest = json.loads((directory / "worksheet_manifest.json").read_text("utf-8"))
        issued = pd.read_parquet(directory / "issued_items.parquet")
        entry: dict[str, Any] = {"items": len(issued), "sheets": {}}
        if sha256_file(directory / "issued_items.parquet") != manifest["issued_items_sha256"]:
            errors.append(f"{worksheet}: issued_items.parquet changed")
        for name in sheets:
            frame = read_sheet(directory / name)
            intact = sha256_file(directory / name) == manifest["sheets"][name]["sha256"]
            empty = bool((frame[REVIEWER_COLUMNS] == "").all().all())
            entry["sheets"][name] = {
                "rows": len(frame),
                "unchanged_since_issue": intact,
                "reviewer_columns_empty": empty,
            }
            if list(frame.columns) != WORKSHEET_COLUMNS:
                errors.append(f"{worksheet}/{name}: unexpected columns")
            if set(frame.columns) & set(ADJUDICATION_CONTEXT_COLUMNS):
                errors.append(f"{worksheet}/{name}: source labels present")
            if not intact or not empty:
                errors.append(f"{worksheet}/{name}: issued sheet modified or not empty")
            if frame["item_id"].duplicated().any() or set(frame["item_id"]) != set(
                issued["item_id"]
            ):
                errors.append(f"{worksheet}/{name}: item IDs differ from issued_items")
            if (frame["description"].str.len() < 100).any():
                errors.append(f"{worksheet}/{name}: item without usable description")
        ids = issued["candidate_id"]
        bad_role = [c for c in ids if role.get(c) not in allowed[worksheet]]
        if bad_role:
            errors.append(
                f"{worksheet}: {len(bad_role)} items outside {sorted(allowed[worksheet])}"
            )
        if set(ids) & consumed:
            errors.append(f"{worksheet}: contains consumed v1 test records")
        if any(not rights.permitted(str(source.get(c)), Use.HUMAN_REVIEW) for c in ids):
            errors.append(f"{worksheet}: contains sources not permitted for human review")
        if any(item_id(worksheet, c) != i for c, i in zip(ids, issued["item_id"], strict=True)):
            errors.append(f"{worksheet}: item_id does not match candidate_id")
        entry["sources"] = {
            str(k): int(v)
            for k, v in pd.Series([source.get(c) for c in ids]).value_counts().items()
        }
        report[worksheet] = entry
    report["ready_for_reviewers"] = not errors
    return report


# ------------------------------------------------------------------ reviews
def _validate_all(paths: V2Paths, build_id: str) -> dict[str, dict[str, ReviewValidation]]:
    registry = load_reviewers(paths.labeling / build_id / "reviewers.yaml")
    out: dict[str, dict[str, ReviewValidation]] = {}
    for worksheet, (directory, sheets) in _sheet_dirs(paths, build_id).items():
        issued = pd.read_parquet(directory / "issued_items.parquet")
        out[worksheet] = {
            name: validate_completed(
                directory / "completed" / name, expected=issued, registry=registry, role=role
            )
            for name, role in sheets.items()
            if (directory / "completed" / name).is_file()
        }
    return out


def validate_reviews(paths: V2Paths, build_dir: Path) -> dict[str, Any]:
    build_id = build_dir.name
    report: dict[str, Any] = {"build_id": build_id, "errors": []}
    registry_path = paths.labeling / build_id / "reviewers.yaml"
    if not registry_path.is_file():
        report["reviewer_registry"] = "missing (no reviews can be accepted yet)"
        for worksheet, (directory, sheets) in _sheet_dirs(paths, build_id).items():
            report[worksheet] = {
                "completed_files": sorted(
                    n for n in sheets if (directory / "completed" / n).is_file()
                )
            }
        report["human_verified_labels"] = 0
        return report
    results = _validate_all(paths, build_id)
    for worksheet, files in results.items():
        entry: dict[str, Any] = {}
        for name, res in files.items():
            report["errors"].extend(res.errors)
            entry[name] = {
                "valid": len(res.valid),
                "blank": res.blank_rows,
                "issued": res.total_rows,
                "complete": res.complete,
            }
        if worksheet == PILOT and set(PILOT_SHEETS) <= set(files):
            entry["agreement"] = agreement(
                files["reviewer_A.csv"].valid, files["reviewer_B.csv"].valid
            )
        if worksheet == AUDIT and "reviewer.csv" in files and files["reviewer.csv"].complete:
            entry["donor_vs_human"] = audit_summary(paths, build_dir, files["reviewer.csv"].valid)
        report[worksheet] = entry
    sealed = paths.sealed / build_id / "external_test_labels.lock.json"
    report["human_verified_labels"] = (
        json.loads(sealed.read_text("utf-8"))["verified_items"] if sealed.is_file() else 0
    )
    return report


def audit_summary(paths: V2Paths, build_dir: Path, labels: list[ReviewerLabel]) -> dict[str, Any]:
    """Compare one auditor's labels with the (hidden) donor markers of training records."""
    issued = pd.read_parquet(paths.labeling / build_dir.name / AUDIT / "issued_items.parquet")
    candidates = pd.read_parquet(build_dir / "candidates.parquet")
    by_candidate = {
        str(c): (int(m), int(a))
        for c, m, a in zip(
            candidates["candidate_id"],
            candidates["donor_rio_mitigation"],
            candidates["donor_rio_adaptation"],
            strict=True,
        )
        if pd.notna(m) and pd.notna(a)
    }
    donor: dict[str, tuple[int, int]] = {
        str(i): by_candidate[str(c)]
        for i, c in zip(issued["item_id"], issued["candidate_id"], strict=True)
    }
    scored = [x for x in labels if not x.insufficient_information]
    human_bin = [int((x.rio_overall or 0) > 0) for x in scored]
    donor_bin = [int(max(donor[x.item_id]) > 0) for x in scored]
    return {
        "items_scored": len(scored),
        "items_insufficient_information": len(labels) - len(scored),
        "binary_agreement": (
            sum(h == d for h, d in zip(human_bin, donor_bin, strict=True)) / len(scored)
            if scored
            else None
        ),
        "binary_cohen_kappa": cohen_kappa(human_bin, donor_bin),
        "donor_positive_human_negative": sum(
            d == 1 and h == 0 for h, d in zip(human_bin, donor_bin, strict=True)
        ),
        "donor_negative_human_positive": sum(
            d == 0 and h == 1 for h, d in zip(human_bin, donor_bin, strict=True)
        ),
        "note": "single human reviewer vs donor self-report; describes training-label noise",
    }


def _needs_adjudication(a: ReviewerLabel, b: ReviewerLabel) -> str | None:
    if a.insufficient_information or b.insufficient_information:
        return "insufficient_information"
    if a.flag_needs_discussion or b.flag_needs_discussion:
        return "flagged_for_discussion"
    if a.scores != b.scores:
        return "disagreement"
    return None


def _pilot_pair(
    paths: V2Paths, build_id: str
) -> tuple[dict[str, ReviewerLabel], dict[str, ReviewerLabel]]:
    files = _validate_all(paths, build_id)[PILOT]
    if set(PILOT_SHEETS) - set(files):
        raise ReviewWorkflowError("Both completed reviewer_A.csv and reviewer_B.csv are required")
    for name, res in files.items():
        if not res.complete:
            raise ReviewWorkflowError(
                f"{name} incomplete or invalid: {res.blank_rows} blank, {len(res.errors)} errors"
            )
    a = {x.item_id: x for x in files["reviewer_A.csv"].valid}
    b = {x.item_id: x for x in files["reviewer_B.csv"].valid}
    if {x.reviewer_id for x in a.values()} & {x.reviewer_id for x in b.values()}:
        raise ReviewWorkflowError("reviewers A and B must be different people")
    return a, b


def create_adjudication_sheet(paths: V2Paths, build_dir: Path) -> Path:
    build_id = build_dir.name
    a, b = _pilot_pair(paths, build_id)
    pilot = pd.read_parquet(paths.sealed / build_id / "pilot_v1.parquet")
    pilot["item_id"] = [item_id(PILOT, c) for c in pilot["candidate_id"]]
    context = pilot.set_index("item_id")
    rows = []
    for iid in sorted(a):
        reason = _needs_adjudication(a[iid], b[iid])
        row: dict[str, Any] = {
            "item_id": iid,
            "needs_adjudication": bool(reason),
            "reason": reason or "agree",
        }
        for tag, lab in (("a", a[iid]), ("b", b[iid])):
            row.update(
                {
                    f"{tag}_reviewer_id": lab.reviewer_id,
                    f"{tag}_rio_mitigation": lab.rio_mitigation,
                    f"{tag}_rio_adaptation": lab.rio_adaptation,
                    f"{tag}_insufficient_information": lab.insufficient_information,
                    f"{tag}_evidence_quote": lab.evidence_quote,
                    f"{tag}_rationale": lab.rationale,
                }
            )
        for column in ADJUDICATION_CONTEXT_COLUMNS:
            row[column] = context.loc[iid, column] if column in context.columns else ""
        row["title"] = context.loc[iid, "title_clean"]
        row["description"] = context.loc[iid, "description_clean"]
        row.update(dict.fromkeys(ADJUDICATOR_COLUMNS, ""))
        rows.append(row)
    out = paths.writable(paths.labeling / build_id / PILOT / "adjudication")
    (out / "completed").mkdir(parents=True, exist_ok=True)
    path = out / "adjudication_sheet.csv"
    write_csv(pd.DataFrame(rows), path)
    return path


def freeze_pilot_labels(paths: V2Paths, build_dir: Path) -> Path:
    """Write sealed, adjudicated external-test labels. Refuses unless every item is resolved."""
    build_id = build_dir.name
    sealed = paths.writable(paths.sealed / build_id)
    target = sealed / "external_test_labels.parquet"
    if target.exists():
        raise FileExistsError(f"Labels already frozen: {target}")
    a, b = _pilot_pair(paths, build_id)
    registry = load_reviewers(paths.labeling / build_id / "reviewers.yaml")
    done = (
        paths.labeling / build_id / PILOT / "adjudication" / "completed" / "adjudication_sheet.csv"
    )
    adjudicated = read_sheet(done).set_index("item_id") if done.is_file() else None
    pilot = pd.read_parquet(sealed / "pilot_v1.parquet")
    records: list[dict[str, Any]] = []
    for row in pilot.to_dict("records"):
        iid = item_id(PILOT, str(row["candidate_id"]))
        ra, rb = a[iid], b[iid]
        reason = _needs_adjudication(ra, rb)
        fields: dict[str, Any] = {"disagreement_status": "agree" if reason is None else reason}
        if reason is None:
            fields.update(
                final_rio_mitigation=ra.rio_mitigation,
                final_rio_adaptation=ra.rio_adaptation,
                final_label_status="verified",
            )
        else:
            if adjudicated is None or iid not in adjudicated.index:
                raise ReviewWorkflowError(f"{iid}: requires adjudication ({reason})")
            adj = adjudicated.loc[iid]
            who = str(adj["adjudicator_id"]).strip()
            status = str(adj["final_status"]).strip()
            if not registry.has_role(who, "adjudicator"):
                raise ReviewWorkflowError(f"{iid}: adjudicator {who!r} not registered")
            if status not in FINAL_STATUSES:
                raise ReviewWorkflowError(f"{iid}: final_status must be one of {FINAL_STATUSES}")
            fields.update(
                adjudicated_by=who,
                adjudication_rationale=str(adj["adjudication_rationale"]),
                final_label_status=status,
            )
            if status == "verified":
                fields.update(
                    final_rio_mitigation=int(str(adj["final_rio_mitigation"])),
                    final_rio_adaptation=int(str(adj["final_rio_adaptation"])),
                )
        record = LabelRecord(
            item_id=iid,
            source_id=str(row["source_id"]),
            publisher=str(row["publisher"]),
            source_project_id=str(row["source_record_id"]),
            document_url=row["document_url"],
            description_sha256=row["description_sha256"],
            document_date=row["text_date"],
            document_version=f"{row['retrieval_id']}:{str(row['raw_file_sha256'])[:16]}",
            reviewer_a=ra,
            reviewer_b=rb,
            split_eligibility="external_test",
            **fields,
        )
        flat = record.model_dump(exclude={"reviewer_a", "reviewer_b"})
        flat.update(
            reviewer_a_id=ra.reviewer_id,
            reviewer_b_id=rb.reviewer_id,
            stratum=row["stratum"],
            inclusion_probability=row["inclusion_probability"],
        )
        records.append(flat)
    frame = pd.DataFrame(records)
    frame.to_parquet(target, index=False)
    stats = agreement(list(a.values()), list(b.values()))
    stats.pop("disagreements", None)
    _write_json(
        {
            "build_id": build_id,
            "label_policy_version": LABEL_POLICY_VERSION,
            "frozen_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "sha256": sha256_file(target),
            "items": len(frame),
            "verified_items": int((frame["final_label_status"] == "verified").sum()),
            "needs_review_items": int((frame["final_label_status"] == "needs_review").sum()),
            "agreement": stats,
        },
        sealed / "external_test_labels.lock.json",
    )
    return target
