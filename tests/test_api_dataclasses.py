import unittest
from dataclasses import asdict

from robinhood.api_dataclasses import (
    FullQuote,
    OptionGreekData,
    StockInfo,
    StockPosition,
)
from tests.support import build_option_greek_data


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


if __name__ == "__main__":
    unittest.main()
