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
        "fundamentals": (f"https://api.robinhood.com/fundamentals/{symbol}/"),
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


def build_index_info_payload(
    *,
    id: str = "index-id",
    simple_name: str = "CBOE Volatility Index",
    symbol: str = "VIX",
    state: str = "active",
    tradable_chain_ids: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": id,
        "simple_name": simple_name,
        "symbol": symbol,
        "state": state,
        "tradable_chain_ids": (
            ["chain-id"] if tradable_chain_ids is None else tradable_chain_ids
        ),
    }


def build_index_quote_payload(
    *,
    symbol: str = "VIX",
    instrument_id: str = "index-id",
    value: str = "18.2",
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "instrument_id": instrument_id,
        "value": value,
    }


def build_stock_position_payload(
    *,
    symbol: str = "SPY",
    quantity: str = "3.5",
    type: str = "long",
    clearing_average_cost: str = "500.25",
    instrument_id: str = "stock-id",
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "quantity": quantity,
        "type": type,
        "clearing_average_cost": clearing_average_cost,
        "instrument_id": instrument_id,
    }


def build_option_position_payload(
    *,
    id: str = "position-id",
    chain_symbol: str = "SPY",
    option_id: str = "option-id",
) -> dict[str, object]:
    return {
        "account": "https://api.robinhood.com/accounts/ACC123/",
        "account_number": "ACC123",
        "average_price": "1.50",
        "chain_id": "chain-id",
        "chain_symbol": chain_symbol,
        "clearing_cost_basis": "150.0",
        "clearing_direction": "debit",
        "clearing_intraday_cost_basis": "75.0",
        "clearing_intraday_direction": "debit",
        "clearing_intraday_running_quantity": "1.0",
        "clearing_running_quantity": "2.0",
        "created_at": "2026-04-01T09:30:00Z",
        "expiration_date": "2026-04-17",
        "id": id,
        "intraday_average_open_price": "1.25",
        "intraday_quantity": "1.0",
        "opened_at": "2026-04-01T09:30:00Z",
        "option": f"https://api.robinhood.com/options/instruments/{option_id}/",
        "option_id": option_id,
        "pending_assignment_quantity": "0",
        "pending_buy_quantity": "0",
        "pending_exercise_quantity": "0",
        "pending_expiration_quantity": "0",
        "pending_expired_quantity": "0",
        "pending_sell_quantity": "0",
        "quantity": "2.0",
        "trade_value_multiplier": "100.0",
        "type": "long",
        "updated_at": "2026-04-01T09:30:00Z",
        "url": f"https://api.robinhood.com/options/positions/{id}/",
    }


def build_stock_order_payload(
    *,
    id: str = "order-id",
    instrument_id: str = "stock-id",
    quantity: str = "2.0",
    average_price: str = "10.5",
    total_amount: str = "21.0",
) -> dict[str, object]:
    return {
        "id": id,
        "instrument_id": instrument_id,
        "side": "buy",
        "type": "market",
        "state": "filled",
        "quantity": quantity,
        "average_price": average_price,
        "fees": "0.0",
        "created_at": "2026-04-01T09:30:00Z",
        "updated_at": "2026-04-01T09:31:00Z",
        "last_transaction_at": "2026-04-01T09:31:00Z",
        "total_notional": {"amount": total_amount},
    }


def build_option_order_payload(
    *,
    id: str = "option-order-id",
    chain_symbol: str = "SPY",
) -> dict[str, object]:
    return {
        "id": id,
        "chain_symbol": chain_symbol,
        "direction": "debit",
        "strategy": "long_call",
        "state": "filled",
        "quantity": "1",
        "created_at": "2026-04-01T09:30:00Z",
        "updated_at": "2026-04-01T09:31:00Z",
        "net_amount": "1.25",
        "legs": [
            {
                "side": "buy",
                "expiration_date": "2026-04-17",
                "option_type": "call",
                "strike_price": "500.0",
                "ratio_quantity": "1",
            }
        ],
    }


def build_orderbook_payload() -> dict[str, object]:
    return {
        "asks": [
            {
                "side": "ask",
                "price": {"amount": "501.25"},
                "quantity": "10",
            }
        ],
        "bids": [
            {
                "side": "bid",
                "price": {"amount": "501.0"},
                "quantity": "8",
            }
        ],
    }


def build_watchlist_payload(
    *,
    id: str = "watchlist-id",
    display_name: str = "Core Holdings",
) -> dict[str, object]:
    return {
        "id": id,
        "display_name": display_name,
    }


def build_watchlist_instrument_payload(
    *,
    object_id: str = "instrument-object-id",
    symbol: str = "SPY",
) -> dict[str, object]:
    return {
        "object_type": "instrument",
        "name": f"{symbol} ETF",
        "symbol": symbol,
        "object_id": object_id,
        "high": "505.0",
        "low": "499.0",
        "average_volume": "1000000",
        "volume": "800000",
        "market_cap": "100000000.0",
        "high_52_weeks": "600.0",
        "low_52_weeks": "400.0",
        "pe_ratio": "25.0",
    }


def build_watchlist_currency_pair_payload(
    *,
    object_id: str = "currency-object-id",
    symbol: str = "BTC-USD",
) -> dict[str, object]:
    return {
        "object_type": "currency_pair",
        "name": "Bitcoin / US Dollar",
        "symbol": symbol,
        "object_id": object_id,
        "market_cap": "2000000000.0",
        "high_52_weeks": "70000.0",
        "low_52_weeks": "25000.0",
    }


def build_watchlist_option_strategy_payload(
    *,
    object_id: str = "strategy-object-id",
    chain_symbol: str = "SPY",
) -> dict[str, object]:
    return {
        "object_type": "option_strategy",
        "object_id": object_id,
        "open_price_direction": "credit",
        "name": "Bull Put Spread",
        "chain_symbol": chain_symbol,
        "open_price_without_tvm": {"amount": "1.15"},
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


def build_http_client(*, session: object | None = None) -> RobinhoodHTTPClient:
    from robinhood._http_client import RobinhoodHTTPClient

    client = RobinhoodHTTPClient.__new__(RobinhoodHTTPClient)
    client.session = session if session is not None else Mock()
    client.logger = None
    return client
