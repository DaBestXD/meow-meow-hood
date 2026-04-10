from __future__ import annotations

from .api_dataclasses import OptionInstrument, OptionRequest


def match_req_to_oi(
    option_request: OptionRequest, option_instrument: OptionInstrument
) -> bool:
    if (
        option_request.strike_price
        and option_request.strike_price != option_instrument.strike_price
    ):
        return False
    if (
        option_request.exp_date
        and option_request.exp_date != option_instrument.expiration_date
    ):
        return False
    if (
        option_request.option_type
        and option_request.option_type != option_instrument.type
    ):
        return False
    if option_request.symbol != option_instrument.chain_symbol:
        return False
    return True


def map_option_requests_to_ois(
    option_requests: list[OptionRequest],
    option_instruments: list[OptionInstrument],
) -> dict[OptionRequest, list[OptionInstrument]]:
    return {
        option_request: [
            option_instrument
            for option_instrument in option_instruments
            if match_req_to_oi(option_request, option_instrument)
        ]
        for option_request in option_requests
    }
