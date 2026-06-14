from __future__ import annotations

from typing import Any, Literal, cast
from unittest.mock import AsyncMock

import pytest

from robinhood import (
    AccountIdNotFoundError,
    InstrumentNotFoundError,
    MalformedOrderError,
)
from robinhood.async_robinhood_class import AsyncRobinhood
from robinhood.constants import API_OPTION_ORDER, API_STOCK_ORDER, BASE_API_LINK
from robinhood.dataclasses.api_dataclasses import (
    InstrumentQuote,
    OptionOrderResponse,
    OptionRequest,
    StockInfo,
    StockOrderResponse,
)
from tests.support import (
    MockAsyncHTTPClient,
    build_async_robinhood_client,
    build_instrument_quote_payload,
    build_option_instrument,
    build_option_order_response_payload,
    build_stock_info_payload,
    build_stock_order_response_payload,
    get_http_mock,
    set_mock_attr,
)


class FakeChain:
    id = "chain-id"


def build_option_leg(
    *,
    symbol: str = "SPY",
    side: Literal["buy", "sell"] | None = "buy",
    position_effect: Literal["open", "close"] | None = "open",
) -> OptionRequest:
    return OptionRequest(
        symbol=symbol,
        exp_date="2026-04-17",
        option_type="call",
        strike_price=500.0,
        side=side,
        position_effect=position_effect,
    )


@pytest.mark.asyncio
class TestTradingAsync:
    @pytest.fixture(autouse=True)
    def _set_client_tracker(self, async_client_tracker) -> None:
        self.track_client = async_client_tracker

    def make_client(self) -> tuple[AsyncRobinhood, MockAsyncHTTPClient]:
        client = build_async_robinhood_client(http_client=MockAsyncHTTPClient())
        client.acc_id = "ACC123"
        client = self.track_client(client)
        return client, get_http_mock(client)

    def set_market_lookup_success(self, client: AsyncRobinhood) -> None:
        set_mock_attr(
            client,
            "_get_stock_info",
            AsyncMock(
                return_value=StockInfo.from_json(build_stock_info_payload())
            ),
        )
        set_mock_attr(
            client,
            "_get_stock_quotes",
            AsyncMock(
                return_value=InstrumentQuote.from_json(
                    build_instrument_quote_payload()
                )
            ),
        )

    async def test_market_stock_order_rejects_invalid_side(self) -> None:
        client, _http_client = self.make_client()

        with pytest.raises(MalformedOrderError):
            await client._place_market_stock_order(
                "SPY",
                cast(Any, "hold"),
                dollar_based_amount=1.0,
            )

    async def test_market_stock_order_requires_exactly_one_amount(self) -> None:
        client, _http_client = self.make_client()

        with pytest.raises(MalformedOrderError):
            await client._place_market_stock_order("SPY", "buy")

        with pytest.raises(MalformedOrderError):
            await client._place_market_stock_order(
                "SPY",
                "buy",
                dollar_based_amount=1.0,
                quantity=1.0,
            )

    async def test_market_stock_order_requires_valid_account_id(self) -> None:
        client, _http_client = self.make_client()
        client.acc_id = 403

        with pytest.raises(AccountIdNotFoundError):
            await client._place_market_stock_order(
                "SPY",
                "buy",
                dollar_based_amount=1.0,
            )

    async def test_market_stock_order_requires_stock_info_and_quote(
        self,
    ) -> None:
        client, _http_client = self.make_client()
        set_mock_attr(client, "_get_stock_info", AsyncMock(return_value=None))
        set_mock_attr(client, "_get_stock_quotes", AsyncMock())

        with pytest.raises(InstrumentNotFoundError):
            await client._place_market_stock_order(
                "SPY",
                "buy",
                dollar_based_amount=1.0,
            )

        set_mock_attr(
            client,
            "_get_stock_info",
            AsyncMock(
                return_value=StockInfo.from_json(build_stock_info_payload())
            ),
        )
        set_mock_attr(client, "_get_stock_quotes", AsyncMock(return_value=None))

        with pytest.raises(ValueError, match="unable to retrieve quote"):
            await client._place_market_stock_order(
                "SPY",
                "buy",
                dollar_based_amount=1.0,
            )

    async def test_market_stock_order_posts_dollar_payload(self) -> None:
        client, http_client = self.make_client()
        self.set_market_lookup_success(client)
        response_payload = build_stock_order_response_payload()
        http_client._post.return_value = response_payload

        result = await client._place_market_stock_order(
            "spy",
            "buy",
            dollar_based_amount=25.0,
        )

        assert StockOrderResponse.from_json(response_payload) == result
        http_client._post.assert_awaited_once()
        await_args = http_client._post.await_args
        assert await_args is not None
        post_kwargs = await_args.kwargs
        assert API_STOCK_ORDER == post_kwargs["endpoint"]
        assert "SPY" == post_kwargs["json"]["symbol"]
        assert {"amount": "25.00", "currency_code": "USD"} == post_kwargs[
            "json"
        ]["dollar_based_amount"]
        assert (
            BASE_API_LINK + "/accounts/ACC123/"
            == post_kwargs["json"]["account"]
        )

    async def test_market_stock_order_posts_quantity_payload(self) -> None:
        client, http_client = self.make_client()
        self.set_market_lookup_success(client)
        response_payload = build_stock_order_response_payload()
        http_client._post.return_value = response_payload

        result = await client._place_market_stock_order(
            "SPY",
            "sell",
            quantity=2.0,
        )

        assert StockOrderResponse.from_json(response_payload) == result
        await_args = http_client._post.await_args
        assert await_args is not None
        post_payload = await_args.kwargs["json"]
        assert "2.0" == post_payload["quantity"]
        assert "close" == post_payload["position_effect"]
        assert "dollar_based_amount" not in post_payload

    async def test_option_order_rejects_mixed_symbols(self) -> None:
        client, _http_client = self.make_client()
        get_option_chain_data = set_mock_attr(
            client,
            "_get_option_chain_data",
            AsyncMock(),
        )
        option_legs = [
            build_option_leg(symbol="SPY"),
            build_option_leg(symbol="QQQ"),
        ]

        with pytest.raises(MalformedOrderError):
            await client._place_option_order(
                option_legs,
                "debit",
                1,
                1.25,
            )

        get_option_chain_data.assert_not_awaited()

    async def test_option_order_requires_chain_and_matching_instruments(
        self,
    ) -> None:
        client, _http_client = self.make_client()
        set_mock_attr(
            client,
            "_get_option_chain_data",
            AsyncMock(return_value=None),
        )

        with pytest.raises(InstrumentNotFoundError):
            await client._place_option_order(
                [build_option_leg()],
                "debit",
                1,
                1.25,
            )

        set_mock_attr(
            client,
            "_get_option_chain_data",
            AsyncMock(return_value=FakeChain()),
        )
        set_mock_attr(client, "_get_oi_helper", AsyncMock(return_value=[]))

        with pytest.raises(ValueError, match="Option legs should match"):
            await client._place_option_order(
                [build_option_leg()],
                "debit",
                1,
                1.25,
            )

    async def test_option_order_requires_side_and_position_effect(self) -> None:
        client, _http_client = self.make_client()
        leg = build_option_leg(side=None, position_effect="open")
        set_mock_attr(
            client,
            "_get_option_chain_data",
            AsyncMock(return_value=FakeChain()),
        )
        set_mock_attr(
            client,
            "_get_oi_helper",
            AsyncMock(return_value=[build_option_instrument(id="option-id")]),
        )

        with pytest.raises(MalformedOrderError):
            await client._place_option_order([leg], "debit", 1, 1.25)

    async def test_option_order_returns_none_when_post_fails(
        self,
        caplog,
    ) -> None:
        client, http_client = self.make_client()
        set_mock_attr(
            client,
            "_get_option_chain_data",
            AsyncMock(return_value=FakeChain()),
        )
        set_mock_attr(
            client,
            "_get_oi_helper",
            AsyncMock(return_value=[build_option_instrument(id="option-id")]),
        )
        http_client._post.return_value = None

        with caplog.at_level(
            "WARNING",
            logger="robinhood.core._trading_impl",
        ):
            result = await client._place_option_order(
                [build_option_leg()],
                "debit",
                1,
                1.25,
            )

        assert result is None

    async def test_option_order_posts_single_leg_payload(self) -> None:
        client, http_client = self.make_client()
        set_mock_attr(
            client,
            "_get_option_chain_data",
            AsyncMock(return_value=FakeChain()),
        )
        option_instrument = build_option_instrument(id="option-id")
        set_mock_attr(
            client,
            "_get_oi_helper",
            AsyncMock(return_value=[option_instrument]),
        )
        response_payload = build_option_order_response_payload()
        http_client._post.return_value = [response_payload]

        result = await client._place_option_order(
            [build_option_leg()],
            "debit",
            1,
            1.25,
        )

        assert OptionOrderResponse.from_json(response_payload) == result
        http_client._post.assert_awaited_once()
        await_args = http_client._post.await_args
        assert await_args is not None
        post_kwargs = await_args.kwargs
        assert API_OPTION_ORDER == post_kwargs["endpoint"]
        assert "debit" == post_kwargs["json"]["direction"]
        assert 1.25 == post_kwargs["json"]["price"]
        assert 1 == post_kwargs["json"]["quantity"]
        assert [
            {
                "option": option_instrument.url,
                "position_effect": "open",
                "ratio_quantity": 1,
                "side": "buy",
            }
        ] == post_kwargs["json"]["legs"]
