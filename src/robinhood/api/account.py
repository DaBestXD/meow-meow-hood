from __future__ import annotations

import logging

from ..api_dataclasses import (
    CurrencyPair,
    Future,
    Instrument,
    OptionOrderHistory,
    OptionPosition,
    OptionStrategy,
    StockOrder,
    StockPosition,
    WatchList,
)
from ..constants import (
    API_NON_OPTION_ORDER_HISTORY,
    API_OPTION_ORDER_HISTORY,
    API_POSITIONS_NON_OPTIONS,
    API_POSITIONS_OPTIONS,
    API_WATCHLIST_DEFAULT,
    API_WATCHLIST_ITEMS,
    PARAM_ACCOUNT_NUMBER,
    PARAM_LIST_ID,
    PARAM_LOAD_ALL_ATTRIBUTES,
    PARAM_NON_ZERO,
)
from ._base import RobinhoodBase

logger = logging.getLogger(__name__)


class AccountMixin(RobinhoodBase):
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

    def get_option_order_history(self) -> list[OptionOrderHistory] | None:
        if isinstance(self.user_id, int):
            return []
        params = {PARAM_ACCOUNT_NUMBER: self.user_id}
        res_json = self._http_client._get(API_OPTION_ORDER_HISTORY, params)
        if not res_json:
            logger.warning("Unable to get option order history")
            return None
        option_orders = [OptionOrderHistory.from_json(o) for o in res_json if o]
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
