from dataclasses import dataclass
from typing import Any, ClassVar, Literal, Self

from .constants import (
    FULL_QUOTE_FLOAT_KEYS,
    FULL_QUOTE_INT_KEYS,
    FULL_QUOTE_NON_FLOAT_KEYS,
    OPTION_CHAIN_FLOAT_KEYS,
    OPTION_CHAIN_INT_KEYS,
    OPTION_CHAIN_NON_FLOAT_KEYS,
    OPTION_GREEK_DATA_FLOAT_KEYS,
    OPTION_GREEK_DATA_INT_KEYS,
    OPTION_GREEK_DATA_NON_FLOAT_KEYS,
    OPTION_INSTRUMENT_FLOAT_KEYS,
    OPTION_INSTRUMENT_NON_FLOAT_KEYS,
    STOCK_INFO_FLOAT_KEYS,
    STOCK_INFO_NON_FLOAT_KEYS,
)


class ApiPayloadMixin:
    _NON_FLOAT_KEYS: ClassVar[set[str]] = set()
    _FLOAT_KEYS: ClassVar[set[str]] = set()
    _INT_KEYS: ClassVar[set[str]] = set()

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Self:
        return cls(
            **ApiPayloadMixin._filter_dict(
                payload,
                cls._NON_FLOAT_KEYS,
                cls._FLOAT_KEYS,
                cls._INT_KEYS,
            )
        )

    @staticmethod
    def _filter_dict(
        payload: dict[str, Any],
        non_float_keys: set[str],
        float_keys: set[str],
        int_keys: set[str],
    ) -> dict[str, Any]:
        new_dict: dict[str, Any] = {}
        for k in non_float_keys:
            new_dict[k] = payload[k]
        for k in float_keys:
            new_dict[k] = float(payload.get(k, 0.0) or 0.0)
        for k in int_keys:
            new_dict[k] = int(payload.get(k, 0) or 0)
        return new_dict


@dataclass(frozen=True, kw_only=True)
class OptionRequest:
    """
    Fields:
        symbol, option_type, strike_price, exp_date, chain_id
    Only required field is symbol
    Optional fields allow for greater control of returned data
    """

    symbol: str
    exp_date: str | None = None
    option_type: Literal["call", "put"] | None = None
    strike_price: float | None = None


@dataclass(frozen=True, slots=True)
class FullQuote(ApiPayloadMixin):
    """
    Useful fields:
        ask/bid price, ask/bid size
    """

    ask_price: float
    ask_size: int
    bid_price: float
    bid_size: int
    last_trade_price: float
    last_extended_hours_trade_price: float
    last_non_reg_trade_price: float
    previous_close: float
    adjusted_previous_close: float
    symbol: str
    updated_at: str
    instrument_id: str
    state: str
    _NON_FLOAT_KEYS: ClassVar[set[str]] = FULL_QUOTE_NON_FLOAT_KEYS
    _FLOAT_KEYS: ClassVar[set[str]] = FULL_QUOTE_FLOAT_KEYS
    _INT_KEYS: ClassVar[set[str]] = FULL_QUOTE_INT_KEYS


@dataclass(frozen=True, slots=True)
class OptionChain(ApiPayloadMixin):
    """
    Option chain metadata
    Useful fields: id, symbol, expiration_dates
    """

    id: str
    symbol: str
    can_open_position: bool
    cash_component: str | None
    expiration_dates: list[str]
    trade_value_multiplier: float
    underlying_instruments: list[dict]
    min_ticks: dict
    min_ticks_multileg: dict
    late_close_state: str
    extended_hours_state: str
    underlyings: list[dict]
    settle_on_open: bool
    sellout_time_to_expiration: int
    _NON_FLOAT_KEYS: ClassVar[set[str]] = OPTION_CHAIN_NON_FLOAT_KEYS
    _FLOAT_KEYS: ClassVar[set[str]] = OPTION_CHAIN_FLOAT_KEYS
    _INT_KEYS: ClassVar[set[str]] = OPTION_CHAIN_INT_KEYS


@dataclass(frozen=True, slots=True)
class OptionInstrument(ApiPayloadMixin):
    """
    Only holds option metadata:
    Not actual option data besides strike price/expiration_date
    """

    chain_id: str
    chain_symbol: str
    created_at: str
    expiration_date: str
    id: str
    issue_date: str
    min_ticks: dict[str, float]
    rhs_tradability: str
    state: str
    strike_price: float
    tradability: str
    type: str
    updated_at: str
    url: str
    sellout_datetime: str
    long_strategy_code: str
    short_strategy_code: str
    underlying_type: str
    _NON_FLOAT_KEYS: ClassVar[set[str]] = OPTION_INSTRUMENT_NON_FLOAT_KEYS
    _FLOAT_KEYS: ClassVar[set[str]] = OPTION_INSTRUMENT_FLOAT_KEYS


@dataclass(frozen=True, slots=True)
class OptionGreekData(ApiPayloadMixin):
    """
    Holds option data:
    Options Greeks, Option price(bid/ask/oi/volume)
    """

    adjusted_mark_price: float
    adjusted_mark_price_round_down: float
    ask_price: float
    ask_size: int
    bid_price: float
    bid_size: int
    break_even_price: float
    high_price: float
    instrument: str
    instrument_id: str
    last_trade_price: float
    last_trade_size: int
    low_price: float
    mark_price: float
    open_interest: int
    previous_close_date: str
    previous_close_price: float
    updated_at: str
    volume: int
    symbol: str
    occ_symbol: str
    state: str
    chance_of_profit_long: float
    chance_of_profit_short: float
    delta: float
    gamma: float
    implied_volatility: float
    rho: float
    theta: float
    vega: float
    pricing_model: str
    high_fill_rate_buy_price: float
    high_fill_rate_sell_price: float
    low_fill_rate_buy_price: float
    low_fill_rate_sell_price: float
    _NON_FLOAT_KEYS: ClassVar[set[str]] = OPTION_GREEK_DATA_NON_FLOAT_KEYS
    _FLOAT_KEYS: ClassVar[set[str]] = OPTION_GREEK_DATA_FLOAT_KEYS
    _INT_KEYS: ClassVar[set[str]] = OPTION_GREEK_DATA_INT_KEYS


@dataclass(frozen=True, slots=True)
class StockInfo(ApiPayloadMixin):
    id: str
    url: str
    quote: str
    fundamentals: str
    market: str
    name: str
    tradeable: bool
    symbol: str
    margin_initial_ratio: float
    maintenance_ratio: float
    country: str
    day_trade_ratio: float
    min_tick_size: float | None
    type: str
    tradable_chain_id: str | None
    short_selling_tradability: str
    _NON_FLOAT_KEYS: ClassVar[set[str]] = STOCK_INFO_NON_FLOAT_KEYS
    _FLOAT_KEYS: ClassVar[set[str]] = STOCK_INFO_FLOAT_KEYS
