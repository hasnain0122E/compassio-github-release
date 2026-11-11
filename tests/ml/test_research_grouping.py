"""Leakage-group construction over ARTIFICIAL records."""

import pytest

from compassio_ml.research.grouping import (
    GroupInput,
    build_groups,
    has_explicit_series_numbering,
    stable_group_id,
)


def rec(
    rid: str,
    *,
    parent: str | None = None,
    title: str | None = None,
    desc: str | None = None,
    recipient: str | None = "Exampleland",
) -> GroupInput:
    return GroupInput(
        record_id=rid,
        parent_id=parent,
        title=title if title is not None else f"Unique example title {rid}",
        description=desc if desc is not None else f"Unique example description {rid}.",
        recipient=recipient,
    )


def test_parent_packages_form_components() -> None:
    result = build_groups([rec("1", parent="P1"), rec("2", parent="P1"), rec("3", parent="P2")])

    assert result.group_of["1"] == result.group_of["2"]
    assert result.group_of["3"] != result.group_of["1"]


def test_transitive_grouping_across_relation_types() -> None:
    """A-B share a parent, B-C share a description: A, B and C are one group."""
    records = [
        rec("A", parent="P1"),
        rec("B", parent="P1", desc="Shared example description."),
        rec("C", desc="shared EXAMPLE description"),  # equal after normalize_text
        rec("D"),
    ]

    groups = build_groups(records).group_of

    assert groups["A"] == groups["B"] == groups["C"]
    assert groups["D"] != groups["A"]


def test_exact_title_relation() -> None:
    groups = build_groups(
        [
            rec("1", title="Example Donation of Medical Supplies"),
            rec("2", title="example donation of medical supplies!"),
        ]
    ).group_of

    assert groups["1"] == groups["2"]


def test_title_series_requires_explicit_numbering_and_same_recipient() -> None:
    records = [
        rec("1", title="Example Highway Project Phase 1", recipient="Exampleland"),
        rec("2", title="Example Highway Project Phase 2", recipient="Exampleland"),
        rec("3", title="Example Highway Project Phase 3", recipient="Otherland"),
    ]

    groups = build_groups(records).group_of

    assert groups["1"] == groups["2"]
    assert groups["3"] != groups["1"]  # different recipient: not the same series


def test_generic_amount_titles_are_not_merged_by_series_rule() -> None:
    """The rejected broad rule (strip all digits) would merge these unrelated grants."""
    records = [
        rec("1", title="Government provides RMB 10 million grant for unspecified purposes"),
        rec("2", title="Government provides RMB 20 million grant for unspecified purposes"),
    ]

    groups = build_groups(records).group_of

    assert groups["1"] != groups["2"]
    assert not has_explicit_series_numbering(records[0].title)


def test_missing_values_create_no_edges() -> None:
    records = [
        GroupInput("1", None, None, None, None),
        GroupInput("2", None, None, None, None),
    ]

    groups = build_groups(records).group_of

    assert groups["1"] != groups["2"]


def test_group_ids_are_stable_and_order_independent() -> None:
    records = [rec("1", parent="P"), rec("2", parent="P"), rec("3")]

    first = build_groups(records).group_of
    second = build_groups(list(reversed(records))).group_of

    assert first == second
    assert first["1"] == stable_group_id(["2", "1"]) == stable_group_id(["1", "2"])
    assert first["1"].startswith("g_") and len(first["1"]) == 18


def test_relation_groups_are_reported() -> None:
    result = build_groups([rec("1", parent="P"), rec("2", parent="P"), rec("3")])

    assert result.relation_groups["parent_id"] == [("1", "2")]
    assert result.relation_groups["description"] == []
    assert result.members()[result.group_of["1"]] == ["1", "2"]


def test_duplicate_record_ids_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        build_groups([rec("1"), rec("1")])


def test_unknown_relation_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown relations"):
        build_groups([rec("1")], relations=("fuzzy_name",))
