"""Protocol-like base used for typing shared implementation mixins."""

from typing import overload

from robinhood.api_dataclasses import (
    FullQuote,
    OptionChain,
    OptionInstrument,
    OptionRequest,
    StockInfo,
)
from robinhood.core._http_async_client import RobinhoodAsyncHTTPClient
from robinhood.db_logic.option_cache import OptionCache


class TypingBase:
    """Attributes and method shapes shared by implementation mixins."""

    def __init__(self) -> None:
        self.user_id: int | str
        self._async_http_client: RobinhoodAsyncHTTPClient
        self._db_cache: OptionCache | None

    @overload
    async def _get_option_chain_data(
        self, symbol: str
    ) -> OptionChain | None: ...

    @overload
    async def _get_option_chain_data(
        self, symbol: list[str]
    ) -> list[OptionChain] | None: ...

    async def _get_option_chain_data(
        self, symbol: str | list[str]
    ) -> list[OptionChain] | OptionChain | None: ...

    async def _get_oi_helper(
        self,
        option_requests: list[OptionRequest],
        chain_symbol_pair: dict[str, str],
    ) -> list[OptionInstrument]:
        raise NotImplementedError

    @overload
    async def _get_stock_info(self, symbols: str) -> StockInfo | None: ...

    @overload
    async def _get_stock_info(
        self, symbols: list[str]
    ) -> list[StockInfo] | None: ...

    async def _get_stock_info(
        self, symbols: str | list[str]
    ) -> StockInfo | list[StockInfo] | None: ...

    @overload
    async def _get_stock_quotes(self, symbol: str) -> FullQuote | None: ...

    @overload
    async def _get_stock_quotes(
        self, symbol: list[str]
    ) -> list[FullQuote] | None: ...

    async def _get_stock_quotes(
        self, symbol: list[str] | str
    ) -> FullQuote | list[FullQuote] | None: ...
