import unittest

import experimental


class TestExperimentalPackage(unittest.TestCase):
    def test_import_exposes_screener_client(self):
        self.assertTrue(hasattr(experimental, "BonfireScreenerClient"))
        self.assertTrue(hasattr(experimental, "build_iv_scan_request"))


if __name__ == "__main__":
    unittest.main()
