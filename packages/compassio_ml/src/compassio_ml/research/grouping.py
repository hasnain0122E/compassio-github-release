"""Leakage-control groups: transitive connected components over explicit relations.

Relations (edges) between records:

* ``parent_id``         - same verified AidData Parent ID (linked package).
* ``description``       - identical description after ``normalize_text`` (case-, accent-,
                          punctuation- and whitespace-insensitive).
* ``title``             - identical title after ``normalize_text``.
* ``title_series``      - restricted rule: the title carries explicit tranche/phase/stage/
                          subprogram/part numbering, AND the series key (numbering removed) AND
                          the recipient are identical. The broad "remove all digits" rule was
                          rejected because it merges unrelated grants across many countries
                          (docs/data/leakage_group_audit.md).

Group ids are ``g_`` + first 16 hex chars of SHA-256 over the sorted member record ids, so
they are stable across runs and Python processes (no built-in ``hash``).
"""

import hashlib
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from compassio_ml.data.parsing import normalize_text, series_key

RELATIONS = ("parent_id", "description", "title", "title_series")

_EXPLICIT_SERIES = re.compile(
    r"\b(tranche|phase|subprogram|sub-program|stage|part)\s*(?:[0-9]+|[ivx]+)\b", re.IGNORECASE
)


class UnionFind:
    def __init__(self, items: Iterable[str]) -> None:
        self._parent = {item: item for item in items}

    def find(self, item: str) -> str:
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[item] != root:  # path compression
            self._parent[item], item = root, self._parent[item]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # Deterministic root choice keeps components independent of edge order.
            low, high = sorted((ra, rb))
            self._parent[high] = low


def stable_group_id(member_ids: Iterable[str]) -> str:
    joined = "\n".join(sorted(member_ids))
    return "g_" + hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def has_explicit_series_numbering(title: str | None) -> bool:
    return bool(title and _EXPLICIT_SERIES.search(title))


@dataclass(frozen=True, slots=True)
class GroupInput:
    record_id: str
    parent_id: str | None
    title: str | None
    description: str | None
    recipient: str | None


@dataclass
class GroupingResult:
    group_of: dict[str, str]
    # relation -> list of edge groups (each a sorted tuple of record ids sharing the key)
    relation_groups: dict[str, list[tuple[str, ...]]] = field(default_factory=dict)

    def members(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = defaultdict(list)
        for record, group in self.group_of.items():
            out[group].append(record)
        return {g: sorted(m) for g, m in out.items()}


def relation_keys(record: GroupInput) -> dict[str, str | None]:
    title_norm = normalize_text(record.title) or None
    series: str | None = None
    if has_explicit_series_numbering(record.title) and record.recipient:
        key = series_key(record.title)
        series = f"{key}||{normalize_text(record.recipient)}" if key else None
    return {
        "parent_id": record.parent_id.strip()
        if record.parent_id and record.parent_id.strip()
        else None,
        "description": normalize_text(record.description) or None,
        "title": title_norm,
        "title_series": series,
    }


def build_groups(
    records: Sequence[GroupInput], relations: Sequence[str] = RELATIONS
) -> GroupingResult:
    unknown = set(relations) - set(RELATIONS)
    if unknown:
        raise ValueError(f"Unknown relations: {sorted(unknown)}")
    ids = [r.record_id for r in records]
    duplicates = [i for i, n in Counter(ids).items() if n > 1]
    if duplicates:
        raise ValueError(f"record_id values must be unique; duplicated: {duplicates[:5]}")

    uf = UnionFind(ids)
    relation_groups: dict[str, list[tuple[str, ...]]] = {}
    keys = {r.record_id: relation_keys(r) for r in records}
    for relation in relations:
        by_key: dict[str, list[str]] = defaultdict(list)
        for record_id in ids:
            value = keys[record_id][relation]
            if value:
                by_key[value].append(record_id)
        groups = [tuple(sorted(m)) for m in by_key.values() if len(m) > 1]
        relation_groups[relation] = sorted(groups)
        for members in groups:
            for other in members[1:]:
                uf.union(members[0], other)

    roots: dict[str, list[str]] = defaultdict(list)
    for record_id in ids:
        roots[uf.find(record_id)].append(record_id)
    group_of: dict[str, str] = {}
    for component in roots.values():
        gid = stable_group_id(component)
        for record_id in component:
            group_of[record_id] = gid
    return GroupingResult(group_of=group_of, relation_groups=relation_groups)


def component_sizes(group_of: Mapping[str, str]) -> Counter[str]:
    return Counter(group_of.values())
