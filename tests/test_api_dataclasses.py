import unittest
from dataclasses import asdict

from robinhood.api_dataclasses import (
    FullQuote,
    IndexInfo,
    IndexQuote,
    OptionGreekData,
    OptionOrderHistory,
    OptionPosition,
    OrderBook,
    StockInfo,
    StockOrder,
    StockPosition,
)
from tests.support import (
    build_index_info_payload,
    build_index_quote_payload,
    build_option_greek_data,
    build_option_order_payload,
    build_option_position_payload,
    build_orderbook_payload,
    build_stock_order_payload,
)


class TestApiDataclasses(unittest.TestCase):
    def test_option_greek_data_from_json_coerces_numeric_fields(self):
        payload = asdict(build_option_greek_data())
        payload["ask_price"] = "1.25"
        payload["ask_size"] = "7"
        payload["bid_price"] = None
        payload.pop("vega")

        greek_data = OptionGreekData.from_json(payload)

        self.assertEqual(1.25, greek_data.ask_price)
        self.assertEqual(7, greek_data.ask_size)
        self.assertEqual(0.0, greek_data.bid_price)
        self.assertEqual(0.0, greek_data.vega)

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

        self.assertEqual("SPY", stock_info.symbol)
        self.assertEqual("chain-id", stock_info.tradable_chain_id)
        self.assertEqual(0.5, stock_info.margin_initial_ratio)
        self.assertEqual(0.0, stock_info.maintenance_ratio)
        self.assertEqual(0.25, stock_info.day_trade_ratio)
        self.assertEqual(0.0, stock_info.min_tick_size)

    def test_full_quote_from_json_coerces_ints_and_floats(self):
        payload = {
            "ask_price": "10.5",
            "ask_size": "11",
            "bid_price": "10.4",
            "bid_size": "9",
            "last_trade_price": None,
            "last_extended_hours_trade_price": "0",
            "last_non_reg_trade_price": "10.3",
            "previous_close": "10.0",
            "adjusted_previous_close": "10.1",
            "symbol": "SPY",
            "updated_at": "2026-04-01T09:30:00Z",
            "instrument_id": "instrument-id",
            "state": "active",
        }

        quote = FullQuote.from_json(payload)

        self.assertEqual(10.5, quote.ask_price)
        self.assertEqual(11, quote.ask_size)
        self.assertEqual(9, quote.bid_size)
        self.assertEqual(0.0, quote.last_trade_price)

    def test_stock_position_from_json_keeps_selected_fields(self):
        payload = {
            "symbol": "TQQQ",
            "quantity": "0.92278000",
            "type": "long",
            "clearing_average_cost": "27.83",
            "instrument_id": "91f7ea28-e413-4ca4-b9fa-91f5822f8b8d",
        }

        position = StockPosition.from_json(payload)

        self.assertEqual("TQQQ", position.symbol)
        self.assertEqual(0.92278, position.quantity)
        self.assertEqual("long", position.type)
        self.assertEqual(27.83, position.clearing_average_cost)
        self.assertEqual(
            "91f7ea28-e413-4ca4-b9fa-91f5822f8b8d",
            position.instrument_id,
        )

    def test_index_info_from_json_uses_simple_name_and_empty_chain_ids(self):
        payload = build_index_info_payload(tradable_chain_ids=[])

        index_info = IndexInfo.from_json(payload)

        self.assertEqual("CBOE Volatility Index", index_info.simple_name)
        self.assertEqual("VIX", index_info.symbol)
        self.assertEqual([], index_info.tradable_chain_ids)

    def test_index_quote_from_json_coerces_numeric_value(self):
        quote = IndexQuote.from_json(build_index_quote_payload(value="19.45"))

        self.assertEqual("VIX", quote.symbol)
        self.assertEqual(19.45, quote.value)
        self.assertEqual("index-id", quote.instrument_id)

    def test_option_position_from_json_coerces_float_fields(self):
        position = OptionPosition.from_json(build_option_position_payload())

        self.assertEqual("SPY", position.chain_symbol)
        self.assertEqual(1.5, position.average_price)
        self.assertEqual(2.0, position.quantity)
        self.assertEqual(100.0, position.trade_value_multiplier)

    def test_stock_order_from_json_uses_total_notional_as_price(self):
        order = StockOrder.from_json(build_stock_order_payload())

        self.assertEqual("order-id", order.id)
        self.assertEqual(2.0, order.quantity)
        self.assertEqual(10.5, order.average_price)
        self.assertEqual(21.0, order.price)

    def test_option_order_from_json_builds_legs_and_net_amount_price(self):
        order = OptionOrderHistory.from_json(build_option_order_payload())

        self.assertEqual("option-order-id", order.id)
        self.assertEqual(1.0, order.quantity)
        self.assertEqual(1.25, order.price)
        self.assertEqual(1, len(order.legs))
        self.assertEqual("buy", order.legs[0].side)
        self.assertEqual(500.0, order.legs[0].strike_price)
        self.assertEqual(1, order.legs[0].ratio_quantity)

    def test_orderbook_from_json_builds_bid_and_ask_levels(self):
        orderbook = OrderBook.from_json(build_orderbook_payload())

        self.assertEqual("ask", orderbook.asks[0].side)
        self.assertEqual(501.25, orderbook.asks[0].price)
        self.assertEqual(10, orderbook.asks[0].quantity)
        self.assertEqual("bid", orderbook.bids[0].side)
        self.assertEqual(501.0, orderbook.bids[0].price)
        self.assertEqual(8, orderbook.bids[0].quantity)


if __name__ == "__main__":
    unittest.main()
