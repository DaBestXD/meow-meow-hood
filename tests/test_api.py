from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from robinhood.async_robinhood_class import AsyncRobinhood
from robinhood.browser_functions.browser_token_parser import Chrome
from robinhood.constants import (
    API_FUTURES_QUOTES,
    API_INDEX_QUOTE,
    API_INSTRUMENTS,
    API_OPTION_CHAINS,
    API_POSITIONS_OPTIONS,
    API_QUOTES,
    API_WATCHLIST,
    API_WATCHLIST_DEFAULT,
    API_WATCHLIST_ITEMS,
    PARAM_ACCOUNT_NUMBER,
    PARAM_ID,
    PARAM_LIST_ID,
    PARAM_LOAD_ALL_ATTRIBUTES,
    PARAM_NON_ZERO,
    PARAM_SYMBOLS,
)
from robinhood.dataclasses.api_dataclasses import (
    IndexQuote,
    InstrumentQuote,
    OptionChain,
    OptionPosition,
    OptionRequest,
    StockInfo,
    StockPosition,
)
from robinhood.dataclasses.watchlist_classes import Future
from robinhood.sync_robinhood_class import Robinhood
from tests.support import (
    build_async_robinhood_client,
    build_index_quote_payload,
    build_instrument_quote_payload,
    build_option_chain_payload,
    build_option_position_payload,
    build_robinhood_client,
    build_stock_info_payload,
    build_stock_position_payload,
    build_watchlist_currency_pair_payload,
    build_watchlist_instrument_payload,
    build_watchlist_option_strategy_payload,
    build_watchlist_payload,
)


class FakeCache:
    def __init__(
        self,
        synced_requests: set[OptionRequest],
        ids_by_request: dict[OptionRequest, list[str]],
    ) -> None:
        self._synced_requests = synced_requests
        self._ids_by_request = ids_by_request

    def is_option_request_synced(self, option_request: OptionRequest) -> bool:
        return option_request in self._synced_requests

    def map_option_request_to_ids(
        self, option_request: OptionRequest
    ) -> dict[OptionRequest, list[str]]:
        return {option_request: self._ids_by_request[option_request]}


def build_async_api_client(*, db_cache: object | None = None) -> AsyncRobinhood:
    client = build_async_robinhood_client(
        http_client=SimpleNamespace(
            _get=AsyncMock(),
            _post=AsyncMock(),
            _delete=AsyncMock(),
            close=AsyncMock(),
        ),
        db_cache=db_cache,
    )
    return client


class TestAsyncRobinhoodAPI(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        loop = getattr(self, "_loop_to_close", None)
        if loop is not None and not loop.is_closed():
            loop.close()

    def _track_loop(self, client: AsyncRobinhood) -> AsyncRobinhood:
        self._loop_to_close = client.event_loop
        return client

    async def test_get_stock_quotes_normalizes_single_symbol(self) -> None:
        client = self._track_loop(build_async_api_client())
        quote_payload = build_instrument_quote_payload(symbol="SPY")
        client._async_http_client._get.return_value = [quote_payload]

        result = await client.get_stock_quotes("spy")

        self.assertEqual(InstrumentQuote.from_json(quote_payload), result)
        client._async_http_client._get.assert_awaited_once_with(
            endpoint=API_QUOTES,
            params={PARAM_SYMBOLS: "SPY"},
        )

    async def test_get_stock_info_inserts_rows_into_cache(self) -> None:
        db_cache = Mock()
        client = self._track_loop(build_async_api_client(db_cache=db_cache))
        stock_info_payload = build_stock_info_payload(
            symbol="SPY",
            id="stock-id",
            tradable_chain_id="chain-id",
        )
        expected = StockInfo.from_json(stock_info_payload)
        client._async_http_client._get.return_value = [stock_info_payload]

        result = await client.get_stock_info(["spy", "qqq"])

        self.assertEqual([expected], result)
        client._async_http_client._get.assert_awaited_once_with(
            endpoint=API_INSTRUMENTS,
            params={PARAM_SYMBOLS: "SPY,QQQ"},
        )
        db_cache.insert_stock_info.assert_called_once_with(expected)

    async def test_get_index_quotes_returns_list_from_nested_payload(
        self,
    ) -> None:
        client = self._track_loop(build_async_api_client())
        vix_payload = build_index_quote_payload(
            symbol="VIX",
            instrument_id="vix-id",
            value="19.4",
        )
        spx_payload = build_index_quote_payload(
            symbol="SPX",
            instrument_id="spx-id",
            value="5000.1",
        )
        client._async_http_client._get.return_value = [
            {"data": [{"data": vix_payload}, {"data": spx_payload}]}
        ]

        result = await client.get_index_quotes(["vix", "spx"])

        self.assertEqual(
            [
                IndexQuote.from_json(vix_payload),
                IndexQuote.from_json(spx_payload),
            ],
            result,
        )
        client._async_http_client._get.assert_awaited_once_with(
            endpoint=API_INDEX_QUOTE,
            params={PARAM_SYMBOLS: "VIX,SPX"},
        )

    async def test_get_option_chain_data_skips_symbols_without_chain_ids(
        self,
    ) -> None:
        client = self._track_loop(build_async_api_client())
        chain_payload = build_option_chain_payload(id="chain-id", symbol="SPY")
        client._async_http_client._get.side_effect = [
            [
                {"tradable_chain_id": None},
                {"tradable_chain_id": "chain-id"},
            ],
            [chain_payload],
        ]

        result = await client.get_option_chain_data(["bad", "spy"])

        self.assertEqual(OptionChain.from_json(chain_payload), result)
        self.assertEqual(
            [
                (
                    (),
                    {
                        "endpoint": API_INSTRUMENTS,
                        "params": {PARAM_SYMBOLS: "BAD,SPY"},
                    },
                ),
                (
                    (),
                    {
                        "endpoint": API_OPTION_CHAINS,
                        "params": {PARAM_ID: "chain-id"},
                    },
                ),
            ],
            client._async_http_client._get.call_args_list,
        )

    async def test_get_strike_prices_returns_cached_strikes_without_http(
        self,
    ) -> None:
        db_cache = Mock()
        db_cache.is_option_request_synced.return_value = True
        db_cache.fetch_strike_prices.side_effect = [[495.0, 500.0], [490.0]]
        client = self._track_loop(build_async_api_client(db_cache=db_cache))

        result = await client.get_strike_prices(
            symbol="SPY",
            exp_date="2026-04-07",
        )

        self.assertEqual(
            {
                OptionRequest(
                    symbol="SPY",
                    option_type="call",
                    exp_date="2026-04-07",
                ): [495.0, 500.0],
                OptionRequest(
                    symbol="SPY",
                    option_type="put",
                    exp_date="2026-04-07",
                ): [490.0],
            },
            result,
        )
        client._async_http_client._get.assert_not_awaited()

    async def test_get_future_quote_returns_single_quote_for_single_id(
        self,
    ) -> None:
        client = self._track_loop(build_async_api_client())
        future_id = "00000000-0000-4000-8000-000000000001"
        quote_payload = {
            "ask_price": "1.0",
            "ask_size": "1",
            "ask_venue_timestamp": "2026-04-01T09:30:00Z",
            "bid_price": "0.9",
            "bid_size": "2",
            "bid_venue_timestamp": "2026-04-01T09:30:00Z",
            "last_trade_price": "0.95",
            "last_trade_size": "3",
            "last_trade_venue_timestamp": "2026-04-01T09:30:00Z",
            "symbol": "/ESM26",
            "instrument_id": future_id,
            "state": "active",
            "updated_at": "2026-04-01T09:30:00Z",
            "out_of_band": False,
        }
        client._async_http_client._get.return_value = [
            {"data": [{"status": "SUCCESS", "data": quote_payload}]}
        ]

        result = await client.get_future_quote(future_id)

        self.assertEqual(future_id, result.instrument_id)
        client._async_http_client._get.assert_awaited_once_with(
            endpoint=API_FUTURES_QUOTES,
            params={PARAM_ID: future_id},
        )

    async def test_get_future_quote_raises_for_more_than_twenty_ids(
        self,
    ) -> None:
        client = self._track_loop(build_async_api_client())
        ids = [f"00000000-0000-4000-8000-{n:012d}" for n in range(21)]

        with self.assertRaises(ValueError):
            await client.get_future_quote(ids)

    async def test_get_account_option_positions_parses_payloads(self) -> None:
        client = self._track_loop(build_async_api_client())
        client.user_id = "ACC123"
        payload = build_option_position_payload()
        client._async_http_client._get.return_value = [payload]

        result = await client.get_account_option_positions()

        self.assertEqual([OptionPosition.from_json(payload)], result)
        client._async_http_client._get.assert_awaited_once_with(
            endpoint=API_POSITIONS_OPTIONS,
            params={
                PARAM_NON_ZERO: "true",
                PARAM_ACCOUNT_NUMBER: "ACC123",
            },
        )

    async def test_get_option_order_history_returns_empty_for_invalid_user_id(
        self,
    ) -> None:
        client = self._track_loop(build_async_api_client())
        client.user_id = 403

        result = await client.get_option_order_history()

        self.assertEqual([], result)
        client._async_http_client._get.assert_not_awaited()

    async def test_get_stock_order_history_warns_for_invalid_user_id(
        self,
    ) -> None:
        client = self._track_loop(build_async_api_client())
        client.user_id = 403

        with self.assertLogs(
            "robinhood.core._account_impl",
            level="WARNING",
        ) as logs:
            result = await client.get_stock_order_history()

        self.assertIsNone(result)
        self.assertIn("user_id not valid", logs.output[0])

    async def test_get_watchlists_parses_supported_item_types(self) -> None:
        client = self._track_loop(build_async_api_client())
        watchlist_payload = build_watchlist_payload(
            id="watchlist-id", display_name="Default"
        )
        client._async_http_client._get.side_effect = [
            [watchlist_payload],
            [
                build_watchlist_option_strategy_payload(),
                build_watchlist_instrument_payload(),
                build_watchlist_currency_pair_payload(),
                {
                    "object_type": "future",
                    "symbol": "/ES",
                    "object_id": "future-object-id",
                    "name": "E-mini S&P 500",
                    "futures_margin_requirement": "1000.0",
                },
            ],
        ]

        result = await client.get_watchlists()

        self.assertEqual("Default", result[0].name)
        self.assertEqual(4, len(result[0].items))
        self.assertIsInstance(result[0].items[-1], Future)
        self.assertEqual(
            [
                unittest.mock.call(API_WATCHLIST_DEFAULT),
                unittest.mock.call(
                    endpoint=API_WATCHLIST_ITEMS,
                    params={
                        PARAM_LIST_ID: "watchlist-id",
                        PARAM_LOAD_ALL_ATTRIBUTES: "False",
                    },
                ),
            ],
            client._async_http_client._get.call_args_list,
        )

    async def test_create_watchlist_posts_sample_payload(self) -> None:
        client = self._track_loop(build_async_api_client())
        client._async_http_client._post.return_value = {"id": "watchlist-id"}

        result = await client.create_watchlist("blahblah")

        self.assertEqual("blahblah", result.name)
        self.assertEqual("watchlist-id", result.id)
        self.assertEqual([], result.items)
        client._async_http_client._post.assert_awaited_once_with(
            endpoint=API_WATCHLIST,
            json={
                "display_name": "blahblah",
                "icon_emoji": "🐱",
                "list_position": 0,
            },
        )

    async def test_delete_watchlist_resolves_id_and_deletes_by_endpoint(
        self,
    ) -> None:
        client = self._track_loop(build_async_api_client())
        client._async_http_client._get.side_effect = [
            [
                build_watchlist_payload(
                    id="watchlist-id",
                    display_name="Default",
                )
            ],
            [],
        ]

        await client.delete_watchlist("Default")

        client._async_http_client._delete.assert_awaited_once_with(
            endpoint=API_WATCHLIST + "watchlist-id/",
        )

    async def test_delete_watchlist_skips_delete_when_missing(self) -> None:
        client = self._track_loop(build_async_api_client())
        client._async_http_client._get.return_value = [
            build_watchlist_payload(
                id="watchlist-id",
                display_name="Default",
            )
        ]

        await client.delete_watchlist("Missing")

        client._async_http_client._delete.assert_not_awaited()

    async def test_add_item_to_watchlist_resolves_instrument_and_list(
        self,
    ) -> None:
        client = self._track_loop(build_async_api_client())
        quote = InstrumentQuote.from_json(
            build_instrument_quote_payload(
                instrument_id="instrument-id",
                symbol="SPY",
            )
        )
        client._get_stock_quotes = AsyncMock(return_value=quote)
        client._get_index_quotes = AsyncMock(return_value=None)
        client._get_future_quote = AsyncMock(return_value=None)
        client._get_currency_quote = AsyncMock(return_value=None)
        client._async_http_client._get.side_effect = [
            [
                build_watchlist_payload(
                    id="watchlist-id",
                    display_name="Default",
                )
            ],
            [],
        ]
        client._async_http_client._post.return_value = {
            "id": "watchlist-item-id"
        }

        result = await client.add_item_to_watchlist("SPY", "Default")

        self.assertEqual({"id": "watchlist-item-id"}, result)
        client._get_stock_quotes.assert_awaited_once_with("SPY")
        client._async_http_client._post.assert_awaited_once_with(
            endpoint=API_WATCHLIST_ITEMS,
            json={
                "watchlist-id": [
                    {
                        "object_id": "instrument-id",
                        "object_type": "instrument",
                        "operation": "create",
                    }
                ],
            },
        )

    async def test_add_item_to_watchlist_returns_none_for_missing_watchlist(
        self,
    ) -> None:
        client = self._track_loop(build_async_api_client())
        quote = InstrumentQuote.from_json(
            build_instrument_quote_payload(
                instrument_id="instrument-id",
                symbol="SPY",
            )
        )
        client._get_stock_quotes = AsyncMock(return_value=quote)
        client._get_index_quotes = AsyncMock(return_value=None)
        client._get_future_quote = AsyncMock(return_value=None)
        client._get_currency_quote = AsyncMock(return_value=None)
        client._async_http_client._get.return_value = [
            build_watchlist_payload(
                id="watchlist-id",
                display_name="Default",
            )
        ]

        result = await client.add_item_to_watchlist("SPY", "Missing")

        self.assertIsNone(result)
        client._async_http_client._post.assert_not_awaited()


class TestSyncRobinhoodAPI(unittest.TestCase):
    def tearDown(self) -> None:
        client = getattr(self, "client", None)
        if client and not client.event_loop.is_closed():
            client.event_loop.close()

    def make_client(self) -> Robinhood:
        client = build_robinhood_client(
            http_client=SimpleNamespace(close=AsyncMock()),
            db_cache=Mock(),
        )
        self.client = client
        return client

    def test_context_manager_returns_self_and_closes_on_exit(self) -> None:
        client = self.make_client()

        with patch.object(client, "close") as mock_close:
            with client as entered:
                self.assertIs(client, entered)

        mock_close.assert_called_once_with()

    def test_close_closes_cache_http_client_and_event_loop(self) -> None:
        client = self.make_client()
        db_cache = client._db_cache

        client.close()

        db_cache.close.assert_called_once_with()
        client._async_http_client.close.assert_awaited_once_with()
        self.assertTrue(client.event_loop.is_closed())
        self.assertIsNone(client._db_cache)

    def test_get_account_stock_positions_returns_private_result(self) -> None:
        client = self.make_client()
        expected = [StockPosition.from_json(build_stock_position_payload())]
        client._get_account_stock_positions = AsyncMock(return_value=expected)

        result = client.get_account_stock_positions()

        self.assertEqual(expected, result)
        client._get_account_stock_positions.assert_awaited_once_with()

    def test_create_watchlist_returns_private_result(self) -> None:
        client = self.make_client()
        client._create_watchlist = AsyncMock(return_value={"id": "list-id"})

        result = client.create_watchlist(
            "Temp",
            icon_emoji="*",
            list_position=2,
        )

        self.assertEqual({"id": "list-id"}, result)
        client._create_watchlist.assert_awaited_once_with("Temp", "*", 2)

    def test_delete_watchlist_returns_private_result(self) -> None:
        client = self.make_client()
        client._delete_watchlist = AsyncMock(return_value=None)

        result = client.delete_watchlist("Temp")

        self.assertIsNone(result)
        client._delete_watchlist.assert_awaited_once_with("Temp")

    def test_add_item_to_watchlist_returns_private_result(self) -> None:
        client = self.make_client()
        client._add_item_to_watchlist = AsyncMock(
            return_value={"id": "item-id"}
        )

        result = client.add_item_to_watchlist("SPY", "Temp")

        self.assertEqual({"id": "item-id"}, result)
        client._add_item_to_watchlist.assert_awaited_once_with("SPY", "Temp")

    @patch("robinhood.core._core_robinhood.auto_open_browser")
    @patch("robinhood.core._core_robinhood.check_if_modified_date_within_range")
    def test_open_browser_refreshes_when_browser_auth_is_recent(
        self,
        mock_check_if_modified_date_within_range: Mock,
        mock_auto_open_browser: Mock,
    ) -> None:
        client = self.make_client()
        mock_check_if_modified_date_within_range.return_value = True

        client.open_browser(Chrome(), wait_time=3, days=7)

        mock_check_if_modified_date_within_range.assert_called_once_with(days=7)
        mock_auto_open_browser.assert_called_once_with(
            unittest.mock.ANY,
            wait_time=3,
        )
