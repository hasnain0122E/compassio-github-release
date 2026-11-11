"""Which columns of ``research_projects`` a future model may read.

Task 004 code must select model inputs only through ``model_input_columns()``. Tests enforce
that no label, label-derived, annotation, split, grouping or post-commitment field can enter.
"""

import re

# Primary inputs: the cleaned text the classifier learns from.
TEXT_INPUTS: tuple[str, ...] = ("title_clean", "description_clean")

# Optional structured context; experiments must report results with and without these.
CONTEXT_INPUTS: tuple[str, ...] = (
    "sector_name",
    "flow_type",
    "funding_agencies_type",
    "recipient_region",
)

# The target and anything derived from it.
TARGET_COLUMNS: tuple[str, ...] = (
    "rio_marker_src",
    "rio_overall",
    "rio_mitigation",
    "rio_adaptation",
    "rio_overall_is_max",
    "is_climate_related",
)

# Patterns that must never match a model input column.
FORBIDDEN_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"^rio_",
        r"climate",
        r"sdg",
        r"label",
        r"staff_comment",
        r"annotat",
        r"implementation",
        r"completion",
        r"retrospective",
        r"group",
        r"split",
        r"eligib",
        r"quarantin",
        r"exclusion",
        r"conflict",
        r"_sha256$",
        r"^record_id$",
        r"^research_row_id$",
        r"^parent_id$",
        r"commitment_year",
        r"commitment_date",
        r"status",
        r"recommended_for_aggregates",
        r"^is_pakistan$",
    )
)


def is_forbidden(column: str) -> bool:
    return any(p.search(column) for p in FORBIDDEN_PATTERNS)


def model_input_columns(*, include_context: bool = False) -> tuple[str, ...]:
    columns = TEXT_INPUTS + (CONTEXT_INPUTS if include_context else ())
    bad = [c for c in columns if is_forbidden(c)]
    if bad:  # defensive: the allowlist itself must never contain forbidden fields
        raise ValueError(f"Forbidden columns in input allowlist: {bad}")
    return columns
