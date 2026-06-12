from dataclasses import asdict

import pytest

from robinhood.dataclasses.api_dataclasses import (
    IndexInfo,
    IndexQuote,
    InstrumentQuote,
    OptionGreekData,
    OptionOrderHistory,
    OptionPosition,
    OptionRequest,
    OrderBook,
    StockInfo,
    StockOrder,
    StockOrderResponse,
    StockPosition,
)
from tests.support import (
    build_index_info_payload,
    build_index_quote_payload,
    build_instrument_quote_payload,
    build_option_greek_data,
    build_option_order_payload,
    build_option_position_payload,
    build_orderbook_payload,
    build_stock_order_payload,
    build_stock_order_response_payload,
)


class TestApiDataclasses:
    def test_option_request_normalizes_symbol(self):
        request = OptionRequest(symbol="spy", exp_date="2026-04-17")

        assert "SPY" == request.symbol

    def test_option_greek_data_from_json_coerces_numeric_fields(self):
        payload = asdict(build_option_greek_data())
        payload["ask_price"] = "1.25"
        payload["ask_size"] = "7"
        payload["bid_price"] = None
        payload.pop("vega")

        greek_data = OptionGreekData.from_json(payload)

        assert 1.25 == greek_data.ask_price
        assert 7 == greek_data.ask_size
        assert 0.0 == greek_data.bid_price
        assert 0.0 == greek_data.vega

    def test_stock_info_from_json_coerces_float_fields_and_preserves_keys(self):
        payload = {
            "id": "stock-id",
            "url": "https://api.robinhood.com/instruments/stock-id/",
            "quote": "https://api.robinhood.com/quotes/SPY/",
            "fundamentals": "https://api.robinhood.com/fundamentals/SPY/",
            "market": "XNYS",
            "name": "SPDR S&P 500 ETF Trust",
            "tradeable": True,
            "symbol": "SPY",
            "country": "US",
            "type": "etp",
            "tradable_chain_id": "chain-id",
            "short_selling_tradability": "tradeable",
            "margin_initial_ratio": "0.50",
            "maintenance_ratio": None,
            "day_trade_ratio": "0.25",
            "min_tick_size": None,
        }

        stock_info = StockInfo.from_json(payload)

        assert "SPY" == stock_info.symbol
        assert "chain-id" == stock_info.tradable_chain_id
        assert 0.5 == stock_info.margin_initial_ratio
        assert 0.0 == stock_info.maintenance_ratio
        assert 0.25 == stock_info.day_trade_ratio
        assert 0.0 == stock_info.min_tick_size

    def test_instrument_quote_from_json_coerces_ints_and_floats(self):
        payload = build_instrument_quote_payload()
        payload["last_trade_price"] = None
        payload["last_extended_hours_trade_price"] = "0"

        quote = InstrumentQuote.from_json(payload)

        assert 10.5 == quote.ask_price
        assert 11 == quote.ask_size
        assert 9 == quote.bid_size
        assert 0.0 == quote.last_trade_price

    def test_stock_position_from_json_keeps_selected_fields(self):
        payload = {
            "symbol": "TQQQ",
            "quantity": "0.92278000",
            "type": "long",
            "clearing_average_cost": "27.83",
            "instrument_id": "91f7ea28-e413-4ca4-b9fa-91f5822f8b8d",
        }

        position = StockPosition.from_json(payload)

        assert "TQQQ" == position.symbol
        assert 0.92278 == position.quantity
        assert "long" == position.type
        assert 27.83 == position.clearing_average_cost
        assert position.total_notional == pytest.approx(25.68, abs=0.01)
        assert "91f7ea28-e413-4ca4-b9fa-91f5822f8b8d" == position.instrument_id

    def test_index_info_from_json_uses_simple_name_and_empty_chain_ids(self):
        payload = build_index_info_payload(tradable_chain_ids=[])

        index_info = IndexInfo.from_json(payload)

        assert "CBOE Volatility Index" == index_info.simple_name
        assert "VIX" == index_info.symbol
        assert [] == index_info.tradable_chain_ids

    def test_index_quote_from_json_coerces_numeric_value(self):
        quote = IndexQuote.from_json(build_index_quote_payload(value="19.45"))

        assert "VIX" == quote.symbol
        assert 19.45 == quote.value
        assert "index-id" == quote.instrument_id

    def test_option_position_from_json_coerces_float_fields(self):
        position = OptionPosition.from_json(build_option_position_payload())

        assert "SPY" == position.chain_symbol
        assert 1.5 == position.average_price
        assert 2.0 == position.quantity
        assert 100.0 == position.trade_value_multiplier

    def test_stock_order_from_json_uses_total_notional_as_price(self):
        order = StockOrder.from_json(build_stock_order_payload())

        assert "order-id" == order.id
        assert 2.0 == order.quantity
        assert 10.5 == order.average_price
        assert 21.0 == order.price

    def test_option_order_from_json_builds_legs_and_net_amount_price(self):
        order = OptionOrderHistory.from_json(build_option_order_payload())

        assert "option-order-id" == order.id
        assert 1.0 == order.quantity
        assert 1.25 == order.price
        assert 1 == len(order.legs)
        assert "buy" == order.legs[0].side
        assert 500.0 == order.legs[0].strike_price
        assert 1 == order.legs[0].ratio_quantity

    def test_stock_order_response_from_json_builds_nested_amounts(self):
        order = StockOrderResponse.from_json(
            build_stock_order_response_payload()
        )

        assert "6a05547e-6b7d-4a8b-8275-f925ab3b4e6c" == order.id
        assert 1.0 == order.quantity
        assert 0.0 == order.cumulative_quantity
        assert 1.35 == order.price
        assert order.average_price is None
        assert 0.0 == order.dollar_based_amount
        assert {
            "amount": "1.35",
            "currency_code": "USD",
            "currency_id": "1072fc76-1862-41ab-82c2-485837590762",
        } == order.total_notional
        assert (
            "https://api.robinhood.com/orders/6a05547e-6b7d-4a8b-8275-f925ab3b4e6c/cancel/"  # noqa: E501
            == order.cancel
        )

    def test_orderbook_from_json_builds_bid_and_ask_levels(self):
        orderbook = OrderBook.from_json(build_orderbook_payload())

        assert "ask" == orderbook.asks[0].side
        assert 501.25 == orderbook.asks[0].price
        assert 10 == orderbook.asks[0].quantity
        assert "bid" == orderbook.bids[0].side
        assert 501.0 == orderbook.bids[0].price
        assert 8 == orderbook.bids[0].quantity
