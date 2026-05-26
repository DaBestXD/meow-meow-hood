from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self

from robinhood.dataclasses.api_dataclasses import ApiPayloadMixin


@dataclass(frozen=True, slots=True)
class Index(ApiPayloadMixin):
    """Index item returned inside watchlist data."""

    name: str
    symbol: str
    object_id: str
    high: float
    low: float
    high_52_weeks: float
    low_52_weeks: float


@dataclass(frozen=True, slots=True)
class CurrencyPair(ApiPayloadMixin):
    """Currency pair item returned inside watchlist data."""

    name: str
    symbol: str
    object_id: str
    market_cap: float
    high_52_weeks: float
    low_52_weeks: float


@dataclass(frozen=True, slots=True)
class Instrument(ApiPayloadMixin):
    """Equity instrument item returned inside watchlist data."""

    name: str
    symbol: str
    object_id: str
    high: float
    low: float
    average_volume: float
    volume: float
    market_cap: float
    high_52_weeks: float
    low_52_weeks: float
    pe_ratio: float


@dataclass(frozen=True, slots=True)
class Future(ApiPayloadMixin):
    """Future item returned inside watchlist data."""

    name: str
    symbol: str
    object_id: str
    futures_margin_requirement: float


@dataclass(frozen=True, slots=True)
class OptionStrategy(ApiPayloadMixin):
    """Option strategy item returned inside watchlist data."""

    object_id: str
    open_price_direction: str
    name: str
    chain_symbol: str
    open_price_without_tvm: float

    @property
    def symbol(self) -> str:
        return self.name

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Self:
        """Create a watchlist option strategy from a nested price payload."""
        non_float_keys, float_keys, int_keys = cls._dataclass_field_factory()
        non_float_keys = non_float_keys - {"strategy_code"}
        float_keys = float_keys - {"open_price_without_tvm"}
        data = cls._filter_dict(payload, non_float_keys, float_keys, int_keys)
        data["open_price_without_tvm"] = float(
            payload["open_price_without_tvm"]["amount"]
        )
        # Raw object_id from the json payload doesn't map to anything
        # useful. Use strategy_code for uuid that is searchable.
        strategy_code = payload.get("strategy_code")
        data["object_id"] = (
            strategy_code[:-3] if strategy_code else data["object_id"]
        )
        return cls(**data)


WatchListItem = Index | CurrencyPair | Instrument | Future | OptionStrategy


@dataclass(frozen=True, slots=True)
class WatchList:
    """Named watchlist and its mixed item collection."""

    name: str
    id: str
    items: list[WatchListItem]
