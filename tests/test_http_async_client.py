from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock, patch

import aiohttp

from robinhood.constants import BASE_API_BONFIRE_LINK, BASE_API_LINK
from robinhood.core._http_async_client import RobinhoodAsyncHTTPClient
from tests.support import build_http_client


class FakeResponse:
    def __init__(
        self,
        *,
        payload: dict | None = None,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload if payload is not None else {}
        self.error = error

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def raise_for_status(self) -> None:
        if self.error is not None:
            raise self.error

    async def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(
        self,
        *,
        get_responses: list[FakeResponse] | None = None,
        post_responses: list[FakeResponse] | None = None,
    ) -> None:
        self._get_responses = list(get_responses or [])
        self._post_responses = list(post_responses or [])
        self.get_calls: list[dict] = []
        self.post_calls: list[dict] = []
        self.close = AsyncMock()

    def get(self, **kwargs) -> FakeResponse:
        self.get_calls.append(kwargs)
        return self._get_responses.pop(0)

    def post(self, **kwargs) -> FakeResponse:
        self.post_calls.append(kwargs)
        return self._post_responses.pop(0)


class TestRobinhoodAsyncHTTPClient(unittest.IsolatedAsyncioTestCase):
    @patch("robinhood.core._http_async_client.aiohttp.ClientSession")
    async def test_create_client_session_sets_headers_and_user_agent(
        self,
        mock_client_session,
    ) -> None:
        session = Mock()
        mock_client_session.return_value = session
        client = RobinhoodAsyncHTTPClient(
            "bearer-token", user_agent="agent/1.0"
        )

        result = await client.create_client_session()

        self.assertIs(session, result)
        mock_client_session.assert_called_once()
        self.assertEqual(
            "Bearer bearer-token",
            mock_client_session.call_args.kwargs["headers"]["Authorization"],
        )
        self.assertEqual(
            "agent/1.0",
            mock_client_session.call_args.kwargs["headers"]["User-Agent"],
        )

    async def test_close_awaits_underlying_session(self) -> None:
        session = Mock()
        session.close = AsyncMock()
        client = build_http_client(session=session)

        await client.close()

        session.close.assert_awaited_once_with()

    async def test_page_get_accumulates_results_until_next_link_is_empty(
        self,
    ) -> None:
        session = FakeSession(
            get_responses=[
                FakeResponse(
                    payload={"next": "page-3", "results": [{"id": 2}]}
                ),
                FakeResponse(payload={"next": None, "results": [{"id": 3}]}),
            ]
        )
        client = build_http_client(session=session)
        client.create_client_session = AsyncMock(return_value=session)

        result = await client._page_get("page-2", [{"id": 1}])

        self.assertEqual([{"id": 1}, {"id": 2}, {"id": 3}], result)
        self.assertEqual(
            [{"url": "page-2"}, {"url": "page-3"}],
            session.get_calls,
        )

    async def test_page_get_calls_error_handler_on_response_error(self) -> None:
        error = aiohttp.ClientResponseError(None, (), status=429)
        session = FakeSession(get_responses=[FakeResponse(error=error)])
        client = build_http_client(session=session)
        client.create_client_session = AsyncMock(return_value=session)
        client._error_status_code_handler = Mock(
            side_effect=RuntimeError("boom")
        )

        with self.assertRaisesRegex(RuntimeError, "boom"):
            await client._page_get("page-2", [{"id": 1}])

        client._error_status_code_handler.assert_called_once_with("page-2", 429)

    async def test_get_returns_results_from_single_page_payload(self) -> None:
        session = FakeSession(
            get_responses=[
                FakeResponse(payload={"next": None, "results": [{"id": 1}]})
            ]
        )
        client = build_http_client(session=session)
        client.create_client_session = AsyncMock(return_value=session)

        result = await client._get(
            endpoint="/quotes/",
            params={"symbols": "SPY"},
        )

        self.assertEqual([{"id": 1}], result)
        self.assertEqual(
            [
                {
                    "url": BASE_API_LINK + "/quotes/",
                    "params": {"symbols": "SPY"},
                }
            ],
            session.get_calls,
        )

    async def test_get_wraps_single_payload_when_results_key_is_missing(
        self,
    ) -> None:
        session = FakeSession(
            get_responses=[
                FakeResponse(payload={"symbol": "SPY", "price": "100.0"})
            ]
        )
        client = build_http_client(session=session)
        client.create_client_session = AsyncMock(return_value=session)

        result = await client._get(
            endpoint="/quotes/",
            params={"symbols": "SPY"},
        )

        self.assertEqual([{"symbol": "SPY", "price": "100.0"}], result)

    async def test_get_follows_pagination_when_next_link_exists(self) -> None:
        session = FakeSession(
            get_responses=[
                FakeResponse(payload={"next": "page-2", "results": [{"id": 1}]})
            ]
        )
        client = build_http_client(session=session)
        client.create_client_session = AsyncMock(return_value=session)
        client._page_get = AsyncMock(return_value=[{"id": 1}, {"id": 2}])

        result = await client._get(endpoint="/options/")

        self.assertEqual([{"id": 1}, {"id": 2}], result)
        client._page_get.assert_awaited_once_with("page-2", results=[{"id": 1}])

    async def test_post_returns_json_from_successful_response(self) -> None:
        session = FakeSession(
            post_responses=[FakeResponse(payload={"id": "order-id"})]
        )
        client = build_http_client(session=session)
        client.create_client_session = AsyncMock(return_value=session)

        result = await client._post(
            endpoint="/orders/",
            base_api_link=BASE_API_BONFIRE_LINK,
            data={"symbol": "SPY"},
        )

        self.assertEqual({"id": "order-id"}, result)
        self.assertEqual(
            [
                {
                    "url": BASE_API_BONFIRE_LINK + "/orders/",
                    "data": {"symbol": "SPY"},
                    "json": None,
                }
            ],
            session.post_calls,
        )

    async def test_post_calls_error_handler_on_response_error(self) -> None:
        error = aiohttp.ClientResponseError(None, (), status=400)
        session = FakeSession(post_responses=[FakeResponse(error=error)])
        client = build_http_client(session=session)
        client.create_client_session = AsyncMock(return_value=session)
        client._error_status_code_handler = Mock()

        result = await client._post(
            endpoint="/orders/",
            base_api_link=BASE_API_BONFIRE_LINK,
            data={"symbol": "SPY"},
        )

        self.assertIsNone(result)
        client._error_status_code_handler.assert_called_once_with(
            "/orders/",
            400,
        )

    def test_error_status_code_handler_raises_on_429(self) -> None:
        client = build_http_client()

        with self.assertRaises(NotImplementedError):
            client._error_status_code_handler("/quotes/", 429)

    def test_error_status_code_handler_logs_critical_on_403(self) -> None:
        client = build_http_client()

        with (
            self.assertLogs(
                "robinhood.core._http_async_client",
                level="CRITICAL",
            ) as logs,
            self.assertRaisesRegex(
                RuntimeError,
                "Access token invalid, relogin into robinhood",
            ),
        ):
            client._error_status_code_handler("/quotes/", 403)

        self.assertIn(
            "Access token invalid, relogin into robinhood",
            logs.output[0],
        )
