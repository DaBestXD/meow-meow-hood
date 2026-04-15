import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from robinhood.api_dataclasses import OptionRequest
from robinhood.db_logic.option_cache import OptionCache
from tests.support import build_option_instrument


class TestOptionCache(unittest.TestCase):
    def make_cache(self) -> OptionCache:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "options.db"
        self.addCleanup(self.temp_dir.cleanup)
        cache = OptionCache(db_path, prune_expired=False)
        self.addCleanup(cache.close)
        return cache

    def test_is_cachable_option_request_rejects_partial_filters(self):
        self.assertTrue(
            OptionCache._is_cachable_option_request(OptionRequest(symbol="SPY"))
        )
        self.assertFalse(
            OptionCache._is_cachable_option_request(
                OptionRequest(symbol="SPY", option_type="call")
            )
        )
        self.assertFalse(
            OptionCache._is_cachable_option_request(
                OptionRequest(symbol="SPY", strike_price=500.0)
            )
        )

    def test_map_option_request_to_ids_filters_by_request_fields(self):
        cache = self.make_cache()
        cache.insert_option_instrument(
            [
                build_option_instrument(
                    id="spy-call-100",
                    chain_symbol="SPY",
                    expiration_date="2026-04-17",
                    type="call",
                    strike_price=100.0,
                ),
                build_option_instrument(
                    id="spy-put-100",
                    chain_symbol="SPY",
                    expiration_date="2026-04-17",
                    type="put",
                    strike_price=100.0,
                ),
                build_option_instrument(
                    id="spy-call-200",
                    chain_symbol="SPY",
                    expiration_date="2026-04-24",
                    type="call",
                    strike_price=200.0,
                ),
                build_option_instrument(
                    id="qqq-call-100",
                    chain_symbol="QQQ",
                    expiration_date="2026-04-17",
                    type="call",
                    strike_price=100.0,
                ),
            ]
        )

        self.assertCountEqual(
            ["spy-call-100", "spy-put-100", "spy-call-200"],
            cache.map_option_request_to_ids(OptionRequest(symbol="SPY"))[
                OptionRequest(symbol="SPY")
            ],
        )
        self.assertCountEqual(
            ["spy-call-100", "spy-put-100"],
            cache.map_option_request_to_ids(
                OptionRequest(symbol="SPY", exp_date="2026-04-17")
            )[OptionRequest(symbol="SPY", exp_date="2026-04-17")],
        )
        self.assertCountEqual(
            ["spy-call-100", "spy-call-200"],
            cache.map_option_request_to_ids(
                OptionRequest(symbol="SPY", option_type="call")
            )[OptionRequest(symbol="SPY", option_type="call")],
        )
        self.assertCountEqual(
            ["spy-call-100", "spy-put-100"],
            cache.map_option_request_to_ids(
                OptionRequest(symbol="SPY", strike_price=100.0)
            )[OptionRequest(symbol="SPY", strike_price=100.0)],
        )

    def test_fetch_expiration_dates_for_symbol_uses_synced_chain_cache(self):
        cache = self.make_cache()
        cache.insert_option_chain(
            SimpleNamespace(
                symbol="SPY",
                expiration_dates=["2026-04-17", "2026-04-24"],
            )
        )

        with (
            patch.object(
                OptionCache, "next_trading_day_timestamp", return_value=2000
            ),
            patch.object(OptionCache, "now_edt_timestamp", return_value=1000),
        ):
            cache.sync_option_chain("SPY")
            dates = cache.fetch_expiration_dates_for_symbol("SPY")

        self.assertCountEqual(["2026-04-17", "2026-04-24"], dates)

    def test_get_chain_id_returns_value_only_when_chain_is_synced(self):
        cache = self.make_cache()
        cache.insert_stock_info(
            SimpleNamespace(
                symbol="SPY",
                id="stock-id",
                tradable_chain_id="chain-id",
            )
        )

        self.assertEqual("", cache.get_chain_id("SPY"))

        with (
            patch.object(
                OptionCache, "next_trading_day_timestamp", return_value=2000
            ),
            patch.object(OptionCache, "now_edt_timestamp", return_value=1000),
        ):
            cache.sync_option_chain("SPY")
            chain_id = cache.get_chain_id("SPY")

        self.assertEqual("chain-id", chain_id)

    def test_execute_query_with_args_supports_single_and_many_args(self):
        cache = self.make_cache()

        cache.execute_query_with_args(
            """
            INSERT INTO main_stock_info VALUES(:symbol, :id, :chain_id)
            """,
            {"symbol": "SPY", "id": "spy-id", "chain_id": "spy-chain"},
        )
        cache.execute_query_with_args(
            """
            INSERT INTO main_stock_info VALUES(:symbol, :id, :chain_id)
            """,
            [
                {"symbol": "QQQ", "id": "qqq-id", "chain_id": "qqq-chain"},
                {"symbol": "IWM", "id": "iwm-id", "chain_id": "iwm-chain"},
            ],
        )

        rows = cache.execute_query_with_args(
            """
            SELECT symbol FROM main_stock_info ORDER BY symbol
            """,
            {},
        )

        self.assertEqual([("IWM",), ("QQQ",), ("SPY",)], rows)

    def test_prune_expired_removes_only_rows_older_than_today(self):
        cache = self.make_cache()
        today_et = datetime.now(ZoneInfo("America/New_York")).date()
        expired = str(today_et - timedelta(days=1))
        fresh = str(today_et + timedelta(days=1))

        cache.execute_query_with_args(
            "INSERT INTO expiration_dates VALUES(:symbol, :exp_date)",
            [
                {"symbol": "SPY", "exp_date": expired},
                {"symbol": "SPY", "exp_date": fresh},
            ],
        )
        cache.execute_query_with_args(
            """
            INSERT INTO option_ids
            VALUES(:option_id, :strike_price, :exp_date, :option_type, :symbol)
            """,
            [
                {
                    "option_id": "expired-id",
                    "strike_price": 100.0,
                    "exp_date": expired,
                    "option_type": "call",
                    "symbol": "SPY",
                },
                {
                    "option_id": "fresh-id",
                    "strike_price": 101.0,
                    "exp_date": fresh,
                    "option_type": "call",
                    "symbol": "SPY",
                },
            ],
        )
        cache.execute_query_with_args(
            """
            INSERT INTO option_expiration_sync
            VALUES(:symbol, :exp_date, :time_to_live)
            """,
            [
                {"symbol": "SPY", "exp_date": expired, "time_to_live": 1},
                {"symbol": "SPY", "exp_date": fresh, "time_to_live": 1},
            ],
        )

        cache.prune_expired()

        self.assertEqual(
            [("SPY", fresh)],
            cache.execute_query_with_args(
                """
                SELECT symbol, exp_date FROM expiration_dates
                ORDER BY exp_date
                """,
                {},
            ),
        )
        self.assertEqual(
            [("fresh-id", fresh)],
            cache.execute_query_with_args(
                """
                SELECT option_id, exp_date FROM option_ids
                ORDER BY option_id
                """,
                {},
            ),
        )
        self.assertEqual(
            [("SPY", fresh)],
            cache.execute_query_with_args(
                """
                SELECT symbol, exp_date FROM option_expiration_sync
                ORDER BY exp_date
                """,
                {},
            ),
        )

    def test_is_option_request_synced_uses_future_ttl_for_cachable_request(
        self,
    ):
        cache = self.make_cache()
        request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        instruments = [
            build_option_instrument(
                chain_symbol="SPY",
                expiration_date="2026-04-17",
            )
        ]

        with patch.object(
            OptionCache, "next_trading_day_timestamp", return_value=2000
        ):
            cache.sync_option_request_full(request, instruments)

        with patch.object(OptionCache, "now_edt_timestamp", return_value=1000):
            self.assertTrue(cache.is_option_request_synced(request))

        with patch.object(OptionCache, "now_edt_timestamp", return_value=3000):
            self.assertFalse(cache.is_option_request_synced(request))

    def test_is_option_request_synced_scopes_expiration_cache_by_symbol(self):
        cache = self.make_cache()
        request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        other_symbol_request = OptionRequest(
            symbol="QQQ", exp_date="2026-04-17"
        )
        instruments = [
            build_option_instrument(
                chain_symbol="SPY",
                expiration_date="2026-04-17",
            )
        ]

        with patch.object(
            OptionCache, "next_trading_day_timestamp", return_value=2000
        ):
            cache.sync_option_request_full(request, instruments)

        with patch.object(OptionCache, "now_edt_timestamp", return_value=1000):
            self.assertTrue(cache.is_option_request_synced(request))
            self.assertFalse(
                cache.is_option_request_synced(other_symbol_request)
            )

    def test_is_option_request_synced_uses_chain_sync_for_symbol_only_request(
        self,
    ):
        cache = self.make_cache()

        with patch.object(
            OptionCache, "next_trading_day_timestamp", return_value=2000
        ):
            cache.sync_option_chain("SPY")

        with patch.object(OptionCache, "now_edt_timestamp", return_value=1000):
            self.assertTrue(
                cache.is_option_request_synced(OptionRequest(symbol="SPY"))
            )

        with patch.object(OptionCache, "now_edt_timestamp", return_value=3000):
            self.assertFalse(
                cache.is_option_request_synced(OptionRequest(symbol="SPY"))
            )

    def test_fetch_strike_prices_returns_sorted_prices(self):
        cache = self.make_cache()
        cache.insert_option_instrument(
            [
                build_option_instrument(
                    id="high",
                    chain_symbol="SPY",
                    expiration_date="2026-04-17",
                    type="call",
                    strike_price=510.0,
                ),
                build_option_instrument(
                    id="low",
                    chain_symbol="SPY",
                    expiration_date="2026-04-17",
                    type="call",
                    strike_price=490.0,
                ),
                build_option_instrument(
                    id="mid",
                    chain_symbol="SPY",
                    expiration_date="2026-04-17",
                    type="call",
                    strike_price=500.0,
                ),
            ]
        )

        result = cache.fetch_strike_prices(
            OptionRequest(
                symbol="SPY",
                exp_date="2026-04-17",
                option_type="call",
            )
        )

        self.assertEqual([490.0, 500.0, 510.0], result)

    def test_sync_option_request_dispatch_only_syncs_broad_requests(self):
        cache = self.make_cache()
        broad_request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        instruments = [build_option_instrument()]
        cache.sync_option_request_full = Mock()

        cache.sync_option_request_dispatch(
            OptionRequest(symbol="SPY", strike_price=500.0),
            instruments,
        )
        cache.sync_option_request_dispatch(
            OptionRequest(symbol="SPY", option_type="call"),
            instruments,
        )
        cache.sync_option_request_dispatch(broad_request, instruments)

        cache.sync_option_request_full.assert_called_once_with(
            broad_request,
            instruments,
        )


if __name__ == "__main__":
    unittest.main()
