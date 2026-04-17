from __future__ import annotations

#  __    __     ______     ______     __     __
# /\ "-./  \   /\  ___\   /\  __ \   /\ \  _ \ \
# \ \ \-./\ \  \ \  __\   \ \ \/\ \  \ \ \/ ".\ \
#  \ \_\ \ \_\  \ \_____\  \ \_____\  \ \__/".~\_\
#   \/_/  \/_/   \/_____/   \/_____/   \/_/   \/_/
#  __    __     ______     ______     __     __
# /\ "-./  \   /\  ___\   /\  __ \   /\ \  _ \ \
# \ \ \-./\ \  \ \  __\   \ \ \/\ \  \ \ \/ ".\ \
#  \ \_\ \ \_\  \ \_____\  \ \_____\  \ \__/".~\_\
#   \/_/  \/_/   \/_____/   \/_____/   \/_/   \/_/
#  __  __     ______     ______     _____
# /\ \_\ \   /\  __ \   /\  __ \   /\  __-.
# \ \  __ \  \ \ \/\ \  \ \ \/\ \  \ \ \/\ \
#  \ \_\ \_\  \ \_____\  \ \_____\  \ \____-
#   \/_/\/_/   \/_____/   \/_____/   \/____/
# 🐈
import logging
import os
from collections import defaultdict
from pathlib import Path
from types import TracebackType
from typing import Any, overload

from dotenv import load_dotenv

from robinhood import StockPosition
from robinhood.configure_logger import MISSING, configure_logger
from robinhood.db_logic.option_cache import OptionCache
from robinhood.set_up_script import set_up

from ._http_client import RobinhoodHTTPClient
from .api_dataclasses import (
    CurrencyPair,
    FullQuote,
    Future,
    IndexInfo,
    IndexQuote,
    Instrument,
    OptionChain,
    OptionGreekData,
    OptionInstrument,
    OptionOrder,
    OptionPosition,
    OptionRequest,
    OptionStrategy,
    OrderBook,
    StockInfo,
    StockOrder,
    WatchList,
)
from .browser_token_parser import (
    Browser,
    auto_open_browser,
    get_acc_id,
    get_token,
)
from .constants import (
    API_INDEX_QUOTE,
    API_INDEXES,
    API_INSTRUMENTS,
    API_NON_OPTION_ORDER_HISTORY,
    API_OPTION_CHAINS,
    API_OPTION_ORDER_HISTORY,
    API_OPTIONS_GREEKS_DATA,
    API_OPTIONS_INSTRUMENTS,
    API_ORDERBOOK,
    API_POSITIONS_NON_OPTIONS,
    API_POSITIONS_OPTIONS,
    API_QUOTES,
    API_WATCHLIST_DEFAULT,
    API_WATCHLIST_ITEMS,
    PARAM_ACCOUNT_NUMBER,
    PARAM_CHAIN_ID,
    PARAM_EXPIRATION_DATE,
    PARAM_ID,
    PARAM_LIST_ID,
    PARAM_LOAD_ALL_ATTRIBUTES,
    PARAM_NON_ZERO,
    PARAM_OPTION_IDS,
    PARAM_OPTION_STATE,
    PARAM_OPTION_STRIKE_PRICE,
    PARAM_OPTION_TYPE,
    PARAM_SYMBOLS,
    PARAM_TRADABLE_CHAIN_ID,
)
from .option_matching import map_option_requests_to_ois, match_req_to_oi

logger = logging.getLogger(__name__)


class Robinhood:
    """Client for Robinhood stock and option market data.

    The client manages bearer token discovery, a shared HTTP session, and an
    optional local SQLite cache for option chain and instrument metadata.
    """

    def __init__(
        self,
        *,
        config_path: str | os.PathLike[str] = Path.cwd(),
        extract_token: bool = True,
        write_env: bool = True,
        open_browser: bool = True,
        user_agent: str | None = None,
        enable_cache: bool = True,
        prune_expired_options: bool = True,
        logging_level: int | None = logging.INFO,
        log_handler: logging.Handler | None | object = MISSING,
        access_token: str | None = None,
    ) -> None:
        """
        Initialize a Robinhood client instance.

        Args:
            config_path: Base directory where ``.meow-meow-config`` is created
                or reused. The client stores its ``.env`` token cache and local
                SQLite database there.
            extract_token: When ``True``, attempt to acquire a fresh bearer
                token from the local browser session if the token loaded from
                ``.env`` is missing or rejected.
            write_env: When ``True`` writes env file to the config_path
            open_browser: When ``True``, allow the browser refresh helper to
                briefly open Robinhood if a stored token is rejected.
            user_agent: Optional ``User-Agent`` header override for the shared
                HTTP session.
            enable_cache: When ``True``, enable the local SQLite instrument
                cache for option chain and option instrument metadata.
            prune_expired_options: When ``True``, remove expired option rows
                when the cache is opened.
            logging_level: Logging level constant for the library logger,
                such as ``logging.INFO`` or ``logging.DEBUG``.
            log_handler: Handler configuration for the library logger.
                Pass no value to use the library's default handler.
                ``None`` to clear library handlers and let records propagate,
                or a ``logging.Handler`` instance to use a custom handler.
            access_token: Explicit bearer token override. When supplied with
                ``extract_token=False`` and ``enable_cache=False``, the client
                skips the config bootstrap path and uses this token directly.
        """
        configure_logger(logging_level, log_handler)
        self.user_id = -1
        if access_token and not extract_token and not enable_cache:
            token = access_token
            self._db_cache = None
            self.env_path = None
        else:
            config_dir = set_up(Path(config_path))
            self.env_path = config_dir / ".env"
            cache_path = config_dir / "meow-meow-hood.db"
            if enable_cache:
                self._db_cache = OptionCache(cache_path, prune_expired_options)
            else:
                self._db_cache = None
            load_dotenv(dotenv_path=self.env_path)
            token = access_token if access_token else os.getenv("BEARER_TOKEN")
            if token:
                self.user_id = get_acc_id(token)
            if extract_token and isinstance(self.user_id, int):
                token, self.user_id = get_token(
                    env_path=self.env_path,
                    open_browser=open_browser,
                    write_env=write_env,
                )
            assert token, "Bearer token cannot be none."
        self._http_client = RobinhoodHTTPClient(token, user_agent)
        logger.info("Robinhood Client Initialized")

    def __enter__(self) -> Robinhood:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Closes the robinhood client"""
        if self._db_cache:
            self._db_cache.close()
            self._db_cache = None
        self._http_client.close()
        logger.info("Robinhood Client Closed")

    def get_expiration_dates(self, symbol: str) -> list[str] | None:
        """
        Returns option_expiration dates for a given symbol as
        a list of strings, date format in yyyy-mm-dd
        """
        if self._db_cache and self._db_cache.is_option_chain_synced(symbol):
            dates = self._db_cache.fetch_expiration_dates_for_symbol(symbol)
            if dates:
                logger.debug(
                    "%s cache hit for %s",
                    self.get_expiration_dates.__name__,
                    symbol,
                )
                return dates
        res_json = self._http_client._get(API_OPTION_CHAINS + f"{symbol}/")
        if not res_json:
            logger.warning("No expiration dates found for %s", symbol)
            return None
        chains = [OptionChain.from_json(r) for r in res_json if r]
        if self._db_cache:
            for c in chains:
                self._db_cache.insert_option_chain(c)
                self._db_cache.sync_option_chain(c.symbol)
        return chains[0].expiration_dates if chains else []

    def get_strike_prices(
        self, *, symbol: str, exp_date: str
    ) -> dict[OptionRequest, list[float]]:
        """
        Returns a dict of OptionRequest and a list of strike prices
        """
        base_request = OptionRequest(symbol=symbol, exp_date=exp_date)
        call_request = OptionRequest(
            symbol=symbol, option_type="call", exp_date=exp_date
        )
        put_request = OptionRequest(
            symbol=symbol, option_type="put", exp_date=exp_date
        )
        if self._db_cache and self._db_cache.is_option_request_synced(
            base_request
        ):
            logger.debug(
                "%s cache hit for %s",
                self.get_strike_prices.__name__,
                symbol,
            )
            return {
                call_request: self._db_cache.fetch_strike_prices(call_request),
                put_request: self._db_cache.fetch_strike_prices(put_request),
            }
        chain = self._db_cache.get_chain_id(symbol) if self._db_cache else None
        if not chain:
            chain = self.get_option_chain_data(symbol)
            if chain:
                chain = chain.id
        if not chain:
            logger.warning(
                "No strike prices found for %s at %s",
                symbol,
                exp_date,
            )
            return {call_request: [], put_request: []}
        params = {
            PARAM_CHAIN_ID: chain,
            PARAM_EXPIRATION_DATE: exp_date,
            PARAM_OPTION_STATE: "active",
        }
        options = self._http_client._get(API_OPTIONS_INSTRUMENTS, params)
        oi_list = [OptionInstrument.from_json(o) for o in options if o]
        if self._db_cache:
            self._db_cache.insert_option_instrument(oi_list)
            dates = {oi.expiration_date for oi in oi_list}
            or_list = [OptionRequest(symbol=symbol, exp_date=d) for d in dates]
            logger.debug(
                "Syncing %d option instruments for %s at %s",
                len(oi_list),
                symbol,
                exp_date,
            )
            map_or_to_oi = map_option_requests_to_ois(or_list, oi_list)
            for k, v in map_or_to_oi.items():
                self._db_cache.sync_option_request_dispatch(k, v)
        call_strikes: list[float] = []
        put_strikes: list[float] = []
        for o in oi_list:
            if o.type == "call":
                call_strikes.append(o.strike_price)
            elif o.type == "put":
                put_strikes.append(o.strike_price)
        logger.info(
            "Call options for %s: %d",
            symbol,
            len(call_strikes),
        )
        logger.info(
            "Put options for %s: %d",
            symbol,
            len(put_strikes),
        )
        return {call_request: call_strikes, put_request: put_strikes}

    @overload
    def get_stock_info(self, symbols: str) -> StockInfo | None: ...

    @overload
    def get_stock_info(self, symbols: list[str]) -> list[StockInfo] | None: ...

    def get_stock_info(
        self, symbols: str | list[str]
    ) -> StockInfo | list[StockInfo] | None:
        """Return stock metadata for one symbol or a list of symbols."""
        if isinstance(symbols, str):
            joined_symbols = symbols
        else:
            joined_symbols = ",".join(symbols)
        res_json = self._http_client._get(
            API_INSTRUMENTS, {PARAM_SYMBOLS: joined_symbols}
        )
        if not res_json:
            return None
        stock_info_list = [StockInfo.from_json(r) for r in res_json if r]
        if self._db_cache:
            for s in stock_info_list:
                self._db_cache.insert_stock_info(s)
        return (
            stock_info_list if len(stock_info_list) > 1 else stock_info_list[0]
        )

    @overload
    def get_index_info(self, symbols: str) -> IndexInfo | None: ...

    @overload
    def get_index_info(self, symbols: list[str]) -> list[IndexInfo] | None: ...

    def get_index_info(
        self,
        symbols: str | list[str],
    ) -> list[IndexInfo] | IndexInfo | None:
        if isinstance(symbols, list):
            symbols = ",".join(symbols)
        params = {PARAM_SYMBOLS: symbols}
        res_json = self._http_client._get(API_INDEXES, params)
        if not res_json:
            return None
        indexes = [IndexInfo.from_json(i) for i in res_json if i]
        if not indexes:
            return None
        return indexes if len(indexes) > 1 else indexes[0]

    @overload
    def get_index_quotes(self, symbols: str) -> IndexQuote | None: ...

    @overload
    def get_index_quotes(
        self, symbols: list[str]
    ) -> list[IndexQuote] | None: ...

    def get_index_quotes(
        self, symbols: str | list[str]
    ) -> list[IndexQuote] | IndexQuote | None:
        if isinstance(symbols, list):
            symbols = ",".join(symbols)
        params = {PARAM_SYMBOLS: symbols}
        res_json = self._http_client._get(API_INDEX_QUOTE, params)
        if not res_json:
            return None
        index_quotes = [
            IndexQuote.from_json(i["data"]) for i in res_json[0]["data"] if i
        ]
        if not index_quotes:
            return None
        return index_quotes if len(index_quotes) > 1 else index_quotes[0]

    @overload
    def get_stock_quotes(self, symbol: str) -> FullQuote | None: ...

    @overload
    def get_stock_quotes(self, symbol: list[str]) -> list[FullQuote] | None: ...

    def get_stock_quotes(
        self, symbol: list[str] | str
    ) -> FullQuote | list[FullQuote] | None:
        """
        Returns a list of FullQuote dataclasses
        Usage: stock = get_stock_quotes("SPY")
        """
        symbol = [symbol] if isinstance(symbol, str) else symbol
        joined_symbol = ",".join(symbol)
        res_json = self._http_client._get(
            endpoint=API_QUOTES, params={PARAM_SYMBOLS: joined_symbol}
        )
        return_val = [FullQuote.from_json(r) for r in res_json if r]
        if not res_json:
            return None
        return return_val if len(return_val) > 1 else return_val[0]

    def _resolve_option_greeks_from_ids(
        self,
        option_requests: list[OptionRequest],
        requests_to_ids: dict[OptionRequest, list[str]],
    ) -> dict[OptionRequest, list[OptionGreekData]]:
        """
        Private helper function.
        Fetch greek data in batches and rebuild the request-to-data mapping.
        """
        seen_ids: set[str] = set()
        all_op_ids: list[str] = []
        for request in option_requests:
            for option_id in requests_to_ids.get(request, []):
                if option_id in seen_ids:
                    continue
                seen_ids.add(option_id)
                all_op_ids.append(option_id)
        op_greek_list: list[OptionGreekData] = []
        for i in range(0, len(all_op_ids), 200):
            op_greek_list.extend(
                self._get_option_greek_data(all_op_ids[i : i + 200])
            )
        greeks_by_id = {o.instrument_id: o for o in op_greek_list}
        return {
            request: [
                greeks_by_id[option_id]
                for option_id in requests_to_ids.get(request, [])
                if option_id in greeks_by_id
            ]
            for request in option_requests
        }

    def no_db_option_greeks_batch_request(
        self,
        option_requests: list[OptionRequest],
    ) -> dict[OptionRequest, list[OptionGreekData]]:
        """
        This doesn't check the db_cache for any hits
        and routes through the normal api path of:
        Option Chain Data --> Option Instrument Data --> Option Greek Data
        """
        if len(option_requests) == 1:
            chains = self.get_option_chain_data(option_requests[0].symbol)
        else:
            chains = self.get_option_chain_data(
                [o.symbol for o in option_requests]
            )
        if not chains:
            logger.warning("No chains returned for all option request")
            return {o: [] for o in option_requests}
        if isinstance(chains, OptionChain):
            chain_symbol_pair = {chains.symbol: chains.id}
        else:
            chain_symbol_pair = {c.symbol: c.id for c in chains}
        opt_instruments = self._get_oi_helper(
            option_requests, chain_symbol_pair
        )
        req_to_ids: dict[OptionRequest, list[str]] = defaultdict(list)
        for oi in opt_instruments:
            for o in option_requests:
                if not match_req_to_oi(o, oi):
                    continue
                req_to_ids[o].append(oi.id)
        return self._resolve_option_greeks_from_ids(option_requests, req_to_ids)

    def _get_oi_helper(
        self,
        option_requests: list[OptionRequest],
        chain_symbol_pair: dict[str, str],
    ) -> list[OptionInstrument]:
        """
        Private helper function.
        Fetch option instruments for the given requests and sync cache rows.
        """
        res_json: list[dict] = []
        for o in option_requests:
            params: dict[str, Any] = {
                PARAM_EXPIRATION_DATE: o.exp_date,
                PARAM_CHAIN_ID: chain_symbol_pair[o.symbol],
                PARAM_OPTION_STATE: "active",
            }
            if o.option_type:
                params[PARAM_OPTION_TYPE] = o.option_type
            if o.strike_price:
                params[PARAM_OPTION_STRIKE_PRICE] = o.strike_price
            res_json.extend(
                self._http_client._get(
                    endpoint=API_OPTIONS_INSTRUMENTS, params=params
                )
            )
        if not res_json:
            return []
        return_val = [OptionInstrument.from_json(r) for r in res_json if r]
        if self._db_cache:
            self._db_cache.insert_option_instrument(return_val)
            mapped_op_req_to_oi = map_option_requests_to_ois(
                option_requests, return_val
            )
            for k, v in mapped_op_req_to_oi.items():
                self._db_cache.sync_option_request_dispatch(k, v)
        return return_val

    @overload
    def get_option_chain_data(self, symbol: str) -> OptionChain | None: ...

    @overload
    def get_option_chain_data(
        self, symbol: list[str]
    ) -> list[OptionChain] | None: ...

    def get_option_chain_data(
        self, symbol: str | list[str]
    ) -> list[OptionChain] | OptionChain | None:
        """Return option chain metadata for one symbol or many symbols."""
        if isinstance(symbol, str):
            res_json = self._http_client._get(API_OPTION_CHAINS + f"{symbol}/")
        else:
            chain_rows = self._http_client._get(
                API_INSTRUMENTS, {PARAM_SYMBOLS: ",".join(symbol)}
            )
            if not chain_rows:
                return None
            chain_ids = [
                chain_id
                for c in chain_rows
                if (chain_id := c.get(PARAM_TRADABLE_CHAIN_ID))
            ]
            if not chain_ids:
                return None
            res_json = self._http_client._get(
                API_OPTION_CHAINS, {PARAM_ID: ",".join(chain_ids)}
            )
        if not res_json:
            return None
        return_val = [OptionChain.from_json(r) for r in res_json if r]
        if self._db_cache:
            for c in return_val:
                self._db_cache.insert_option_chain(c)
                self._db_cache.sync_option_chain(c.symbol)
        return return_val if len(return_val) > 1 else return_val[0]

    def _get_option_greek_data(
        self, option_ids: list[str]
    ) -> list[OptionGreekData]:
        """
        Takes the list of options ids and returns
        """
        joined_option_ids = ",".join(option_ids)
        if not joined_option_ids:
            print("warning no option id supplied")
            return []
        res_json = self._http_client._get(
            endpoint=API_OPTIONS_GREEKS_DATA,
            params={PARAM_OPTION_IDS: joined_option_ids},
        )
        if not res_json:
            logger.warning(
                "No greeks returned for %d option ids",
                len(option_ids),
            )
            return []
        return_val = [OptionGreekData.from_json(o) for o in res_json if o]
        return return_val

    def get_option_greeks_batch_request(
        self,
        option_requests: OptionRequest | list[OptionRequest],
    ) -> dict[OptionRequest, list[OptionGreekData]]:
        """Return option greek data grouped by the input request objects."""
        if isinstance(option_requests, OptionRequest):
            option_requests = [option_requests]
        if not self._db_cache:
            return self.no_db_option_greeks_batch_request(option_requests)

        cached_requests: list[OptionRequest] = []
        req_to_ids: dict[OptionRequest, list[str]] = {}
        missed_cache_hits: list[OptionRequest] = []
        for r in option_requests:
            if not self._db_cache.is_option_request_synced(r):
                missed_cache_hits.append(r)
                continue
            cached_requests.append(r)
            req_to_ids.update(self._db_cache.map_option_request_to_ids(r))
        if cached_requests:
            logger.debug(
                "%s cache hit for %s",
                self.get_option_greeks_batch_request.__name__,
                ", ".join(dict.fromkeys(r.symbol for r in cached_requests)),
            )
        return_val = self._resolve_option_greeks_from_ids(
            cached_requests, req_to_ids
        )
        if missed_cache_hits:
            return_val.update(
                self.no_db_option_greeks_batch_request(missed_cache_hits)
            )
        return return_val

    def refresh_access_token(self, browser: Browser) -> None:
        """
        This function should only need to be run once a week.
        In theory as long as you keep running this function it should
        refresh the access token. Opening the browser is necessary
        for refreshing the access token.
        pkill/taskKill is the easiest way to clean up the open browser
        though not ideal as it closes all the entire browser.
        """
        auto_open_browser(browser)
        if not self.env_path:
            logger.warning("No env path was provided. Not writing to env")
            token, _ = get_token("", write_env=False)
        else:
            token, _ = get_token(self.env_path)
        self._http_client.session.headers["Authorization"] = f"Bearer {token}"
        return None

    def execute_custom_sql(
        self, query: str, args: list[dict[str, Any] | dict[str, Any]]
    ) -> list[Any] | None:
        """
        Use if you need to execute a custom sql query
        Use a list of args if you need to use ``executemany()``
        """
        if not self._db_cache:
            logger.warning("No db enabled! Nothing to execute!")
            return None
        else:
            return self._db_cache.execute_query_with_args(query, args)

    def get_account_stock_positions(self) -> list[StockPosition] | None:
        """
        Returns list of StockPosition classes
        Set raw_data to `true` if you want the raw dictionary
        back with no processing.
        """
        if isinstance(self.user_id, int):
            return []
        params = {PARAM_NON_ZERO: "true", PARAM_ACCOUNT_NUMBER: self.user_id}
        res_json = self._http_client._get(API_POSITIONS_NON_OPTIONS, params)
        if not res_json:
            logger.warning("Unable to get account stock positions")
            return None
        stock_positions = [StockPosition.from_json(s) for s in res_json if s]
        return stock_positions

    def get_account_option_positions(self) -> list[OptionPosition] | None:
        """Returns list of OptionPosition classes"""
        params = {PARAM_NON_ZERO: "true", PARAM_ACCOUNT_NUMBER: self.user_id}
        res_json = self._http_client._get(API_POSITIONS_OPTIONS, params)
        if not res_json:
            logger.warning("Unable to get account option positions")
            return None
        option_positions = [
            OptionPosition.from_json(op) for op in res_json if op
        ]
        return option_positions

    def get_option_order_history(self) -> list[OptionOrder] | None:
        if isinstance(self.user_id, int):
            return []
        params = {PARAM_ACCOUNT_NUMBER: self.user_id}
        res_json = self._http_client._get(API_OPTION_ORDER_HISTORY, params)
        if not res_json:
            logger.warning("Unable to get option order history")
            return None
        option_orders = [OptionOrder.from_json(o) for o in res_json if o]
        return option_orders

    def get_stock_order_history(self) -> list[StockOrder] | None:
        if isinstance(self.user_id, int):
            logger.warning("user_id not valid")
            return None
        params = {PARAM_ACCOUNT_NUMBER: self.user_id}
        res_json = self._http_client._get(API_NON_OPTION_ORDER_HISTORY, params)
        if not res_json:
            logger.warning("Unable to find non-option order history")
            return None
        stock_orders = [StockOrder.from_json(s) for s in res_json if s]
        return stock_orders

    def get_orderbook(self, symbol: str) -> OrderBook | None:
        si = self.get_stock_info(symbol)
        if not si:
            logger.warning("%s returned none", symbol)
            return None
        res_json = self._http_client._get(API_ORDERBOOK + f"{si.id}/")
        if not res_json:
            logger.warning("%s returned none", symbol)
            return None
        return OrderBook.from_json(res_json[0])

    def get_watchlists(self) -> list[WatchList] | None:
        res_json = self._http_client._get(API_WATCHLIST_DEFAULT)
        if not res_json:
            return None
        watchlists: list[WatchList] = []
        for s in res_json:
            items = self._watchlist_helper(s["id"])
            watchlists.append(
                WatchList(name=s["display_name"], id=s["id"], items=items)
            )
        if not watchlists:
            logger.warning("No watchlists were found.")
            return None
        return watchlists

    def _watchlist_helper(
        self, id: str
    ) -> list[OptionStrategy | Instrument | Future | CurrencyPair]:
        params = {
            PARAM_LIST_ID: id,
            # This is needed for the options watchlist
            # Won't work otherwise
            PARAM_LOAD_ALL_ATTRIBUTES: "False",
        }
        res_json = self._http_client._get(API_WATCHLIST_ITEMS, params)
        if not res_json:
            return []
        items: list[OptionStrategy | Instrument | Future | CurrencyPair] = []
        for o in res_json:
            # no get, silent failure stinky
            item_type = o["object_type"]
            if item_type == "option_strategy":
                items.append(OptionStrategy.from_json(o))
            if item_type == "instrument":
                items.append(Instrument.from_json(o))
            if item_type == "currency_pair":
                items.append(CurrencyPair.from_json(o))
            if item_type == "future":
                items.append(Future.from_json(o))
        return items
