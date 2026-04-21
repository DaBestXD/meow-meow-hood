from __future__ import annotations

import logging
from collections import Counter
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


class TradingMixin(RobinhoodBase):
    def open_option_position(
        self,
        option_legs: list[OptionRequest],
        order_type: Literal["debit", "credit"],
        quantity: int,
        limit_price: float,
    ) -> OptionOrderResponse | None:
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
                raise ValueError
            legs.append(
                {
                    "option": oi.url,
                    "position_effect": leg.position_effect,
                    "ratio_quantity": ratio[leg],
                    "side": leg.side,
                }
            )
        p = OptionOrder(
            account=BASE_API_LINK + f"accounts/{self.user_id}",
            legs=legs,
            ref_id=str(uuid4()),
            direction=order_type,
            price=limit_price,
            quantity=quantity,
        )
        res_json = self._http_client._post(
            endpoint=API_OPTION_ORDER, json=p.__dict__
        )
        if not res_json:
            logger.warning("Failed to place order for %s", option_legs)
            return None
        return OptionOrderResponse.from_json(res_json[0])
