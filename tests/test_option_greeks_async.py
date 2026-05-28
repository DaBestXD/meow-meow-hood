from __future__ import annotations

import asyncio
import unittest
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock

from robinhood.async_robinhood_class import AsyncRobinhood
from robinhood.constants import API_OPTIONS_GREEKS_DATA, PARAM_OPTION_IDS
from robinhood.dataclasses.api_dataclasses import OptionChain, OptionRequest
from tests.support import (
    build_async_robinhood_client,
    build_option_chain_payload,
    build_option_greek_data,
    build_option_instrument,
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


def build_async_client(*, db_cache: object | None = None) -> AsyncRobinhood:
    client = build_async_robinhood_client(
        http_client=SimpleNamespace(_get=AsyncMock()),
        db_cache=db_cache,
    )
    client.event_loop.close()
    return client


class TestAsyncOptionGreeks(unittest.IsolatedAsyncioTestCase):
    async def test_resolve_option_greeks_from_ids_chunks_dedupes_and_rebuilds(
        self,
    ) -> None:
        client = build_async_client()
        req1 = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        req2 = OptionRequest(symbol="SPY", exp_date="2026-04-24")
        req3 = OptionRequest(symbol="QQQ", exp_date="2026-04-17")
        req1_ids = [f"id{i}" for i in range(150)]
        req2_ids = ["id149"] + [f"id{i}" for i in range(150, 204)] + ["missing"]
        req_to_ids = {req1: req1_ids, req2: req2_ids, req3: []}
        calls: list[list[str]] = []

        async def fake_get_option_greek_data(option_ids: list[str]) -> list:
            calls.append(list(option_ids))
            return [
                build_option_greek_data(instrument_id=option_id)
                for option_id in option_ids
                if option_id != "missing"
            ]

        client._get_option_greek_data = fake_get_option_greek_data

        result = await client._resolve_option_greeks_from_ids(
            [req1, req2, req3], req_to_ids
        )

        self.assertEqual(2, len(calls))
        self.assertEqual(200, len(calls[0]))
        self.assertEqual(5, len(calls[1]))
        self.assertEqual(
            req1_ids,
            [greek.instrument_id for greek in result[req1]],
        )
        self.assertEqual(
            [option_id for option_id in req2_ids if option_id != "missing"],
            [greek.instrument_id for greek in result[req2]],
        )
        self.assertEqual([], result[req3])

    async def test_resolve_option_greeks_from_ids_returns_empty_for_empty_ids(
        self,
    ) -> None:
        client = build_async_client()
        request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        client._get_option_greek_data = AsyncMock()

        result = await client._resolve_option_greeks_from_ids(
            [request], {request: []}
        )

        self.assertEqual({request: []}, result)
        client._get_option_greek_data.assert_not_awaited()

    async def test_resolve_option_greeks_starts_all_chunks_before_failure(
        self,
    ) -> None:
        client = build_async_client()
        request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        option_ids = [f"id{i}" for i in range(400)]
        second_chunk_started = asyncio.Event()
        release_second_chunk = asyncio.Event()
        second_chunk_finished = asyncio.Event()

        async def fake_get_option_greek_data(batch_ids: list[str]) -> list:
            if batch_ids[0] == "id0":
                await second_chunk_started.wait()
                raise RuntimeError("boom")
            second_chunk_started.set()
            await release_second_chunk.wait()
            second_chunk_finished.set()
            return [
                build_option_greek_data(instrument_id=option_id)
                for option_id in batch_ids
            ]

        client._get_option_greek_data = fake_get_option_greek_data

        with self.assertRaisesRegex(RuntimeError, "boom"):
            await client._resolve_option_greeks_from_ids(
                [request], {request: option_ids}
            )

        self.assertTrue(second_chunk_started.is_set())
        release_second_chunk.set()
        await asyncio.wait_for(second_chunk_finished.wait(), timeout=1)

    async def test_no_db_option_greeks_returns_empty_when_no_chains(
        self,
    ) -> None:
        client = build_async_client()
        request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        client._get_option_chain_data = AsyncMock(return_value=None)
        client._get_oi_helper = AsyncMock()

        with self.assertLogs(
            "robinhood.core._option_impl",
            level="WARNING",
        ) as logs:
            result = await client._no_db_option_greeks_batch_request([request])

        self.assertEqual({request: []}, result)
        self.assertIn(
            "No chains returned for all option request",
            logs.output[0],
        )
        client._get_oi_helper.assert_not_awaited()

    async def test_no_db_option_greeks_batch_request_uses_single_chain_object(
        self,
    ) -> None:
        client = build_async_client()
        request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        chain = OptionChain.from_json(
            build_option_chain_payload(id="chain-id", symbol="SPY")
        )
        option_instrument = build_option_instrument(
            id="instrument-id",
            chain_symbol="SPY",
            expiration_date="2026-04-17",
        )
        expected = {
            request: [build_option_greek_data(instrument_id="instrument-id")]
        }
        client._get_option_chain_data = AsyncMock(return_value=chain)
        client._get_oi_helper = AsyncMock(return_value=[option_instrument])
        client._resolve_option_greeks_from_ids = AsyncMock(
            return_value=expected
        )

        result = await client._no_db_option_greeks_batch_request([request])

        self.assertEqual(expected, result)
        client._get_oi_helper.assert_awaited_once_with(
            [request],
            {"SPY": "chain-id"},
        )
        client._resolve_option_greeks_from_ids.assert_awaited_once_with(
            [request],
            {request: ["instrument-id"]},
        )

    async def test_get_option_greeks_batch_request_normalizes_single_request(
        self,
    ) -> None:
        client = build_async_client()
        request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        expected = {request: [build_option_greek_data(instrument_id="id1")]}
        client._no_db_option_greeks_batch_request = AsyncMock(
            return_value=expected
        )

        result = await client._get_option_greeks_batch_request(request)

        self.assertEqual(expected, result)
        client._no_db_option_greeks_batch_request.assert_awaited_once_with(
            [request]
        )

    async def test_get_option_greeks_batch_request_merges_cache_hits_and_misses(
        self,
    ) -> None:
        cached_request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        missed_request = OptionRequest(symbol="QQQ", exp_date="2026-04-17")
        client = build_async_client(
            db_cache=FakeCache(
                synced_requests={cached_request},
                ids_by_request={cached_request: ["cached-1", "cached-2"]},
            )
        )
        cached_result = {
            cached_request: [
                build_option_greek_data(instrument_id="cached-1"),
                build_option_greek_data(instrument_id="cached-2"),
            ]
        }
        live_result = {
            missed_request: [build_option_greek_data(instrument_id="live-1")]
        }
        client._resolve_option_greeks_from_ids = AsyncMock(
            return_value=cached_result
        )
        client._no_db_option_greeks_batch_request = AsyncMock(
            return_value=live_result
        )

        result = await client._get_option_greeks_batch_request(
            [cached_request, missed_request]
        )

        self.assertEqual(
            {
                cached_request: cached_result[cached_request],
                missed_request: live_result[missed_request],
            },
            result,
        )
        client._resolve_option_greeks_from_ids.assert_awaited_once_with(
            [cached_request],
            {cached_request: ["cached-1", "cached-2"]},
        )
        client._no_db_option_greeks_batch_request.assert_awaited_once_with(
            [missed_request]
        )

    async def test_get_option_greeks_batch_request_logs_cache_hit(self) -> None:
        request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        client = build_async_client(
            db_cache=FakeCache(
                synced_requests={request},
                ids_by_request={request: ["cached-1"]},
            )
        )
        client._resolve_option_greeks_from_ids = AsyncMock(
            return_value={request: []}
        )
        client._no_db_option_greeks_batch_request = AsyncMock(return_value={})

        with self.assertLogs(
            "robinhood.core._option_impl",
            level="DEBUG",
        ) as logs:
            result = await client._get_option_greeks_batch_request(request)

        self.assertEqual({request: []}, result)
        self.assertIn(
            "get_option_greeks_batch_request cache hit for SPY",
            logs.output[0],
        )

    async def test_get_option_greek_data_returns_empty_without_ids(
        self,
    ) -> None:
        client = build_async_client()

        with self.assertLogs(
            "robinhood.core._option_impl",
            level="WARNING",
        ) as logs:
            result = await client._get_option_greek_data([])

        self.assertEqual([], result)
        self.assertIn("warning no option id supplied", logs.output[0])
        client._async_http_client._get.assert_not_awaited()

    async def test_get_option_greek_data_fetches_payloads_for_option_ids(
        self,
    ) -> None:
        client = build_async_client()
        greek = build_option_greek_data(instrument_id="id-1")
        client._async_http_client._get = AsyncMock(return_value=[asdict(greek)])

        result = await client._get_option_greek_data(["id-1"])

        self.assertEqual([greek], result)
        client._async_http_client._get.assert_awaited_once_with(
            endpoint=API_OPTIONS_GREEKS_DATA,
            params={PARAM_OPTION_IDS: "id-1"},
        )
