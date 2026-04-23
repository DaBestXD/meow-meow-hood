from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from types import NotImplementedType
from typing import Any, Literal, Self, TypedDict, get_type_hints


class ApiPayloadMixin:
    @classmethod
    @cache
    def _test(cls):
        non_float_keys: set[str] = set()
        float_keys: set[str] = set()
        int_keys: set[str] = set()
        for k, v in get_type_hints(cls).items():
            if v is float:
                float_keys.add(k)
            elif v is int:
                int_keys.add(k)
            else:
                non_float_keys.add(k)
        return non_float_keys, float_keys, int_keys

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Self:
        return cls(**cls._filter_dict(payload, *cls._test()))

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
    position_effect: Literal["open", "close"] | None = None
    side: Literal["sell", "buy"] | None = None

    def __mul__(self, num: int) -> list[Self]:
        if not isinstance(num, int):
            raise NotImplementedType
        if num <= 0:
            raise ValueError(
                f"{self.__class__.__name__} multiplier must be > 0"
            )
        return [self] * num

    def __rmul__(self, num: int) -> list[Self] | NotImplementedType:
        return self.__mul__(num)


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


@dataclass(frozen=True, slots=True)
class IndexQuote(ApiPayloadMixin):
    symbol: str
    value: float
    instrument_id: str

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Self:
        return cls(**cls._filter_dict(payload, *cls._test()))


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

    def __str__(self) -> str:
        return f"Symbol: {self.chain_symbol}, exp_date: {self.expiration_date}, type: {self.type}, strike_price: {self.strike_price}"  # noqa: E501


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
    min_tick_size: float
    type: str
    tradable_chain_id: str | None
    short_selling_tradability: str


@dataclass(frozen=True, slots=True)
class StockPosition(ApiPayloadMixin):
    symbol: str
    quantity: float
    type: str
    clearing_average_cost: float
    instrument_id: str


@dataclass(frozen=True, slots=True)
class OptionPosition(ApiPayloadMixin):
    account: str
    account_number: str
    average_price: float
    chain_id: str
    chain_symbol: str
    clearing_cost_basis: float
    clearing_direction: str
    clearing_intraday_cost_basis: float
    clearing_intraday_direction: str
    clearing_intraday_running_quantity: float
    clearing_running_quantity: float
    created_at: str
    expiration_date: str
    id: str
    intraday_average_open_price: float
    intraday_quantity: float
    opened_at: str
    option: str
    option_id: str
    pending_assignment_quantity: float
    pending_buy_quantity: float
    pending_exercise_quantity: float
    pending_expiration_quantity: float
    pending_expired_quantity: float
    pending_sell_quantity: float
    quantity: float
    trade_value_multiplier: float
    type: str
    updated_at: str
    url: str


@dataclass(frozen=True, slots=True)
class StockOrder(ApiPayloadMixin):
    id: str
    instrument_id: str
    side: str
    type: str
    state: str
    quantity: float
    average_price: float
    price: float
    fees: float
    created_at: str
    updated_at: str
    last_transaction_at: str | None

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Self:
        data = cls._filter_dict(payload, *cls._test())
        total_notional = payload.get("total_notional") or {}
        data["price"] = float(total_notional.get("amount", 0.0) or 0.0)
        return cls(**data)


@dataclass(frozen=True, slots=True)
class OptionOrderLeg(ApiPayloadMixin):
    side: str
    expiration_date: str
    option_type: str
    strike_price: float
    ratio_quantity: int


@dataclass(frozen=True, slots=True)
class OptionOrderHistory(ApiPayloadMixin):
    id: str
    chain_symbol: str
    direction: str
    strategy: str | None
    state: str
    quantity: float
    price: float
    created_at: str
    updated_at: str
    legs: list[OptionOrderLeg]

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Self:
        data = cls._filter_dict(payload, *cls._test())
        data["price"] = float(payload.get("net_amount", 0.0) or 0.0)
        data["legs"] = [
            OptionOrderLeg.from_json(leg) for leg in payload.get("legs", [])
        ]

        return cls(**data)


@dataclass(slots=True)
class BidAsk:
    side: Literal["bid", "ask"]
    price: float
    quantity: int


@dataclass(frozen=True, slots=True)
class OrderBook:
    asks: list[BidAsk]
    bids: list[BidAsk]

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Self:
        data = {}
        data["asks"] = [
            BidAsk(b["side"], float(b["price"]["amount"]), int(b["quantity"]))
            for b in payload["asks"]
        ]
        data["bids"] = [
            BidAsk(b["side"], float(b["price"]["amount"]), int(b["quantity"]))
            for b in payload["bids"]
        ]
        return cls(**data)


@dataclass(frozen=True, slots=True)
class IndexInfo(ApiPayloadMixin):
    id: str
    simple_name: str
    symbol: str
    state: Literal["active", "inactive"]
    tradable_chain_ids: list[str]

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Self:
        return cls(**cls._filter_dict(payload, *cls._test()))


@dataclass(frozen=True, slots=True)
class Index(ApiPayloadMixin):
    name: str
    symbol: str
    object_id: str
    high: float
    low: float
    high_52_weeks: float
    low_52_weeks: float


@dataclass(frozen=True, slots=True)
class CurrencyPair(ApiPayloadMixin):
    name: str
    symbol: str
    object_id: str
    market_cap: float
    high_52_weeks: float
    low_52_weeks: float


@dataclass(frozen=True, slots=True)
class Instrument(ApiPayloadMixin):
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
    symbol: str
    object_id: str
    name: str
    futures_margin_requirement: float


@dataclass(frozen=True, slots=True)
class OptionStrategy(ApiPayloadMixin):
    object_id: str
    open_price_direction: str
    name: str
    chain_symbol: str
    open_price_without_tvm: float

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Self:
        non_float_keys, float_keys, int_keys = cls._test()
        float_keys = float_keys - {"open_price_without_tvm"}
        data = cls._filter_dict(payload, non_float_keys, float_keys, int_keys)
        data["open_price_without_tvm"] = float(
            payload["open_price_without_tvm"]["amount"]
        )
        return cls(**data)


@dataclass(frozen=True, slots=True)
class WatchList:
    name: str
    id: str
    items: list[CurrencyPair | Future | Instrument | OptionStrategy]


class _OptionLeg(TypedDict):
    option: str
    position_effect: Literal["open", "close"]
    ratio_quantity: int
    side: Literal["buy", "sell"]


@dataclass(frozen=True, kw_only=True)
class OptionOrder:
    account: str
    direction: Literal["debit", "credit"]
    form_source: str = "option_chain"
    legs: list[_OptionLeg]
    market_hours: str = "regular_hours"
    override_day_trade_checks: str = "false"
    price: float
    quantity: int
    ref_id: str
    time_in_force: str = "gfd"
    trigger: str = "immediate"
    type: str = "limit"


@dataclass(frozen=True)
class OptionOrderResponse(ApiPayloadMixin):
    id: str
    chain_symbol: str
    cancel_url: str
    direction: Literal["debit", "credit"]
    premium: float
    estimated_total_new_amount: float
    strategy: str


@dataclass(frozen=True, slots=True)
class FuturesProduct(ApiPayloadMixin):
    id: str
    symbol: str
    displaySymbol: str
    description: str
    priceIncrements: float
    activeFuturesContractId: str
    simpleName: str
    settlementStartTime: str


@dataclass(frozen=True, slots=True)
class FuturesContract(ApiPayloadMixin):
    id: str
    productId: str
    symbol: str
    displaySymbol: str
    description: str
    multiplier: float
    expirationMmy: str
    expiration: str
    customerLastCloseDate: str
    tradability: str
    state: str
    settlementStartTime: str
    firstTradeDate: str
    settlementDate: str


@dataclass(frozen=True, slots=True)
class FuturesQuote(ApiPayloadMixin):
    ask_price: float
    ask_size: int
    ask_venue_timestamp: str
    bid_price: float
    bid_size: int
    bid_venue_timestamp: str
    last_trade_price: float
    last_trade_size: int
    last_trade_venue_timestamp: str
    symbol: str
    instrument_id: str
    state: str
    updated_at: str
    out_of_band: bool
