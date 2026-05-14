import logging
from functools import cache
from types import TracebackType
from typing import Literal, Self, overload

from robinhood.api_dataclasses import (
    FullQuote,
    FuturesContract,
    FuturesProduct,
    FuturesQuote,
    IndexInfo,
    IndexQuote,
    OptionChain,
    OptionGreekData,
    OptionOrderHistory,
    OptionOrderResponse,
    OptionPosition,
    OptionRequest,
    OrderBook,
    StockInfo,
    StockOrder,
    StockOrderResponse,
    StockPosition,
    WatchList,
)
from robinhood.core._core_robinhood import _CoreRobinhood

logger = logging.getLogger(__name__)


class Robinhood(_CoreRobinhood):
    def __enter__(self) -> Self:
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
        self._run(self._async_http_client.close())
        self.event_loop.close()
        logger.info("Robinhood Client Closed")

    @overload
    def get_stock_info(self, symbols: str) -> StockInfo | None: ...
    @overload
    def get_stock_info(self, symbols: list[str]) -> list[StockInfo] | None: ...

    def get_stock_info(
        self, symbols: str | list[str]
    ) -> StockInfo | list[StockInfo] | None:
        return self._run(self._get_stock_info(symbols))

    @overload
    def get_index_info(self, symbols: str) -> IndexInfo | None: ...
    @overload
    def get_index_info(self, symbols: list[str]) -> list[IndexInfo] | None: ...

    def get_index_info(
        self, symbols: str | list[str]
    ) -> IndexInfo | list[IndexInfo] | None:
        return self._run(self._get_index_info(symbols))

    @overload
    def get_index_quotes(self, symbols: str) -> IndexQuote | None: ...
    @overload
    def get_index_quotes(
        self, symbols: list[str]
    ) -> list[IndexQuote] | None: ...

    def get_index_quotes(
        self, symbols: str | list[str]
    ) -> IndexQuote | list[IndexQuote] | None:
        return self._run(self._get_index_quotes(symbols))

    @overload
    def get_stock_quotes(self, symbol: str) -> FullQuote | None: ...
    @overload
    def get_stock_quotes(self, symbol: list[str]) -> list[FullQuote] | None: ...

    def get_stock_quotes(
        self, symbol: str | list[str]
    ) -> FullQuote | list[FullQuote] | None:
        return self._run(self._get_stock_quotes(symbol))

    def get_orderbook(self, symbol: str) -> OrderBook | None:
        return self._run(self._get_orderbook(symbol))

    def get_future_info(self, symbol: str) -> FuturesProduct | None:
        return self._run(self._get_future_info(symbol))

    @overload
    def get_future_quote(self, ids: str) -> FuturesQuote | None: ...
    @overload
    def get_future_quote(self, ids: list[str]) -> list[FuturesQuote] | None: ...

    def get_future_quote(
        self, ids: str | list[str]
    ) -> FuturesQuote | list[FuturesQuote] | None:
        """
        Accepts either exact symbols such as /ESM26
        or actual contract id
        Using exact symbols has some overhead costs,
        suggested to use contract ids.
        Use exact symbol name ex: /ESM26, forward slash is not optional
        """
        return self._run(self._get_future_quote(ids))

    @cache
    def get_all_futures_products(self) -> list[FuturesProduct] | None:
        return self._run(self._get_all_futures_products())

    def get_active_contracts_for_id(
        self, id: str
    ) -> list[FuturesContract] | None:
        return self._run(self._get_active_contracts_for_id(id))

    def get_expiration_dates(self, symbol: str) -> list[str] | None:
        """
        Returns option_expiration dates for a given symbol as
        a list of strings, date format in yyyy-mm-dd
        """
        return self._run(self._get_expiration_dates(symbol))

    def get_strike_prices(
        self, *, symbol: str, exp_date: str
    ) -> dict[OptionRequest, list[float]]:
        """
        Returns a dict of OptionRequest and a list of strike prices
        """
        return self._run(
            self._get_strike_prices(symbol=symbol, exp_date=exp_date)
        )

    def no_db_option_greeks_batch_request(
        self,
        option_requests: list[OptionRequest],
    ) -> dict[OptionRequest, list[OptionGreekData]]:
        """
        This doesn't check the db_cache for any hits
        and routes through the normal api path of:
        Option Chain Data --> Option Instrument Data --> Option Greek Data
        """
        return self._run(
            self._no_db_option_greeks_batch_request(option_requests)
        )

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
        return self._run(self._get_option_chain_data(symbol))

    def get_option_greeks_batch_request(
        self,
        option_requests: OptionRequest | list[OptionRequest],
    ) -> dict[OptionRequest, list[OptionGreekData]]:
        """Return option greek data grouped by the input request objects."""
        return self._run(self._get_option_greeks_batch_request(option_requests))

    def place_stock_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        order_type: Literal["market", "limit"],
        market_hours: Literal[
            "regular_hours", "extended_hours"
        ] = "regular_hours",
        time_in_force: Literal["gfd", "gtc"] = "gfd",
    ):
        """Not done yet"""
        raise NotImplementedError

    def place_option_order(
        self,
        option_legs: list[OptionRequest],
        order_type: Literal["debit", "credit"],
        quantity: int,
        limit_price: float,
    ) -> OptionOrderResponse | None:
        """
        This can be used to open/close positions
        Supports multi leg strategies and different leg ratios
        Example of ratio:
        `ratio = (Strike100 * 2) + (Strike50 * 4)`
        `open_option_position(ratio, 'credit', 1, 1.50)`
        """
        return self._run(
            self._place_option_order(
                option_legs,
                order_type,
                quantity,
                limit_price,
            )
        )

    def get_account_stock_positions(self) -> list[StockPosition] | None:
        """
        Returns list of StockPosition classes
        Set raw_data to `true` if you want the raw dictionary
        back with no processing.
        """
        return self._run(self._get_account_stock_positions())

    def get_account_option_positions(self) -> list[OptionPosition] | None:
        """Returns list of OptionPosition classes"""
        return self._run(self._get_account_option_positions())

    def get_option_order_history(self) -> list[OptionOrderHistory] | None:
        """Returns option order history"""
        return self._run(self._get_option_order_history())

    def get_stock_order_history(self) -> list[StockOrder] | None:
        """Returns option stock order history"""
        return self._run(self._get_stock_order_history())

    def get_watchlists(self) -> list[WatchList] | None:
        """
        Return a list of watchlist items
        Return types include:
            `OptionStrategy`, `Instrument`, `Future`, `CurrencyPair`
        """
        return self._run(self._get_watchlists())

    def place_limit_stock_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        price: float,
        quantity: float,
        market_hours: Literal[
            "regular_hours", "extended_hours"
        ] = "regular_hours",
        time_in_force: Literal["gfd", "gtc"] = "gtc",
        dollar_based_amount: float | None = None,
        currency_code: str = "USD",
    ) -> StockOrderResponse | None:
        return self._run(
            self._place_limit_stock_order(
                symbol,
                side,
                price,
                quantity,
                market_hours,
                time_in_force,
                dollar_based_amount,
                currency_code,
            )
        )

    def place_market_stock_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        market_hours: Literal[
            "regular_hours", "extended_hours"
        ] = "regular_hours",
        time_in_force: Literal["gfd", "gtc"] = "gtc",
        dollar_based_amount: float | None = None,
        quantity: float | None = None,
        currency_code: str = "USD",
    ) -> StockOrderResponse | None:
        return self._run(
            self._place_market_stock_order(
                symbol,
                side,
                market_hours,
                time_in_force,
                dollar_based_amount,
                quantity,
                currency_code,
            )
        )
