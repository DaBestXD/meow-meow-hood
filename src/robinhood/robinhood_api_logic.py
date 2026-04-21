from __future__ import annotations

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
from types import TracebackType
from typing import Any

from dotenv import load_dotenv

from robinhood.configure_logger import MISSING, configure_logger
from robinhood.db_logic.option_cache import OptionCache
from robinhood.set_up_script import set_up

from ._http_client import RobinhoodHTTPClient
from .api import (
    AccountMixin,
    MarketDataMixin,
    OptionsMixin,
    TradingMixin,
)
from .browser_token_parser import (
    Browser,
    auto_open_browser,
    get_acc_id,
    get_token,
)

logger = logging.getLogger(__name__)


class Robinhood(MarketDataMixin, OptionsMixin, AccountMixin, TradingMixin):
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
        Initialize a Robinhood client instance.

        Args:
            config_path: Base directory where ``.meow-meow-config`` is created
                or reused. The client stores its ``.env`` token cache and local
                SQLite database there.
            extract_token: When ``True``, attempt to acquire a fresh bearer
                token from the local browser session if the token loaded from
                ``.env`` is missing or rejected.
            write_env: When ``True`` writes env file to the config_path
            open_browser: When ``True``, allow the browser refresh helper to
                briefly open Robinhood if a stored token is rejected.
            user_agent: Optional ``User-Agent`` header override for the shared
                HTTP session.
            enable_cache: When ``True``, enable the local SQLite instrument
                cache for option chain and option instrument metadata.
            prune_expired_options: When ``True``, remove expired option rows
                when the cache is opened.
            logging_level: Logging level constant for the library logger,
                such as ``logging.INFO`` or ``logging.DEBUG``.
            log_handler: Handler configuration for the library logger.
                Pass no value to use the library's default handler.
                ``None`` to clear library handlers and let records propagate,
                or a ``logging.Handler`` instance to use a custom handler.
            access_token: Explicit bearer token override. When supplied with
                ``extract_token=False`` and ``enable_cache=False``, the client
                skips the config bootstrap path and uses this token directly.
        """
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
            assert token, "Bearer token cannot be none."
        self._http_client = RobinhoodHTTPClient(token, user_agent)
        logger.info("Robinhood Client Initialized")

    def __enter__(self) -> Robinhood:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Closes the robinhood client"""
        if self._db_cache:
            self._db_cache.close()
            self._db_cache = None
        self._http_client.close()
        logger.info("Robinhood Client Closed")

    def refresh_access_token(self, browser: Browser) -> None:
        """
        This function should only need to be run once a week.
        In theory as long as you keep running this function it should
        refresh the access token. Opening the browser is necessary
        for refreshing the access token.
        pkill/taskKill is the easiest way to clean up the open browser
        though not ideal as it closes all the entire browser.
        """
        auto_open_browser(browser)
        if not self.env_path:
            logger.warning("No env path was provided. Not writing to env")
            token, _ = get_token("", write_env=False)
        else:
            token, _ = get_token(self.env_path)
        self._http_client.session.headers["Authorization"] = f"Bearer {token}"
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
