import importlib
import unittest
from unittest.mock import patch

import robinhood


class TestPackageInit(unittest.TestCase):
    def test_package_version_comes_from_distribution_metadata(self):
        with patch("importlib.metadata.version", return_value="9.9.9"):
            importlib.reload(robinhood)
            self.assertEqual("9.9.9", robinhood.__version__)

        importlib.reload(robinhood)


if __name__ == "__main__":
    unittest.main()
