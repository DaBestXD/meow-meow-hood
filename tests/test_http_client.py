import unittest
from unittest.mock import Mock, call, patch

from robinhood._http_client import RobinhoodHTTPClient
from robinhood.constants import BASE_API_LINK, MAX_LIMIT, PARAM_LIMIT
from tests.support import build_http_client


class TestRobinhoodHTTPClient(unittest.TestCase):
    @patch("robinhood._http_client.requests.Session")
    def test_init_sets_headers_and_optional_user_agent(self, mock_session_cls):
        session = Mock()
        session.headers = {}
        mock_session_cls.return_value = session

        client = RobinhoodHTTPClient("bearer-token", user_agent="agent/1.0")

        self.assertIs(client.session, session)
        self.assertEqual(
            "Bearer bearer-token", session.headers["Authorization"]
        )
        self.assertEqual("agent/1.0", session.headers["User-Agent"])

    def test_page_get_accumulates_results_until_next_link_is_empty(self):
        session = Mock()
        session.get.side_effect = [
            Mock(
                status_code=200,
                json=Mock(
                    return_value={"next": "page-3", "results": [{"id": 2}]}
                ),
            ),
            Mock(
                status_code=200,
                json=Mock(return_value={"next": None, "results": [{"id": 3}]}),
            ),
        ]
        client = build_http_client(session=session)

        result = client._page_get("page-2", [{"id": 1}])

        self.assertEqual([{"id": 1}, {"id": 2}, {"id": 3}], result)
        self.assertEqual(
            [call(url="page-2"), call(url="page-3")],
            session.get.call_args_list,
        )

    def test_get_returns_results_from_single_page_payload(self):
        session = Mock()
        session.get.return_value = Mock(
            status_code=200,
            json=Mock(return_value={"next": None, "results": [{"id": 1}]}),
        )
        client = build_http_client(session=session)

        result = client._get("/quotes/", {"symbols": "SPY"})

        self.assertEqual([{"id": 1}], result)
        session.get.assert_called_once_with(
            url=BASE_API_LINK + "/quotes/",
            params={"symbols": "SPY"},
            timeout=5,
        )

    def test_get_returns_empty_list_from_empty_paginated_payload(self):
        session = Mock()
        session.get.return_value = Mock(
            status_code=200,
            json=Mock(
                return_value={"next": None, "previous": None, "results": []}
            ),
        )
        client = build_http_client(session=session)

        result = client._get("/options/instruments/", {"chain_id": "chain-id"})

        self.assertEqual([], result)

    def test_get_wraps_single_payload_when_results_key_is_missing(self):
        session = Mock()
        session.get.return_value = Mock(
            status_code=200,
            json=Mock(return_value={"symbol": "SPY", "price": "100.0"}),
        )
        client = build_http_client(session=session)

        result = client._get("/quotes/", {"symbols": "SPY"})

        self.assertEqual([{"symbol": "SPY", "price": "100.0"}], result)

    def test_get_uses_first_page_only_when_custom_limit_disables_paging(self):
        session = Mock()
        session.get.return_value = Mock(
            status_code=200,
            json=Mock(return_value={"next": "page-2", "results": [{"id": 1}]}),
        )
        client = build_http_client(session=session)
        client._page_get = Mock()

        result = client._get("/options/", {PARAM_LIMIT: MAX_LIMIT - 1})

        self.assertEqual([{"id": 1}], result)
        client._page_get.assert_not_called()

    def test_get_follows_pagination_when_limit_is_default(self):
        session = Mock()
        session.get.return_value = Mock(
            status_code=200,
            json=Mock(return_value={"next": "page-2", "results": [{"id": 1}]}),
        )
        client = build_http_client(session=session)
        client._page_get = Mock(return_value=[{"id": 1}, {"id": 2}])

        result = client._get("/options/", {PARAM_LIMIT: MAX_LIMIT})

        self.assertEqual([{"id": 1}, {"id": 2}], result)
        client._page_get.assert_called_once_with("page-2", results=[{"id": 1}])

    def test_get_returns_empty_list_on_non_200(self):
        session = Mock()
        session.get.return_value = Mock(status_code=500)
        client = build_http_client(session=session)

        result = client._get("/quotes/")

        self.assertEqual([], result)


if __name__ == "__main__":
    unittest.main()
