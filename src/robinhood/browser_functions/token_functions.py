from __future__ import annotations

import base64
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from robinhood.browser_functions.browser_token_parser import (
    Browser,
)
from robinhood.robinhood_errors import TokenExtractionError

logger = logging.getLogger(__name__)


def _return_access_token_expiry(access_token: str) -> int:
    """Return the token expiry date"""
    token = access_token
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload: dict[str, Any] = json.loads(
        base64.urlsafe_b64decode(payload_b64).decode()
    )
    return int(payload["exp"])


def _refresh_access_token(
    access_token: str,
    browser: Browser,
    max_day_without_access: int = 7,
) -> str | None:
    """
    Convenience wrapper function checks token expirary date,
    if expired and recoverable will open browser to retrieve and
    return the new token.
    None response means token is not expired, RuntimeError means
    you will need to manually log back into Robinhood
    String response means an auth session was sucessfully recovered
    """
    token_exp = _return_access_token_expiry(access_token)
    if token_exp > int(time.time()):
        logger.info(
            "Access token is not expired, exp: %s",
            datetime.fromtimestamp(token_exp),
        )
        return None
    days_old = (
        datetime.now(timezone.utc)
        - datetime.fromtimestamp(
            browser._file_to_stat_check.stat().st_mtime, timezone.utc
        )
    ).days
    if days_old < max_day_without_access:
        token = browser.get_token()
        if not token:
            raise TokenExtractionError(
                f"{_refresh_access_token.__qualname__} unable to retrieve token"
            )
        logger.info("Fresh token has been extracted")
        return token
    # Raise error if there's no way to recover the auth token
    raise RuntimeError(
        "Token is expired and auth modified date is greater than 7 days. You will need to relogin manually"  # noqa E501
    )
