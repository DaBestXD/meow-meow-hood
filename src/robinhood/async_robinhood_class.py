import logging
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


class AsyncRobinhood(_CoreRobinhood):
    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Closes the robinhood client"""
        if self._db_cache:
            self._db_cache.close()
            self._db_cache = None
        await self._async_http_client.close()
        self.event_loop.close()
        logger.info("Robinhood Client Closed")

    @overload
    async def get_stock_info(self, symbols: str) -> StockInfo | None: ...
    @overload
    async def get_stock_info(
        self, symbols: list[str]
    ) -> list[StockInfo] | None: ...

    async def get_stock_info(
        self, symbols: str | list[str]
    ) -> StockInfo | list[StockInfo] | None:
        return await self._get_stock_info(symbols)

    @overload
    async def get_index_info(self, symbols: str) -> IndexInfo | None: ...
    @overload
    async def get_index_info(
        self, symbols: list[str]
    ) -> list[IndexInfo] | None: ...

    async def get_index_info(
        self, symbols: str | list[str]
    ) -> IndexInfo | list[IndexInfo] | None:
        return await self._get_index_info(symbols)

    @overload
    async def get_index_quotes(self, symbols: str) -> IndexQuote | None: ...
    @overload
    async def get_index_quotes(
        self, symbols: list[str]
    ) -> list[IndexQuote] | None: ...

    async def get_index_quotes(
        self, symbols: str | list[str]
    ) -> IndexQuote | list[IndexQuote] | None:
        return await self._get_index_quotes(symbols)

    @overload
    async def get_stock_quotes(self, symbols: str) -> FullQuote | None: ...
    @overload
    async def get_stock_quotes(
        self, symbols: list[str]
    ) -> list[FullQuote] | None: ...

    async def get_stock_quotes(
        self, symbols: str | list[str]
    ) -> FullQuote | list[FullQuote] | None:
        return await self._get_stock_quotes(symbols)

    async def get_orderbook(self, symbol: str) -> OrderBook | None:
        return await self._get_orderbook(symbol)

    async def get_future_info(self, symbol: str) -> FuturesProduct | None:
        return await self._get_future_info(symbol)

    @overload
    async def get_future_quote(self, ids: str) -> FuturesQuote | None: ...
    @overload
    async def get_future_quote(
        self, ids: list[str]
    ) -> list[FuturesQuote] | None: ...

    async def get_future_quote(
        self, ids: str | list[str]
    ) -> FuturesQuote | list[FuturesQuote] | None:
        """
        Accepts either exact symbols such as /ESM26
        or actual contract id
        Using exact symbols has some overhead costs,
        suggested to use contract ids.
        Use exact symbol name ex: /ESM26, forward slash is not optional
        """
        return await self._get_future_quote(ids)

    async def get_all_futures_products(self) -> list[FuturesProduct] | None:
        return await self._get_all_futures_products()

    async def get_active_contracts_for_id(
        self, id: str
    ) -> list[FuturesContract] | None:
        return await self._get_active_contracts_for_id(id)

    async def get_expiration_dates(self, symbol: str) -> list[str] | None:
        """
        Returns option_expiration dates for a given symbol as
        a list of strings, date format in yyyy-mm-dd
        """
        return await self._get_expiration_dates(symbol)

    async def get_strike_prices(
        self, *, symbol: str, exp_date: str
    ) -> dict[OptionRequest, list[float]]:
        """
        Returns a dict of OptionRequest and a list of strike prices
        """
        return await self._get_strike_prices(symbol=symbol, exp_date=exp_date)

    async def no_db_option_greeks_batch_request(
        self,
        option_requests: list[OptionRequest],
    ) -> dict[OptionRequest, list[OptionGreekData]]:
        """
        This doesn't check the db_cache for any hits
        and routes through the normal api path of:
        Option Chain Data --> Option Instrument Data --> Option Greek Data
        """
        return await self._no_db_option_greeks_batch_request(option_requests)

    @overload
    async def get_option_chain_data(
        self, symbol: str
    ) -> OptionChain | None: ...

    @overload
    async def get_option_chain_data(
        self, symbol: list[str]
    ) -> list[OptionChain] | None: ...

    async def get_option_chain_data(
        self, symbol: str | list[str]
    ) -> list[OptionChain] | OptionChain | None:
        """Return option chain metadata for one symbol or many symbols."""
        return await self._get_option_chain_data(symbol)

    async def get_option_greeks_batch_request(
        self,
        option_requests: OptionRequest | list[OptionRequest],
    ) -> dict[OptionRequest, list[OptionGreekData]]:
        """Return option greek data grouped by the input request objects."""
        return await self._get_option_greeks_batch_request(option_requests)

    async def place_limit_stock_order(
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
        return await self._place_limit_stock_order(
            symbol,
            side,
            price,
            quantity,
            market_hours,
            time_in_force,
            dollar_based_amount,
            currency_code,
        )

    async def place_market_stock_order(
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
        return await self._place_market_stock_order(
            symbol,
            side,
            market_hours,
            time_in_force,
            dollar_based_amount,
            quantity,
            currency_code,
        )

    async def place_option_order(
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
        return await self._place_option_order(
            option_legs,
            order_type,
            quantity,
            limit_price,
        )

    async def get_account_stock_positions(self) -> list[StockPosition] | None:
        """Returns list of StockPosition classes"""
        return await self._get_account_stock_positions()

    async def get_account_option_positions(self) -> list[OptionPosition] | None:
        """Returns list of OptionPosition classes"""
        return await self._get_account_option_positions()

    async def get_option_order_history(self) -> list[OptionOrderHistory] | None:
        """Returns option order history"""
        return await self._get_option_order_history()

    async def get_stock_order_history(self) -> list[StockOrder] | None:
        """Returns option stock order history"""
        return await self._get_stock_order_history()

    async def get_watchlists(self) -> list[WatchList] | None:
        """
        Return a list of watchlist items
        Return types include:
            `OptionStrategy`, `Instrument`, `Future`, `CurrencyPair`
        """
        return await self._get_watchlists()
