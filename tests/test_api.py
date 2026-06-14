from __future__ import annotations

from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from robinhood.async_robinhood_class import AsyncRobinhood
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
    MockAsyncHTTPClient,
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
    get_http_mock,
    set_mock_attr,
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
        http_client=MockAsyncHTTPClient(),
        db_cache=db_cache,
    )
    return client


@pytest.mark.asyncio
class TestAsyncRobinhoodAPI:
    @pytest.fixture(autouse=True)
    def _set_client_tracker(self, async_client_tracker) -> None:
        self.track_client = async_client_tracker

    def _track_loop(
        self,
        client: AsyncRobinhood,
    ) -> tuple[AsyncRobinhood, MockAsyncHTTPClient]:
        client = self.track_client(client)
        return client, get_http_mock(client)

    async def test_get_stock_quotes_normalizes_single_symbol(self) -> None:
        client, http_client = self._track_loop(build_async_api_client())
        quote_payload = build_instrument_quote_payload(symbol="SPY")
        http_client._get.return_value = [quote_payload]

        result = await client.get_stock_quotes("spy")

        assert InstrumentQuote.from_json(quote_payload) == result
        http_client._get.assert_awaited_once_with(
            endpoint=API_QUOTES,
            params={PARAM_SYMBOLS: "SPY"},
        )

    async def test_get_stock_info_inserts_rows_into_cache(self) -> None:
        db_cache = Mock()
        client, http_client = self._track_loop(
            build_async_api_client(db_cache=db_cache)
        )
        stock_info_payload = build_stock_info_payload(
            symbol="SPY",
            id="stock-id",
            tradable_chain_id="chain-id",
        )
        expected = StockInfo.from_json(stock_info_payload)
        http_client._get.return_value = [stock_info_payload]

        result = await client.get_stock_info(["spy", "qqq"])

        assert [expected] == result
        http_client._get.assert_awaited_once_with(
            endpoint=API_INSTRUMENTS,
            params={PARAM_SYMBOLS: "SPY,QQQ"},
        )
        db_cache.insert_stock_info.assert_called_once_with(expected)

    async def test_get_index_quotes_returns_list_from_nested_payload(
        self,
    ) -> None:
        client, http_client = self._track_loop(build_async_api_client())
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
        http_client._get.return_value = [
            {"data": [{"data": vix_payload}, {"data": spx_payload}]}
        ]

        result = await client.get_index_quotes(["vix", "spx"])

        assert [
            IndexQuote.from_json(vix_payload),
            IndexQuote.from_json(spx_payload),
        ] == result
        http_client._get.assert_awaited_once_with(
            endpoint=API_INDEX_QUOTE,
            params={PARAM_SYMBOLS: "VIX,SPX"},
        )

    async def test_get_option_chain_data_skips_symbols_without_chain_ids(
        self,
    ) -> None:
        client, http_client = self._track_loop(build_async_api_client())
        chain_payload = build_option_chain_payload(id="chain-id", symbol="SPY")
        http_client._get.side_effect = [
            [
                {"tradable_chain_id": None},
                {"tradable_chain_id": "chain-id"},
            ],
            [chain_payload],
        ]

        result = await client.get_option_chain_data(["bad", "spy"])

        assert OptionChain.from_json(chain_payload) == result
        assert [
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
        ] == http_client._get.call_args_list

    async def test_get_strike_prices_returns_cached_strikes_without_http(
        self,
    ) -> None:
        db_cache = Mock()
        db_cache.is_option_request_synced.return_value = True
        db_cache.fetch_strike_prices.side_effect = [[495.0, 500.0], [490.0]]
        client, http_client = self._track_loop(
            build_async_api_client(db_cache=db_cache)
        )

        result = await client.get_strike_prices(
            symbol="SPY",
            exp_date="2026-04-07",
        )

        assert ([495.0, 500.0], [490.0]) == result
        http_client._get.assert_not_awaited()

    async def test_get_future_quote_returns_single_quote_for_single_id(
        self,
    ) -> None:
        client, http_client = self._track_loop(build_async_api_client())
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
        http_client._get.return_value = [
            {"data": [{"status": "SUCCESS", "data": quote_payload}]}
        ]

        result = await client.get_future_quote(future_id)

        assert result is not None
        assert future_id == result.instrument_id
        http_client._get.assert_awaited_once_with(
            endpoint=API_FUTURES_QUOTES,
            params={PARAM_ID: future_id},
        )

    async def test_get_future_quote_raises_for_more_than_twenty_ids(
        self,
    ) -> None:
        client, http_client = self._track_loop(build_async_api_client())
        ids = [f"00000000-0000-4000-8000-{n:012d}" for n in range(21)]

        with pytest.raises(ValueError):
            await client.get_future_quote(ids)

    async def test_get_account_option_positions_parses_payloads(self) -> None:
        client, http_client = self._track_loop(build_async_api_client())
        client.acc_id = "ACC123"
        payload = build_option_position_payload()
        http_client._get.return_value = [payload]

        result = await client.get_account_option_positions()

        assert [OptionPosition.from_json(payload)] == result
        http_client._get.assert_awaited_once_with(
            endpoint=API_POSITIONS_OPTIONS,
            params={
                PARAM_NON_ZERO: "true",
                PARAM_ACCOUNT_NUMBER: "ACC123",
            },
        )

    async def test_get_option_order_history_returns_empty_for_invalid_user_id(
        self,
    ) -> None:
        client, http_client = self._track_loop(build_async_api_client())
        client.acc_id = 403

        result = await client.get_option_order_history()

        assert [] == result
        http_client._get.assert_not_awaited()

    async def test_get_stock_order_history_warns_for_invalid_user_id(
        self,
        caplog,
    ) -> None:
        client, http_client = self._track_loop(build_async_api_client())
        client.acc_id = 403

        with caplog.at_level(
            "WARNING",
            logger="robinhood.core._account_impl",
        ):
            result = await client.get_stock_order_history()

        assert result is None
        assert "user_id not valid" in caplog.text

    async def test_get_watchlists_parses_supported_item_types(self) -> None:
        client, http_client = self._track_loop(build_async_api_client())
        watchlist_payload = build_watchlist_payload(
            id="watchlist-id", display_name="Default"
        )
        http_client._get.side_effect = [
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

        assert result is not None
        assert "Default" == result[0].name
        assert 4 == len(result[0].items)
        assert isinstance(result[0].items[-1], Future)
        assert [
            call(API_WATCHLIST_DEFAULT),
            call(
                endpoint=API_WATCHLIST_ITEMS,
                params={
                    PARAM_LIST_ID: "watchlist-id",
                    PARAM_LOAD_ALL_ATTRIBUTES: "False",
                },
            ),
        ] == http_client._get.call_args_list

    async def test_create_watchlist_posts_sample_payload(self) -> None:
        client, http_client = self._track_loop(build_async_api_client())
        http_client._post.return_value = {"id": "watchlist-id"}

        result = await client.create_watchlist("blahblah")

        assert "blahblah" == result.name
        assert "watchlist-id" == result.id
        assert [] == result.items
        http_client._post.assert_awaited_once_with(
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
        client, http_client = self._track_loop(build_async_api_client())
        http_client._get.side_effect = [
            [
                build_watchlist_payload(
                    id="watchlist-id",
                    display_name="Default",
                )
            ],
            [],
        ]

        await client.delete_watchlist("Default")

        http_client._delete.assert_awaited_once_with(
            endpoint=API_WATCHLIST + "watchlist-id/",
        )

    async def test_delete_watchlist_skips_delete_when_missing(self) -> None:
        client, http_client = self._track_loop(build_async_api_client())
        http_client._get.return_value = [
            build_watchlist_payload(
                id="watchlist-id",
                display_name="Default",
            )
        ]

        await client.delete_watchlist("Missing")

        http_client._delete.assert_not_awaited()

    async def test_add_item_to_watchlist_resolves_instrument_and_list(
        self,
    ) -> None:
        client, http_client = self._track_loop(build_async_api_client())
        quote = InstrumentQuote.from_json(
            build_instrument_quote_payload(
                instrument_id="instrument-id",
                symbol="SPY",
            )
        )
        get_stock_quotes = set_mock_attr(
            client,
            "_get_stock_quotes",
            AsyncMock(return_value=quote),
        )
        set_mock_attr(client, "_get_index_quotes", AsyncMock(return_value=None))
        set_mock_attr(client, "_get_future_quote", AsyncMock(return_value=None))
        set_mock_attr(
            client,
            "_get_currency_quote",
            AsyncMock(return_value=None),
        )
        http_client._get.side_effect = [
            [
                build_watchlist_payload(
                    id="watchlist-id",
                    display_name="Default",
                )
            ],
            [],
        ]
        http_client._post.return_value = {"id": "watchlist-item-id"}

        result = await client.add_item_to_watchlist("SPY", "Default")

        assert {"id": "watchlist-item-id"} == result
        get_stock_quotes.assert_awaited_once_with("SPY")
        http_client._post.assert_awaited_once_with(
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
        client, http_client = self._track_loop(build_async_api_client())
        quote = InstrumentQuote.from_json(
            build_instrument_quote_payload(
                instrument_id="instrument-id",
                symbol="SPY",
            )
        )
        set_mock_attr(
            client, "_get_stock_quotes", AsyncMock(return_value=quote)
        )
        set_mock_attr(client, "_get_index_quotes", AsyncMock(return_value=None))
        set_mock_attr(client, "_get_future_quote", AsyncMock(return_value=None))
        set_mock_attr(
            client,
            "_get_currency_quote",
            AsyncMock(return_value=None),
        )
        http_client._get.return_value = [
            build_watchlist_payload(
                id="watchlist-id",
                display_name="Default",
            )
        ]

        result = await client.add_item_to_watchlist("SPY", "Missing")

        assert result is None
        http_client._post.assert_not_awaited()


class TestSyncRobinhoodAPI:
    @pytest.fixture(autouse=True)
    def _set_client_tracker(self, sync_client_tracker) -> None:
        self.track_client = sync_client_tracker

    def make_client(self) -> Robinhood:
        client = build_robinhood_client(
            http_client=MockAsyncHTTPClient(),
            db_cache=Mock(),
        )
        return self.track_client(client)

    def test_context_manager_returns_self_and_closes_on_exit(self) -> None:
        client = self.make_client()

        with patch.object(client, "close") as mock_close:
            with client as entered:
                assert client is entered

        mock_close.assert_called_once_with()

    def test_close_closes_cache_http_client_and_event_loop(self) -> None:
        db_cache = Mock()
        client = build_robinhood_client(
            http_client=MockAsyncHTTPClient(),
            db_cache=db_cache,
        )
        self.track_client(client)
        http_client = get_http_mock(client)

        client.close()

        db_cache.close.assert_called_once_with()
        http_client.close.assert_awaited_once_with()
        assert client.event_loop.is_closed()
        assert client._db_cache is None

    def test_get_account_stock_positions_returns_private_result(self) -> None:
        client = self.make_client()
        expected = [StockPosition.from_json(build_stock_position_payload())]
        get_account_stock_positions = set_mock_attr(
            client,
            "_get_account_stock_positions",
            AsyncMock(return_value=expected),
        )

        result = client.get_account_stock_positions()

        assert expected == result
        get_account_stock_positions.assert_awaited_once_with()

    def test_create_watchlist_returns_private_result(self) -> None:
        client = self.make_client()
        create_watchlist = set_mock_attr(
            client,
            "_create_watchlist",
            AsyncMock(return_value={"id": "list-id"}),
        )

        result = client.create_watchlist(
            "Temp",
            icon_emoji="*",
            list_position=2,
        )

        assert {"id": "list-id"} == result
        create_watchlist.assert_awaited_once_with("Temp", "*", 2)

    def test_delete_watchlist_returns_private_result(self) -> None:
        client = self.make_client()
        delete_watchlist = set_mock_attr(
            client,
            "_delete_watchlist",
            AsyncMock(return_value=None),
        )

        result = client.delete_watchlist("Temp")

        assert result is None
        delete_watchlist.assert_awaited_once_with("Temp")

    def test_add_item_to_watchlist_returns_private_result(self) -> None:
        client = self.make_client()
        add_item_to_watchlist = set_mock_attr(
            client,
            "_add_item_to_watchlist",
            AsyncMock(return_value={"id": "item-id"}),
        )

        result = client.add_item_to_watchlist("SPY", "Temp")

        assert {"id": "item-id"} == result
        add_item_to_watchlist.assert_awaited_once_with("SPY", "Temp")

    def test_refresh_access_token_uses_current_browser(self) -> None:
        client = self.make_client()
        browser = Mock()
        browser.last_accessed_greater_than_n_days.return_value = False
        set_mock_attr(client, "browser_type", browser)
        http_client = get_http_mock(client)
        http_client.access_token = "old-token"
        http_client.update_session_token = Mock()
        http_client.session = object()

        with patch(
            "robinhood.core._core_robinhood._refresh_access_token",
            return_value="new-token",
        ) as mock_refresh:
            client.refresh_access_token()

        browser.open_and_close_browser.assert_not_called()
        mock_refresh.assert_called_once_with("old-token", browser)
        http_client.update_session_token.assert_called_once_with("new-token")
        assert "new-token" == http_client.access_token
        assert http_client.session is None
