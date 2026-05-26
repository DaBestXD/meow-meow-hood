from typing import Any, Literal, TypeVar

from robinhood.dataclasses.api_dataclasses import (
    CurrencyQuote,
    FuturesQuote,
    IndexInfo,
    OptionGreekData,
    StockInfo,
)
from robinhood.dataclasses.watchlist_classes import (
    CurrencyPair,
    Future,
    Index,
    Instrument,
    OptionStrategy,
)

T = TypeVar("T")
StrWatchListItem = Literal[
    "instrument", "currency_pair", "option_strategy", "future", "index"
]

_WatchListTyping = (
    StockInfo | IndexInfo | FuturesQuote | CurrencyQuote | OptionGreekData
)
WatchListItem = Index | CurrencyPair | Instrument | Future | OptionStrategy

JsonPayload = dict[str, Any]
