from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from robinhood import MalformedOrderError
from robinhood.async_robinhood_class import AsyncRobinhood
from robinhood.constants import (
    API_CURRENCY_QUOTES,
    API_OPTION_CHAINS,
    API_OPTION_ORDER,
    API_STOCK_ORDER,
    PARAM_SYMBOLS,
)
from robinhood.dataclasses.api_dataclasses import (
    InstrumentQuote,
    OptionRequest,
)
from robinhood.sync_robinhood_class import Robinhood
from tests.support import (
    build_async_robinhood_client,
    build_instrument_quote_payload,
    build_option_chain_payload,
    build_robinhood_client,
)


def build_async_public_client(
    *,
    db_cache: object | None = None,
) -> AsyncRobinhood:
    client = build_async_robinhood_client(
        http_client=SimpleNamespace(
            _get=AsyncMock(),
            _post=AsyncMock(),
            close=AsyncMock(),
        ),
        db_cache=db_cache,
    )
    client.user_id = "ACC123"
    return client


@pytest.mark.asyncio
class TestAsyncRobinhoodPublicContracts:
    @pytest.fixture(autouse=True)
    def _set_client_tracker(self, async_client_tracker) -> None:
        self.track_client = async_client_tracker

    def make_client(
        self,
        *,
        db_cache: object | None = None,
    ) -> AsyncRobinhood:
        return self.track_client(build_async_public_client(db_cache=db_cache))

    async def test_async_context_manager_exits_through_close(self) -> None:
        client = self.make_client()
        client.close = AsyncMock()

        async with client as entered:
            assert client is entered

        client.close.assert_awaited_once_with()

    async def test_async_close_without_cache_closes_http_and_loop(self) -> None:
        client = self.make_client()
        http_client = client._async_http_client

        await client.close()

        http_client.close.assert_awaited_once_with()
        assert client.event_loop.is_closed()
        assert client._db_cache is None

    async def test_async_close_with_cache_closes_cache_once(self) -> None:
        db_cache = Mock()
        client = self.make_client(db_cache=db_cache)

        await client.close()

        db_cache.close.assert_called_once_with()
        assert client._db_cache is None

    async def test_public_stock_quotes_single_list_and_empty_shapes(
        self,
    ) -> None:
        client = self.make_client()
        spy_payload = build_instrument_quote_payload(
            symbol="SPY",
            instrument_id="spy-id",
        )
        qqq_payload = build_instrument_quote_payload(
            symbol="QQQ",
            instrument_id="qqq-id",
        )

        client._async_http_client._get.return_value = [spy_payload]
        result = await client.get_stock_quotes("spy")

        assert InstrumentQuote.from_json(spy_payload) == result
        client._async_http_client._get.assert_awaited_with(
            endpoint="/quotes/",
            params={PARAM_SYMBOLS: "SPY"},
        )

        client._async_http_client._get.reset_mock()
        client._async_http_client._get.return_value = [
            spy_payload,
            qqq_payload,
        ]

        result = await client.get_stock_quotes(["spy", "qqq"])

        assert [
            InstrumentQuote.from_json(spy_payload),
            InstrumentQuote.from_json(qqq_payload),
        ] == result
        client._async_http_client._get.assert_awaited_with(
            endpoint="/quotes/",
            params={PARAM_SYMBOLS: "SPY,QQQ"},
        )

        client._async_http_client._get.reset_mock()
        client._async_http_client._get.return_value = []

        assert await client.get_stock_quotes("SPY") is None

    async def test_public_stock_quotes_malformed_payload_propagates(
        self,
    ) -> None:
        client = self.make_client()
        client._async_http_client._get.return_value = [{"symbol": "SPY"}]

        with pytest.raises(KeyError):
            await client.get_stock_quotes("SPY")

    async def test_public_index_quotes_skip_malformed_nested_results(
        self,
    ) -> None:
        client = self.make_client()
        client._async_http_client._get.return_value = [
            {"data": [{"status": "SUCCESS", "data": {"symbol": "VIX"}}]}
        ]

        assert await client.get_index_quotes("vix") is None

    async def test_public_currency_quote_normalizes_symbol_for_lookup(
        self,
    ) -> None:
        client = self.make_client()
        client._async_http_client._get.return_value = []

        result = await client.get_currency_quote("btc")

        assert result is None
        client._async_http_client._get.assert_awaited_once_with(
            endpoint=API_CURRENCY_QUOTES,
            params={PARAM_SYMBOLS: "BTCUSD"},
        )

    async def test_public_orderbook_short_circuits_when_stock_missing(
        self,
    ) -> None:
        client = self.make_client()
        client._get_stock_info = AsyncMock(return_value=None)

        assert await client.get_orderbook("spy") is None
        client._async_http_client._get.assert_not_awaited()

    async def test_public_future_quote_rejects_more_than_twenty_ids(
        self,
    ) -> None:
        client = self.make_client()
        ids = [f"00000000-0000-4000-8000-{n:012d}" for n in range(21)]

        with pytest.raises(ValueError):
            await client.get_future_quote(ids)

        client._async_http_client._get.assert_not_awaited()

    async def test_public_expiration_dates_empty_chain_response_returns_none(
        self,
    ) -> None:
        client = self.make_client()
        client._async_http_client._get.return_value = []

        assert await client.get_expiration_dates("spy") is None
        client._async_http_client._get.assert_awaited_once_with(
            API_OPTION_CHAINS + "SPY/"
        )

    async def test_public_expiration_dates_valid_chain_response_returns_dates(
        self,
    ) -> None:
        client = self.make_client()
        client._async_http_client._get.return_value = [
            build_option_chain_payload(
                symbol="SPY",
                expiration_dates=["2026-04-17", "2026-05-15"],
            )
        ]

        assert [
            "2026-04-17",
            "2026-05-15",
        ] == await client.get_expiration_dates("spy")

    async def test_public_strike_prices_returns_none_when_no_chain(
        self,
    ) -> None:
        client = self.make_client()
        client._get_option_chain_data = AsyncMock(return_value=None)

        result = await client.get_strike_prices(
            symbol="spy",
            exp_date="2026-04-17",
        )

        assert result is None

    async def test_public_option_greeks_empty_request_list_returns_empty(
        self,
    ) -> None:
        client = self.make_client()
        client._get_option_chain_data = AsyncMock(return_value=None)

        result = await client.get_option_greeks_batch_request([])

        assert {} == result

    async def test_public_no_db_option_greeks_returns_empty_for_no_chain(
        self,
    ) -> None:
        client = self.make_client()
        request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        client._get_option_chain_data = AsyncMock(return_value=None)

        result = await client.no_db_option_greeks_batch_request([request])

        assert {request: []} == result

    async def test_public_trading_rejects_invalid_user_inputs(self) -> None:
        client = self.make_client()

        with pytest.raises(MalformedOrderError):
            await client.place_market_stock_order(
                "SPY",
                "hold",
                dollar_based_amount=1,
            )

        with pytest.raises(MalformedOrderError):
            await client.place_limit_stock_order(
                "SPY",
                "buy",
                price=0,
                quantity=1,
            )

    async def test_public_cancel_methods_use_expected_endpoints(self) -> None:
        client = self.make_client()

        await client.cancel_stock_order("stock-order-id")
        await client.cancel_option_order("option-order-id")

        assert [
            call(endpoint=API_STOCK_ORDER + "stock-order-id/cancel/"),
            call(endpoint=API_OPTION_ORDER + "option-order-id/cancel/"),
        ] == client._async_http_client._post.await_args_list

    async def test_public_account_raw_json_returns_unsanitized_payload(
        self,
    ) -> None:
        client = self.make_client()
        raw_payload = [{"unexpected": object()}]
        client._async_http_client._get.return_value = raw_payload

        assert raw_payload is await client.get_accounts(raw_json_response=True)


class TestSyncRobinhoodPublicContracts:
    @pytest.fixture(autouse=True)
    def _set_client_tracker(self, sync_client_tracker) -> None:
        self.track_client = sync_client_tracker

    def make_client(self, *, db_cache: object | None = None) -> Robinhood:
        client = build_robinhood_client(
            http_client=SimpleNamespace(close=AsyncMock()),
            db_cache=db_cache,
        )
        client.user_id = "ACC123"
        return self.track_client(client)

    def test_sync_context_manager_exits_through_close(self) -> None:
        client = self.make_client()
        client.close = Mock()

        with client as entered:
            assert client is entered

        client.close.assert_called_once_with()

    def test_sync_close_without_cache_closes_http_and_loop(self) -> None:
        client = self.make_client()
        http_client = client._async_http_client

        client.close()

        http_client.close.assert_awaited_once_with()
        assert client.event_loop.is_closed()
        assert client._db_cache is None

    def test_sync_close_with_cache_closes_cache_once(self) -> None:
        db_cache = Mock()
        client = self.make_client(db_cache=db_cache)

        client.close()

        db_cache.close.assert_called_once_with()
        assert client._db_cache is None

    def test_sync_public_methods_route_through_run(self) -> None:
        cases = [
            ("get_stock_info", "_get_stock_info", ("SPY",), {}),
            (
                "get_option_greeks_batch_request",
                "_get_option_greeks_batch_request",
                (OptionRequest(symbol="SPY"),),
                {},
            ),
            (
                "place_market_stock_order",
                "_place_market_stock_order",
                ("SPY", "buy"),
                {"quantity": 1},
            ),
            (
                "get_account_stock_positions",
                "_get_account_stock_positions",
                (),
                {},
            ),
            ("create_watchlist", "_create_watchlist", ("Temp",), {}),
            ("cancel_stock_order", "_cancel_stock_order", ("order-id",), {}),
        ]

        for public_name, private_name, args, kwargs in cases:
            client = self.make_client()
            awaitable = object()
            expected = object()
            setattr(client, private_name, Mock(return_value=awaitable))
            client._run = Mock(return_value=expected)

            result = getattr(client, public_name)(*args, **kwargs)

            assert expected is result
            getattr(client, private_name).assert_called_once()
            client._run.assert_called_once_with(awaitable)
            client.event_loop.close()

    def test_sync_public_methods_propagate_run_exceptions(self) -> None:
        client = self.make_client()
        awaitable = object()
        client._get_stock_info = Mock(return_value=awaitable)
        client._run = Mock(side_effect=RuntimeError("boom"))

        with pytest.raises(RuntimeError, match="boom"):
            client.get_stock_info("SPY")

        client._run.assert_called_once_with(awaitable)

    def test_sync_change_account_updates_public_account_target(self) -> None:
        client = self.make_client()

        result = client.change_account("ACC456")

        assert result is None
        assert "ACC456" == client.user_id
