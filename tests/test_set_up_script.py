import tempfile
import unittest
from pathlib import Path

from robinhood.set_up_script import DEFAULT_CONFIG_NAME, set_up


class TestSetUpScript(unittest.TestCase):
    def test_set_up_creates_default_config_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            result = set_up(base_dir)

            self.assertEqual(base_dir / DEFAULT_CONFIG_NAME, result)
            self.assertTrue(result.is_dir())

    def test_set_up_returns_existing_config_dir_without_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            existing_dir = base_dir / ".custom-config"
            existing_dir.mkdir()

            result = set_up(base_dir, ".custom-config")

            self.assertEqual(existing_dir, result)
            self.assertTrue(result.is_dir())


if __name__ == "__main__":
    unittest.main()
