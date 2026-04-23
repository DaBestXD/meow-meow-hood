from __future__ import annotations

import logging
from functools import cache
from typing import overload

from ..api_dataclasses import (
    FullQuote,
    FuturesContract,
    FuturesProduct,
    FuturesQuote,
    IndexInfo,
    IndexQuote,
    OrderBook,
    StockInfo,
)
from ..constants import (
    API_FUTURES_CONTRACTS,
    API_FUTURES_PRODUCTS,
    API_FUTURES_QUOTES,
    API_INDEX_QUOTE,
    API_INDEXES,
    API_INSTRUMENTS,
    API_ORDERBOOK,
    API_QUOTES,
    DATA,
    PARAM_ID,
    PARAM_PRODUCT_IDS,
    PARAM_SYMBOLS,
    STATUS,
    SUCCESS,
)
from ._base import RobinhoodBase

logger = logging.getLogger(__name__)


class MarketDataMixin(RobinhoodBase):
    @overload
    def get_stock_info(self, symbols: str) -> StockInfo | None: ...

    @overload
    def get_stock_info(self, symbols: list[str]) -> list[StockInfo] | None: ...

    def get_stock_info(
        self, symbols: str | list[str]
    ) -> StockInfo | list[StockInfo] | None:
        """Return stock metadata for one symbol or a list of symbols."""
        if isinstance(symbols, list):
            symbols = ",".join(symbols)
        res_json = self._http_client._get(
            API_INSTRUMENTS, {PARAM_SYMBOLS: symbols}
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

    # A note on the futures endpoint due to how Robinhood
    # handles params and filtering single symbol look-ups
    # should prob be used...
    # This endpoint is complete garbage nested return vals😾

    # no need to raise ValueError if incorrect type is used
    # some faith in the user is required...
    def get_future_info(self, symbol: str) -> FuturesProduct | None:
        """
        This is a convience function that calls `get_all_futures_products`
        and filters for the symbols.
        Symbols should be as follows:
        /ES not specific future contracts like /ESM26,
        """
        futures_prods = self.get_all_futures_products()
        if not futures_prods:
            # get_all_futures_products has a warning logger already
            # if no reponse back
            return None
        for i, f in enumerate(futures_prods):
            if f.displaySymbol.startswith(symbol):
                return futures_prods[i]
        logger.warning("%s was not found", symbol)
        return None

    @overload
    def get_future_quote(
        self,
        ids: str,
    ) -> FuturesQuote | None: ...

    @overload
    def get_future_quote(
        self,
        ids: list[str],
    ) -> list[FuturesQuote] | None: ...

    def get_future_quote(
        self,
        ids: str | list[str],
    ) -> list[FuturesQuote] | FuturesQuote | None:
        """
        Accepts either exact symbols such as /ESM26
        or actual contract id
        Using exact symbols has some overhead costs,
        suggested to use contract ids.
        Use exact symbol name ex: /ESM26, forward slash is not optional
        """
        if isinstance(ids, str):
            ids = [ids]
        if len(ids) > 20:
            raise ValueError("max amount of ids is 20")
        params = {PARAM_ID: ",".join(ids)}
        res_json = self._http_client._get(API_FUTURES_QUOTES, params)
        if not res_json or not (quote_list := res_json[0][DATA]):
            logger.warning("No valid quotes were returned for ids")
            return None
        quotes: list[FuturesQuote] = []
        for n in quote_list:
            if n[STATUS] != SUCCESS:
                continue
            quotes.append(FuturesQuote.from_json(n[DATA]))
        if not quotes:
            return None
        if isinstance(ids, str):
            return quotes[0]
        return quotes

    @cache
    def get_all_futures_products(
        self,
    ) -> list[FuturesProduct] | None:
        """
        Return a list of all Futures Products
        Runtime cache idk how this will impact memory usage but
        I can't be assed to create a new table and entries, and
        table prunning, etc...
        Def a todo and move away from @cache deco.
        """
        res_json = self._http_client._get(API_FUTURES_PRODUCTS)
        if not res_json:
            logger.warning("Unable to retrieve futures products list")
            return None
        futures = [FuturesProduct.from_json(f) for f in res_json if f]
        # In the event of a completly empty list return None
        # though this shouldn't really matter
        # and I should prob change this for all return values later
        # Just leaving this here as a placeholder/reminder
        return None if not futures else futures

    def get_active_contracts_for_id(
        self, id: str
    ) -> list[FuturesContract] | None:
        """
        Take a future product id and returns all active contracts
        Sorted by earliest expiration
        Contract id can be found from a FuturesProduct's id var
        """
        params = {PARAM_PRODUCT_IDS: id}
        res_json = self._http_client._get(API_FUTURES_CONTRACTS, params)
        if not res_json:
            logger.warning("No contracts returned for %s", id)
            return None
        future_contracts = [FuturesContract.from_json(f) for f in res_json if f]
        future_contracts.sort(key=lambda fut: fut.expirationMmy)
        return future_contracts
