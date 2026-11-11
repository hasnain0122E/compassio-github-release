"""Generic, source-agnostic profiling helpers over string-typed frames."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pandas as pd

from compassio_ml.audit.models import ColumnProfile, TableSchema
from compassio_ml.data.parsing import is_blank, normalize_text, parse_amount, series_key


def blank_mask(series: pd.Series) -> pd.Series:
    return series.map(lambda v: v is None or (isinstance(v, float) and v != v) or is_blank(str(v)))


def present_count(series: pd.Series) -> int:
    return int((~blank_mask(series)).sum())


def table_schema(source_id: str, table: str, unit: str, frame: pd.DataFrame) -> TableSchema:
    columns = []
    for name in frame.columns:
        col = frame[name]
        blanks = int(blank_mask(col).sum())
        distinct = int(col[~blank_mask(col)].nunique())
        columns.append(
            ColumnProfile(
                name=str(name), non_blank=len(col) - blanks, blank=blanks, distinct=distinct
            )
        )
    return TableSchema(
        source_id=source_id,
        table=table,
        unit_of_observation=unit,
        row_count=len(frame),
        columns=tuple(columns),
    )


@dataclass(frozen=True, slots=True)
class DuplicateStats:
    rows_in_duplicate_groups: int
    groups: int
    distinct_values: int


def duplicate_stats(values: pd.Series, key: Callable[[str], str] = str) -> DuplicateStats:
    """Duplicates among non-blank values after applying ``key``."""
    present = values[~blank_mask(values)].map(lambda v: key(str(v)))
    present = present[present != ""]
    counts = present.value_counts()
    dup = counts[counts > 1]
    return DuplicateStats(
        rows_in_duplicate_groups=int(dup.sum()),
        groups=len(dup),
        distinct_values=len(counts),
    )


def normalized_duplicates(values: pd.Series) -> DuplicateStats:
    return duplicate_stats(values, normalize_text)


def series_duplicates(values: pd.Series) -> DuplicateStats:
    return duplicate_stats(values, series_key)


@dataclass(frozen=True, slots=True)
class ParsedColumn[T]:
    values: list[T | None]
    failures: int
    failure_examples: tuple[str, ...]

    @property
    def present(self) -> int:
        return sum(v is not None for v in self.values)


def parse_column[T](series: pd.Series, parser: Callable[[str | None], T | None]) -> ParsedColumn[T]:
    out: list[T | None] = []
    failures = 0
    examples: list[str] = []
    for raw in series.tolist():
        text = None if raw is None or (isinstance(raw, float) and raw != raw) else str(raw)
        try:
            out.append(parser(text))
        except ValueError:
            failures += 1
            out.append(None)
            if len(examples) < 3 and text is not None:
                examples.append(text[:40])
    return ParsedColumn(values=out, failures=failures, failure_examples=tuple(examples))


def amounts(series: pd.Series) -> ParsedColumn[Decimal]:
    return parse_column(series, parse_amount)


def date_range(values: Iterable[date | int | None]) -> tuple[str | None, str | None]:
    present = [v for v in values if v is not None]
    if not present:
        return None, None
    return str(min(present)), str(max(present))


def count_year(values: Iterable[date | int | None], year: int) -> int:
    total = 0
    for v in values:
        if v is None:
            continue
        y = v if isinstance(v, int) else v.year
        total += y == year
    return total
