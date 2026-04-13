import logging

MISSING = object()


def configure_logger(
    logging_level: int | None = logging.INFO,
    log_handler: logging.Handler | None | object = MISSING,
) -> None:
    logger = logging.getLogger("robinhood")
    if logging_level is None:
        return None
    logger.setLevel(logging_level)
    _clear_handlers(logger)
    if log_handler is None:
        logger.propagate = True
        return None
    if log_handler is MISSING:
        log_handler = _default_handler()
    assert isinstance(log_handler, logging.Handler)
    logger.addHandler(log_handler)
    logger.propagate = False


def _default_handler() -> logging.Handler:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s")
    )
    return handler


def _clear_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
