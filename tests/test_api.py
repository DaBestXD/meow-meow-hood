import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import ANY, Mock, call, patch

from robinhood.api_dataclasses import (
    FullQuote,
    OptionChain,
    OptionRequest,
    StockInfo,
)
from robinhood.constants import (
    API_INSTRUMENTS,
    API_OPTION_CHAINS,
    API_OPTIONS_GREEKS_DATA,
    API_OPTIONS_INSTRUMENTS,
    API_POSITIONS_NON_OPTIONS,
    API_POSITIONS_OPTIONS,
    API_QUOTES,
    PARAM_ACCOUNT_NUMBER,
    PARAM_CHAIN_ID,
    PARAM_EXPIRATION_DATE,
    PARAM_ID,
    PARAM_NON_ZERO,
    PARAM_OPTION_IDS,
    PARAM_OPTION_STATE,
    PARAM_OPTION_STRIKE_PRICE,
    PARAM_OPTION_TYPE,
    PARAM_SYMBOLS,
)
from robinhood.robinhood_api_logic import Robinhood
from tests.support import (
    build_full_quote_payload,
    build_option_chain_payload,
    build_option_greek_data,
    build_option_instrument,
    build_robinhood_client,
    build_stock_info_payload,
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


class TestRobinhoodOptionFlow(unittest.TestCase):
    @patch("robinhood.robinhood_api_logic.OptionCache")
    @patch("robinhood.robinhood_api_logic.RobinhoodHTTPClient")
    @patch("robinhood.robinhood_api_logic.get_token")
    @patch("robinhood.robinhood_api_logic.get_acc_id")
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
            extract_token=True,
            enable_cache=True,
            config_path="/tmp/test-cache.db",
        )

        mock_load_dotenv.assert_called_once_with(dotenv_path=ANY)
        mock_get_acc_id.assert_called_once_with("env-token")
        mock_get_token.assert_not_called()
        mock_http_client_cls.assert_called_once_with("env-token", None)
        mock_option_cache_cls.assert_called_once_with(
            Path("/tmp/test-cache.db")
            / ".meow-meow-config"
            / "meow-meow-hood.db",
            True,
        )
        client.close()

    @patch("robinhood.robinhood_api_logic.OptionCache")
    @patch("robinhood.robinhood_api_logic.RobinhoodHTTPClient")
    @patch("robinhood.robinhood_api_logic.get_token")
    @patch("robinhood.robinhood_api_logic.get_acc_id")
    @patch("robinhood.robinhood_api_logic.os.getenv")
    @patch("robinhood.robinhood_api_logic.load_dotenv")
    def test_init_refreshes_token_when_env_token_is_rejected(
        self,
        mock_load_dotenv,
        mock_getenv,
        mock_get_acc_id,
        mock_get_token,
        mock_http_client_cls,
        mock_option_cache_cls,
    ):
        mock_getenv.return_value = "stale-token"
        mock_get_acc_id.return_value = 403
        mock_get_token.return_value = ("fresh-token", "ACC123")

        client = Robinhood(extract_token=True, enable_cache=False)

        mock_load_dotenv.assert_called_once_with(dotenv_path=ANY)
        mock_get_acc_id.assert_called_once_with("stale-token")
        mock_get_token.assert_called_once_with(
            env_path=ANY,
            open_browser=True,
        )
        self.assertEqual(
            ".env",
            mock_get_token.call_args.kwargs["env_path"].name,
        )
        mock_http_client_cls.assert_called_once_with("fresh-token", None)
        mock_option_cache_cls.assert_not_called()
        client.close()

    @patch("robinhood.robinhood_api_logic.OptionCache")
    @patch("robinhood.robinhood_api_logic.RobinhoodHTTPClient")
    @patch("robinhood.robinhood_api_logic.get_token")
    @patch("robinhood.robinhood_api_logic.get_acc_id")
    @patch("robinhood.robinhood_api_logic.os.getenv")
    @patch("robinhood.robinhood_api_logic.load_dotenv")
    def test_init_refreshes_token_without_browser_override(
        self,
        mock_load_dotenv,
        mock_getenv,
        mock_get_acc_id,
        mock_get_token,
        mock_http_client_cls,
        mock_option_cache_cls,
    ):
        mock_getenv.return_value = "stale-token"
        mock_get_acc_id.return_value = 403
        mock_get_token.return_value = ("fresh-token", "ACC123")

        client = Robinhood(
            extract_token=True,
            enable_cache=False,
        )

        mock_load_dotenv.assert_called_once_with(dotenv_path=ANY)
        mock_get_acc_id.assert_called_once_with("stale-token")
        mock_get_token.assert_called_once_with(
            env_path=ANY,
            open_browser=True,
        )
        mock_http_client_cls.assert_called_once_with("fresh-token", None)
        mock_option_cache_cls.assert_not_called()
        client.close()

    def test_close_closes_cache_and_http_client(self):
        http_client = Mock()
        db_cache = Mock()
        client = build_robinhood_client(
            http_client=http_client,
            db_cache=db_cache,
        )

        client.close()

        http_client.close.assert_called_once_with()
        db_cache.close.assert_called_once_with()
        self.assertIsNone(client._db_cache)

    def test_context_manager_returns_self_and_closes_on_exit(self):
        client = build_robinhood_client()

        with patch.object(client, "close") as mock_close:
            with client as entered:
                self.assertIs(client, entered)

        mock_close.assert_called_once_with()

    def test_resolve_option_greeks_from_ids_chunks_dedupes_and_rebuilds(self):
        client = build_robinhood_client()
        req1 = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        req2 = OptionRequest(symbol="SPY", exp_date="2026-04-24")
        req3 = OptionRequest(symbol="QQQ", exp_date="2026-04-17")
        req1_ids = [f"id{i}" for i in range(150)]
        req2_ids = ["id149"] + [f"id{i}" for i in range(150, 204)] + ["missing"]
        req_to_ids = {req1: req1_ids, req2: req2_ids, req3: []}
        calls: list[list[str]] = []

        def fake_get_option_greek_data(option_ids: list[str]) -> list:
            calls.append(list(option_ids))
            return [
                build_option_greek_data(instrument_id=option_id)
                for option_id in option_ids
                if option_id != "missing"
            ]

        client._get_option_greek_data = fake_get_option_greek_data

        result = client._resolve_option_greeks_from_ids(
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

    def test_live_option_request_maps_instruments_back_to_requests(self):
        client = build_robinhood_client()
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
        chain = OptionChain.from_json(
            build_option_chain_payload(id="chain-id", symbol="SPY")
        )
        client.get_option_chain_data = Mock(return_value=[chain])
        client._get_oi_helper = Mock(return_value=[inst_call, inst_put])
        client._resolve_option_greeks_from_ids = Mock(
            return_value={req_all: [], req_call: []}
        )

        result = client.no_db_option_greeks_batch_request([req_all, req_call])

        self.assertEqual({req_all: [], req_call: []}, result)
        client._resolve_option_greeks_from_ids.assert_called_once_with(
            [req_all, req_call],
            {
                req_all: ["call-id", "put-id"],
                req_call: ["call-id"],
            },
        )

    def test_get_option_greeks_batch_request_normalizes_single_request(self):
        client = build_robinhood_client()
        request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        expected = {request: [build_option_greek_data(instrument_id="id1")]}
        client.no_db_option_greeks_batch_request = Mock(return_value=expected)

        result = client.get_option_greeks_batch_request(request)

        self.assertEqual(expected, result)
        client.no_db_option_greeks_batch_request.assert_called_once_with(
            [request]
        )

    def test_get_strike_prices_returns_empty_lists_for_empty_results(self):
        client = build_robinhood_client()
        client.get_option_chain_data = Mock(
            return_value=OptionChain.from_json(
                build_option_chain_payload(id="chain-id", symbol="SPY")
            )
        )
        client._http_client._get.return_value = []

        result = client.get_strike_prices(symbol="SPY", exp_date="2026-04-06")

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
        client._http_client._get.assert_called_once_with(
            API_OPTIONS_INSTRUMENTS,
            {
                PARAM_CHAIN_ID: "chain-id",
                PARAM_EXPIRATION_DATE: "2026-04-06",
                PARAM_OPTION_STATE: "active",
            },
        )

    def test_get_strike_prices_parses_valid_option_instrument_payloads(self):
        client = build_robinhood_client()
        client.get_option_chain_data = Mock(
            return_value=OptionChain.from_json(
                build_option_chain_payload(id="chain-id", symbol="SPY")
            )
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
        db_cache = Mock()
        db_cache.is_option_request_synced.return_value = True
        db_cache.fetch_strike_prices.side_effect = [
            [495.0, 500.0],
            [490.0],
        ]
        client = build_robinhood_client(db_cache=db_cache)

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
        db_cache.is_option_request_synced.assert_called_once_with(
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
            db_cache.fetch_strike_prices.call_args_list,
        )
        client._http_client._get.assert_not_called()

    def test_get_option_greeks_batch_request_merges_cache_hits_and_misses(self):
        client = build_robinhood_client(
            db_cache=FakeCache(
                synced_requests={
                    OptionRequest(symbol="SPY", exp_date="2026-04-17")
                },
                ids_by_request={
                    OptionRequest(
                        symbol="SPY",
                        exp_date="2026-04-17",
                    ): ["cached-1", "cached-2"]
                },
            )
        )
        cached_request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        missed_request = OptionRequest(symbol="QQQ", exp_date="2026-04-17")
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
            [cached_request, missed_request]
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
        )
        client.no_db_option_greeks_batch_request.assert_called_once_with(
            [missed_request]
        )

    def test_get_option_greeks_batch_request_logs_cache_hit(self):
        client = build_robinhood_client(
            db_cache=FakeCache(
                synced_requests={
                    OptionRequest(symbol="SPY", exp_date="2026-04-17")
                },
                ids_by_request={
                    OptionRequest(
                        symbol="SPY",
                        exp_date="2026-04-17",
                    ): ["cached-1"]
                },
            )
        )
        request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        client._resolve_option_greeks_from_ids = Mock(
            return_value={request: []}
        )
        client.no_db_option_greeks_batch_request = Mock(return_value={})

        with self.assertLogs(
            "robinhood.robinhood_api_logic", level="DEBUG"
        ) as logs:
            result = client.get_option_greeks_batch_request(request)

        self.assertEqual({request: []}, result)
        self.assertIn(
            "DEBUG:robinhood.robinhood_api_logic:"
            "get_option_greeks_batch_request cache hit for SPY",
            logs.output,
        )

    def test_get_expiration_dates_returns_cached_dates_without_http(self):
        db_cache = Mock()
        db_cache.fetch_expiration_dates_for_symbol.return_value = ["2026-04-17"]
        client = build_robinhood_client(db_cache=db_cache)

        result = client.get_expiration_dates("SPY")

        self.assertEqual(["2026-04-17"], result)
        client._http_client._get.assert_not_called()

    def test_get_expiration_dates_fetches_and_syncs_cache_on_miss(self):
        db_cache = Mock()
        db_cache.fetch_expiration_dates_for_symbol.return_value = []
        client = build_robinhood_client(db_cache=db_cache)
        chain_payload = build_option_chain_payload(
            symbol="SPY",
            expiration_dates=["2026-04-17", "2026-04-24"],
        )
        expected_chain = OptionChain.from_json(chain_payload)
        client._http_client._get.return_value = [chain_payload]

        result = client.get_expiration_dates("SPY")

        self.assertEqual(["2026-04-17", "2026-04-24"], result)
        client._http_client._get.assert_called_once_with(
            API_OPTION_CHAINS + "SPY/"
        )
        db_cache.insert_option_chain.assert_called_once_with(expected_chain)
        db_cache.sync_option_chain.assert_called_once_with("SPY")

    def test_get_expiration_dates_returns_none_when_no_chain_data_exists(self):
        client = build_robinhood_client()
        client._http_client._get.return_value = []

        with self.assertLogs(
            "robinhood.robinhood_api_logic", level="WARNING"
        ) as logs:
            result = client.get_expiration_dates("SPY")

        self.assertIsNone(result)
        self.assertIn("No expiration dates found for SPY", logs.output[0])

    def test_get_stock_quotes_normalizes_single_symbol(self):
        client = build_robinhood_client()
        quote_payload = build_full_quote_payload(symbol="SPY")
        client._http_client._get.return_value = [quote_payload]

        result = client.get_stock_quotes("SPY")

        self.assertEqual(FullQuote.from_json(quote_payload), result)
        client._http_client._get.assert_called_once_with(
            endpoint=API_QUOTES,
            params={PARAM_SYMBOLS: "SPY"},
        )

    def test_get_stock_quotes_returns_none_for_empty_payload(self):
        client = build_robinhood_client()
        client._http_client._get.return_value = []

        result = client.get_stock_quotes("SPY")

        self.assertIsNone(result)

    def test_get_stock_quotes_returns_list_for_multiple_symbols(self):
        client = build_robinhood_client()
        spy_quote = build_full_quote_payload(
            symbol="SPY",
            instrument_id="spy-id",
        )
        qqq_quote = build_full_quote_payload(
            symbol="QQQ",
            instrument_id="qqq-id",
        )
        client._http_client._get.return_value = [spy_quote, qqq_quote]

        result = client.get_stock_quotes(["SPY", "QQQ"])

        self.assertEqual(
            [
                FullQuote.from_json(spy_quote),
                FullQuote.from_json(qqq_quote),
            ],
            result,
        )

    def test_get_stock_info_inserts_rows_into_cache(self):
        db_cache = Mock()
        client = build_robinhood_client(db_cache=db_cache)
        stock_info_payload = build_stock_info_payload(
            symbol="SPY",
            id="stock-id",
            tradable_chain_id="chain-id",
        )
        expected_stock_info = StockInfo.from_json(stock_info_payload)
        client._http_client._get.return_value = [stock_info_payload]

        result = client.get_stock_info(["SPY", "QQQ"])

        self.assertEqual(expected_stock_info, result)
        client._http_client._get.assert_called_once_with(
            API_INSTRUMENTS,
            {PARAM_SYMBOLS: "SPY,QQQ"},
        )
        db_cache.insert_stock_info.assert_called_once_with(expected_stock_info)

    def test_get_stock_info_returns_none_for_empty_payload(self):
        client = build_robinhood_client()
        client._http_client._get.return_value = []

        result = client.get_stock_info("SPY")

        self.assertIsNone(result)

    def test_get_stock_info_returns_list_for_multiple_rows(self):
        db_cache = Mock()
        client = build_robinhood_client(db_cache=db_cache)
        spy_payload = build_stock_info_payload(
            id="spy-id",
            symbol="SPY",
            tradable_chain_id="spy-chain",
        )
        qqq_payload = build_stock_info_payload(
            id="qqq-id",
            symbol="QQQ",
            tradable_chain_id="qqq-chain",
        )
        client._http_client._get.return_value = [spy_payload, qqq_payload]

        result = client.get_stock_info(["SPY", "QQQ"])

        self.assertEqual(
            [
                StockInfo.from_json(spy_payload),
                StockInfo.from_json(qqq_payload),
            ],
            result,
        )
        self.assertEqual(
            [
                call(StockInfo.from_json(spy_payload)),
                call(StockInfo.from_json(qqq_payload)),
            ],
            db_cache.insert_stock_info.call_args_list,
        )

    def test_get_oi_helper_syncs_cache_mappings(self):
        db_cache = Mock()
        client = build_robinhood_client(db_cache=db_cache)
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
        option_payload = asdict(option_instrument)
        client._http_client._get.return_value = [option_payload]

        result = client._get_oi_helper([option_request], {"SPY": "chain-id"})

        self.assertEqual([option_instrument], result)
        client._http_client._get.assert_called_once_with(
            endpoint=API_OPTIONS_INSTRUMENTS,
            params={
                PARAM_EXPIRATION_DATE: "2026-04-17",
                PARAM_CHAIN_ID: "chain-id",
                PARAM_OPTION_STATE: "active",
                PARAM_OPTION_TYPE: "call",
                PARAM_OPTION_STRIKE_PRICE: 500.0,
            },
        )
        db_cache.insert_option_instrument.assert_called_once_with(
            [option_instrument]
        )
        db_cache.sync_option_request_dispatch.assert_called_once_with(
            option_request,
            [option_instrument],
        )

    def test_get_option_chain_data_skips_symbols_without_chain_ids(self):
        client = build_robinhood_client()
        chain_payload = build_option_chain_payload(id="chain-id", symbol="SPY")
        client._http_client._get.side_effect = [
            [
                {"tradable_chain_id": None},
                {"tradable_chain_id": "chain-id"},
            ],
            [chain_payload],
        ]

        result = client.get_option_chain_data(["BAD", "SPY"])

        self.assertEqual(OptionChain.from_json(chain_payload), result)
        self.assertEqual(
            [
                call(API_INSTRUMENTS, {PARAM_SYMBOLS: "BAD,SPY"}),
                call(API_OPTION_CHAINS, {PARAM_ID: "chain-id"}),
            ],
            client._http_client._get.call_args_list,
        )

    def test_get_strike_prices_returns_empty_lists_when_chain_lookup_fails(
        self,
    ):
        db_cache = Mock()
        db_cache.is_option_request_synced.return_value = False
        db_cache.get_chain_id.return_value = ""
        client = build_robinhood_client(db_cache=db_cache)
        client.get_option_chain_data = Mock(return_value=None)

        with self.assertLogs(
            "robinhood.robinhood_api_logic", level="WARNING"
        ) as logs:
            result = client.get_strike_prices(
                symbol="SPY",
                exp_date="2026-04-07",
            )

        self.assertEqual(
            {
                OptionRequest(
                    symbol="SPY",
                    option_type="call",
                    exp_date="2026-04-07",
                ): [],
                OptionRequest(
                    symbol="SPY",
                    option_type="put",
                    exp_date="2026-04-07",
                ): [],
            },
            result,
        )
        self.assertIn(
            "No strike prices found for SPY at 2026-04-07",
            logs.output[0],
        )
        client._http_client._get.assert_not_called()

    def test_no_db_option_greeks_batch_request_returns_empty_when_no_chains(
        self,
    ):
        client = build_robinhood_client()
        request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
        client.get_option_chain_data = Mock(return_value=None)
        client._get_oi_helper = Mock()

        with self.assertLogs(
            "robinhood.robinhood_api_logic", level="WARNING"
        ) as logs:
            result = client.no_db_option_greeks_batch_request([request])

        self.assertEqual({request: []}, result)
        self.assertIn(
            "No chains returned for all option request",
            logs.output[0],
        )
        client._get_oi_helper.assert_not_called()

    def test_no_db_option_greeks_batch_request_uses_single_chain_object(self):
        client = build_robinhood_client()
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
        client.get_option_chain_data = Mock(return_value=chain)
        client._get_oi_helper = Mock(return_value=[option_instrument])
        client._resolve_option_greeks_from_ids = Mock(return_value=expected)

        result = client.no_db_option_greeks_batch_request([request])

        self.assertEqual(expected, result)
        client._get_oi_helper.assert_called_once_with(
            [request],
            {"SPY": "chain-id"},
        )
        client._resolve_option_greeks_from_ids.assert_called_once_with(
            [request],
            {request: ["instrument-id"]},
        )

    def test_get_option_greek_data_returns_empty_without_ids(self):
        client = build_robinhood_client()

        with patch("builtins.print") as mock_print:
            result = client._get_option_greek_data([])

        self.assertEqual([], result)
        mock_print.assert_called_once_with("warning no option id supplied")
        client._http_client._get.assert_not_called()

    def test_get_option_greek_data_fetches_payloads_for_option_ids(self):
        client = build_robinhood_client()
        greek = build_option_greek_data(instrument_id="id-1")
        client._http_client._get.return_value = [asdict(greek)]

        result = client._get_option_greek_data(["id-1"])

        self.assertEqual([greek], result)
        client._http_client._get.assert_called_once_with(
            endpoint=API_OPTIONS_GREEKS_DATA,
            params={PARAM_OPTION_IDS: "id-1"},
        )

    def test_refresh_access_token_without_env_path_updates_session_header(self):
        http_client = Mock()
        http_client.session.headers = {"Authorization": "Bearer stale-token"}
        client = build_robinhood_client(http_client=http_client)
        client.env_path = None

        with (
            patch(
                "robinhood.robinhood_api_logic.auto_open_browser"
            ) as mock_open,
            patch(
                "robinhood.robinhood_api_logic.get_token",
                return_value=("fresh-token", "ACC123"),
            ) as mock_get_token,
            self.assertLogs(
                "robinhood.robinhood_api_logic", level="WARNING"
            ) as logs,
        ):
            client.refresh_access_token(object())

        mock_open.assert_called_once()
        mock_get_token.assert_called_once_with("", write_env=False)
        self.assertEqual(
            "Bearer fresh-token",
            http_client.session.headers["Authorization"],
        )
        self.assertIn(
            "No env path was provided. Not writing to env",
            logs.output[0],
        )

    def test_execute_custom_sql_returns_none_without_cache(self):
        client = build_robinhood_client()

        with self.assertLogs(
            "robinhood.robinhood_api_logic", level="WARNING"
        ) as logs:
            result = client.execute_custom_sql("SELECT 1", {})

        self.assertIsNone(result)
        self.assertIn("No db enabled! Nothing to execute!", logs.output[0])

    def test_execute_custom_sql_delegates_to_cache(self):
        db_cache = Mock()
        db_cache.execute_query_with_args.return_value = [("SPY",)]
        client = build_robinhood_client(db_cache=db_cache)

        result = client.execute_custom_sql(
            "SELECT symbol FROM main_stock_info WHERE symbol = :symbol",
            {"symbol": "SPY"},
        )

        self.assertEqual([("SPY",)], result)
        db_cache.execute_query_with_args.assert_called_once_with(
            "SELECT symbol FROM main_stock_info WHERE symbol = :symbol",
            {"symbol": "SPY"},
        )

    def test_get_account_positions_returns_none_when_user_id_is_not_loaded(
        self,
    ):
        client = build_robinhood_client()
        client.user_id = 403

        result = client.get_account_stock_positions()

        self.assertIsNone(result)
        client._http_client._get.assert_not_called()

    def test_get_account_positions_queries_both_position_endpoints(self):
        client = build_robinhood_client()
        client.user_id = "ACC123"
        client._http_client._get.side_effect = [
            [{"stock": "position"}],
            [{"option": "position"}],
        ]

        with patch("builtins.print") as mock_print:
            result = client.get_account_stock_positions()

        params = {PARAM_NON_ZERO: "true", PARAM_ACCOUNT_NUMBER: "ACC123"}
        self.assertIsNone(result)
        self.assertEqual(
            [
                call(API_POSITIONS_NON_OPTIONS, params),
                call(API_POSITIONS_OPTIONS, params),
            ],
            client._http_client._get.call_args_list,
        )
        mock_print.assert_called_once_with([{"option": "position"}])


if __name__ == "__main__":
    unittest.main()
