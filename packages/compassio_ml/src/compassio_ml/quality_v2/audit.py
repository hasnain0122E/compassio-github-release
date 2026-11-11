"""Deterministic donor-label audit. Semantic warnings NEVER replace source labels."""

import hashlib
import json
import math
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from compassio_ml.external.development import _development_dir, load_development_pool
from compassio_ml.external.partition import TRAIN, VALID, check_pool_integrity
from compassio_ml.external.paths import V2Paths
from compassio_ml.external.registry import read_retrieval_manifest, verify_retrieval
from compassio_ml.external.rights import DEFAULT_RIGHTS_CONFIG, Use, load_rights
from compassio_ml.integrity import sha256_file
from compassio_ml.safety.xml import iter_xml_elements

VERSION = "donor_quality_v1"
SOURCES = frozenset({"iati_fcdo", "iati_ec_intpa"})
ATTRIBUTION = {
    "iati_fcdo": "Contains public sector information licensed under the Open Government "
    "Licence v3.0. Source: FCDO IATI; automated diagnostics added by Compassio.",
    "iati_ec_intpa": "Source: European Commission DG INTPA IATI; EU-owned content CC BY 4.0 "
    "notice, third-party rights may differ. Automated diagnostics added by Compassio.",
}
PATTERNS = {
    "mitigation": r"\b(?:mitigat\w*|decarboni\w*|low[- ]carbon|renewable\w*|solar|wind power|"
    r"energy efficien\w*|greenhouse gas\w*|emissions? reduc\w*|carbon sequestration)\b",
    "adaptation": r"\b(?:adaptation|climate[- ]resilien\w*|drought\w*|flood\w*|"
    r"sea[- ]level|climate risk\w*|climate vulnerab\w*|extreme weather|disaster risk)\b",
    "climate": r"\b(?:climate change|global warming|climate action|climate finance)\b",
    "retrospective": r"\b(?:has been completed|was completed|have achieved|has achieved|"
    r"lessons learned|results achieved|since completion|successfully delivered)\b",
}


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def dump_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", "utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows), "utf-8"
    )


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def git_state(repo: Path) -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True, text=True, timeout=30
        ).stdout.strip()

    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


def load_verified_development(paths: V2Paths, build_id: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    directory = _development_dir(paths, build_id)
    manifest_path = directory / "build_manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    for name in ("candidates.parquet", "partition_membership.parquet"):
        if sha256_file(directory / name) != manifest["outputs_sha256"][name]:
            raise ValueError(f"Development input checksum mismatch: {name}")
    rights = load_rights(paths.repo_root / DEFAULT_RIGHTS_CONFIG)
    membership = pd.read_parquet(directory / "partition_membership.parquet")
    integrity = check_pool_integrity(membership, rights.restricted_sources())
    frame = load_development_pool(paths, build_id)
    if frame["candidate_id"].duplicated().any():
        raise ValueError("Duplicate development candidate IDs")
    expected = membership[membership["source_id"] != "aiddata"]
    expected = expected[expected["v2_partition"].isin([TRAIN, VALID])]
    joined = frame.merge(
        expected[["candidate_id", "v2_partition", "partition_group_id", "project_family_id"]],
        on="candidate_id",
        suffixes=("", "_membership"),
        validate="one_to_one",
    )
    if len(joined) != len(frame) or len(frame) != len(expected):
        raise ValueError("Development candidates differ from membership")
    for key in ("v2_partition", "partition_group_id", "project_family_id"):
        if (joined[key] != joined[f"{key}_membership"]).any():
            raise ValueError(f"Development membership mismatch: {key}")
    if not set(frame["source_id"]) <= SOURCES:
        raise ValueError("Only registered IATI donors are supported by this audit")
    for source in set(frame["source_id"]):
        if not rights.permitted(source, Use.EVALUATION):
            raise PermissionError(f"Automated audit not permitted for {source}")
    return frame, {
        "build_id": build_id,
        "build_manifest_sha256": sha256_file(manifest_path),
        "inputs": manifest["inputs"],
        "development_sha256": manifest["outputs_sha256"]["candidates.parquet"],
        "membership_sha256": manifest["outputs_sha256"]["partition_membership.parquet"],
        "pool_integrity": integrity,
        "rights_sha256": sha256_file(paths.repo_root / DEFAULT_RIGHTS_CONFIG),
        "rights": rights.model_dump(mode="json"),
    }


def raw_marker_audit(
    paths: V2Paths, frame: pd.DataFrame, retrieval_pins: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Read registered donor XML only. Skip non-development IDs before inspecting markers.

    Multiple markers for one objective are retained; no first/last-value repair is performed.
    These observations also catch contradictory duplicate activity IDs across XML files.
    """
    wanted = set(frame["candidate_id"])
    result: dict[str, dict[str, Any]] = {}
    for source in sorted(set(frame["source_id"])):
        pin = retrieval_pins[source]
        directory = paths.external_raw / source / pin["retrieval_id"]
        if sha256_file(directory / "retrieval_manifest.json") != pin["manifest_sha256"]:
            raise ValueError(f"Retrieval manifest drift: {source}")
        if errors := verify_retrieval(directory):
            raise ValueError(f"Retrieval integrity failure: {errors[:3]}")
        for entry in read_retrieval_manifest(directory)["files"]:
            if entry.get("role") != "data":
                continue
            for activity in iter_xml_elements(directory / entry["file"], "iati-activity"):
                cid = f"{source}:{(activity.findtext('iati-identifier') or '').strip()}"
                if cid not in wanted:
                    continue
                observed = result.setdefault(
                    cid, {"occurrences": 0, "mitigation": [], "adaptation": []}
                )
                observed["occurrences"] += 1
                for marker in activity.findall("policy-marker"):
                    if (marker.get("vocabulary") or "1") != "1":
                        continue
                    objective = {"6": "mitigation", "7": "adaptation"}.get(marker.get("code") or "")
                    if objective:
                        observed[objective].append(marker.get("significance") or "")
    if wanted - set(result):
        raise ValueError(f"{len(wanted - set(result))} development IDs absent from pinned XML")
    return result


def evidence_spans(title: str, description: str) -> dict[str, list[dict[str, Any]]]:
    return {
        kind: [
            {"field": field, "start": match.start(), "end": match.end(), "quote": match.group()}
            for field, text in (("title", title), ("description", description))
            for match in re.finditer(pattern, text, flags=re.IGNORECASE)
        ]
        for kind, pattern in PATTERNS.items()
    }


def _score(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (ValueError, TypeError):
        return None
    return int(n) if n in (0, 1, 2) else None


def audit_records(frame: pd.DataFrame, raw: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    repeated_families = set(
        frame.loc[frame["project_family_id"].duplicated(False), "project_family_id"]
    )
    for input_row in frame.sort_values("candidate_id").to_dict("records"):
        row: dict[str, Any] = {str(k): v for k, v in input_row.items()}
        cid = str(row["candidate_id"])
        mit, ada = (_score(row[f"donor_rio_{k}"]) for k in ("mitigation", "adaptation"))
        overall = _score(row["donor_rio_overall"])
        flags: list[str] = []
        if row["project_family_id"] in repeated_families:
            flags.append("multiple_records_same_family")
        observed = raw[cid]
        extra = json.loads(row["extra"]) if row.get("extra") else {}
        if extra.get("invalid_rio_significance") or any(
            v not in ("0", "1", "2") for k in ("mitigation", "adaptation") for v in observed[k]
        ):
            flags.append("invalid_rio_value")
        for k in ("mitigation", "adaptation"):
            if len(set(observed[k])) > 1:
                flags.append(f"contradictory_raw_{k}")
        if observed["occurrences"] > 1:
            flags.append("duplicate_native_activity")
        valid = mit is not None and ada is not None
        if not valid or row["donor_marker_status"] != "explicit_both":
            flags.append("missing_or_partial_objectives")
        if mit is not None and ada is not None and overall != max(mit, ada):
            flags.append("contradictory_overall")
        if row["donor_marker_status"] == "explicit_both" and not valid:
            flags.append("invalid_rio_value")
        for k, score in (("mitigation", mit), ("adaptation", ada)):
            if score is not None and str(score) not in observed[k]:
                flags.append("parsed_raw_marker_mismatch")
        evidence = evidence_spans(
            str(row.get("title_clean") or ""), str(row.get("description_clean") or "")
        )
        if (
            valid
            and overall
            and not any(evidence[k] for k in ("mitigation", "adaptation", "climate"))
        ):
            flags.append("positive_without_lexical_evidence")
        if (
            valid
            and overall == 0
            and any(evidence[k] for k in ("mitigation", "adaptation", "climate"))
        ):
            flags.append("negative_with_climate_lexical_evidence")
        if evidence["retrospective"]:
            flags.append("retrospective_wording")
        for objective, value in (("mitigation", mit), ("adaptation", ada)):
            if value is not None and value > 0 and not evidence[objective]:
                flags.append(f"positive_{objective}_without_lexical_evidence")
        structural = {
            "invalid_rio_value",
            "contradictory_overall",
            "parsed_raw_marker_mismatch",
            "missing_or_partial_objectives",
            "contradictory_raw_mitigation",
            "contradictory_raw_adaptation",
        }
        eligible = bool(row["has_usable_text"]) and valid and not (set(flags) & structural)
        rows.append(
            {
                "candidate_id": cid,
                "source_id": row["source_id"],
                "publisher": row["publisher"],
                "v2_partition": row["v2_partition"],
                "project_family_id": row["project_family_id"],
                "partition_group_id": row["partition_group_id"],
                "sector_family": row["sector_family"],
                "text_sha256": row["text_sha256"],
                "description_sha256": row["description_sha256"],
                "label_origin": "B_donor_reported_rio" if valid else "unknown_or_invalid",
                "donor_values": {"mitigation": mit, "adaptation": ada, "overall": overall},
                "donor_marker_status": row["donor_marker_status"],
                "raw_observation": observed,
                "has_usable_text": bool(row["has_usable_text"]),
                "eligible_source_label": eligible,
                "flags": sorted(set(flags)),
                "evidence": evidence,
                "rights_status": row["rights_status"],
                "human_verified": False,
            }
        )
    for group_key, flag in (
        ("project_family_id", "family_label_variation"),
        ("description_sha256", "identical_description_label_conflict"),
    ):
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            if row[group_key] and row["eligible_source_label"]:
                groups[str(row[group_key])].append(row)
        for group in groups.values():
            values = {
                (r["donor_values"]["mitigation"], r["donor_values"]["adaptation"]) for r in group
            }
            if len(values) > 1:
                for row in group:
                    row["flags"].append(flag)
    for row in rows:
        row["flags"] = sorted(set(row["flags"]))
        # Priority is a reproducible triage score, NOT a probability of a wrong label.
        row["uncertainty_priority"] = sum(
            3 if "contradict" in f or "invalid" in f or "conflict" in f else 1 for f in row["flags"]
        )
    return rows


def population_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    eligible = [r for r in rows if r["eligible_source_label"]]
    return {
        "records": len(rows),
        "source_reported_usable": sum(
            r["has_usable_text"] and r["donor_marker_status"] == "explicit_both" for r in rows
        ),
        "eligible_donor_labelled": len(eligible),
        "positive": sum(r["donor_values"]["overall"] > 0 for r in eligible),
        "negative": sum(r["donor_values"]["overall"] == 0 for r in eligible),
        "non_energy_positive": sum(
            r["donor_values"]["overall"] > 0 and r["sector_family"] != "energy" for r in eligible
        ),
        "adaptation_only": sum(
            r["donor_values"]["adaptation"] > 0 and r["donor_values"]["mitigation"] == 0
            for r in eligible
        ),
        "project_families": len({r["project_family_id"] for r in eligible}),
        "partition_groups": len({r["partition_group_id"] for r in eligible}),
    }


def vocabulary_shortcuts(frame: pd.DataFrame) -> dict[str, Any]:
    """Training document-frequency associations only. No validation fitting or model scoring."""
    train = frame[(frame["v2_partition"] == TRAIN) & frame["has_usable_text"]]
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    totals: Counter[str] = Counter()
    for row in train.to_dict("records"):
        source = str(row["source_id"])
        tokens = set(
            re.findall(r"\b[a-z]{3,}\b", f"{row['title_clean']} {row['description_clean']}".lower())
        )
        counts[source].update(tokens)
        totals[source] += 1
    result: list[dict[str, Any]] = []
    for source in sorted(totals):
        others = sum(n for s, n in totals.items() if s != source)
        if not others:
            continue
        for token, n in counts[source].items():
            if n < 10:
                continue
            other_n = sum(c[token] for s, c in counts.items() if s != source)
            ratio = ((n + 1) / (totals[source] + 2)) / ((other_n + 1) / (others + 2))
            if ratio >= 4:
                result.append(
                    {
                        "source_id": source,
                        "token": token,
                        "documents": n,
                        "source_document_rate": round(n / totals[source], 6),
                        "other_document_rate": round(other_n / others, 6),
                        "log2_smoothed_rate_ratio": round(math.log2(ratio), 4),
                    }
                )
    return {
        "scope": "training_only",
        "minimum_document_frequency": 10,
        "minimum_rate_ratio": 4,
        "interpretation": "publisher association, not causal label leakage",
        "top_associations": sorted(
            result, key=lambda r: (-r["log2_smoothed_rate_ratio"], r["source_id"], r["token"])
        )[:100],
    }


def audit_dataset(paths: V2Paths, build_id: str) -> Path:
    frame, provenance = load_verified_development(paths, build_id)
    raw = raw_marker_audit(paths, frame, provenance["inputs"]["retrievals"])
    rows = audit_records(frame, raw)
    source_hash = canonical_hash(
        {
            p.name: hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for p in sorted(Path(__file__).parent.glob("*.py"))
        }
    )
    inputs = {
        "version": VERSION,
        "provenance": provenance,
        "code_sha256": source_hash,
        "lexicon": PATTERNS,
    }
    audit_id = "quality_" + canonical_hash(inputs)[:16]
    output = paths.writable(paths.output_root / "automated_quality" / audit_id)
    counts = population_counts(rows)
    summary: dict[str, Any] = {
        "audit_id": audit_id,
        "version": VERSION,
        "inputs": inputs,
        "counts": counts,
        "human_verified_labels": 0,
        "ai_assessed_records": 0,
        "source_labels_modified": False,
        "attribution": ATTRIBUTION,
        "flag_counts": dict(sorted(Counter(f for r in rows for f in r["flags"]).items())),
        "by_source_flag_counts": {
            source: dict(
                sorted(
                    Counter(f for r in rows if r["source_id"] == source for f in r["flags"]).items()
                )
            )
            for source in sorted(SOURCES)
        },
        "by_source_partition": {
            f"{source}/{part}": population_counts(
                [r for r in rows if r["source_id"] == source and r["v2_partition"] == part]
            )
            for source in sorted(SOURCES)
            for part in (TRAIN, VALID)
        },
        "by_sector_partition": {
            f"{sector}/{part}": population_counts(
                [r for r in rows if r["sector_family"] == sector and r["v2_partition"] == part]
            )
            for sector in sorted(set(frame["sector_family"]))
            for part in (TRAIN, VALID)
        },
        "vocabulary_shortcuts": vocabulary_shortcuts(frame),
        "limitations": [
            "Lexical evidence warnings are not label errors; negation and implicit "
            "objectives may be missed.",
            "Family label variation can reflect different components, not a contradiction.",
            "Source labels, automated heuristics, AI outputs and human labels "
            "are separate evidence classes.",
            "Same-publisher validation cannot establish independent generalization or impact.",
            "No development audit reads the human-evaluation pool or human worksheets.",
        ],
        "readiness": {
            "decision": "development_experiments_justified_on_source_labels_only"
            if counts["positive"] and counts["negative"]
            else "blocked_no_two_class_source_labels",
            "conditions": [
                "Internal research under current source rights only.",
                "Group-aware train-only fitting, calibration and threshold choice.",
                "Report donor/publisher/sector slices and family-weighted sensitivity analyses.",
                "Do not treat AI agreement or donor validation as independent accuracy.",
                "No relabeling or validation selection using this uncertainty queue.",
            ],
            "independent_test_ready": False,
            "production_ready": False,
        },
    }
    queue = sorted(
        [r for r in rows if r["flags"]],
        key=lambda r: (-r["uncertainty_priority"], r["candidate_id"]),
    )
    output.mkdir(parents=True, exist_ok=True)
    # Never overwrite an earlier report. Recompute and compare all deterministic outputs.
    files = {
        "quality_report.json": json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
        "record_quality.jsonl": "".join(
            json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows
        ),
        "uncertainty_queue.jsonl": "".join(
            json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in queue
        ),
    }
    for name, text in files.items():
        target = output / name
        if target.exists():
            if target.read_text("utf-8") != text:
                raise ValueError(f"Non-reproducible audit output: {target}")
        else:
            target.write_text(text, "utf-8")
    receipt = output / f"verification_{git_state(paths.repo_root)['commit']}.json"
    dump_json(
        receipt,
        {
            "git": git_state(paths.repo_root),
            "audit_id": audit_id,
            "outputs_sha256": {name: sha256_file(output / name) for name in files},
        },
    )
    return output


def load_eligible_donor_records(paths: V2Paths, audit_id: str, partition: str) -> pd.DataFrame:
    """Experiment input with original donor labels, structural exclusions only.

    Reproduce the audit before accepting its eligibility list. Lexical or AI disagreements
    never drive label replacement or filtering. No independent accuracy is implied.
    """
    if partition not in (TRAIN, VALID):
        raise PermissionError("Only development partitions are allowed")
    directory = (paths.output_root / "automated_quality" / audit_id).resolve()
    if directory.parent != (paths.output_root / "automated_quality").resolve():
        raise ValueError("Expected a direct audit identifier")
    report = json.loads((directory / "quality_report.json").read_text("utf-8"))
    build_id = report["inputs"]["provenance"]["build_id"]
    if audit_dataset(paths, build_id) != directory:
        raise ValueError("Audit no longer matches code/rights/inputs")
    frame, _ = load_verified_development(paths, build_id)
    ids = {
        r["candidate_id"]
        for r in load_jsonl(directory / "record_quality.jsonl")
        if r["eligible_source_label"] and r["v2_partition"] == partition
    }
    return frame[frame["candidate_id"].isin(ids)].assign(label_origin="B_donor_reported_rio")
