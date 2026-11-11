"""Exact decimal storage that is safe on both SQLite and PostgreSQL.

PostgreSQL stores money as ``NUMERIC(38, 10)``. SQLite has no exact decimal type (its NUMERIC
affinity silently converts to binary floating point), so there the canonical decimal text is
stored instead. Both round-trip ``decimal.Decimal`` exactly; arithmetic happens in Python with
``Decimal`` (``compassio_ml.finance``), never with binary floats.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import Numeric, String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator, TypeEngine

PG_PRECISION = 38
PG_SCALE = 10


class DecimalText(TypeDecorator[Decimal]):
    impl = String(64)
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Numeric(PG_PRECISION, PG_SCALE, asdecimal=True))
        return dialect.type_descriptor(String(64))

    def process_bind_param(self, value: Decimal | None, dialect: Dialect) -> Any:
        if value is None:
            return None
        if not isinstance(value, Decimal):
            raise TypeError(f"money must be decimal.Decimal, got {type(value).__name__}")
        if not value.is_finite():
            raise ValueError("money must be finite")
        if dialect.name == "postgresql":
            return value
        return format(value, "f")

    def process_result_value(self, value: Any, dialect: Dialect) -> Decimal | None:
        if value is None:
            return None
        return value if isinstance(value, Decimal) else Decimal(str(value))
