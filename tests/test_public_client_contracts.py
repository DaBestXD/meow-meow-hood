from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

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
from robinhood.errors import MalformedOrderError
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


class TestAsyncRobinhoodPublicContracts(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        client = getattr(self, "client", None)
        if client and not client.event_loop.is_closed():
            client.event_loop.close()

    def make_client(
        self,
        *,
        db_cache: object | None = None,
    ) -> AsyncRobinhood:
        self.client = build_async_public_client(db_cache=db_cache)
        return self.client

    async def test_async_context_manager_exits_through_close(self) -> None:
        client = self.make_client()
        client.close = AsyncMock()

        async with client as entered:
            self.assertIs(client, entered)

        client.close.assert_awaited_once_with()

    async def test_async_close_without_cache_closes_http_and_loop(self) -> None:
        client = self.make_client()
        http_client = client._async_http_client

        await client.close()

        http_client.close.assert_awaited_once_with()
        self.assertTrue(client.event_loop.is_closed())
        self.assertIsNone(client._db_cache)

    async def test_async_close_with_cache_closes_cache_once(self) -> None:
        db_cache = Mock()
        client = self.make_client(db_cache=db_cache)

        await client.close()

        db_cache.close.assert_called_once_with()
        self.assertIsNone(client._db_cache)

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

        with self.subTest("single symbol collapses to one object"):
            client._async_http_client._get.return_value = [spy_payload]
            result = await client.get_stock_quotes("spy")

            self.assertEqual(InstrumentQuote.from_json(spy_payload), result)
            client._async_http_client._get.assert_awaited_with(
                endpoint="/quotes/",
                params={PARAM_SYMBOLS: "SPY"},
            )

        with self.subTest("multiple symbols preserve a list"):
            client._async_http_client._get.reset_mock()
            client._async_http_client._get.return_value = [
                spy_payload,
                qqq_payload,
            ]

            result = await client.get_stock_quotes(["spy", "qqq"])

            self.assertEqual(
                [
                    InstrumentQuote.from_json(spy_payload),
                    InstrumentQuote.from_json(qqq_payload),
                ],
                result,
            )
            client._async_http_client._get.assert_awaited_with(
                endpoint="/quotes/",
                params={PARAM_SYMBOLS: "SPY,QQQ"},
            )

        with self.subTest("empty response returns None"):
            client._async_http_client._get.reset_mock()
            client._async_http_client._get.return_value = []

            self.assertIsNone(await client.get_stock_quotes("SPY"))

    async def test_public_stock_quotes_malformed_payload_propagates(
        self,
    ) -> None:
        client = self.make_client()
        client._async_http_client._get.return_value = [{"symbol": "SPY"}]

        with self.assertRaises(KeyError):
            await client.get_stock_quotes("SPY")

    async def test_public_index_quotes_skip_malformed_nested_results(
        self,
    ) -> None:
        client = self.make_client()
        client._async_http_client._get.return_value = [
            {"data": [{"status": "SUCCESS", "data": {"symbol": "VIX"}}]}
        ]

        self.assertIsNone(await client.get_index_quotes("vix"))

    async def test_public_currency_quote_normalizes_symbol_for_lookup(
        self,
    ) -> None:
        client = self.make_client()
        client._async_http_client._get.return_value = []

        result = await client.get_currency_quote("btc")

        self.assertIsNone(result)
        client._async_http_client._get.assert_awaited_once_with(
            endpoint=API_CURRENCY_QUOTES,
            params={PARAM_SYMBOLS: "BTCUSD"},
        )

    async def test_public_orderbook_short_circuits_when_stock_missing(
        self,
    ) -> None:
        client = self.make_client()
        client._get_stock_info = AsyncMock(return_value=None)

        self.assertIsNone(await client.get_orderbook("spy"))
        client._async_http_client._get.assert_not_awaited()

    async def test_public_future_quote_rejects_more_than_twenty_ids(
        self,
    ) -> None:
        client = self.make_client()
        ids = [f"00000000-0000-4000-8000-{n:012d}" for n in range(21)]

        with self.assertRaises(ValueError):
            await client.get_future_quote(ids)

        client._async_http_client._get.assert_not_awaited()

    async def test_public_expiration_dates_empty_chain_response_returns_none(
        self,
    ) -> None:
        client = self.make_client()
        client._async_http_client._get.return_value = []

        self.assertIsNone(await client.get_expiration_dates("spy"))
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

        self.assertEqual(
            ["2026-04-17", "2026-05-15"],
            await client.get_expiration_dates("spy"),
        )

    async def test_public_strike_prices_returns_empty_when_no_chain(
        self,
    ) -> None:
        client = self.make_client()
        client._get_option_chain_data = AsyncMock(return_value=None)

        result = await client.get_strike_prices(
            symbol="spy",
            exp_date="2026-04-17",
        )

        self.assertEqual(2, len(result))
        self.assertEqual([[], []], list(result.values()))
        self.assertEqual(
            {"call", "put"},
            {request.option_type for request in result},
        )

    async def test_public_option_greeks_empty_request_list_returns_empty(
        self,
    ) -> None:
        client = self.make_client()
        client._get_option_chain_data = AsyncMock(return_value=None)

        result = await client.get_option_greeks_batch_request([])

        self.assertEqual({}, result)

    async def test_public_no_db_option_greeks_returns_empty_for_no_chain(
        self,
    ) -> None:
        client = self.make_client()
        request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        client._get_option_chain_data = AsyncMock(return_value=None)

        result = await client.no_db_option_greeks_batch_request([request])

        self.assertEqual({request: []}, result)

    async def test_public_trading_rejects_invalid_user_inputs(self) -> None:
        client = self.make_client()

        with self.subTest("market side"):
            with self.assertRaises(MalformedOrderError):
                await client.place_market_stock_order(
                    "SPY",
                    "hold",
                    dollar_based_amount=1,
                )

        with self.subTest("limit price"):
            with self.assertRaises(MalformedOrderError):
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

        self.assertEqual(
            [
                unittest.mock.call(
                    endpoint=API_STOCK_ORDER + "stock-order-id/cancel/"
                ),
                unittest.mock.call(
                    endpoint=API_OPTION_ORDER + "option-order-id/cancel/"
                ),
            ],
            client._async_http_client._post.await_args_list,
        )

    async def test_public_account_raw_json_returns_unsanitized_payload(
        self,
    ) -> None:
        client = self.make_client()
        raw_payload = [{"unexpected": object()}]
        client._async_http_client._get.return_value = raw_payload

        self.assertIs(
            raw_payload,
            await client.get_accounts(raw_json_response=True),
        )


class TestSyncRobinhoodPublicContracts(unittest.TestCase):
    def tearDown(self) -> None:
        client = getattr(self, "client", None)
        if client and not client.event_loop.is_closed():
            client.event_loop.close()

    def make_client(self, *, db_cache: object | None = None) -> Robinhood:
        self.client = build_robinhood_client(
            http_client=SimpleNamespace(close=AsyncMock()),
            db_cache=db_cache,
        )
        self.client.user_id = "ACC123"
        return self.client

    def test_sync_context_manager_exits_through_close(self) -> None:
        client = self.make_client()
        client.close = Mock()

        with client as entered:
            self.assertIs(client, entered)

        client.close.assert_called_once_with()

    def test_sync_close_without_cache_closes_http_and_loop(self) -> None:
        client = self.make_client()
        http_client = client._async_http_client

        client.close()

        http_client.close.assert_awaited_once_with()
        self.assertTrue(client.event_loop.is_closed())
        self.assertIsNone(client._db_cache)

    def test_sync_close_with_cache_closes_cache_once(self) -> None:
        db_cache = Mock()
        client = self.make_client(db_cache=db_cache)

        client.close()

        db_cache.close.assert_called_once_with()
        self.assertIsNone(client._db_cache)

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
            with self.subTest(public_name=public_name):
                client = self.make_client()
                awaitable = object()
                expected = object()
                setattr(client, private_name, Mock(return_value=awaitable))
                client._run = Mock(return_value=expected)

                result = getattr(client, public_name)(*args, **kwargs)

                self.assertIs(expected, result)
                getattr(client, private_name).assert_called_once()
                client._run.assert_called_once_with(awaitable)
                client.event_loop.close()

    def test_sync_public_methods_propagate_run_exceptions(self) -> None:
        client = self.make_client()
        awaitable = object()
        client._get_stock_info = Mock(return_value=awaitable)
        client._run = Mock(side_effect=RuntimeError("boom"))

        with self.assertRaisesRegex(RuntimeError, "boom"):
            client.get_stock_info("SPY")

        client._run.assert_called_once_with(awaitable)

    def test_sync_change_account_updates_public_account_target(self) -> None:
        client = self.make_client()

        result = client.change_account("ACC456")

        self.assertIsNone(result)
        self.assertEqual("ACC456", client.user_id)


if __name__ == "__main__":
    unittest.main()
