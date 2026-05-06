from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from ..api_dataclasses import (
    OptionOrder,
    OptionOrderResponse,
    OptionRequest,
    _OptionLeg,
)
from ..constants import (
    API_OPTION_ORDER,
    BASE_API_LINK,
)
from ..option_matching import map_option_requests_to_ois
from ._base import RobinhoodBase

logger = logging.getLogger(__name__)


@dataclass
class StockOrder:
    account: str
    instrument: str
    market_hours: str
    position_effect: str
    ref_id: str
    side: Literal["buy", "sell"]
    time_in_force: Literal["gfd", "gtc"]
    type: Literal["market", "limit"]
    trigger: Literal["immediate"] = "immediate"
    order_form_version: int = 7

    data = {
        "account": "https://api.robinhood.com/accounts/447853730/",
        "instrument": "https://api.robinhood.com/instruments/8f92e76f-1e0e-4478-8580-16a6ffcfaef5/",
        "market_hours": "regular_hours",
        "order_form_version": 7,
        "position_effect": "open",
        "ref_id": str(uuid4()),
        "side": "buy",
        "symbol": "SPY",
        "time_in_force": "gfd",
        "trigger": "immediate",
        "type": "market",
        "dollar_based_amount": {"amount": "1.00", "currency_code": "USD"},
    }


class TradingMixin(RobinhoodBase):
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
        stock_info = self.get_stock_info(symbol)
        if not stock_info:
            return None
        # Todo find differences in limit vs market order for stock purchasing
        # StockOrder(
        #     account=BASE_API_LINK + f"accounts/{self.user_id}",
        #     instrument=stock_info.url,
        #     market_hours=market_hours,
        #     time_in_force=time_in_force,
        #     ref_id=str(uuid4()),
        #     side=side,
        # )

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
        # ? I don't even remember why I used this 😹
        # oh... chain_id not symbol
        chain_symbol_pair = {o.symbol: o.symbol for o in option_legs}
        if len(chain_symbol_pair) > 1:
            raise ValueError("Order should only be for one symbol")
        chain = self.get_option_chain_data(*chain_symbol_pair)
        if not chain:
            raise ValueError(
                f"Unable to find chain id for {[*chain_symbol_pair][0]}"
            )
        # 😹 wtf is this piece of shit
        chain_symbol_pair[[*chain_symbol_pair][0]] = chain.id
        oi_list = self._get_oi_helper(option_legs, chain_symbol_pair)
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
                raise ValueError("position_effect/side cannot be None")
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
        res_json = self._http_client._post(
            endpoint=API_OPTION_ORDER,
            json=opt_order,
        )
        if not res_json:
            logger.warning("Failed to place order for %s", option_legs)
            return None
        return OptionOrderResponse.from_json(res_json[0])
