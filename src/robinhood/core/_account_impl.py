"""Account, position, order history, and watchlist implementation methods."""

from __future__ import annotations

import logging
from typing import Any, Literal, overload
from uuid import UUID

import aiohttp

from robinhood.constants import (
    API_ACCOUNT,
    API_ACCOUNT_LIVE,
    API_NON_OPTION_ORDER_HISTORY,
    API_OPTION_ORDER_HISTORY,
    API_POSITIONS_NON_OPTIONS,
    API_POSITIONS_OPTIONS,
    API_UNIFIED_TRANSFERS,
    API_WATCHLIST,
    API_WATCHLIST_DEFAULT,
    API_WATCHLIST_ITEMS,
    BASE_API_BONFIRE_LINK,
    PARAM_ACCOUNT_NUMBER,
    PARAM_LIST_ID,
    PARAM_LOAD_ALL_ATTRIBUTES,
    PARAM_NON_ZERO,
)
from robinhood.core._typing_base import TypingBase
from robinhood.dataclasses.api_dataclasses import (
    AccountValue,
    AchTransfer,
    OptionOrderHistory,
    OptionPosition,
    RobinhoodAccount,
    StockOrder,
    StockPosition,
)
from robinhood.dataclasses.watchlist_classes import (
    CurrencyPair,
    Future,
    Index,
    Instrument,
    OptionStrategy,
    WatchList,
    WatchListItem,
)
from robinhood.robinhood_errors import (
    FailedToCreateWatchlistError,
    FailedToDeleteWatchlistError,
    FailedToModifyWatchlistError,
    InvalidTypeError,
)
from robinhood.utils._normalize_symbol import check_if_uuid4

logger = logging.getLogger(__name__)


class AccountImpl(TypingBase):
    """Mixin containing account and watchlist request implementations."""

    async def _get_account_stock_positions(
        self,
    ) -> list[StockPosition] | None:
        """
        [Public]
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
        """
        [Public]
        Returns list of OptionPosition classes
        """
        params = {PARAM_NON_ZERO: "true", PARAM_ACCOUNT_NUMBER: self.user_id}
        res_json = await self._async_http_client._get(
            endpoint=API_POSITIONS_OPTIONS,
            params=params,
        )
        if not res_json:
            logger.warning("Unable to get account option positions")
            return None
        option_positions = [OptionPosition.from_json(op) for op in res_json]
        return option_positions

    async def _get_option_order_history(
        self,
    ) -> list[OptionOrderHistory] | None:
        """
        [Public]
        Return option order history
        """
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
        """
        [Public]
        Returns a list of StockOrder classes
        """
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

    async def _get_watchlist_by_name(
        self,
        watchlist_name: str,
    ) -> WatchList | None:
        """
        [Public]
        Return the watchlist matching a display name.
        """
        res_json = await self._async_http_client._get(API_WATCHLIST_DEFAULT)
        if not res_json:
            logger.warning("No watchlists were found.")
            return None

        watchlist_name = watchlist_name.lower()
        for w in res_json:
            display_name = w["display_name"]
            if watchlist_name == display_name.lower():
                logger.info("Found watchlist %s", watchlist_name)
                return WatchList(
                    name=display_name,
                    id=w["id"],
                    items=await self._watchlist_helper(w["id"]),
                )
        logger.warning("Watchlist %s was not found.", watchlist_name)
        return None

    async def _create_watchlist(
        self,
        display_name: str,
        icon_emoji: str = "🐱",
        list_position: int = 0,
    ) -> WatchList:
        """
        [Public]
        Create a Robinhood watchlist
        Returns the newly created watchlist object
        """
        payload = {
            "display_name": display_name,
            "icon_emoji": icon_emoji,
            "list_position": list_position,
        }
        res_json = await self._async_http_client._post(
            endpoint=API_WATCHLIST,
            json=payload,
        )
        if not res_json:
            raise FailedToCreateWatchlistError(
                f"{display_name, icon_emoji} failed to create"
            )
        return WatchList(
            name=res_json.get("display_name", display_name),
            id=res_json["id"],
            items=[],
        )

    async def _delete_watchlist(
        self,
        watchlist_name: str,
    ) -> None:
        """
        [Public]
        Delete a Robinhood watchlist by display name or id.
        """
        watchlist = await self._get_watchlist_by_name(watchlist_name)
        if not watchlist:
            return None
        try:
            await self._async_http_client._delete(
                endpoint=f"{API_WATCHLIST}{watchlist.id}/"
            )
        except aiohttp.ClientResponseError:
            raise FailedToDeleteWatchlistError(
                f"Failed to delete {watchlist_name}"
            )
        logger.info(f"Deleted watchlist with {watchlist_name}")
        return None

    async def _add_item_to_watchlist(
        self,
        item: str,
        watchlist_name: str,
    ) -> dict | None:
        """
        [Public]
        Add an equity symbol to a Robinhood watchlist.
        """
        result = await self._watchlist_item_helper_function(
            item, watchlist_name, "create"
        )
        logger.info("Added %s to %s", item, watchlist_name)
        return result

    async def _remove_item_from_watchlist(
        self,
        item: str,
        watchlist_name: str,
    ) -> dict | None:
        """
        [Public]
        Remove an item from a Robinhood watchlist
        """
        result = await self._watchlist_item_helper_function(
            item, watchlist_name, "delete"
        )
        logger.info("Deleted %s from %s", item, watchlist_name)
        return result

    def _watchlist_option_helper_function(
        self,
        option_id: str,
        side: Literal["long", "short"],
        method: Literal["create", "delete"],
    ) -> dict[str, Any]:
        """
        [Private]
        Option order form
        """
        return {
            "legs": [
                {
                    "option_id": option_id,
                    "position_type": side,
                    "ratio_quantity": 1,
                }
            ],
            "object_type": "option_strategy",
            "operation": method,
        }

    async def _watchlist_item_helper_function(
        self,
        item: str,
        watchlist_name: str,
        method: Literal["create", "delete"],
        option_side: Literal["long", "short"] = "long",
    ):
        """
        [Private]
        If providing an option uuid, option positions defaults
        to long. Robinhood does not support adding multi-leg option
        strategies to the option watchlist, and only the option watchlist
        can add options.
        Note: for there is some name mismatching if you use BTC-USD with
        futures endpoint to specify crypto/currency_pair use a hyphen to
        designate so.
        """
        _item: str | UUID
        if check_if_uuid4(item):
            _item = UUID(item, version=4)
        else:
            _item = item
        result = await self._check_input_type(_item)
        if not result:
            raise InvalidTypeError(f"{item} not valid")
        item_type, item_id = result
        watchlist = await self._get_watchlist_by_name(watchlist_name)
        if not watchlist:
            return None

        # bruh
        object_type = "futures" if item_type == "future" else item_type
        if object_type == "option_strategy":
            if not check_if_uuid4(item_id):
                raise ValueError(
                    f"{item_id} must be a valid option strategy UUID"
                )
            payload = self._watchlist_option_helper_function(
                item_id,
                option_side,
                method,
            )
        else:
            payload = {
                "object_id": item_id,
                "object_type": object_type,
                "operation": method,
            }
        total_payload = {watchlist.id: [payload]}
        try:
            return await self._async_http_client._post(
                endpoint=API_WATCHLIST_ITEMS,
                json=total_payload,
            )
        except aiohttp.ClientResponseError:
            raise FailedToModifyWatchlistError(
                f"{item} cannot be add/deleted from {watchlist_name}"
            )

    async def _get_watchlists(self) -> list[WatchList] | None:
        """
        [Public]
        Returns list of Watchlist classes
        To each item from the watchlist use `watchlist.items`
        This function will always return your options watchlist
        (OptionStrategies can only appear in the options watchlist)

        Possible items:
        -`OptionStrategy`
        -`Instrument`
        -`Future`
        -`CurrencyPair`
        -`OptionStrategy`
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

    async def _watchlist_helper(self, id: str) -> list[WatchListItem]:
        """
        [Private]
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
        items: list[WatchListItem] = []
        for o in res_json:
            # no get, silent failure stinky
            item_type = o["object_type"]
            if item_type == "option_strategy":
                items.append(OptionStrategy.from_json(o))
            if item_type == "instrument":
                items.append(Instrument.from_json(o))
            if item_type == "currency_pair":
                items.append(CurrencyPair.from_json(o))
            if item_type in {"future", "futures"}:
                items.append(Future.from_json(o))
            if item_type == "index":
                items.append(Index.from_json(o))
        return items

    @overload
    async def _get_ach_transfers(
        self, raw_json_response: Literal[False]
    ) -> list[AchTransfer] | None: ...

    @overload
    async def _get_ach_transfers(
        self, raw_json_response: Literal[True]
    ) -> list[dict] | None: ...

    async def _get_ach_transfers(
        self, raw_json_response: bool = False
    ) -> list[AchTransfer] | list[dict] | None:
        """
        [Public]
        Returns all ach transfers
        Use `raw_json_response = True` for raw json response
        """
        res_json = await self._async_http_client._get(
            API_UNIFIED_TRANSFERS, BASE_API_BONFIRE_LINK
        )
        if raw_json_response:
            return res_json
        return [AchTransfer.from_json(r) for r in res_json if r]

    @overload
    async def _get_accounts(
        self, *, raw_json_response: Literal[False]
    ) -> list[RobinhoodAccount] | list[dict] | None: ...

    @overload
    async def _get_accounts(
        self, *, raw_json_response: Literal[True]
    ) -> list[RobinhoodAccount] | list[dict] | None: ...

    async def _get_accounts(
        self, *, raw_json_response: bool = False
    ) -> list[RobinhoodAccount] | list[dict] | None:
        """
        [Public]
        Returns all robinhood accounts
        Use `raw_json_response = True` for raw json response
        """
        res_json = await self._async_http_client._get(API_ACCOUNT)
        if raw_json_response:
            return res_json
        return [RobinhoodAccount.from_json(r) for r in res_json if r]

    def _change_account(self, acc_id: str) -> None:
        """
        [Public]
        Changing account id will affect where stock/option orders
        are placed
        Sync function
        """
        self.user_id = acc_id
        return None

    async def _get_account_value_impl(
        self, acc_id: str | None = None
    ) -> AccountValue | None:
        """
        [Public]
        Uses the classes' self.user_id if acc_id is not provided
        Returns an AccountValue dataclass
        """
        acc = self.user_id if not acc_id else acc_id
        res_json = await self._async_http_client._get(
            API_ACCOUNT_LIVE + f"{acc}/live", BASE_API_BONFIRE_LINK
        )
        return AccountValue.from_json(res_json[0])
