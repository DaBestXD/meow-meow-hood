import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
            OptionCache.is_cachable_option_request(OptionRequest(symbol="SPY"))
        )
        self.assertFalse(
            OptionCache.is_cachable_option_request(
                OptionRequest(symbol="SPY", option_type="call")
            )
        )
        self.assertFalse(
            OptionCache.is_cachable_option_request(
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
