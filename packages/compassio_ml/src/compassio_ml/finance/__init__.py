"""Source-aware financial data contract (Task 004.5).

See docs/architecture/financial_data_contract.md.
"""

from compassio_ml.finance.contract import (
    AggregationError,
    AggregationResult,
    AmountLevel,
    AmountUnit,
    FlowKind,
    MonetaryAmount,
    PriceBasis,
    aggregate,
)

__all__ = [
    "AggregationError",
    "AggregationResult",
    "AmountLevel",
    "AmountUnit",
    "FlowKind",
    "MonetaryAmount",
    "PriceBasis",
    "aggregate",
]
