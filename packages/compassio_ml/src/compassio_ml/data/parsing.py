"""Strict, explicit parsers for values found in source files.

Every parser either returns a value, returns ``None`` for a genuinely blank
cell, or raises ``ValueError``. Nothing is guessed silently.
"""

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_BLANK = frozenset({"", "nan", "none", "null", "n/a", "na", "-"})


def is_blank(value: str | None) -> bool:
    return value is None or value.strip().lower() in _BLANK


def parse_amount(value: str | None) -> Decimal | None:
    """Parse a monetary cell into ``Decimal``; thousands separators are allowed.

    Units and currency are *not* inferred here; callers record them per field.
    """
    if value is None or is_blank(value):
        return None
    text = value.strip().replace(",", "").replace(chr(0x00A0), "")
    if text.startswith("$"):
        text = text[1:]
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Not a numeric amount: {value!r}") from exc
    if not amount.is_finite():
        raise ValueError(f"Non-finite amount: {value!r}")
    return amount


def parse_year(value: str | None, *, minimum: int = 1950, maximum: int = 2100) -> int | None:
    if value is None or is_blank(value):
        return None
    text = value.strip()
    if text.endswith(".0"):
        text = text[:-2]
    if not text.isdigit():
        raise ValueError(f"Not a year: {value!r}")
    year = int(text)
    if not minimum <= year <= maximum:
        raise ValueError(f"Year {year} outside plausible range {minimum}-{maximum}")
    return year


def parse_date(value: str | None, formats: tuple[str, ...]) -> date | None:
    """Parse with the first matching explicit ``strptime`` format (no fuzzy guessing)."""
    if value is None or is_blank(value):
        return None
    text = value.strip()
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Date {value!r} matches none of the formats {formats}")


ISO_DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S")
GCF_DATE_FORMATS = ("%b %d, %Y",)


def parse_iso_datetime_date(value: str | None) -> date | None:
    """Date part of an ISO-8601 date/datetime with optional timezone."""
    if value is None or is_blank(value):
        return None
    try:
        return datetime.fromisoformat(value.strip()).date()
    except ValueError as exc:
        raise ValueError(f"Not an ISO-8601 date: {value!r}") from exc


_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE = re.compile(r"\s+")
_SERIES = re.compile(
    r"\b(tranche|phase|project|subprogram|sub program|program|programme|stage|part|loan|grant)"
    r"\s*([0-9]+|[ivx]+)\b"
)
_DIGITS = re.compile(r"\d+")


def normalize_text(value: str | None) -> str:
    """Case-, accent-, punctuation- and whitespace-insensitive key for exact matching."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = _PUNCT.sub(" ", text)
    return _SPACE.sub(" ", text).strip()


def series_key(value: str | None) -> str:
    """Normalized text with tranche/phase numbering and digits removed.

    Groups records such as "Program - Tranche 1" and "Program - Tranche 2" that are
    *related* (same series) but not the same record. Used only to flag for review.
    """
    text = normalize_text(value)
    text = _SERIES.sub(r"\1", text)
    text = _DIGITS.sub("", text)
    return _SPACE.sub(" ", text).strip()


def split_country_list(value: str | None) -> list[str]:
    """Split a comma-separated country list. Country names in the inspected GCF
    export use the "Name (the)" convention and contain no internal commas."""
    if value is None or is_blank(value):
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def split_codes(value: str | None) -> list[str]:
    """Split a code list separated by commas, semicolons or pipes."""
    if value is None or is_blank(value):
        return []
    return [part.strip() for part in re.split(r"[,;|]", value) if part.strip()]
