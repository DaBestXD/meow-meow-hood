from __future__ import annotations

import logging
from typing import overload

from ..api_dataclasses import (
    FullQuote,
    IndexInfo,
    IndexQuote,
    OrderBook,
    StockInfo,
)
from ..constants import (
    API_INDEX_QUOTE,
    API_INDEXES,
    API_INSTRUMENTS,
    API_ORDERBOOK,
    API_QUOTES,
    PARAM_SYMBOLS,
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
