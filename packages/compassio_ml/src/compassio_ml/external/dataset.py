"""Build the v2 candidate datasets from verified retrievals + the frozen v1 table (read-only).

Outputs (all under the v2 output root, git-ignored):

* ``datasets/<build_id>/``: ``candidates.parquet`` (training + validation candidates ONLY),
  ``excluded_records.parquet`` (external records excluded from every pool, with reasons),
  ``partition_membership.parquet`` (every external record + AidData record IDs, no AidData
  text), ``links.parquet``, ``suspected_matches_for_review.csv``, ``build_manifest.json``.
* ``sealed_external_test/<build_id>/candidate_pool.parquet``: external-test candidates.
  Training and selection code must never read this directory.
* ``restricted_reference/<build_id>/records.parquet``: rights-restricted records (GCF pages),
  kept for separately authorised reference use only.

Pool invariants are checked by ``partition.check_pool_integrity`` before anything is written.

``build_id`` is a hash of the inputs, so the same inputs always map to the same directory and
a rebuild is compared byte-for-byte with the existing outputs.
"""

import hashlib
import json
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from compassio_ml.external import gcf, iati, worldbank
from compassio_ml.external.linkage import link
from compassio_ml.external.partition import (
    DESIGN_VERSION,
    DEVELOPMENT_PARTITIONS,
    EXTERNAL,
    RESTRICTED,
    SEED,
    assign_partitions,
    check_pool_integrity,
)
from compassio_ml.external.paths import V2Paths
from compassio_ml.external.records import (
    MIN_USABLE_DESCRIPTION_CHARS,
    CandidateRecord,
    description_key,
    text_key,
)
from compassio_ml.external.registry import (
    latest_retrieval,
    read_retrieval_manifest,
    verify_retrieval,
)
from compassio_ml.external.rights import DEFAULT_RIGHTS_CONFIG, Use, load_rights
from compassio_ml.external.v1_inputs import load_v1_research
from compassio_ml.integrity import sha256_file

PARSERS: dict[str, Callable[[Path], list[CandidateRecord]]] = {
    worldbank.SOURCE_ID: worldbank.parse_retrieval,
    gcf.SOURCE_ID: gcf.parse_retrieval,
    iati.FCDO.source_id: lambda d: iati.parse_retrieval(d, iati.FCDO),
    iati.EC_INTPA.source_id: lambda d: iati.parse_retrieval(d, iati.EC_INTPA),
}
OUTPUT_FILES = (
    "candidates.parquet",
    "excluded_records.parquet",
    "partition_membership.parquet",
    "links.parquet",
    "suspected_matches_for_review.csv",
)


CRLF = bytes((13, 10))
LF = bytes((10,))


def text_file_hash(path: Path) -> str:
    """SHA-256 of a committed text file with CRLF normalised to LF (checkout-independent)."""
    return hashlib.sha256(path.read_bytes().replace(CRLF, LF)).hexdigest()


class RetrievalIntegrityError(RuntimeError):
    """A retrieved file no longer matches its retrieval manifest."""


@dataclass
class BuildResult:
    build_id: str
    directory: Path
    sealed_directory: Path
    external: pd.DataFrame
    aiddata: pd.DataFrame
    links: pd.DataFrame
    reproduced: bool | None
    manifest: dict[str, Any]


def iso2_to_iso3(gcf_directory: Path) -> dict[str, str]:
    """ISO2->ISO3 pairs as published in the retrieved GCF ODL project list."""
    manifest = read_retrieval_manifest(gcf_directory)
    index = next(f for f in manifest["files"] if f.get("role") == "index")
    mapping: dict[str, str] = {}
    for project in gcf.parse_odl((gcf_directory / str(index["file"])).read_text("utf-8")):
        for country in project.get("Countries") or []:
            if country.get("ISO2") and country.get("ISO3"):
                mapping[str(country["ISO2"])] = str(country["ISO3"])
    return mapping


def _resolve(records: list[CandidateRecord], mapping: dict[str, str]) -> None:
    for record in records:
        resolved = set()
        for code in record.country_iso3:
            if code.startswith("ISO2:"):
                resolved.add(mapping.get(code[5:], code))
            else:
                resolved.add(code)
        record.country_iso3 = sorted(resolved)


def _git_head(repo: Path) -> dict[str, object]:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, check=True, timeout=30
        ).stdout.strip()

    return {
        "commit": git("rev-parse", "HEAD"),
        "dirty": bool(git("status", "--porcelain", "--", "packages", "configs")),
    }


def _code_hash() -> str:
    """SHA-256 over the v2 package sources, so a code change always yields a new build ID."""
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes().replace(CRLF, LF))
    return digest.hexdigest()


def _aiddata_rows(v1: pd.DataFrame) -> pd.DataFrame:
    title = v1["title_clean"]
    desc = v1["description_clean"]
    return pd.DataFrame(
        {
            "candidate_id": v1["candidate_id"],
            "source_id": "aiddata",
            "title_clean": title,
            "description_clean": desc,
            "country_iso3": v1["recipient_iso3"].fillna(""),
            "parent_ids": "",
            "cross_references": "",
            "text_sha256": [text_key(t, d) for t, d in zip(title, desc, strict=True)],
            "description_sha256": [description_key(d) for d in desc],
            "has_usable_text": desc.fillna("").str.len() >= MIN_USABLE_DESCRIPTION_CHARS,
            "v1_group": v1["leakage_group_id"],
        }
    )


def _write_outputs(
    directory: Path,
    sealed: Path,
    restricted: Path,
    external: pd.DataFrame,
    membership: pd.DataFrame,
    links: pd.DataFrame,
) -> None:
    for folder in (directory, sealed, restricted):
        folder.mkdir(parents=True, exist_ok=True)
    development = external["v2_partition"].isin(DEVELOPMENT_PARTITIONS)
    external[development].to_parquet(directory / "candidates.parquet", index=False)
    other = ~development & ~external["v2_partition"].isin([EXTERNAL, RESTRICTED])
    external[other].to_parquet(directory / "excluded_records.parquet", index=False)
    external[external["v2_partition"] == RESTRICTED].to_parquet(
        restricted / "records.parquet", index=False
    )
    membership.to_parquet(directory / "partition_membership.parquet", index=False)
    links.to_parquet(directory / "links.parquet", index=False)
    suspected = links[links["strength"] == "suspected_requires_review"]
    suspected.to_csv(directory / "suspected_matches_for_review.csv", index=False)
    external[external["v2_partition"] == EXTERNAL].to_parquet(
        sealed / "candidate_pool.parquet", index=False
    )


def build(paths: V2Paths, rights_path: Path | None = None) -> BuildResult:
    rights_file = rights_path or paths.repo_root / DEFAULT_RIGHTS_CONFIG
    rights = load_rights(rights_file)
    retrievals: dict[str, Path] = {}
    for source_id in PARSERS:
        directory = latest_retrieval(paths, source_id)
        errors = verify_retrieval(directory)
        if errors:
            raise RetrievalIntegrityError(f"{source_id}: {errors[:5]}")
        retrievals[source_id] = directory
    mapping = iso2_to_iso3(retrievals[gcf.SOURCE_ID])

    records: list[CandidateRecord] = []
    for source_id, parser in PARSERS.items():
        parsed = parser(retrievals[source_id])
        _resolve(parsed, mapping)
        records.extend(parsed)
    external = pd.DataFrame([r.to_row() for r in records])
    external["v1_group"] = None

    v1 = load_v1_research(paths)
    aiddata = _aiddata_rows(v1)
    common = [
        "candidate_id",
        "source_id",
        "title_clean",
        "description_clean",
        "country_iso3",
        "parent_ids",
        "cross_references",
        "text_sha256",
        "description_sha256",
        "has_usable_text",
        "v1_group",
    ]
    union = pd.concat([external[common], aiddata[common]], ignore_index=True)
    result = link(union)

    meta = union[["candidate_id", "source_id"]].merge(result.assignments, on="candidate_id")
    meta = meta.merge(
        v1[["candidate_id", "v1_consumed_test", "split_primary", "eligibility_status"]].rename(
            columns={"split_primary": "v1_primary_split", "eligibility_status": "v1_eligibility"}
        ),
        on="candidate_id",
        how="left",
    )
    meta["v1_consumed_test"] = meta["v1_consumed_test"].fillna(False).astype(bool)
    restricted_sources = rights.restricted_sources()
    trainable = frozenset(s for s in set(meta["source_id"]) if rights.permitted(s, Use.TRAINING))
    partitions = assign_partitions(
        meta, SEED, restricted_sources=restricted_sources, trainable_sources=trainable
    )
    membership = meta.merge(partitions, on="candidate_id", validate="one_to_one")
    integrity = check_pool_integrity(membership, restricted_sources)
    external = external.drop(columns=["v1_group"]).merge(
        membership.drop(columns=["source_id"]), on="candidate_id", validate="one_to_one"
    )
    external = external.sort_values("candidate_id").reset_index(drop=True)
    membership = membership.sort_values("candidate_id").reset_index(drop=True)
    links = result.links.sort_values(["relation", "left_id", "right_id"]).reset_index(drop=True)

    lock = json.loads((paths.repo_root / "configs" / "research_split_v1.lock.json").read_text())
    inputs = {
        "retrievals": {
            s: {
                "retrieval_id": d.name,
                "manifest_sha256": sha256_file(d / "retrieval_manifest.json"),
            }
            for s, d in retrievals.items()
        },
        "v1_table_sha256": lock["table"]["sha256"],
        "v1_membership_sha256": lock["membership"]["sha256"],
        "design_version": DESIGN_VERSION,
        "seed": SEED,
        "registry_sha256": text_file_hash(paths.repo_root / "configs" / "external_sources_v2.yaml"),
        "rights_sha256": text_file_hash(rights_file),
        "code_sha256": _code_hash(),
    }
    build_id = (
        "v2build_" + hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:12]
    )
    directory = paths.writable(paths.datasets / build_id)
    sealed = paths.writable(paths.sealed / build_id)
    restricted_dir = paths.writable(paths.restricted_reference / build_id)

    reproduced: bool | None = None
    if (directory / "build_manifest.json").exists():
        with tempfile.TemporaryDirectory() as tmp:
            _write_outputs(
                Path(tmp) / "d", Path(tmp) / "s", Path(tmp) / "r", external, membership, links
            )
            same = all(
                sha256_file(Path(tmp) / "d" / n) == sha256_file(directory / n) for n in OUTPUT_FILES
            )
            same = same and sha256_file(Path(tmp) / "s" / "candidate_pool.parquet") == sha256_file(
                sealed / "candidate_pool.parquet"
            )
            same = same and sha256_file(Path(tmp) / "r" / "records.parquet") == sha256_file(
                restricted_dir / "records.parquet"
            )
        if not same:
            raise RuntimeError(f"Rebuild of {build_id} differs from existing outputs")
        reproduced = True
        manifest = json.loads((directory / "build_manifest.json").read_text(encoding="utf-8"))
    else:
        _write_outputs(directory, sealed, restricted_dir, external, membership, links)
        manifest = {
            "build_id": build_id,
            "inputs": inputs,
            "code": _git_head(paths.repo_root),
            "outputs_sha256": {n: sha256_file(directory / n) for n in OUTPUT_FILES},
            "sealed_outputs_sha256": {
                "candidate_pool.parquet": sha256_file(sealed / "candidate_pool.parquet")
            },
            "restricted_outputs_sha256": {
                "records.parquet": sha256_file(restricted_dir / "records.parquet")
            },
            "pool_integrity": integrity,
            "rights": {
                "version": rights.version,
                "restricted_sources": sorted(restricted_sources),
                "training_permitted_sources": sorted(trainable),
            },
            "country_mapping": {
                "source": "GCF ODL Countries ISO2/ISO3 pairs (country codes only; no GCF "
                "text, label or record enters any pool)",
                "pairs": len(mapping),
            },
        }
        with (directory / "build_manifest.json").open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
    v1_roles = membership[membership["source_id"] == "aiddata"]
    return BuildResult(build_id, directory, sealed, external, v1_roles, links, reproduced, manifest)
