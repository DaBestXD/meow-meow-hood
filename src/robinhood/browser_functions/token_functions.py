from __future__ import annotations

import base64
import json
import logging
import sqlite3
import sys
import time
from datetime import datetime, timezone
from os import PathLike
from pathlib import Path
from typing import Any

import requests
from typing_extensions import deprecated

from robinhood.browser_functions.browser_token_parser import (
    CHROME_LINUX,
    CHROME_MAC,
    CHROME_WINDOWS,
    DB_PATH,
    FIRE_LINUX,
    FIRE_MAC,
    FIRE_WINDOWS,
    Browser,
    Chrome,
    Firefox,
    get_token,
)

logger = logging.getLogger(__name__)


@deprecated("No need to test this")
def test_ping(access_token: str, attempts: int = 3) -> bool:
    """
    IDK why this exists can probably delete later
    """
    test_link = "https://api.robinhood.com/accounts/"
    headers = {"authorization": f"{access_token}"}
    res = requests.get(test_link, headers=headers, timeout=5)
    if res.status_code >= 500 and attempts >= 0:
        logger.warning("5XX error retrying...")
        test_ping(access_token, attempts - 1)
    return res.ok


def return_access_token_expiry(access_token: str) -> int:
    """Return the token expiry date"""
    token = access_token
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload: dict[str, Any] = json.loads(
        base64.urlsafe_b64decode(payload_b64).decode()
    )
    logger.debug("payload expirary: %s", payload["exp"])
    return int(payload["exp"])


def _chrome_helper(f: Path) -> int:
    for i in f.iterdir():
        if ".log" not in i.name:
            continue
        return int(i.stat().st_mtime)
    raise ValueError("unable to find file mod time")


def _firefox_helper(f: Path) -> int:
    # this will break if you have mulitple firefox profiles and
    # you have logged into robinhood on both
    for n in f.iterdir():
        if not n.is_dir():
            continue
        db_file = n / DB_PATH
        db_file_path = "file:" + str(db_file) + "?immutable=1"
        try:
            # check to make sure this is the correct db file
            with sqlite3.connect(db_file_path, uri=True) as _:
                logger.debug("Connected to %s", db_file_path)
            return int(db_file.stat().st_mtime)
        except sqlite3.OperationalError:
            continue
    raise ValueError("unable to find file mod time")


def file_stat(browser: Browser) -> int:
    """Return the file modified timestamp"""
    if sys.platform == "darwin":
        if isinstance(browser, Firefox):
            return _firefox_helper(FIRE_MAC)
        if isinstance(browser, Chrome):
            return _chrome_helper(CHROME_MAC)

    if sys.platform == "win32":
        if isinstance(browser, Firefox):
            return _firefox_helper(FIRE_WINDOWS)
        if isinstance(browser, Chrome):
            return _chrome_helper(CHROME_WINDOWS)

    if sys.platform == "linux":
        if isinstance(browser, Firefox):
            return _firefox_helper(FIRE_LINUX)
        if isinstance(browser, Chrome):
            return _chrome_helper(CHROME_LINUX)

    raise ValueError("unable to find db_file stat")


def check_if_modified_date_within_range(days: int = 7) -> bool:
    """
    Check if the last modified date is within a certain range,
    default is 7 days. If this fails the check you will most likely
    need to relogin into robinhood manually
    """
    last_mod = -1
    for b in (Firefox(), Chrome()):
        try:
            last_mod = file_stat(b)
        except ValueError:
            logger.debug("auth information not found in %s", repr(b))
            continue
    last_mod = (
        datetime.now(timezone.utc)
        - datetime.fromtimestamp(last_mod, timezone.utc)
    ).days
    return last_mod >= days


def _refresh_access_token(
    access_token: str,
    env_path: str | PathLike[str],
    write_env: bool,
) -> str | None:
    """
    Convenience wrapper function checks token expirary date,
    if expired and recoverable will open browser to retrieve and
    return the new token.
    None response means token is not expired, RuntimeError means
    you will need to manually log back into Robinhood
    """
    token_exp = return_access_token_expiry(access_token)
    if not (token_exp <= int(time.time())):
        logger.info("Access token is not expired, exp: %s", str(token_exp))
        return None
    # Raise error if there's no way to recover the auth token
    if token_exp <= int(time.time()) and check_if_modified_date_within_range():
        raise RuntimeError(
            """Token is expired and auth modified date is greater than 30 days.
            You will need to relogin manually"""
        )
    elif token_exp <= int(time.time()):
        # if the token is expired but its within the mod period
        access_token, _ = get_token(
            env_path=env_path, write_env=write_env, open_browser=True
        )
        return access_token
    return None
