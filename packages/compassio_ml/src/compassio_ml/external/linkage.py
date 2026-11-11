"""Deterministic cross-source relationships, project families and partition groups.

Two levels, never confused:

* **project family** (``fam_*``): connected components of *evidence-backed* links only -
  IATI parent/child, explicit identifiers in text (World Bank P-codes, GCF FP/SAP codes),
  exact duplicate text (normalized title+description or description hash), and the frozen v1
  ``leakage_group_id`` of AidData records. Referenced IDs that are not in the candidate set are
  kept as virtual nodes, so two records citing the same missing project still share a family.
* **partition group** (``pg_*``): families further joined by *suspected* fuzzy matches (same
  country, TF-IDF cosine >= threshold, or identical normalized title with different text).
  Suspected matches are reported separately for human review and are **not** treated as the
  same project; they only keep possibly-related text in one partition (conservative for leakage).
"""

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from compassio_ml.data.parsing import normalize_text

FUZZY_COSINE_THRESHOLD = 0.85
MIN_FUZZY_CHARS = 100
CHUNK_ROWS = 512


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, item: str) -> None:
        self.parent.setdefault(item, item)

    def find(self, item: str) -> str:
        self.add(item)
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != root:
            self.parent[item], item = root, self.parent[item]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            if rb < ra:
                ra, rb = rb, ra
            self.parent[rb] = ra


def stable_id(prefix: str, members: Iterable[str]) -> str:
    digest = hashlib.sha256("\n".join(sorted(members)).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:16]}"


@dataclass
class LinkageResult:
    links: pd.DataFrame  # left_id, right_id, relation, evidence, strength
    assignments: pd.DataFrame  # candidate_id, project_family_id, partition_group_id, sizes


def _explode(values: pd.Series) -> Iterable[tuple[str, str]]:
    for cid, raw in values.items():
        if isinstance(raw, str) and raw:
            for ref in raw.split(";"):
                if ref:
                    yield str(cid), ref


def evidence_links(nodes: pd.DataFrame) -> pd.DataFrame:
    """``nodes`` columns: candidate_id, parent_ids, cross_references, text_sha256,
    description_sha256, has_usable_text, v1_group (nullable)."""
    rows: list[tuple[str, str, str, str]] = []
    indexed = nodes.set_index("candidate_id")
    for cid, parent in _explode(indexed["parent_ids"]):
        rows.append((cid, parent, "iati_parent_child", "related-activity type=1"))
    for cid, ref in _explode(indexed["cross_references"]):
        if ref != cid:
            rows.append((cid, ref, "explicit_identifier_in_text", ref.split(":", 1)[1]))
    usable = nodes[nodes["has_usable_text"]]
    for key_col, relation in (
        ("text_sha256", "exact_text_duplicate"),
        ("description_sha256", "exact_description_duplicate"),
    ):
        keyed = usable[usable[key_col].notna()]
        for key, group in keyed.groupby(key_col):
            ids = sorted(group["candidate_id"])
            for other in ids[1:]:
                rows.append((ids[0], other, relation, str(key)[:16]))
    v1 = nodes[nodes["v1_group"].notna()]
    for cid, group_id in zip(v1["candidate_id"], v1["v1_group"], strict=True):
        rows.append((str(cid), f"v1_group:{group_id}", "v1_leakage_group", str(group_id)))
    frame = pd.DataFrame(rows, columns=["left_id", "right_id", "relation", "evidence"])
    frame["strength"] = "evidence_backed"
    return frame.drop_duplicates().reset_index(drop=True)


def fuzzy_links(nodes: pd.DataFrame, threshold: float = FUZZY_COSINE_THRESHOLD) -> pd.DataFrame:
    """Suspected near-duplicates across *different* records within the same country block.

    ``nodes`` columns: candidate_id, country_block (one row per candidate x country),
    text (title + description), title_norm, source_id."""
    usable = nodes[nodes["text"].str.len() >= MIN_FUZZY_CHARS].reset_index(drop=True)
    rows: list[tuple[str, str, str, str]] = []
    if usable.empty:
        return pd.DataFrame(columns=["left_id", "right_id", "relation", "evidence", "strength"])
    vectorizer = TfidfVectorizer(
        min_df=1, ngram_range=(1, 2), sublinear_tf=True, stop_words="english", dtype=np.float32
    )
    matrix = vectorizer.fit_transform(usable["text"])
    for _block, idx in usable.groupby("country_block").indices.items():
        if len(idx) < 2:
            continue
        sub = matrix[idx]
        ids = usable["candidate_id"].to_numpy()[idx]
        srcs = usable["source_id"].to_numpy()[idx]
        for start in range(0, len(idx), CHUNK_ROWS):
            sims = (sub[start : start + CHUNK_ROWS] @ sub.T).tocoo()
            keep = sims.data >= threshold
            for i, j, value in zip(
                sims.row[keep] + start, sims.col[keep], sims.data[keep], strict=True
            ):
                if i >= j or ids[i] == ids[j]:
                    continue
                if srcs[i] == srcs[j] == "aiddata":
                    continue  # within-AidData relations are already the frozen v1 groups
                rows.append(
                    (
                        str(ids[i]),
                        str(ids[j]),
                        "suspected_text_similarity",
                        f"tfidf_cosine={value:.3f}",
                    )
                )
    titled = usable[usable["title_norm"].str.len() >= 15]
    for (_block, _title), group in titled.groupby(["country_block", "title_norm"]):
        title_ids = sorted(set(group["candidate_id"]))
        sources = set(group["source_id"])
        if len(title_ids) > 1 and sources != {"aiddata"}:
            for other in title_ids[1:]:
                rows.append((title_ids[0], other, "suspected_same_title", "normalized title equal"))
    frame = pd.DataFrame(rows, columns=["left_id", "right_id", "relation", "evidence"])
    frame["strength"] = "suspected_requires_review"
    return frame.drop_duplicates(subset=["left_id", "right_id", "relation"]).reset_index(drop=True)


def assign_groups(
    candidate_ids: list[str], evidence: pd.DataFrame, fuzzy: pd.DataFrame
) -> pd.DataFrame:
    families = UnionFind()
    for cid in candidate_ids:
        families.add(cid)
    for left, right in zip(evidence["left_id"], evidence["right_id"], strict=True):
        families.union(str(left), str(right))
    partitions = UnionFind()
    for cid in candidate_ids:
        partitions.union(cid, families.find(cid))
    for left, right in zip(fuzzy["left_id"], fuzzy["right_id"], strict=True):
        partitions.union(families.find(str(left)), families.find(str(right)))

    fam_members: dict[str, list[str]] = {}
    for cid in candidate_ids:
        fam_members.setdefault(families.find(cid), []).append(cid)
    fam_id = {root: stable_id("fam", members) for root, members in fam_members.items()}
    pg_members: dict[str, list[str]] = {}
    for cid in candidate_ids:
        pg_members.setdefault(partitions.find(cid), []).append(cid)
    pg_id = {root: stable_id("pg", members) for root, members in pg_members.items()}
    rows = []
    for cid in candidate_ids:
        froot, proot = families.find(cid), partitions.find(cid)
        rows.append(
            {
                "candidate_id": cid,
                "project_family_id": fam_id[froot],
                "project_family_size": len(fam_members[froot]),
                "partition_group_id": pg_id[proot],
                "partition_group_size": len(pg_members[proot]),
            }
        )
    return pd.DataFrame(rows)


def build_fuzzy_nodes(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per candidate x resolved country (``NONE`` when no country)."""
    base = pd.DataFrame(
        {
            "candidate_id": frame["candidate_id"],
            "source_id": frame["source_id"],
            "text": (frame["title_clean"].fillna("") + " " + frame["description_clean"].fillna("")),
            "title_norm": frame["title_clean"].map(normalize_text),
            "country_block": frame["country_iso3"]
            .fillna("")
            .map(lambda s: [c for c in str(s).split(";") if c] or ["NONE"]),
        }
    )
    return base.explode("country_block").reset_index(drop=True)


def link(frame: pd.DataFrame, threshold: float = FUZZY_COSINE_THRESHOLD) -> LinkageResult:
    """``frame`` holds external candidates *and* AidData rows in the common columns."""
    evidence = evidence_links(frame)
    fuzzy = fuzzy_links(build_fuzzy_nodes(frame), threshold)
    assignments = assign_groups(list(frame["candidate_id"]), evidence, fuzzy)
    links = pd.concat([evidence, fuzzy], ignore_index=True)
    return LinkageResult(links=links, assignments=assignments)
