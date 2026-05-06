import sys
import base64
import json
import time
from typing import Any

import requests

from robinhood.browser_functions.browser_token_parser import (
    Browser,
    Firefox,
    Chrome,
    CHROME_MAC,
)


def test_ping(access_token: str, attempts: int = 3) -> bool:
    test_link = "https://api.robinhood.com/accounts/"
    headers = {"authorization": f"{access_token}"}
    res = requests.get(test_link, headers=headers, timeout=5)
    if res.status_code >= 500 and attempts >= 0:
        test_ping(access_token, attempts - 1)
    return res.ok


def check_access_token_expiry(access_token: str) -> bool:
    token = access_token
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload: dict[str, Any] = json.loads(
        base64.urlsafe_b64decode(payload_b64).decode()
    )
    return int(payload["exp"]) > int(time.time())


# First check if JWT is expired yes --> check if the file metadata last
# modified date if longer then 7 days ? then raise warning "Need to relogin"
# else use open browser function then get token function, old token should
# be replaced with the new token
#
# Auth loop:
# - if 401/403 error:
# - Check if JWT token is expired
# - if yes check browser modified date less than 7 days ?
#   - raise warning
# - else open browser / close browser to reset cached token
# - get new token


def file_stat(browser: Browser) -> None:
    if sys.platform == "darwin":
        if isinstance(browser, Firefox):
            pass
        if isinstance(browser, Chrome):
            for i in CHROME_MAC.iterdir():
                if ".log" not in i.name:
                    continue
                print(i.stat().st_mtime < int(time.time()))


def refresh_access_token(access_token: str, browser: Browser) -> str | None:
    """
    Use browser that you are logged into.
    Either `Firefox()` or `Chrome()`
    """
    # Plan decode JWT token check if expiration date is within a random
    # amount of days (1-7) ?
    # Not sure how robinhood determines when to log out user browser side
    # if it falls within this range open browser, then put db entry that
    # browser was last opened when / or just check the local storage
    # last access date that is probably easier.
    # Yeah the db plan is probably stupid nvm XD
    # Then have a guard against 403 / 401 errors to reset the currently
    # stored access_token
    # return the expiration time so you can just check when auth should be
    # changed ?
    if not check_access_token_expiry(access_token):
        pass
    if sys.platform == "darwin":
        if isinstance(browser, Firefox):
            pass
        if isinstance(browser, Chrome):
            for i in CHROME_MAC.iterdir():
                if ".log" not in i.name:
                    continue
                print(i.stat().st_mtime < int(time.time()))

    return None
