import importlib
import importlib.metadata as metadata
from unittest.mock import patch

import robinhood


class TestPackageInit:
    def test_package_exports_public_client_types(self):
        expected_exports = {
            "AccountIdNotFoundError",
            "AchTransfer",
            "AuthenticationError",
            "AsyncRobinhood",
            "BidAsk",
            "ConfigurationError",
            "CurrencyPair",
            "CurrencyQuote",
            "EndpointNotFoundError",
            "FailedToCreateWatchlistError",
            "FailedToDeleteWatchlistError",
            "FailedToModifyWatchlistError",
            "InstrumentQuote",
            "Future",
            "FuturesContract",
            "FuturesProduct",
            "FuturesQuote",
            "Index",
            "IndexInfo",
            "IndexQuote",
            "Instrument",
            "InstrumentNotFoundError",
            "InvalidTypeError",
            "MalformedOrderError",
            "NoFutureProductsReturnedError",
            "OptionChain",
            "OptionGreekData",
            "OptionInstrument",
            "OptionOrderHistory",
            "OptionOrderResponse",
            "OptionPosition",
            "OptionRequest",
            "OptionStrategy",
            "OrderFailedError",
            "OrderBook",
            "RateLimitError",
            "Robinhood",
            "RobinhoodAccount",
            "RobinhoodError",
            "StockInfo",
            "StockOrder",
            "StockOrderResponse",
            "StockPosition",
            "TokenExtractionError",
            "WatchList",
            "__version__",
        }

        assert expected_exports.issubset(set(robinhood.__all__))
        for export_name in expected_exports:
            assert hasattr(robinhood, export_name), export_name

    def test_package_version_comes_from_distribution_metadata(self):
        with patch("importlib.metadata.version", return_value="9.9.9"):
            importlib.reload(robinhood)
            assert "9.9.9" == robinhood.__version__

        importlib.reload(robinhood)

    def test_package_version_falls_back_when_distribution_is_missing(self):
        with patch(
            "importlib.metadata.version",
            side_effect=metadata.PackageNotFoundError,
        ):
            importlib.reload(robinhood)
            assert "0.0.0" == robinhood.__version__

        importlib.reload(robinhood)
