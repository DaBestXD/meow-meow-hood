from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

from robinhood.api_dataclasses import OptionGreekData, OptionInstrument

if TYPE_CHECKING:
    from robinhood._http_client import RobinhoodHTTPClient
    from robinhood.robinhood_api_logic import Robinhood


def build_option_instrument(
    *,
    id: str = "instrument-id",
    chain_id: str = "chain-id",
    chain_symbol: str = "SPY",
    expiration_date: str = "2026-04-17",
    strike_price: float = 500.0,
    type: str = "call",
) -> OptionInstrument:
    return OptionInstrument(
        chain_id=chain_id,
        chain_symbol=chain_symbol,
        created_at="2026-04-01T09:30:00Z",
        expiration_date=expiration_date,
        id=id,
        issue_date="2026-04-01",
        min_ticks={"cutoff_price": 3.0, "below_tick": 0.01, "above_tick": 0.05},
        rhs_tradability="tradable",
        state="active",
        strike_price=strike_price,
        tradability="tradable",
        type=type,
        updated_at="2026-04-01T09:30:00Z",
        url=f"https://api.robinhood.com/options/instruments/{id}/",
        sellout_datetime="2026-04-17T16:00:00Z",
        long_strategy_code="long_call",
        short_strategy_code="short_call",
        underlying_type="equity",
    )


def build_option_greek_data(
    *,
    instrument_id: str = "instrument-id",
    symbol: str = "SPY",
) -> OptionGreekData:
    return OptionGreekData(
        adjusted_mark_price=1.0,
        adjusted_mark_price_round_down=0.99,
        ask_price=1.05,
        ask_size=10,
        bid_price=0.95,
        bid_size=12,
        break_even_price=501.0,
        high_price=1.2,
        instrument=f"https://api.robinhood.com/options/instruments/{instrument_id}/",
        instrument_id=instrument_id,
        last_trade_price=1.0,
        last_trade_size=1,
        low_price=0.8,
        mark_price=1.0,
        open_interest=100,
        previous_close_date="2026-04-01",
        previous_close_price=0.9,
        updated_at="2026-04-01T09:30:00Z",
        volume=200,
        symbol=symbol,
        occ_symbol=f"{symbol}260417C00500000",
        state="active",
        chance_of_profit_long=0.5,
        chance_of_profit_short=0.5,
        delta=0.5,
        gamma=0.1,
        implied_volatility=0.2,
        rho=0.01,
        theta=-0.02,
        vega=0.03,
        pricing_model="black_scholes",
        high_fill_rate_buy_price=1.01,
        high_fill_rate_sell_price=0.99,
        low_fill_rate_buy_price=0.98,
        low_fill_rate_sell_price=0.96,
    )


def build_option_chain_payload(
    *,
    id: str = "chain-id",
    symbol: str = "SPY",
    expiration_dates: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": id,
        "symbol": symbol,
        "can_open_position": True,
        "cash_component": None,
        "expiration_dates": expiration_dates or ["2026-04-17", "2026-04-24"],
        "trade_value_multiplier": "100.0",
        "underlying_instruments": [
            {
                "id": "stock-id",
                "instrument": f"https://api.robinhood.com/instruments/{symbol}/",
            }
        ],
        "min_ticks": {
            "cutoff_price": 3.0,
            "below_tick": 0.01,
            "above_tick": 0.05,
        },
        "min_ticks_multileg": {
            "cutoff_price": 3.0,
            "below_tick": 0.01,
            "above_tick": 0.05,
        },
        "late_close_state": "regular_hours",
        "extended_hours_state": "closed",
        "underlyings": [{"symbol": symbol, "quantity": 100}],
        "settle_on_open": False,
        "sellout_time_to_expiration": 3600,
    }


def build_full_quote_payload(
    *,
    symbol: str = "SPY",
    instrument_id: str = "instrument-id",
) -> dict[str, object]:
    return {
        "ask_price": "10.5",
        "ask_size": "11",
        "bid_price": "10.4",
        "bid_size": "9",
        "last_trade_price": "10.45",
        "last_extended_hours_trade_price": "10.3",
        "last_non_reg_trade_price": "10.35",
        "previous_close": "10.0",
        "adjusted_previous_close": "10.1",
        "symbol": symbol,
        "updated_at": "2026-04-01T09:30:00Z",
        "instrument_id": instrument_id,
        "state": "active",
    }


def build_stock_info_payload(
    *,
    id: str = "stock-id",
    symbol: str = "SPY",
    tradable_chain_id: str = "chain-id",
) -> dict[str, object]:
    return {
        "id": id,
        "url": f"https://api.robinhood.com/instruments/{id}/",
        "quote": f"https://api.robinhood.com/quotes/{symbol}/",
        "fundamentals": (
            f"https://api.robinhood.com/fundamentals/{symbol}/"
        ),
        "market": "XNYS",
        "name": f"{symbol} Test Instrument",
        "tradeable": True,
        "symbol": symbol,
        "country": "US",
        "type": "etp",
        "tradable_chain_id": tradable_chain_id,
        "short_selling_tradability": "tradeable",
        "margin_initial_ratio": "0.50",
        "maintenance_ratio": "0.25",
        "day_trade_ratio": "0.25",
        "min_tick_size": "0.01",
    }


def build_robinhood_client(
    *,
    http_client: object | None = None,
    db_cache: object | None = None,
) -> Robinhood:
    from robinhood.robinhood_api_logic import Robinhood

    client = Robinhood.__new__(Robinhood)
    client._http_client = http_client if http_client is not None else Mock()
    client._db_cache = db_cache
    client.logger = None
    return client


def build_http_client(
    *, session: object | None = None
) -> RobinhoodHTTPClient:
    from robinhood._http_client import RobinhoodHTTPClient

    client = RobinhoodHTTPClient.__new__(RobinhoodHTTPClient)
    client.session = session if session is not None else Mock()
    client.logger = None
    return client
