from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path
from types import TracebackType
from typing import Any

from dotenv import load_dotenv

from robinhood.db_logic.option_cache import OptionCache

from ._http_client import RobinhoodHTTPClient
from .api_dataclasses import (
    FullQuote,
    OptionChain,
    OptionGreekData,
    OptionInstrument,
    OptionRequest,
    StockInfo,
)
from .browser_token_parser import _get_acc_id, get_token
from .constants import (
    API_INSTRUMENTS,
    API_OPTION_CHAINS,
    API_OPTIONS_GREEKS_DATA,
    API_OPTIONS_INSTRUMENTS,
    API_QUOTES,
    DEFAULT_DB_PATH,
    MAX_LIMIT,
    PARAM_CHAIN_ID,
    PARAM_EXPIRATION_DATE,
    PARAM_ID,
    PARAM_LIMIT,
    PARAM_OPTION_IDS,
    PARAM_OPTION_STATE,
    PARAM_OPTION_STRIKE_PRICE,
    PARAM_OPTION_TYPE,
    PARAM_SYMBOLS,
    PARAM_TRADABLE_CHAIN_ID,
    PROJECT_DIR,
)
from .option_matching import map_option_requests_to_ois, match_req_to_oi


class Robinhood:
    def __init__(
        self,
        *,
        env_path: str | os.PathLike[str] = PROJECT_DIR,
        auto_login: bool = True,
        open_browser: bool = False,
        user_agent: str | None = None,
        cache: bool = True,
        db_path: str | os.PathLike[str] = DEFAULT_DB_PATH,
        prune_expired_options: bool = True,
        logging: bool = False,
    ) -> None:
        """
        Initialize a Robinhood client instance.

        Args:
            env_path: Project directory, as a string or path-like object, that
                contains the ``.env`` file used to load a cached
                ``BEARER_TOKEN``.
            auto_login: When ``True``, attempt to acquire a fresh bearer token
                from the local browser session if the token loaded from
                ``.env`` is missing or rejected.
            open_browser: When ``True``, allow ``get_token()`` to open the
                configured browser and Robinhood page if token recovery needs a
                browser refresh.
            user_agent: Optional ``User-Agent`` header override for the shared
                HTTP session.
            cache: When ``True``, enable the local SQLite instrument cache.
            db_path: Filesystem path, as a string or path-like object, for the
                SQLite cache database.
            prune_expired_options: When ``True``, remove expired option rows
                when the cache is opened.
            logging: Reserved flag for future request logging. It is currently
                a no-op.
        """
        env_path = Path(env_path)
        db_path = Path(db_path)
        load_dotenv(env_path / ".env")
        token: str | None = os.getenv("BEARER_TOKEN")
        self.user_id = -1
        if token:
            self.user_id = _get_acc_id(token)
        if auto_login and isinstance(self.user_id, int):
            token, self.user_id = get_token(open_browser=open_browser)
        assert token, "Bearer token cannot be none."
        if logging:
            pass
        self._http_client = RobinhoodHTTPClient(token, user_agent)
        self._db_cache: OptionCache | None = None
        if cache:
            self._db_cache = OptionCache(db_path, prune_expired_options)

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

    def get_expiration_dates(self, symbol: str) -> list[str]:
        """
        Returns option_expiration dates for a given symbol as
        a list of strings, date format in yyyy-mm-dd
        """
        if self._db_cache:
            dates = self._db_cache.fetch_expiration_dates_for_symbol(symbol)
            if dates:
                return dates
        res_json = self._http_client._get(API_OPTION_CHAINS + f"{symbol}/")
        if not res_json:
            print(f"No chain found for {symbol}")
            return []
        chains = [OptionChain.from_json(r) for r in res_json if r]
        if not chains:
            return []
        if self._db_cache:
            for c in chains:
                self._db_cache.insert_option_chain(c)
                self._db_cache.sync_option_chain(c.symbol)
        return chains[0].expiration_dates

    def get_strike_prices(
        self, *, symbol: str, exp_date: str
    ) -> dict[OptionRequest, list[float]]:
        """
        Usage get_strike_prices("SPY","2026-04-20")
        Returns a dict of OptionRequest and a list of strike prices
        """
        chain = self._db_cache.get_chain_id(symbol) if self._db_cache else None
        if not chain:
            chain = self.get_option_chain_data(symbol)
            if chain:
                chain = chain[0].id
        call_req = OptionRequest(
            symbol=symbol, option_type="call", exp_date=exp_date
        )
        put_req = OptionRequest(
            symbol=symbol, option_type="put", exp_date=exp_date
        )
        if not chain:
            return {call_req: [], put_req: []}
        params = {
            PARAM_CHAIN_ID: chain,
            PARAM_EXPIRATION_DATE: exp_date,
            PARAM_OPTION_STATE: "active",
        }
        options = self._http_client._get(API_OPTIONS_INSTRUMENTS, params)
        oi_list = [OptionInstrument.from_json(o) for o in options]
        if self._db_cache:
            self._db_cache.insert_option_instrument(oi_list)
            dates = {oi.expiration_date for oi in oi_list}
            or_list = [OptionRequest(symbol=symbol, exp_date=d) for d in dates]
            map_or_to_oi = map_option_requests_to_ois(or_list, oi_list)
            for k, v in map_or_to_oi.items():
                self._db_cache.sync_option_request_dispatch(k, v)
        call_strikes = []
        put_strikes = []
        for o in oi_list:
            if o.type == "call":
                call_strikes.append(o.strike_price)
            elif o.type == "put":
                put_strikes.append(o.strike_price)
        return {call_req: call_strikes, put_req: put_strikes}

    def get_stock_info(self, symbols: str | list[str]) -> list[StockInfo]:
        if isinstance(symbols, str):
            joined_symbols = symbols
        else:
            joined_symbols = ",".join(symbols)
        res_json = self._http_client._get(
            API_INSTRUMENTS, {PARAM_SYMBOLS: joined_symbols}
        )
        if not res_json:
            return []
        stock_info_list = [StockInfo.from_json(r) for r in res_json]
        if self._db_cache:
            for s in stock_info_list:
                self._db_cache.insert_stock_info(s)
        return stock_info_list

    def get_stock_quotes(self, symbol: list[str] | str) -> list[FullQuote]:
        """
        Returns a list of FullQuote dataclasses
        Usage: stock = get_stock_quotes("SPY")
        """
        symbol = [symbol] if isinstance(symbol, str) else symbol
        joined_symbol = ",".join(symbol)
        res_json = self._http_client._get(
            endpoint=API_QUOTES, params={PARAM_SYMBOLS: joined_symbol}
        )
        if not res_json:
            return []
        return [FullQuote.from_json(r) for r in res_json if r]

    def _resolve_option_greeks_from_ids(
        self,
        option_requests: list[OptionRequest],
        req_to_ids: dict[OptionRequest, list[str]],
        limit: int = MAX_LIMIT,
    ) -> dict[OptionRequest, list[OptionGreekData]]:
        seen_ids: set[str] = set()
        all_op_ids: list[str] = []
        for request in option_requests:
            for option_id in req_to_ids.get(request, []):
                if option_id in seen_ids:
                    continue
                seen_ids.add(option_id)
                all_op_ids.append(option_id)
        op_greek_list: list[OptionGreekData] = []
        for i in range(0, len(all_op_ids), 200):
            op_greek_list.extend(
                self._get_option_greek_data(all_op_ids[i : i + 200], limit)
            )
        greeks_by_id = {o.instrument_id: o for o in op_greek_list}
        return {
            request: [
                greeks_by_id[option_id]
                for option_id in req_to_ids.get(request, [])
                if option_id in greeks_by_id
            ]
            for request in option_requests
        }

    def live_option_request(
        self,
        option_requests: list[OptionRequest],
        limit: int = MAX_LIMIT,
    ) -> dict[OptionRequest, list[OptionGreekData]]:
        """
        This doesn't check the db_cache for any hits
        and routes through the normal api path of:
        Option Chain Data --> Option Instrument Data --> Option Greek Data
        """
        chains = self.get_option_chain_data([o.symbol for o in option_requests])
        if not chains:
            print("No chains for any option request")
            return {o: [] for o in option_requests}
        chain_symbol_pair = {c.symbol: c.id for c in chains}
        opt_instruments = self._get_oi_helper(
            option_requests, chain_symbol_pair, limit
        )
        req_to_ids: dict[OptionRequest, list[str]] = defaultdict(list)
        for oi in opt_instruments:
            for o in option_requests:
                if not match_req_to_oi(o, oi):
                    continue
                req_to_ids[o].append(oi.id)
        return self._resolve_option_greeks_from_ids(
            option_requests, req_to_ids, limit
        )

    def _get_oi_helper(
        self,
        option_requests: list[OptionRequest],
        chain_symbol_pair: dict[str, str],
        limit: int = MAX_LIMIT,
    ) -> list[OptionInstrument]:
        limit = MAX_LIMIT if limit > MAX_LIMIT else limit
        res_json: list[dict] = []
        for o in option_requests:
            params: dict[str, Any] = {
                PARAM_EXPIRATION_DATE: o.exp_date,
                PARAM_CHAIN_ID: chain_symbol_pair[o.symbol],
                PARAM_LIMIT: limit,
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

    def get_option_chain_data(
        self, symbol: str | list[str]
    ) -> list[OptionChain]:
        if isinstance(symbol, str):
            res_json = self._http_client._get(API_OPTION_CHAINS + f"{symbol}/")
        else:
            chain_rows = self._http_client._get(
                API_INSTRUMENTS, {PARAM_SYMBOLS: ",".join(symbol)}
            )
            if not chain_rows:
                return []
            chain_ids = [
                chain_id
                for c in chain_rows
                if (chain_id := c.get(PARAM_TRADABLE_CHAIN_ID))
            ]
            if not chain_ids:
                return []
            res_json = self._http_client._get(
                API_OPTION_CHAINS, {PARAM_ID: ",".join(chain_ids)}
            )
        if not res_json:
            return []
        return_val = [OptionChain.from_json(r) for r in res_json if r]
        if self._db_cache:
            for c in return_val:
                self._db_cache.insert_option_chain(c)
        return return_val

    def _get_option_greek_data(
        self, option_ids: list[str], limit: int = MAX_LIMIT
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
            params={PARAM_OPTION_IDS: joined_option_ids, PARAM_LIMIT: limit},
        )
        if not res_json:
            return []
        return_val = [OptionGreekData.from_json(o) for o in res_json if o]
        return return_val

    def get_option_greeks_batch_request(
        self,
        option_requests: OptionRequest | list[OptionRequest],
        limit: int = MAX_LIMIT,
    ) -> dict[OptionRequest, list[OptionGreekData]]:

        if isinstance(option_requests, OptionRequest):
            option_requests = [option_requests]
        if not self._db_cache:
            return self.live_option_request(option_requests, limit)

        cached_requests: list[OptionRequest] = []
        req_to_ids: dict[OptionRequest, list[str]] = {}
        missed_cache_hits: list[OptionRequest] = []
        for r in option_requests:
            if not self._db_cache.is_option_request_synced(r):
                missed_cache_hits.append(r)
                continue
            cached_requests.append(r)
            req_to_ids.update(self._db_cache.map_option_request_to_ids(r))
        return_val = self._resolve_option_greeks_from_ids(
            cached_requests, req_to_ids, limit
        )
        if missed_cache_hits:
            return_val.update(
                self.live_option_request(missed_cache_hits, limit)
            )
        return return_val
