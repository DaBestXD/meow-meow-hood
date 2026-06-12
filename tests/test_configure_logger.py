import logging

from robinhood.utils.configure_logger import MISSING, configure_logger


class TestConfigureLogger:
    def test_missing_replaces_existing_default_handler(
        self,
        robinhood_logger,
    ) -> None:
        configure_logger(logging.INFO, MISSING)

        configure_logger(logging.INFO, MISSING)

        assert 1 == len(robinhood_logger.handlers)
        assert isinstance(robinhood_logger.handlers[0], logging.StreamHandler)
        assert not robinhood_logger.propagate

    def test_none_clears_handlers_and_reenable_propagation(
        self,
        robinhood_logger,
    ) -> None:
        configure_logger(logging.INFO, MISSING)

        configure_logger(logging.INFO, None)

        assert [] == robinhood_logger.handlers
        assert robinhood_logger.propagate

    def test_custom_handler_is_reconfigured_without_duplicates(
        self,
        robinhood_logger,
    ) -> None:
        handler = logging.NullHandler()

        configure_logger(logging.DEBUG, handler)
        configure_logger(logging.DEBUG, handler)

        assert [handler] == robinhood_logger.handlers
        assert logging.DEBUG == robinhood_logger.level
        assert not robinhood_logger.propagate

    def test_none_logging_level_leaves_existing_configuration_unchanged(
        self,
        robinhood_logger,
    ):
        handler = logging.NullHandler()
        robinhood_logger.addHandler(handler)
        robinhood_logger.setLevel(logging.WARNING)
        robinhood_logger.propagate = True

        configure_logger(None, MISSING)

        assert [handler] == robinhood_logger.handlers
        assert logging.WARNING == robinhood_logger.level
        assert robinhood_logger.propagate
