from dataclasses import dataclass


@dataclass(slots=True)
class FullQuote:
    ask_price: float
    ask_size: int
    venue_ask_time: str
    bid_price: float
    bid_size: int
    venue_bid_time: str
    last_trade_price: float
    venue_last_trade_time: str
    last_extended_hours_trade_price: float
    last_non_reg_trade_price: float
    venue_last_non_reg_trade_time: str
    previous_close: float
    adjusted_previous_close: float
    previous_close_date: str
    symbol: str
    trading_halted: bool
    has_traded: bool
    last_trade_price_source: str
    last_non_reg_trade_price_source: str
    updated_at: str
    instrument: str
    instrument_id: str
    state: str

@dataclass(frozen=True, slots=True)
class OptionChain:
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
class OptionInstrument:
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
