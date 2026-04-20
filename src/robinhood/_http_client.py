import logging
import time
from typing import Any

import requests

from .constants import (
    BASE_API_LINK,
    MAX_LIMIT,
    PARAM_LIMIT,
    RESULTS,
)

logger = logging.getLogger(__name__)


class RobinhoodHTTPClient:
    def __init__(
        self,
        token: str,
        user_agent: str | None = None,
    ) -> None:
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {token}"
        if user_agent:
            self.session.headers["User-Agent"] = user_agent
        logger.debug("RobinhoodHTTPClient Initialized")

    def close(self) -> None:
        self.session.close()
        logger.debug("RobinhoodHTTPClient Closed")

    def _error_status_code_handler(
        self, endpoint: str, status_code: int
    ) -> None:
        """
        Current logic is to sleep for 65 seconds after hitting a rate limit.
        No retry is attempted and an empty value is returned
        """
        if status_code == 429:
            logger.warning("HTTP 429 returned, sleeping for 65 seconds...")
            time.sleep(65)
        if status_code == 403 or status_code == 401:
            # TODO raise error here
            logger.critical("Access token invalid, relogin into robinhood")
        else:
            logger.warning("%s returned: %d", endpoint, status_code)
        return None

    def _page_get(self, endpoint: str, results: list[dict]) -> list[dict]:
        while True:
            logger.debug(
                "GET request: %s, %s", endpoint, self._page_get.__name__
            )
            res = self.session.get(url=endpoint)
            if res.status_code >= 300:
                self._error_status_code_handler(endpoint, res.status_code)
                return []
            res_json = res.json()
            endpoint = res_json.get("next")
            results.extend(res_json.get(RESULTS, []))
            if not endpoint:
                break
        return results

    def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        base_api_link: str = BASE_API_LINK,
    ) -> list[dict[str, Any]]:
        logger.debug(
            "GET request: %s, Params length: %d",
            endpoint,
            len(params) if params else 0,
        )
        res = self.session.get(
            url=base_api_link + endpoint, params=params, timeout=5
        )
        if res.status_code != 200:
            self._error_status_code_handler(endpoint, res.status_code)
            return []
        res_json = res.json()
        next_link: str | None = res_json.get("next")
        limit: int | None = params.get(PARAM_LIMIT) if params else None
        if not next_link:
            return res_json.get(RESULTS, [res_json])
        if limit and limit != MAX_LIMIT:
            return res_json.get(RESULTS, [res_json])
        return self._page_get(next_link, results=res_json.get(RESULTS, []))

    def _post(
        self,
        endpoint: str,
        base_api_link: str = BASE_API_LINK,
        data: dict | None = None,
        json: dict | None = None,
    ) -> dict | None:
        res = self.session.post(
            url=base_api_link + endpoint,
            data=data,
            json=json,
        )
        logger.debug(
            "POST request: %s, data length: %d",
            endpoint,
            len(data) if data else 0,
        )
        if res.status_code >= 300:
            self._error_status_code_handler(endpoint, res.status_code)
            return None
        return res.json()

    def _delete(self):
        raise NotImplementedError
