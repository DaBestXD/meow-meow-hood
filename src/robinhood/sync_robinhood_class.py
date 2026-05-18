"""Synchronous public Robinhood client."""

import logging
from functools import cache
from types import TracebackType
from typing import Literal, Self, overload

from robinhood.api_dataclasses import (
    AchTransfer,
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
    RobinhoodAccount,
    StockInfo,
    StockOrder,
    StockOrderResponse,
    StockPosition,
    WatchList,
)
from robinhood.core._core_robinhood import _CoreRobinhood

logger = logging.getLogger(__name__)


class Robinhood(_CoreRobinhood):
    """
    Synchronous Robinhood API client.
    Use this client when calling methods from regular synchronous Python code.
    It manages an internal event loop around the shared async implementation.
    Recommended to use the context manger to avoid resouce leaks.
    Remember to call `close()` if no context manger is used
    """

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
        """Return stock metadata for one symbol or a list of symbols."""
        return self._run(self._get_stock_info(symbols))

    @overload
    def get_index_info(self, symbols: str) -> IndexInfo | None: ...
    @overload
    def get_index_info(self, symbols: list[str]) -> list[IndexInfo] | None: ...

    def get_index_info(
        self, symbols: str | list[str]
    ) -> IndexInfo | list[IndexInfo] | None:
        """Return index metadata for one symbol or a list of symbols."""
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
        """Return index quotes for one symbol or a list of symbols."""
        return self._run(self._get_index_quotes(symbols))

    @overload
    def get_stock_quotes(self, symbol: str) -> FullQuote | None: ...
    @overload
    def get_stock_quotes(self, symbol: list[str]) -> list[FullQuote] | None: ...

    def get_stock_quotes(
        self, symbol: str | list[str]
    ) -> FullQuote | list[FullQuote] | None:
        """Return stock quote data for one symbol or a list of symbols."""
        return self._run(self._get_stock_quotes(symbol))

    def get_orderbook(self, symbol: str) -> OrderBook | None:
        """Return bid and ask order book rows for a stock symbol."""
        return self._run(self._get_orderbook(symbol))

    def get_future_info(self, symbol: str) -> FuturesProduct | None:
        """
        Return futures product metadata for a root symbol such as `/ES`.

        Use this for futures product symbols, not exact futures contract symbols
        such as `/ESM26`.
        """
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
        """Return all futures products, cached for the current process."""
        return self._run(self._get_all_futures_products())

    def get_active_contracts_for_id(
        self, id: str
    ) -> list[FuturesContract] | None:
        """
        Return active futures contracts for a futures product id.

        The result is sorted by earliest expiration. Product ids are available
        from `FuturesProduct.id`.
        """
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
        """
        Place a limit stock order.

        Provide `quantity` for a share-based order. `market_hours` defaults to
        regular hours and `time_in_force` defaults to `gtc`.
        """
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
        """
        Place a market stock order.

        Use either `dollar_based_amount` or `quantity`. `market_hours` defaults
        to regular hours and `time_in_force` defaults to `gtc`.
        """
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

    def cancel_option_order(self, id: str) -> None:
        """Use option order id from OptionOrderResponse to cancel"""
        return self._run(self._cancel_option_order(id))

    def cancel_stock_order(self, id: str) -> None:
        """Use stock order id from StockOrderResponse to cancel"""
        return self._run(self._cancel_stock_order(id))

    def get_ach_transfers(
        self, raw_json_response: bool = False
    ) -> list[AchTransfer] | list[dict] | None:
        """
        Returns all ach transfers
        Use `raw_json_response = True` for raw json response
        """
        return self._run(self._get_ach_transfers(raw_json_response))

    def get_accounts(
        self, raw_json_response: bool = False
    ) -> list[RobinhoodAccount] | list[dict] | None:
        """
        Returns all robinhood accounts
        Use `raw_json_response = True` for raw json response
        """
        return self._run(self._get_accounts(raw_json_response))

    def change_account(self, acc_id: str) -> None:
        """
        Changing account id will affect where stock/option orders
        are placed
        Sync function
        """
        return self._change_account(acc_id)
