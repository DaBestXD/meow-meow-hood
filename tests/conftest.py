from __future__ import annotations

import logging
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest

from robinhood.db_logic.option_cache import OptionCache


@pytest.fixture
def async_client_tracker() -> Generator[Callable[[Any], Any]]:
    clients: list[Any] = []

    def track(client: Any) -> Any:
        clients.append(client)
        return client

    yield track

    for client in clients:
        loop = getattr(client, "event_loop", None)
        if loop is not None and not loop.is_closed():
            loop.close()


@pytest.fixture
def sync_client_tracker() -> Generator[Callable[[Any], Any]]:
    clients: list[Any] = []

    def track(client: Any) -> Any:
        clients.append(client)
        return client

    yield track

    for client in clients:
        loop = getattr(client, "event_loop", None)
        if loop is not None and not loop.is_closed():
            loop.close()


@pytest.fixture
def robinhood_logger() -> Generator[logging.Logger]:
    logger = logging.getLogger("robinhood")
    original_handlers = list(logger.handlers)
    original_level = logger.level
    original_propagate = logger.propagate

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    yield logger

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    for handler in original_handlers:
        logger.addHandler(handler)
    logger.setLevel(original_level)
    logger.propagate = original_propagate


@pytest.fixture
def option_cache_factory(
    tmp_path: Path,
) -> Generator[Callable[[], OptionCache]]:
    caches: list[OptionCache] = []

    def make_cache() -> OptionCache:
        db_path = tmp_path / f"options_{len(caches)}.db"
        cache = OptionCache(db_path, prune_expired=False)
        caches.append(cache)
        return cache

    yield make_cache

    for cache in caches:
        cache.close()
