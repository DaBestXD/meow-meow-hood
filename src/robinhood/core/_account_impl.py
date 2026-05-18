"""Account, position, order history, and watchlist implementation methods."""

from __future__ import annotations

import logging

from robinhood.api_dataclasses import (
    AchTransfer,
    CurrencyPair,
    Future,
    Instrument,
    OptionOrderHistory,
    OptionPosition,
    OptionStrategy,
    RobinhoodAccount,
    StockOrder,
    StockPosition,
    WatchList,
)
from robinhood.constants import (
    API_ACCOUNT,
    API_NON_OPTION_ORDER_HISTORY,
    API_OPTION_ORDER_HISTORY,
    API_POSITIONS_NON_OPTIONS,
    API_POSITIONS_OPTIONS,
    API_UNIFIED_TRANSFERS,
    API_WATCHLIST_DEFAULT,
    API_WATCHLIST_ITEMS,
    BASE_API_BONFIRE_LINK,
    PARAM_ACCOUNT_NUMBER,
    PARAM_LIST_ID,
    PARAM_LOAD_ALL_ATTRIBUTES,
    PARAM_NON_ZERO,
)
from robinhood.core._typing_base import TypingBase

logger = logging.getLogger(__name__)


class AccountImpl(TypingBase):
    """Mixin containing account and watchlist request implementations."""

    async def _get_account_stock_positions(
        self,
    ) -> list[StockPosition] | None:
        """
        Returns list of StockPosition classes
        """
        if isinstance(self.user_id, int):
            return None
        params = {PARAM_NON_ZERO: "true", PARAM_ACCOUNT_NUMBER: self.user_id}
        res_json = await self._async_http_client._get(
            endpoint=API_POSITIONS_NON_OPTIONS,
            params=params,
        )
        if not res_json:
            logger.warning("Unable to get account stock positions")
            return None
        stock_positions = [StockPosition.from_json(s) for s in res_json if s]
        return stock_positions

    async def _get_account_option_positions(
        self,
    ) -> list[OptionPosition] | None:
        """Returns list of OptionPosition classes"""
        params = {PARAM_NON_ZERO: "true", PARAM_ACCOUNT_NUMBER: self.user_id}
        res_json = await self._async_http_client._get(
            endpoint=API_POSITIONS_OPTIONS,
            params=params,
        )
        if not res_json:
            logger.warning("Unable to get account option positions")
            return None
        option_positions = [
            OptionPosition.from_json(op) for op in res_json if op
        ]
        return option_positions

    async def _get_option_order_history(
        self,
    ) -> list[OptionOrderHistory] | None:
        if isinstance(self.user_id, int):
            return []
        params = {PARAM_ACCOUNT_NUMBER: self.user_id}
        res_json = await self._async_http_client._get(
            endpoint=API_OPTION_ORDER_HISTORY,
            params=params,
        )
        if not res_json:
            logger.warning("Unable to get option order history")
            return None
        option_orders = [OptionOrderHistory.from_json(o) for o in res_json if o]
        return option_orders

    async def _get_stock_order_history(self) -> list[StockOrder] | None:
        """Returns a list of StockOrder classes"""
        if isinstance(self.user_id, int):
            logger.warning("user_id not valid")
            return None
        params = {PARAM_ACCOUNT_NUMBER: self.user_id}
        res_json = await self._async_http_client._get(
            endpoint=API_NON_OPTION_ORDER_HISTORY,
            params=params,
        )
        if not res_json:
            logger.warning("Unable to find non-option order history")
            return None
        stock_orders = [StockOrder.from_json(s) for s in res_json if s]
        return stock_orders

    async def _get_watchlists(self) -> list[WatchList] | None:
        """
        Returns list of Watchlist classes
        To each item from the watchlist use `watchlist.items`
        This function will always return your options watchlist
        Possible items:
        -`OptionStrategy`
        -`Instrument`
        -`Future`
        -`CurrencyPair`
        """
        res_json = await self._async_http_client._get(API_WATCHLIST_DEFAULT)
        if not res_json:
            return None
        watchlists: list[WatchList] = []
        for s in res_json:
            items = await self._watchlist_helper(s["id"])
            watchlists.append(
                WatchList(
                    name=s["display_name"],
                    id=s["id"],
                    items=items,
                )
            )
        if not watchlists:
            logger.warning("No watchlists were found.")
            return None
        return watchlists

    async def _watchlist_helper(
        self, id: str
    ) -> list[OptionStrategy | Instrument | Future | CurrencyPair]:
        """
        Helper function to normalize json into watchlist item classes
        """
        params = {
            PARAM_LIST_ID: id,
            # This is needed for the options watchlist
            # Won't work otherwise
            PARAM_LOAD_ALL_ATTRIBUTES: "False",
        }
        res_json = await self._async_http_client._get(
            endpoint=API_WATCHLIST_ITEMS,
            params=params,
        )
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

    async def _get_ach_transfers(
        self, raw_json_response: bool = False
    ) -> list[AchTransfer] | list[dict] | None:
        """
        Returns all ach transfers
        Use `raw_json_response = True` for raw json response
        """
        res_json = await self._async_http_client._get(
            API_UNIFIED_TRANSFERS, BASE_API_BONFIRE_LINK
        )
        if raw_json_response:
            return res_json
        return [AchTransfer.from_json(r) for r in res_json if r]

    async def _get_accounts(
        self, raw_json_response: bool = False
    ) -> list[RobinhoodAccount] | list[dict] | None:
        """
        Returns all robinhood accounts
        Use `raw_json_response = True` for raw json response
        """
        res_json = await self._async_http_client._get(API_ACCOUNT)
        if raw_json_response:
            return res_json
        return [RobinhoodAccount.from_json(r) for r in res_json if r]

    def _change_account(self, acc_id: str) -> None:
        """
        Changing account id will affect where stock/option orders
        are placed
        Sync function
        """
        self.user_id = acc_id
        return None
