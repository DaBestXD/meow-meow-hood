import pytest

from robinhood.dataclasses.api_dataclasses import OptionRequest
from robinhood.utils.option_matching import (
    map_option_requests_to_ois,
    match_req_to_oi,
)
from tests.support import build_option_instrument


class TestOptionMatching:
    def test_match_req_to_oi_accepts_exact_and_broad_requests(self):
        option_instrument = build_option_instrument(
            chain_symbol="SPY",
            expiration_date="2026-04-17",
            type="call",
            strike_price=500.0,
        )

        assert match_req_to_oi(OptionRequest(symbol="SPY"), option_instrument)
        assert match_req_to_oi(
            OptionRequest(
                symbol="SPY",
                exp_date="2026-04-17",
                option_type="call",
                strike_price=500.0,
            ),
            option_instrument,
        )

    @pytest.mark.parametrize(
        "option_request",
        [
            OptionRequest(symbol="QQQ"),
            OptionRequest(symbol="SPY", exp_date="2026-04-24"),
            OptionRequest(symbol="SPY", option_type="put"),
            OptionRequest(symbol="SPY", strike_price=400.0),
        ],
    )
    def test_match_req_to_oi_rejects_field_mismatches(
        self,
        option_request,
    ):
        option_instrument = build_option_instrument(
            chain_symbol="SPY",
            expiration_date="2026-04-17",
            type="call",
            strike_price=500.0,
        )

        assert not match_req_to_oi(option_request, option_instrument)

    def test_map_option_requests_to_ois_groups_matching_instruments(self):
        req_all = OptionRequest(symbol="SPY")
        req_call = OptionRequest(
            symbol="SPY", exp_date="2026-04-17", option_type="call"
        )
        req_put = OptionRequest(
            symbol="SPY", exp_date="2026-04-17", option_type="put"
        )
        instruments = [
            build_option_instrument(
                id="call-1",
                chain_symbol="SPY",
                expiration_date="2026-04-17",
                type="call",
            ),
            build_option_instrument(
                id="put-1",
                chain_symbol="SPY",
                expiration_date="2026-04-17",
                type="put",
            ),
            build_option_instrument(
                id="qqq-call",
                chain_symbol="QQQ",
                expiration_date="2026-04-17",
                type="call",
            ),
        ]

        result = map_option_requests_to_ois(
            [req_all, req_call, req_put], instruments
        )

        assert ["call-1", "put-1"] == [option.id for option in result[req_all]]
        assert ["call-1"] == [option.id for option in result[req_call]]
        assert ["put-1"] == [option.id for option in result[req_put]]
