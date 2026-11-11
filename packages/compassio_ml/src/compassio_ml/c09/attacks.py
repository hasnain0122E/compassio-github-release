"""Deterministic surface attacks, with original-coordinate, replayable edit receipts.

Only allowlisted administrative words and safe separators are eligible. Numeric tokens,
climate terms, negations and all other words are protected. The denominator is ORIGINAL
eligible Unicode code points, across both fields, excluding the model's separator.
"""

import hashlib
import random
import re
from dataclasses import asdict, dataclass

WORDS = frozenset(
    [
        "project",
        "projects",
        "programme",
        "programmes",
        "program",
        "programs",
        "support",
        "development",
        "activities",
        "management",
        "implementation",
        "community",
        "communities",
        "services",
        "technical",
        "assistance",
        "capacity",
        "improve",
        "improving",
        "provide",
        "providing",
        "strengthening",
        "information",
        "national",
        "local",
        "regional",
        "working",
        "partners",
        "through",
        "including",
    ]
)
# Deliberately small, auditable visual map. No transliteration of natural-language scripts.
CONFUSABLES = dict(
    zip(
        "aceopxyACEOPXY",
        "\u0430\u0441\u0435\u043e\u0440\u0445\u0443\u0410\u0421\u0415\u041e\u0420\u0425\u0423",
        strict=True,
    )
)
KINDS = ("confusable", "invisible", "whitespace", "punctuation", "typo")


@dataclass(frozen=True)
class Edit:
    field: int
    index: int
    before: str
    after: str


def eligible(text: str) -> set[int]:
    """Letters of neutral words, plus non-financial whitespace/sentence separators."""
    positions: set[int] = set()
    for m in re.finditer(r"\b[A-Za-z]+\b", text):
        if m.group().lower() in WORDS:
            positions.update(range(m.start(), m.end()))
    # Do not touch spacing or punctuation adjacent to any number or currency.
    for i in range(1, len(text) - 1):
        if text[i] in " \t\n,;" and text[i - 1].isalpha() and text[i + 1].isalpha():
            positions.add(i)
    for m in re.finditer(r"(?<=[A-Za-z])[,;](?=\s*[A-Za-z])", text):
        positions.add(m.start())
    return positions


def budget(fields: tuple[str, str]) -> tuple[int, int]:
    n = sum(len(eligible(t)) for t in fields)
    return n, n // 50


def replay(fields: tuple[str, str], edits: tuple[Edit, ...]) -> tuple[str, str]:
    """Validate the entire receipt, then apply edits right-to-left in original coordinates."""
    n, limit = budget(fields)
    del n
    if len(edits) > limit:
        raise ValueError("2% edit budget exceeded")
    seen: set[tuple[int, int]] = set()
    for e in edits:
        if e.field not in (0, 1) or (e.field, e.index) in seen:
            raise ValueError("invalid or duplicate edit coordinate")
        seen.add((e.field, e.index))
        if e.index not in eligible(fields[e.field]):
            raise ValueError("protected position")
        if len(e.before) > 1 or len(e.after) > 1 or e.before == e.after:
            raise ValueError("each receipt operation must be one character edit")
        if not e.before and not e.after:
            raise ValueError("empty edit")
        if e.before and fields[e.field][e.index] != e.before:
            raise ValueError("receipt does not match original")
    out = list(fields)
    for e in sorted(edits, key=lambda e: (e.field, e.index), reverse=True):
        t = out[e.field]
        out[e.field] = t[: e.index] + e.after + t[e.index + len(e.before) :]
    return out[0], out[1]


def distance(a: str, b: str, limit: int) -> int:
    """Exact Levenshtein distance up to limit; return limit+1 when outside the band."""
    prefix = 0
    while prefix < min(len(a), len(b)) and a[prefix] == b[prefix]:
        prefix += 1
    a, b = a[prefix:], b[prefix:]
    while a and b and a[-1] == b[-1]:
        a, b = a[:-1], b[:-1]
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = {j: j for j in range(min(len(b), limit) + 1)}
    for i, char in enumerate(a, 1):
        cur: dict[int, int] = {0: i} if i <= limit else {}
        for j in range(max(1, i - limit), min(len(b), i + limit) + 1):
            cur[j] = min(
                prev.get(j, limit + 1) + 1,
                cur.get(j - 1, limit + 1) + 1,
                prev.get(j - 1, limit + 1) + (char != b[j - 1]),
            )
        prev = cur
    return min(prev.get(len(b), limit + 1), limit + 1)


@dataclass(frozen=True)
class Attack:
    kind: str
    fields: tuple[str, str]
    edits: tuple[Edit, ...]
    eligible_characters: int
    edit_distance: int

    @property
    def percent(self) -> float:
        return (
            100 * self.edit_distance / self.eligible_characters if self.eligible_characters else 0
        )

    def receipt(self) -> dict[str, object]:
        return {**asdict(self), "edit_percent": self.percent, "operation_count": len(self.edits)}


def attack(fields: tuple[str, str], kind: str, seed: int) -> Attack:
    if kind not in KINDS:
        raise ValueError(kind)
    n, limit = budget(fields)
    options: list[Edit] = []
    for f, text in enumerate(fields):
        for i in sorted(eligible(text)):
            c = text[i]
            if kind == "confusable" and c in CONFUSABLES:
                options.append(Edit(f, i, c, CONFUSABLES[c]))
            elif kind == "invisible" and c.isalpha():
                options.append(Edit(f, i, "", "\u200b"))
            elif kind == "whitespace" and c.isspace():
                options.append(Edit(f, i, c, "\u00a0"))
            elif kind == "punctuation" and c in ",;":
                options.append(Edit(f, i, c, {",": "\uff0c", ";": "\uff1b"}[c]))
            elif kind == "typo" and c.isalpha() and i > 0 and text[i - 1].isalpha():
                # A duplicated interior letter in an administrative word, never a new term.
                options.append(Edit(f, i, "", c))
    random.Random(seed).shuffle(options)
    edits = tuple(sorted(options[:limit], key=lambda e: (e.field, e.index)))
    changed = replay(fields, edits)
    d = sum(distance(a, b, limit) for a, b in zip(fields, changed, strict=True))
    if d > len(edits) or d * 50 > n:
        raise ValueError("independent distance verification failed")
    return Attack(kind, changed, edits, n, d)


def seed_for(identifier: str, trial: int = 0) -> int:
    return int(hashlib.sha256(f"c09-v1|{identifier}|{trial}".encode()).hexdigest()[:16], 16)
