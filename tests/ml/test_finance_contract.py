"""Financial data contract validators. ARTIFICIAL amounts only (example_* ids)."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from compassio_ml.finance import (
    AggregationError,
    AmountLevel,
    AmountUnit,
    FlowKind,
    MonetaryAmount,
    PriceBasis,
    aggregate,
)


def amount(**over: Any) -> MonetaryAmount:
    fields: dict[str, Any] = {
        "source_id": "example_source",
        "source_record_id": "example_1",
        "flow_kind": FlowKind.COMMITMENT,
        "level": AmountLevel.PROJECT,
        "value": Decimal("100"),
        "unit": AmountUnit.UNITS,
        "currency": "USD",
        "observation_date": date(2000, 1, 1),
        "date_meaning": "commitment date",
    }
    fields.update(over)
    return MonetaryAmount(**fields)


def test_sum_within_one_meaning_and_unit_scaling() -> None:
    result = aggregate(
        [
            amount(),
            amount(source_record_id="example_2", value=Decimal("2.5"), unit=AmountUnit.MILLIONS),
            amount(source_record_id="example_3", value=Decimal("1"), unit=AmountUnit.THOUSANDS),
        ]
    )

    assert result.total_in_units == Decimal("2501100")
    assert result.summed_records == 3
    assert result.currency == "USD"  # unchanged: no conversion


def test_missing_values_are_excluded_and_counted_never_zero() -> None:
    result = aggregate([amount(), amount(source_record_id="example_2", value=None)])

    assert result.total_in_units == Decimal("100")
    assert result.summed_records == 1
    assert result.missing_value_records == 1


@pytest.mark.parametrize(
    "other",
    [
        {"flow_kind": FlowKind.DISBURSEMENT},
        {"flow_kind": FlowKind.CO_FINANCING},
        {"currency": "EUR"},
        {"price_basis": PriceBasis.CONSTANT_2021_USD},
        {"level": AmountLevel.TRANSACTION},
    ],
)
def test_different_meanings_cannot_be_added(other: dict[str, Any]) -> None:
    with pytest.raises(AggregationError, match="different"):
        aggregate([amount(), amount(source_record_id="example_2", **other)])


def test_unknown_currency_blocks_aggregation() -> None:
    with pytest.raises(AggregationError, match="unknown currency"):
        aggregate([amount(currency=None), amount(source_record_id="example_2", currency=None)])


@pytest.mark.parametrize("level", [AmountLevel.COUNTRY_AGGREGATE, AmountLevel.FUND_AGGREGATE])
def test_aggregates_are_never_summed(level: AmountLevel) -> None:
    with pytest.raises(AggregationError, match="aggregates"):
        aggregate([amount(level=level), amount(source_record_id="example_2", level=level)])


def test_multi_country_amounts_are_not_summed() -> None:
    with pytest.raises(AggregationError, match="multi-country"):
        aggregate([amount(), amount(source_record_id="example_2", multi_country=True)])


def test_duplicate_representations_must_be_resolved() -> None:
    a = amount(source_id="example_a", project_key="example_project")
    b = amount(source_id="example_b", source_record_id="example_2", project_key="example_project")

    with pytest.raises(AggregationError, match="duplicate representations"):
        aggregate([a, b])


@pytest.mark.parametrize("currency", ["usd", "US$", "DOLLAR", ""])
def test_currency_must_be_iso_4217(currency: str) -> None:
    with pytest.raises(ValidationError):
        amount(currency=currency)


def test_negative_values_only_for_transaction_reversals() -> None:
    reversal = amount(
        level=AmountLevel.TRANSACTION,
        flow_kind=FlowKind.DISBURSEMENT,
        value=Decimal("-50"),
        date_meaning="transaction date",
    )

    assert reversal.value == Decimal("-50")
    with pytest.raises(ValidationError, match="negative"):
        amount(value=Decimal("-1"))


def test_constant_price_basis_requires_usd_and_value_must_be_finite() -> None:
    with pytest.raises(ValidationError, match="USD"):
        amount(currency="EUR", price_basis=PriceBasis.CONSTANT_2021_USD)
    with pytest.raises(ValidationError, match="finite"):
        amount(value=Decimal("Infinity"))


def test_empty_aggregation_and_estimated_count() -> None:
    with pytest.raises(AggregationError):
        aggregate([])
    result = aggregate([amount(estimated=True), amount(source_record_id="example_2")])
    assert result.estimated_records == 1
