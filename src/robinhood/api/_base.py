from __future__ import annotations

from pathlib import Path
from typing import overload

from robinhood import OptionChain, OptionInstrument, OptionRequest

from .._http_client import RobinhoodHTTPClient
from ..db_logic.option_cache import OptionCache


class RobinhoodBase:
    _http_client: RobinhoodHTTPClient
    _db_cache: OptionCache | None
    user_id: str | int
    env_path: Path | None

    @overload
    def get_option_chain_data(self, symbol: str) -> OptionChain | None: ...

    @overload
    def get_option_chain_data(
        self, symbol: list[str]
    ) -> list[OptionChain] | None: ...

    def get_option_chain_data(
        self, symbol: str | list[str]
    ) -> list[OptionChain] | OptionChain | None: ...

    def _get_oi_helper(
        self,
        option_requests: list[OptionRequest],
        chain_symbol_pair: dict[str, str],
    ) -> list[OptionInstrument]:
        raise NotImplementedError
