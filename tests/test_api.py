from dataclasses import asdict
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, Mock, call, patch

from robinhood.api_dataclasses import OptionRequest
from robinhood.constants import (
    API_INSTRUMENTS,
    API_OPTION_CHAINS,
    API_OPTIONS_INSTRUMENTS,
    API_QUOTES,
    MAX_LIMIT,
    PARAM_CHAIN_ID,
    PARAM_EXPIRATION_DATE,
    PARAM_LIMIT,
    PARAM_OPTION_STATE,
    PARAM_OPTION_STRIKE_PRICE,
    PARAM_OPTION_TYPE,
    PARAM_SYMBOLS,
)
from robinhood.robinhood_api_logic import Robinhood
from tests.support import build_option_greek_data, build_option_instrument


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


class TestRobinhoodOptionFlow(unittest.TestCase):
    def make_client(self) -> Robinhood:
        client = Robinhood.__new__(Robinhood)
        client._db_cache = None
        client._http_client = Mock()
        return client

    @patch("robinhood.robinhood_api_logic.OptionCache")
    @patch("robinhood.robinhood_api_logic.RobinhoodHTTPClient")
    @patch("robinhood.robinhood_api_logic.get_token")
    @patch("robinhood.robinhood_api_logic._get_acc_id")
    @patch("robinhood.robinhood_api_logic.os.getenv")
    @patch("robinhood.robinhood_api_logic.load_dotenv")
    def test_init_uses_env_token_without_refreshing(
        self,
        mock_load_dotenv,
        mock_getenv,
        mock_get_acc_id,
        mock_get_token,
        mock_http_client_cls,
        mock_option_cache_cls,
    ):
        mock_getenv.return_value = "env-token"
        mock_get_acc_id.return_value = "ACC123"

        client = Robinhood(
            auto_login=True,
            cache=True,
            db_path="/tmp/test-cache.db",
        )

        mock_load_dotenv.assert_called_once()
        mock_get_token.assert_not_called()
        mock_http_client_cls.assert_called_once_with("env-token", None)
        mock_option_cache_cls.assert_called_once_with(
            Path("/tmp/test-cache.db"),
            True,
        )
        client.close()

    @patch("robinhood.robinhood_api_logic.OptionCache")
    @patch("robinhood.robinhood_api_logic.RobinhoodHTTPClient")
    @patch("robinhood.robinhood_api_logic.get_token")
    @patch("robinhood.robinhood_api_logic._get_acc_id")
    @patch("robinhood.robinhood_api_logic.os.getenv")
    @patch("robinhood.robinhood_api_logic.load_dotenv")
    def test_init_refreshes_token_when_env_token_is_rejected(
        self,
        _mock_load_dotenv,
        mock_getenv,
        mock_get_acc_id,
        mock_get_token,
        mock_http_client_cls,
        mock_option_cache_cls,
    ):
        mock_getenv.return_value = "stale-token"
        mock_get_acc_id.return_value = 403
        mock_get_token.return_value = ("fresh-token", "ACC123")

        client = Robinhood(auto_login=True, cache=False)

        mock_get_token.assert_called_once_with(open_browser=False)
        mock_http_client_cls.assert_called_once_with("fresh-token", None)
        mock_option_cache_cls.assert_not_called()
        client.close()

    def test_close_closes_cache_and_http_client(self):
        client = self.make_client()
        client._db_cache = Mock()
        client._http_client = Mock()

        client.close()

        client._http_client.close.assert_called_once_with()
        self.assertIsNone(client._db_cache)

    def test_resolve_option_greeks_from_ids_chunks_dedupes_and_rebuilds(self):
        client = self.make_client()
        req1 = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        req2 = OptionRequest(symbol="SPY", exp_date="2026-04-24")
        req3 = OptionRequest(symbol="QQQ", exp_date="2026-04-17")
        req1_ids = [f"id{i}" for i in range(150)]
        req2_ids = ["id149"] + [f"id{i}" for i in range(150, 204)] + ["missing"]
        req_to_ids = {req1: req1_ids, req2: req2_ids, req3: []}
        calls: list[tuple[list[str], int]] = []

        def fake_get_option_greek_data(
            option_ids: list[str], limit: int
        ) -> list:
            calls.append((list(option_ids), limit))
            return [
                build_option_greek_data(instrument_id=option_id)
                for option_id in option_ids
                if option_id != "missing"
            ]

        client._get_option_greek_data = fake_get_option_greek_data

        result = client._resolve_option_greeks_from_ids(
            [req1, req2, req3], req_to_ids, limit=17
        )

        self.assertEqual(2, len(calls))
        self.assertEqual(200, len(calls[0][0]))
        self.assertEqual(5, len(calls[1][0]))
        self.assertTrue(all(limit == 17 for _, limit in calls))
        self.assertEqual(
            req1_ids,
            [greek.instrument_id for greek in result[req1]],
        )
        self.assertEqual(
            [option_id for option_id in req2_ids if option_id != "missing"],
            [greek.instrument_id for greek in result[req2]],
        )
        self.assertEqual([], result[req3])

    def test_live_option_request_maps_instruments_back_to_requests(self):
        client = self.make_client()
        req_all = OptionRequest(symbol="SPY")
        req_call = OptionRequest(
            symbol="SPY", option_type="call", exp_date="2026-04-17"
        )
        inst_call = build_option_instrument(
            id="call-id",
            chain_symbol="SPY",
            expiration_date="2026-04-17",
            type="call",
        )
        inst_put = build_option_instrument(
            id="put-id",
            chain_symbol="SPY",
            expiration_date="2026-04-17",
            type="put",
        )
        client.get_option_chain_data = Mock(
            return_value=[SimpleNamespace(symbol="SPY", id="chain-id")]
        )
        client._get_oi_helper = Mock(return_value=[inst_call, inst_put])
        client._resolve_option_greeks_from_ids = Mock(
            return_value={req_all: [], req_call: []}
        )

        result = client.no_db_option_greeks_batch_request(
            [req_all, req_call], limit=11
        )

        self.assertEqual({req_all: [], req_call: []}, result)
        client._resolve_option_greeks_from_ids.assert_called_once_with(
            [req_all, req_call],
            {
                req_all: ["call-id", "put-id"],
                req_call: ["call-id"],
            },
            11,
        )

    def test_get_option_greeks_batch_request_normalizes_single_request(self):
        client = self.make_client()
        request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        expected = {request: [build_option_greek_data(instrument_id="id1")]}
        client.no_db_option_greeks_batch_request = Mock(return_value=expected)

        result = client.get_option_greeks_batch_request(request, limit=50)

        self.assertEqual(expected, result)
        client.no_db_option_greeks_batch_request.assert_called_once_with(
            [request], 50
        )

    def test_get_strike_prices_returns_empty_lists_for_empty_results(self):
        client = self.make_client()
        client.get_option_chain_data = Mock(
            return_value=[SimpleNamespace(id="chain-id")]
        )
        client._http_client._get.return_value = []

        with patch(
            "robinhood.robinhood_api_logic.OptionInstrument.from_json"
        ) as mock_from_json:
            result = client.get_strike_prices(
                symbol="SPY", exp_date="2026-04-06"
            )

        self.assertEqual(
            {
                OptionRequest(
                    symbol="SPY",
                    option_type="call",
                    exp_date="2026-04-06",
                ): [],
                OptionRequest(
                    symbol="SPY",
                    option_type="put",
                    exp_date="2026-04-06",
                ): [],
            },
            result,
        )
        mock_from_json.assert_not_called()
        client._http_client._get.assert_called_once_with(
            API_OPTIONS_INSTRUMENTS,
            {
                PARAM_CHAIN_ID: "chain-id",
                PARAM_EXPIRATION_DATE: "2026-04-06",
                PARAM_OPTION_STATE: "active",
            },
        )

    def test_get_strike_prices_parses_valid_option_instrument_payloads(self):
        client = self.make_client()
        client.get_option_chain_data = Mock(
            return_value=[SimpleNamespace(id="chain-id")]
        )
        call_payload = asdict(
            build_option_instrument(
                id="call-id",
                expiration_date="2026-04-07",
                strike_price=500.0,
                type="call",
            )
        )
        put_payload = asdict(
            build_option_instrument(
                id="put-id",
                expiration_date="2026-04-07",
                strike_price=495.0,
                type="put",
            )
        )
        client._http_client._get.return_value = [call_payload, put_payload]

        result = client.get_strike_prices(symbol="SPY", exp_date="2026-04-07")

        self.assertEqual(
            {
                OptionRequest(
                    symbol="SPY",
                    option_type="call",
                    exp_date="2026-04-07",
                ): [500.0],
                OptionRequest(
                    symbol="SPY",
                    option_type="put",
                    exp_date="2026-04-07",
                ): [495.0],
            },
            result,
        )

    def test_get_strike_prices_returns_cached_strikes_without_http(self):
        client = self.make_client()
        client._db_cache = Mock()
        client._db_cache.is_option_request_synced.return_value = True
        client._db_cache.fetch_strike_prices.side_effect = [
            [495.0, 500.0],
            [490.0],
        ]

        result = client.get_strike_prices(symbol="SPY", exp_date="2026-04-07")

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
        client._db_cache.is_option_request_synced.assert_called_once_with(
            OptionRequest(symbol="SPY", exp_date="2026-04-07")
        )
        self.assertEqual(
            [
                call(
                    OptionRequest(
                        symbol="SPY",
                        option_type="call",
                        exp_date="2026-04-07",
                    )
                ),
                call(
                    OptionRequest(
                        symbol="SPY",
                        option_type="put",
                        exp_date="2026-04-07",
                    )
                ),
            ],
            client._db_cache.fetch_strike_prices.call_args_list,
        )
        client._http_client._get.assert_not_called()

    def test_get_option_greeks_batch_request_merges_cache_hits_and_misses(self):
        client = self.make_client()
        cached_request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        missed_request = OptionRequest(symbol="QQQ", exp_date="2026-04-17")
        client._db_cache = FakeCache(
            synced_requests={cached_request},
            ids_by_request={cached_request: ["cached-1", "cached-2"]},
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
        client._resolve_option_greeks_from_ids = Mock(
            return_value=cached_result
        )
        client.no_db_option_greeks_batch_request = Mock(
            return_value=live_result
        )

        result = client.get_option_greeks_batch_request(
            [cached_request, missed_request],
            limit=23,
        )

        self.assertEqual(
            {
                cached_request: cached_result[cached_request],
                missed_request: live_result[missed_request],
            },
            result,
        )
        client._resolve_option_greeks_from_ids.assert_called_once_with(
            [cached_request],
            {cached_request: ["cached-1", "cached-2"]},
            23,
        )
        client.no_db_option_greeks_batch_request.assert_called_once_with(
            [missed_request], 23
        )

    def test_get_expiration_dates_returns_cached_dates_without_http(self):
        client = self.make_client()
        client._db_cache = Mock()
        client._db_cache.fetch_expiration_dates_for_symbol.return_value = [
            "2026-04-17"
        ]

        result = client.get_expiration_dates("SPY")

        self.assertEqual(["2026-04-17"], result)
        client._http_client._get.assert_not_called()

    def test_get_expiration_dates_fetches_and_syncs_cache_on_miss(self):
        client = self.make_client()
        client._db_cache = Mock()
        client._db_cache.fetch_expiration_dates_for_symbol.return_value = []
        client._http_client._get.return_value = [{"payload": "ignored"}]
        chain = SimpleNamespace(
            symbol="SPY",
            expiration_dates=["2026-04-17", "2026-04-24"],
        )

        with patch(
            "robinhood.robinhood_api_logic.OptionChain.from_json",
            return_value=chain,
        ):
            result = client.get_expiration_dates("SPY")

        self.assertEqual(["2026-04-17", "2026-04-24"], result)
        client._http_client._get.assert_called_once_with(
            API_OPTION_CHAINS + "SPY/"
        )
        client._db_cache.insert_option_chain.assert_called_once_with(chain)
        client._db_cache.sync_option_chain.assert_called_once_with("SPY")

    def test_get_stock_quotes_normalizes_single_symbol(self):
        client = self.make_client()
        client._http_client._get.return_value = [{"payload": "ignored"}]
        quote = SimpleNamespace(symbol="SPY")

        with patch(
            "robinhood.robinhood_api_logic.FullQuote.from_json",
            return_value=quote,
        ):
            result = client.get_stock_quotes("SPY")

        self.assertEqual([quote], result)
        client._http_client._get.assert_called_once_with(
            endpoint=API_QUOTES,
            params={PARAM_SYMBOLS: "SPY"},
        )

    def test_get_stock_info_inserts_rows_into_cache(self):
        client = self.make_client()
        client._db_cache = Mock()
        client._http_client._get.return_value = [{"payload": "ignored"}]
        stock_info = SimpleNamespace(
            symbol="SPY",
            id="stock-id",
            tradable_chain_id="chain-id",
        )

        with patch(
            "robinhood.robinhood_api_logic.StockInfo.from_json",
            return_value=stock_info,
        ):
            result = client.get_stock_info(["SPY", "QQQ"])

        self.assertEqual([stock_info], result)
        client._http_client._get.assert_called_once_with(
            API_INSTRUMENTS,
            {PARAM_SYMBOLS: "SPY,QQQ"},
        )
        client._db_cache.insert_stock_info.assert_called_once_with(stock_info)

    def test_get_oi_helper_clamps_limit_and_syncs_cache_mappings(self):
        client = self.make_client()
        client._db_cache = Mock()
        client._http_client._get.return_value = [{"payload": "ignored"}]
        option_request = OptionRequest(
            symbol="SPY",
            exp_date="2026-04-17",
            option_type="call",
            strike_price=500.0,
        )
        option_instrument = build_option_instrument(
            id="instrument-id",
            chain_symbol="SPY",
            expiration_date="2026-04-17",
            type="call",
            strike_price=500.0,
        )

        with (
            patch(
                "robinhood.robinhood_api_logic.OptionInstrument.from_json",
                return_value=option_instrument,
            ),
            patch(
                "robinhood.robinhood_api_logic.map_option_requests_to_ois",
                return_value={option_request: [option_instrument]},
            ),
        ):
            result = client._get_oi_helper(
                [option_request],
                {"SPY": "chain-id"},
                limit=MAX_LIMIT + 50,
            )

        self.assertEqual([option_instrument], result)
        client._http_client._get.assert_called_once_with(
            endpoint=API_OPTIONS_INSTRUMENTS,
            params={
                PARAM_EXPIRATION_DATE: "2026-04-17",
                PARAM_CHAIN_ID: "chain-id",
                PARAM_LIMIT: MAX_LIMIT,
                PARAM_OPTION_STATE: "active",
                PARAM_OPTION_TYPE: "call",
                PARAM_OPTION_STRIKE_PRICE: 500.0,
            },
        )
        client._db_cache.sync_option_request_dispatch.assert_called_once_with(
            option_request,
            [option_instrument],
        )

    def test_get_option_chain_data_skips_symbols_without_chain_ids(self):
        client = self.make_client()
        client._http_client._get.side_effect = [
            [
                {"tradable_chain_id": None},
                {"tradable_chain_id": "chain-id"},
            ],
            [{"payload": "ignored"}],
        ]
        chain = SimpleNamespace(symbol="SPY", id="chain-id")

        with patch(
            "robinhood.robinhood_api_logic.OptionChain.from_json",
            return_value=chain,
        ):
            result = client.get_option_chain_data(["BAD", "SPY"])

        self.assertEqual([chain], result)
        self.assertEqual(
            [
                ((API_INSTRUMENTS, {PARAM_SYMBOLS: "BAD,SPY"}),),
                ((API_OPTION_CHAINS, {"ids": "chain-id"}),),
            ],
            client._http_client._get.call_args_list,
        )


if __name__ == "__main__":
    unittest.main()
