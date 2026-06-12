from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

from robinhood.async_robinhood_class import AsyncRobinhood
from robinhood.constants import (
    API_FUTURES_CONTRACTS,
    API_FUTURES_PRODUCTS,
    API_INDEXES,
    API_INSTRUMENTS,
    API_ORDERBOOK,
    PARAM_PRODUCT_IDS,
    PARAM_SYMBOLS,
)
from robinhood.dataclasses.api_dataclasses import (
    FuturesContract,
    FuturesProduct,
    IndexInfo,
    OrderBook,
)
from tests.support import (
    build_async_robinhood_client,
    build_futures_contract_payload,
    build_futures_product_payload,
    build_index_info_payload,
    build_orderbook_payload,
    build_stock_info_payload,
)


@pytest.mark.asyncio
class TestAsyncMarketData:
    @pytest.fixture(autouse=True)
    def _set_client_tracker(self, async_client_tracker) -> None:
        self.track_client = async_client_tracker

    def make_client(self) -> AsyncRobinhood:
        client = build_async_robinhood_client(
            http_client=SimpleNamespace(_get=AsyncMock())
        )
        return self.track_client(client)

    async def test_get_stock_info_returns_none_for_empty_response(self):
        client = self.make_client()
        client._async_http_client._get.return_value = []

        result = await client.get_stock_info("SPY")

        assert result is None
        client._async_http_client._get.assert_awaited_once_with(
            endpoint=API_INSTRUMENTS,
            params={PARAM_SYMBOLS: "SPY"},
        )

    async def test_get_index_info_returns_single_result_shape(self):
        client = self.make_client()
        payload = build_index_info_payload(symbol="VIX")
        client._async_http_client._get.return_value = [payload]

        result = await client.get_index_info("VIX")

        assert IndexInfo.from_json(payload) == result
        client._async_http_client._get.assert_awaited_once_with(
            endpoint=API_INDEXES,
            params={PARAM_SYMBOLS: "VIX"},
        )

    async def test_get_index_info_returns_none_for_empty_response(self):
        client = self.make_client()
        client._async_http_client._get.return_value = []

        result = await client.get_index_info("VIX")

        assert result is None

    async def test_get_orderbook_returns_snapshot_for_symbol(self):
        client = self.make_client()
        stock_payload = build_stock_info_payload(id="stock-id", symbol="SPY")
        orderbook_payload = build_orderbook_payload()
        client._async_http_client._get.side_effect = [
            [stock_payload],
            [orderbook_payload],
        ]

        result = await client.get_orderbook("SPY")

        assert OrderBook.from_json(orderbook_payload) == result
        assert [
            call(
                endpoint=API_INSTRUMENTS,
                params={PARAM_SYMBOLS: "SPY"},
            ),
            call(API_ORDERBOOK + "stock-id/"),
        ] == client._async_http_client._get.call_args_list

    async def test_get_orderbook_returns_none_for_empty_snapshot(self, caplog):
        client = self.make_client()
        client._async_http_client._get.side_effect = [
            [build_stock_info_payload(id="stock-id", symbol="SPY")],
            [],
        ]

        with caplog.at_level(
            "WARNING",
            logger="robinhood.core._market_data_impl",
        ):
            result = await client.get_orderbook("SPY")

        assert result is None

    async def test_get_future_info_filters_products_by_display_symbol(self):
        client = self.make_client()
        es_payload = build_futures_product_payload(
            id="es-product",
            display_symbol="/ES",
        )
        nq_payload = build_futures_product_payload(
            id="nq-product",
            display_symbol="/NQ",
        )
        client._async_http_client._get.return_value = [es_payload, nq_payload]

        result = await client.get_future_info("/NQ")

        assert FuturesProduct.from_json(nq_payload) == result
        client._async_http_client._get.assert_awaited_once_with(
            API_FUTURES_PRODUCTS
        )

    async def test_get_all_futures_products_returns_none_for_empty_response(
        self,
        caplog,
    ):
        client = self.make_client()
        client._async_http_client._get.return_value = []

        with caplog.at_level(
            "WARNING",
            logger="robinhood.core._market_data_impl",
        ):
            result = await client.get_all_futures_products()

        assert result is None

    async def test_get_active_contracts_for_id_sorts_by_expiration(self):
        client = self.make_client()
        later = build_futures_contract_payload(
            id="later",
            display_symbol="/ESU26",
            expiration_mmy="202609",
        )
        earlier = build_futures_contract_payload(
            id="earlier",
            display_symbol="/ESM26",
            expiration_mmy="202606",
        )
        client._async_http_client._get.return_value = [later, earlier]

        result = await client.get_active_contracts_for_id("future-product-id")

        assert [
            FuturesContract.from_json(earlier),
            FuturesContract.from_json(later),
        ] == result
        client._async_http_client._get.assert_awaited_once_with(
            endpoint=API_FUTURES_CONTRACTS,
            params={PARAM_PRODUCT_IDS: "future-product-id"},
        )
