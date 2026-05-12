from __future__ import annotations

import asyncio

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
import logging
import os
from pathlib import Path
from typing import Any, Coroutine

from dotenv import load_dotenv

from robinhood.browser_functions.browser_token_parser import (
    Browser,
    auto_open_browser,
    get_acc_id,
    get_token,
)
from robinhood.browser_functions.token_functions import (
    _refresh_access_token,
    check_if_modified_date_within_range,
)
from robinhood.configure_logger import MISSING, configure_logger
from robinhood.core._account_impl import AccountImpl
from robinhood.core._http_async_client import RobinhoodAsyncHTTPClient
from robinhood.core._market_data_impl import MarketDataImpl
from robinhood.core._option_impl import OptionsImpl
from robinhood.core._trading_impl import TradingImpl
from robinhood.db_logic.option_cache import OptionCache
from robinhood.set_up_script import set_up
from robinhood.types import T

logger = logging.getLogger(__name__)


class _CoreRobinhood(
    MarketDataImpl,
    AccountImpl,
    OptionsImpl,
    TradingImpl,
):
    def __init__(
        self,
        *,
        config_path: str | os.PathLike[str] = Path.cwd(),
        extract_token: bool = True,
        write_env: bool = True,
        open_browser: bool = True,
        user_agent: str | None = None,
        enable_cache: bool = True,
        prune_expired_options: bool = True,
        logging_level: int | None = logging.INFO,
        log_handler: logging.Handler | None | object = MISSING,
        access_token: str | None = None,
    ) -> None:
        """
        Core implementation of the robinhood class for both sync
        and async classes.
        """
        self.event_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        configure_logger(logging_level, log_handler)
        self.user_id = -1
        if access_token and not extract_token and not enable_cache:
            token = access_token
            self._db_cache = None
            self.env_path = None
        else:
            config_dir = set_up(Path(config_path))
            self.env_path = config_dir / ".env"
            cache_path = config_dir / "meow-meow-hood.db"
            if enable_cache:
                self._db_cache = OptionCache(cache_path, prune_expired_options)
            else:
                self._db_cache = None
            load_dotenv(dotenv_path=self.env_path)
            token = access_token if access_token else os.getenv("BEARER_TOKEN")
            if token:
                self.user_id = get_acc_id(token)
            if extract_token and isinstance(self.user_id, int):
                token, self.user_id = get_token(
                    env_path=self.env_path,
                    open_browser=open_browser,
                    write_env=write_env,
                )
            if not token:
                raise RuntimeError("Bearer token cannot be none.")
        self._async_http_client = RobinhoodAsyncHTTPClient(token, user_agent)
        logger.info("Robinhood Client Initialized")

    def _run(self, coro: Coroutine[Any, Any, T]) -> T:
        return self.event_loop.run_until_complete(coro)

    def open_browser(
        self,
        browser: Browser,
        wait_time: int = 10,
        days: int = 1,
    ) -> None:
        """
        Checks if the last modified date is greater than one day,
        then open the browser pointed at robinhood, closes after
        N seconds(default is 10 seconds)
        """
        if not check_if_modified_date_within_range(days=days):
            auto_open_browser(browser, wait_time=wait_time)
        return None

    def refresh_access_token(self) -> None:
        """
        Function that will automatically open browser if token is expired,
        and attempts to retrieve a new token
        """
        access_token = self._async_http_client.access_token
        env_path = self.env_path if self.env_path else ""
        token = _refresh_access_token(
            access_token,
            env_path,
            True if self.env_path else False,
        )
        if isinstance(token, str):
            self._async_http_client.access_token = token
        return None

    def execute_custom_sql(
        self, query: str, args: list[dict[str, Any] | dict[str, Any]]
    ) -> list[Any] | None:
        """
        Use if you need to execute a custom sql query
        Use a list of args if you need to use ``executemany()``
        """
        if not self._db_cache:
            logger.warning("No db enabled! Nothing to execute!")
            return None
        else:
            return self._db_cache.execute_query_with_args(query, args)
