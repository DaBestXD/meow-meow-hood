import importlib
import importlib.metadata as metadata
import unittest
from unittest.mock import patch

import robinhood


class TestPackageInit(unittest.TestCase):
    def test_package_exports_public_client_types(self):
        expected_exports = {
            "BidAsk",
            "CurrencyPair",
            "FullQuote",
            "Future",
            "IndexInfo",
            "IndexQuote",
            "Instrument",
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
            "StockInfo",
            "StockOrder",
            "StockPosition",
            "WatchList",
            "__version__",
        }

        self.assertTrue(expected_exports.issubset(set(robinhood.__all__)))
        for export_name in expected_exports:
            self.assertTrue(hasattr(robinhood, export_name), export_name)

    def test_package_version_comes_from_distribution_metadata(self):
        with patch("importlib.metadata.version", return_value="9.9.9"):
            importlib.reload(robinhood)
            self.assertEqual("9.9.9", robinhood.__version__)

        importlib.reload(robinhood)

    def test_package_version_falls_back_when_distribution_is_missing(self):
        with patch(
            "importlib.metadata.version",
            side_effect=metadata.PackageNotFoundError,
        ):
            importlib.reload(robinhood)
            self.assertEqual("0.0.0", robinhood.__version__)

        importlib.reload(robinhood)


if __name__ == "__main__":
    unittest.main()
