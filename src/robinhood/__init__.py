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

from robinhood.dataclasses.api_dataclasses import (
    AchTransfer,
    BidAsk,
    CurrencyQuote,
    FuturesContract,
    FuturesProduct,
    FuturesQuote,
    IndexInfo,
    IndexQuote,
    InstrumentQuote,
    OptionChain,
    OptionGreekData,
    OptionInstrument,
    OptionOrderHistory,
    OptionOrderResponse,
    OptionPosition,
    OptionRequest,
    OrderBook,
    RobinhoodAccount,
    StockInfo,
    StockOrder,
    StockOrderResponse,
    StockPosition,
)
from robinhood.dataclasses.watchlist_classes import (
    CurrencyPair,
    Future,
    Index,
    Instrument,
    OptionStrategy,
    WatchList,
)

from .async_robinhood_class import AsyncRobinhood
from .sync_robinhood_class import Robinhood

try:
    __version__ = metadata.version("meow-meow-hood")
except metadata.PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "AchTransfer",
    "AsyncRobinhood",
    "BidAsk",
    "CurrencyPair",
    "CurrencyQuote",
    "InstrumentQuote",
    "Future",
    "FuturesContract",
    "FuturesProduct",
    "FuturesQuote",
    "Index",
    "Instrument",
    "IndexInfo",
    "IndexQuote",
    "OptionChain",
    "OptionGreekData",
    "OptionInstrument",
    "OptionOrderHistory",
    "OptionOrderResponse",
    "OptionPosition",
    "OptionRequest",
    "OptionStrategy",
    "OrderBook",
    "Robinhood",
    "RobinhoodAccount",
    "StockInfo",
    "StockOrder",
    "StockOrderResponse",
    "StockPosition",
    "WatchList",
    "__version__",
]
