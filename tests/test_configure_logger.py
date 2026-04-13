import logging
import unittest

from robinhood.configure_logger import MISSING, configure_logger


class TestConfigureLogger(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger("robinhood")
        self.original_handlers = list(self.logger.handlers)
        self.original_level = self.logger.level
        self.original_propagate = self.logger.propagate
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)

    def tearDown(self) -> None:
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)
        for handler in self.original_handlers:
            self.logger.addHandler(handler)
        self.logger.setLevel(self.original_level)
        self.logger.propagate = self.original_propagate

    def test_missing_replaces_existing_default_handler(self) -> None:
        configure_logger(logging.INFO, MISSING)

        configure_logger(logging.INFO, MISSING)

        self.assertEqual(1, len(self.logger.handlers))
        self.assertIsInstance(self.logger.handlers[0], logging.StreamHandler)
        self.assertFalse(self.logger.propagate)

    def test_none_clears_handlers_and_reenable_propagation(self) -> None:
        configure_logger(logging.INFO, MISSING)

        configure_logger(logging.INFO, None)

        self.assertEqual([], self.logger.handlers)
        self.assertTrue(self.logger.propagate)

    def test_custom_handler_is_reconfigured_without_duplicates(self) -> None:
        handler = logging.NullHandler()

        configure_logger(logging.DEBUG, handler)
        configure_logger(logging.DEBUG, handler)

        self.assertEqual([handler], self.logger.handlers)
        self.assertEqual(logging.DEBUG, self.logger.level)
        self.assertFalse(self.logger.propagate)
