from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from robinhood.async_robinhood_class import AsyncRobinhood
from robinhood.constants import API_OPTION_ORDER, API_STOCK_ORDER, BASE_API_LINK
from robinhood.dataclasses.api_dataclasses import (
    FullQuote,
    OptionOrderResponse,
    OptionRequest,
    StockInfo,
    StockOrderResponse,
)
from robinhood.errors import (
    AccountIdNotFoundError,
    InstruemtNotFoundError,
    MalformedOrderError,
)
from tests.support import (
    build_async_robinhood_client,
    build_full_quote_payload,
    build_option_instrument,
    build_option_order_response_payload,
    build_stock_info_payload,
    build_stock_order_response_payload,
)


def build_option_leg(
    *,
    symbol: str = "SPY",
    side: str | None = "buy",
    position_effect: str | None = "open",
) -> OptionRequest:
    return OptionRequest(
        symbol=symbol,
        exp_date="2026-04-17",
        option_type="call",
        strike_price=500.0,
        side=side,
        position_effect=position_effect,
    )


class TestTradingAsync(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        client = getattr(self, "client", None)
        if client and not client.event_loop.is_closed():
            client.event_loop.close()

    def make_client(self) -> AsyncRobinhood:
        client = build_async_robinhood_client(
            http_client=SimpleNamespace(_post=AsyncMock())
        )
        client.user_id = "ACC123"
        self.client = client
        return client

    def set_market_lookup_success(self, client: AsyncRobinhood) -> None:
        client._get_stock_info = AsyncMock(
            return_value=StockInfo.from_json(build_stock_info_payload())
        )
        client._get_stock_quotes = AsyncMock(
            return_value=FullQuote.from_json(build_full_quote_payload())
        )

    async def test_market_stock_order_rejects_invalid_side(self) -> None:
        client = self.make_client()

        with self.assertRaises(MalformedOrderError):
            await client._place_market_stock_order(
                "SPY",
                "hold",
                dollar_based_amount=1.0,
            )

    async def test_market_stock_order_requires_exactly_one_amount(self) -> None:
        client = self.make_client()

        with self.assertRaises(MalformedOrderError):
            await client._place_market_stock_order("SPY", "buy")

        with self.assertRaises(MalformedOrderError):
            await client._place_market_stock_order(
                "SPY",
                "buy",
                dollar_based_amount=1.0,
                quantity=1.0,
            )

    async def test_market_stock_order_requires_valid_account_id(self) -> None:
        client = self.make_client()
        client.user_id = 403

        with self.assertRaises(AccountIdNotFoundError):
            await client._place_market_stock_order(
                "SPY",
                "buy",
                dollar_based_amount=1.0,
            )

    async def test_market_stock_order_requires_stock_info_and_quote(
        self,
    ) -> None:
        client = self.make_client()
        client._get_stock_info = AsyncMock(return_value=None)
        client._get_stock_quotes = AsyncMock()

        with self.assertRaises(InstruemtNotFoundError):
            await client._place_market_stock_order(
                "SPY",
                "buy",
                dollar_based_amount=1.0,
            )

        client._get_stock_info = AsyncMock(
            return_value=StockInfo.from_json(build_stock_info_payload())
        )
        client._get_stock_quotes = AsyncMock(return_value=None)

        with self.assertRaisesRegex(ValueError, "unable to retrieve quote"):
            await client._place_market_stock_order(
                "SPY",
                "buy",
                dollar_based_amount=1.0,
            )

    async def test_market_stock_order_posts_dollar_payload(self) -> None:
        client = self.make_client()
        self.set_market_lookup_success(client)
        response_payload = build_stock_order_response_payload()
        client._async_http_client._post.return_value = response_payload

        result = await client._place_market_stock_order(
            "spy",
            "buy",
            dollar_based_amount=25.0,
        )

        self.assertEqual(StockOrderResponse.from_json(response_payload), result)
        client._async_http_client._post.assert_awaited_once()
        post_kwargs = client._async_http_client._post.await_args.kwargs
        self.assertEqual(API_STOCK_ORDER, post_kwargs["endpoint"])
        self.assertEqual("SPY", post_kwargs["json"]["symbol"])
        self.assertEqual(
            {"amount": "25.00", "currency_code": "USD"},
            post_kwargs["json"]["dollar_based_amount"],
        )
        self.assertEqual(
            BASE_API_LINK + "/accounts/ACC123/",
            post_kwargs["json"]["account"],
        )

    async def test_market_stock_order_posts_quantity_payload(self) -> None:
        client = self.make_client()
        self.set_market_lookup_success(client)
        response_payload = build_stock_order_response_payload()
        client._async_http_client._post.return_value = response_payload

        result = await client._place_market_stock_order(
            "SPY",
            "sell",
            quantity=2.0,
        )

        self.assertEqual(StockOrderResponse.from_json(response_payload), result)
        post_payload = client._async_http_client._post.await_args.kwargs["json"]
        self.assertEqual("2.0", post_payload["quantity"])
        self.assertEqual("close", post_payload["position_effect"])
        self.assertNotIn("dollar_based_amount", post_payload)

    async def test_option_order_rejects_mixed_symbols(self) -> None:
        client = self.make_client()
        client._get_option_chain_data = AsyncMock()
        option_legs = [
            build_option_leg(symbol="SPY"),
            build_option_leg(symbol="QQQ"),
        ]

        with self.assertRaises(MalformedOrderError):
            await client._place_option_order(
                option_legs,
                "debit",
                1,
                1.25,
            )

        client._get_option_chain_data.assert_not_awaited()

    async def test_option_order_requires_chain_and_matching_instruments(
        self,
    ) -> None:
        client = self.make_client()
        client._get_option_chain_data = AsyncMock(return_value=None)

        with self.assertRaises(InstruemtNotFoundError):
            await client._place_option_order(
                [build_option_leg()],
                "debit",
                1,
                1.25,
            )

        client._get_option_chain_data = AsyncMock(
            return_value=SimpleNamespace(id="chain-id")
        )
        client._get_oi_helper = AsyncMock(return_value=[])

        with self.assertRaisesRegex(ValueError, "Option legs should match"):
            await client._place_option_order(
                [build_option_leg()],
                "debit",
                1,
                1.25,
            )

    async def test_option_order_requires_side_and_position_effect(self) -> None:
        client = self.make_client()
        leg = build_option_leg(side=None, position_effect="open")
        client._get_option_chain_data = AsyncMock(
            return_value=SimpleNamespace(id="chain-id")
        )
        client._get_oi_helper = AsyncMock(
            return_value=[build_option_instrument(id="option-id")]
        )

        with self.assertRaises(MalformedOrderError):
            await client._place_option_order([leg], "debit", 1, 1.25)

    async def test_option_order_returns_none_when_post_fails(self) -> None:
        client = self.make_client()
        client._get_option_chain_data = AsyncMock(
            return_value=SimpleNamespace(id="chain-id")
        )
        client._get_oi_helper = AsyncMock(
            return_value=[build_option_instrument(id="option-id")]
        )
        client._async_http_client._post.return_value = None

        with self.assertLogs(
            "robinhood.core._trading_impl",
            level="WARNING",
        ):
            result = await client._place_option_order(
                [build_option_leg()],
                "debit",
                1,
                1.25,
            )

        self.assertIsNone(result)

    async def test_option_order_posts_single_leg_payload(self) -> None:
        client = self.make_client()
        client._get_option_chain_data = AsyncMock(
            return_value=SimpleNamespace(id="chain-id")
        )
        option_instrument = build_option_instrument(id="option-id")
        client._get_oi_helper = AsyncMock(return_value=[option_instrument])
        response_payload = build_option_order_response_payload()
        client._async_http_client._post.return_value = [response_payload]

        result = await client._place_option_order(
            [build_option_leg()],
            "debit",
            1,
            1.25,
        )

        self.assertEqual(
            OptionOrderResponse.from_json(response_payload),
            result,
        )
        client._async_http_client._post.assert_awaited_once()
        post_kwargs = client._async_http_client._post.await_args.kwargs
        self.assertEqual(API_OPTION_ORDER, post_kwargs["endpoint"])
        self.assertEqual("debit", post_kwargs["json"]["direction"])
        self.assertEqual(1.25, post_kwargs["json"]["price"])
        self.assertEqual(1, post_kwargs["json"]["quantity"])
        self.assertEqual(
            [
                {
                    "option": option_instrument.url,
                    "position_effect": "open",
                    "ratio_quantity": 1,
                    "side": "buy",
                }
            ],
            post_kwargs["json"]["legs"],
        )


if __name__ == "__main__":
    unittest.main()
