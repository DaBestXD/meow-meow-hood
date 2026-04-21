from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, overload

from ..api_dataclasses import (
    OptionChain,
    OptionGreekData,
    OptionInstrument,
    OptionRequest,
)
from ..constants import (
    API_INSTRUMENTS,
    API_OPTION_CHAINS,
    API_OPTIONS_GREEKS_DATA,
    API_OPTIONS_INSTRUMENTS,
    PARAM_CHAIN_ID,
    PARAM_EXPIRATION_DATE,
    PARAM_ID,
    PARAM_OPTION_IDS,
    PARAM_OPTION_STATE,
    PARAM_OPTION_STRIKE_PRICE,
    PARAM_OPTION_TYPE,
    PARAM_SYMBOLS,
    PARAM_TRADABLE_CHAIN_ID,
)
from ..option_matching import map_option_requests_to_ois, match_req_to_oi
from ._base import RobinhoodBase

logger = logging.getLogger(__name__)


class OptionsMixin(RobinhoodBase):
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
        return_val: list[OptionInstrument] = [
            OptionInstrument.from_json(r) for r in res_json if r
        ]
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
