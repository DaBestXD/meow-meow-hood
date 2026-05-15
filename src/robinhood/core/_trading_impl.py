"""Trading implementation methods for stock and option orders."""

from __future__ import annotations

import logging
from collections import Counter
from typing import Literal
from uuid import uuid4

from robinhood.api_dataclasses import (
    OptionOrder,
    OptionOrderResponse,
    OptionRequest,
    StockOrderDollarAmount,
    StockOrderLimit,
    StockOrderResponse,
    StockOrderStockAmount,
    _OptionLeg,
)
from robinhood.constants import (
    API_OPTION_ORDER,
    API_STOCK_ORDER,
    BASE_API_LINK,
)
from robinhood.core._typing_base import TypingBase
from robinhood.errors import (
    AccountIdNotFoundError,
    InstruemtNotFoundError,
    MalformedOrderError,
)
from robinhood.option_matching import map_option_requests_to_ois

logger = logging.getLogger(__name__)


class TradingImpl(TypingBase):
    """Mixin containing stock and option order submission helpers."""

    async def _stock_order_factory(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        s_type: Literal["market", "limit"],
        time_in_force: Literal["gfd", "gtc"],
        market_hours: Literal[
            "regular_hours", "extended_hours"
        ] = "regular_hours",
        dollar_based_amount: float | None = None,
        quantity: float | None = None,
        currency_code: str = "USD",
        price: float = -1,
    ) -> StockOrderLimit | StockOrderStockAmount | StockOrderDollarAmount:
        self._malform_order_check(
            side, dollar_based_amount, quantity, s_type, price
        )
        res = await self._get_stock_info(symbol)
        if not res:
            raise InstruemtNotFoundError(f"{symbol} was not found")
        quote = await self._get_stock_quotes(symbol)
        if not quote:
            raise ValueError(f"unable to retrieve quote for {symbol}")
        _stock_dict = {
            "account": BASE_API_LINK + f"/accounts/{self.user_id}/",
            "instrument": res.url,
            "ref_id": str(uuid4()),
            "market_hours": market_hours,
            "symbol": symbol,
            "side": side,
            "type": s_type,
            "time_in_force": time_in_force,
            "order_form_version": 7,
            "ask_price": str(quote.ask_price),
            "bid_price": str(quote.bid_price),
            "bid_ask_timestamp": quote.updated_at,
            "position_effect": "open" if side == "buy" else "close",
            "trigger": "immediate",
        }
        if s_type == "limit":
            return StockOrderLimit(
                **_stock_dict,
                price=str(price),
                quantity=str(quantity),
            )
        if s_type == "market":
            if dollar_based_amount:
                return StockOrderDollarAmount(
                    **_stock_dict,
                    dollar_based_amount={
                        "amount": f"{dollar_based_amount:.2f}",
                        "currency_code": currency_code,
                    },
                )
            if quantity:
                return StockOrderStockAmount(
                    **_stock_dict,
                    quantity=str(quantity),
                )
        raise MalformedOrderError

    def _malform_order_check(
        self,
        side: str,
        dollar_based_amount: float | None,
        quantity: float | None,
        s_type: Literal["market", "limit"],
        price: float,
    ) -> None:
        if s_type == "limit" and price <= 0:
            raise MalformedOrderError("price must be greater than 0")
        if side != "buy" and side != "sell":
            raise MalformedOrderError(
                f"must be literal 'side' or 'buy': {side} was used instead"
            )
        if not dollar_based_amount and not quantity:
            raise MalformedOrderError(
                "must provide either a dollar amount of stock based amount"
            )
        if dollar_based_amount and quantity:
            raise MalformedOrderError("only one amount value accepted")
        if isinstance(self.user_id, int):
            raise AccountIdNotFoundError(
                "no valid account id was found at startup"
            )
        return None

    async def _place_limit_stock_order(
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
    ):
        """
        Defaults to regular_hours use extended_hours when needed.
        Defaults to 'gtc' swap to 'gfd' when needed.
        """
        self._malform_order_check(
            side,
            dollar_based_amount,
            quantity,
            "limit",
            price,
        )
        order = await self._stock_order_factory(
            symbol,
            side,
            "limit",
            time_in_force,
            market_hours,
            dollar_based_amount,
            quantity,
            currency_code,
            price,
        )
        res_json = await self._async_http_client._post(
            endpoint=API_STOCK_ORDER,
            json=order.__dict__,
        )
        return StockOrderResponse.from_json(res_json) if res_json else None

    async def _place_market_stock_order(
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
        Defaults to regular_hours use extended_hours when needed.
        Defaults to 'gtc' swap to 'gfd' when needed.
        Use either a dollar based amount or stock based amount
        If you use a stock_based_amount defaults to use the stock's
        ask price, use limit order for greater price control.
        """
        self._malform_order_check(
            side,
            dollar_based_amount,
            quantity,
            "market",
            -1,
        )
        order = await self._stock_order_factory(
            symbol,
            side,
            "market",
            time_in_force,
            market_hours,
            dollar_based_amount,
            quantity,
            currency_code,
        )
        try:
            if isinstance(order, StockOrderStockAmount):
                res_json = await self._async_http_client._post(
                    endpoint=API_STOCK_ORDER,
                    json=order.__dict__,
                )
                return (
                    StockOrderResponse.from_json(res_json) if res_json else None
                )
            if isinstance(order, StockOrderDollarAmount):
                res_json = await self._async_http_client._post(
                    endpoint=API_STOCK_ORDER,
                    json=order.__dict__,
                )
                return (
                    StockOrderResponse.from_json(res_json) if res_json else None
                )
        # TODO: change this to better error handling
        except Exception:
            raise MalformedOrderError

    async def _place_option_order(
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
        # ? I don't even remember why I used this 😹
        # oh... chain_id not symbol
        chain_symbol_pair = {o.symbol: o.symbol for o in option_legs}
        if len(chain_symbol_pair) > 1:
            raise MalformedOrderError("Order should only be for one symbol")
        chain = await self._get_option_chain_data(*chain_symbol_pair)
        if not chain:
            raise InstruemtNotFoundError(
                f"Unable to find chain id for {[*chain_symbol_pair][0]}"
            )
        # 😹 wtf is this piece of shit
        chain_symbol_pair[[*chain_symbol_pair][0]] = chain.id
        oi_list = await self._get_oi_helper(option_legs, chain_symbol_pair)
        ratio = dict(Counter(option_legs))
        if len(oi_list) != len(option_legs):
            raise ValueError(
                "Option legs should match length of OptionInstruments"
            )
        n = map_option_requests_to_ois(option_legs, oi_list)
        legs: list[_OptionLeg] = []
        for leg, oi in n.items():
            oi = oi[0]
            if not leg.position_effect or not leg.side:
                raise MalformedOrderError("position_effect/side cannot be None")
            legs.append(
                {
                    "option": oi.url,
                    "position_effect": leg.position_effect,
                    "ratio_quantity": ratio[leg],
                    "side": leg.side,
                }
            )
        opt_order = OptionOrder(
            account=BASE_API_LINK + f"accounts/{self.user_id}",
            legs=legs,
            ref_id=str(uuid4()),
            direction=order_type,
            price=limit_price,
            quantity=quantity,
        ).__dict__
        res_json = await self._async_http_client._post(
            endpoint=API_OPTION_ORDER,
            json=opt_order,
        )
        if not res_json:
            logger.warning("Failed to place order for %s", option_legs)
            return None
        return OptionOrderResponse.from_json(res_json[0])
