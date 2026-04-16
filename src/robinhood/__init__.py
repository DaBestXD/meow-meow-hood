#  __    __     ______     ______     __     __
# /\ "-./  \   /\  ___\   /\  __ \   /\ \  _ \ \
# \ \ \-./\ \  \ \  __\   \ \ \/\ \  \ \ \/ ".\ \
#  \ \_\ \ \_\  \ \_____\  \ \_____\  \ \__/".~\_\
#   \/_/  \/_/   \/_____/   \/_____/   \/_/   \/_/
#  __    __     ______     ______     __     __
# /\ "-./  \   /\  ___\   /\  __ \   /\ \  _ \ \
# \ \ \-./\ \  \ \  __\   \ \ \/\ \  \ \ \/ ".\ \
#  \ \_\ \ \_\  \ \_____\  \ \_____\  \ \__/".~\_\
#   \/_/  \/_/   \/_____/   \/_____/   \/_/   \/_/
#  __  __     ______     ______     _____
# /\ \_\ \   /\  __ \   /\  __ \   /\  __-.
# \ \  __ \  \ \ \/\ \  \ \ \/\ \  \ \ \/\ \
#  \ \_\ \_\  \ \_____\  \ \_____\  \ \____-
#   \/_/\/_/   \/_____/   \/_____/   \/____/
# 🐈
import importlib.metadata as metadata

from .api_dataclasses import (
    BidAsk,
    CurrencyPair,
    FullQuote,
    Future,
    Instrument,
    OptionChain,
    OptionGreekData,
    OptionInstrument,
    OptionRequest,
    OptionStrategy,
    OrderBook,
    StockInfo,
    StockPosition,
    WatchList,
)
from .robinhood_api_logic import Robinhood

try:
    __version__ = metadata.version("meow-meow-hood")
except metadata.PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "BidAsk",
    "CurrencyPair",
    "FullQuote",
    "Future",
    "Instrument",
    "OptionChain",
    "OptionGreekData",
    "OptionInstrument",
    "OptionRequest",
    "OptionStrategy",
    "OrderBook",
    "Robinhood",
    "StockInfo",
    "StockPosition",
    "WatchList",
    "__version__",
]
