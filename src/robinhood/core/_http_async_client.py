"""Async HTTP client used by the public Robinhood clients."""

import logging
from typing import Any, Never

import aiohttp

from robinhood.constants import BASE_API_LINK, RESULTS
from robinhood.robinhood_errors import (
    AuthenticationError,
    EndpointNotFoundError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class RobinhoodAsyncHTTPClient:
    """Small aiohttp wrapper for Robinhood GET, POST, and paginated requests."""

    def __init__(self, access_token: str, user_agent: str | None) -> None:
        self.session: aiohttp.ClientSession | None = None
        self.access_token: str = access_token
        self.user_agent = user_agent

    async def close(self) -> None:
        """Close the underlying aiohttp session when it exists."""
        if not self.session:
            return None
        await self.session.close()

    # This should be blocking maybe?
    def _error_status_code_handler(
        self, endpoint: str, status_code: int
    ) -> Never:
        """
        Raise the current package-level error for HTTP response statuses.

        `401` and `403` raise `AuthenticationError`. `429` and `5xx` currently
        raise `NotImplementedError` until retry and rate-limit handling is
        added.
        Other statuses are logged and return `None`.
        """
        if status_code >= 500:
            # TODO: add retry logic for 5XX errors
            raise NotImplementedError(f"{endpoint}, {status_code}")
        if status_code == 404 or status_code == 400:
            raise EndpointNotFoundError(f"{endpoint}, {status_code}")
        if status_code == 429:
            logger.warning("429 error returned, you are being rate limited.")
            raise RateLimitError(f"{endpoint}, {status_code}")
        if status_code == 403 or status_code == 401:
            logger.critical("Access token invalid, relogin into robinhood")
            raise AuthenticationError(
                "Access token invalid, relogin into robinhood"
            )
        else:
            logger.warning("%s returned: %d", endpoint, status_code)
        raise RuntimeError(
            f"{endpoint} returned unexpected error {status_code}"
        )

    def update_session_token(self, token: str) -> None:
        if self.session:
            logger.debug("Updating session auth token %s", token[:7])
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        return None

    async def create_client_session(self) -> aiohttp.ClientSession:
        """Create or return the cached aiohttp client session."""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=15, connect=5)
            headers = {"Authorization": f"Bearer {self.access_token}"}
            if self.user_agent:
                headers["User-Agent"] = self.user_agent
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=timeout,
            )
        return self.session

    async def _page_get(
        self,
        endpoint: str,
        results: list[dict],
    ) -> list[dict]:
        session = await self.create_client_session()
        while True:
            logger.debug(
                "GET request: %s, %s", endpoint, self._page_get.__name__
            )
            try:
                async with session.get(url=endpoint) as res:
                    res.raise_for_status()
                    res_json = await res.json()
                    endpoint = res_json.get("next")
                    results.extend(res_json.get(RESULTS, []))
                    if not endpoint:
                        break
            except aiohttp.ClientResponseError as e:
                self._error_status_code_handler(endpoint, e.status)
        return results

    async def _get(
        self,
        endpoint: str,
        base_api_link: str = BASE_API_LINK,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        session = await self.create_client_session()
        try:
            async with session.get(
                url=base_api_link + endpoint,
                params=params,
            ) as res:
                res.raise_for_status()
                res_json = await res.json()
                next_link: str | None = res_json.get("next")
                if not next_link:
                    return res_json.get(RESULTS, [res_json])
                return await self._page_get(
                    next_link, results=res_json.get(RESULTS, [])
                )
        except aiohttp.ClientResponseError as e:
            self._error_status_code_handler(endpoint, e.status)

    async def _download(
        self, endpoint: str, base_api_link: str = BASE_API_LINK
    ) -> bytes:
        session = await self.create_client_session()
        async with session.get(
            url=base_api_link + endpoint,
        ) as res:
            res.raise_for_status()
            return await res.read()

    async def _delete(
        self,
        endpoint: str,
        base_api_link: str = BASE_API_LINK,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        session = await self.create_client_session()
        try:
            async with session.delete(
                url=base_api_link + endpoint,
                data=data,
                json=json,
            ) as res:
                logger.debug(
                    "DELETE request: %s, data: %s json: %s",
                    endpoint,
                    data if data else "none",
                    json if json else "none",
                )
                res.raise_for_status()
                if getattr(res, "status", None) == 204:
                    return None
                try:
                    return await res.json()
                except aiohttp.ContentTypeError:
                    return None
        except aiohttp.ClientResponseError as e:
            self._error_status_code_handler(endpoint, e.status)
        return None

    async def _post(
        self,
        endpoint: str,
        base_api_link: str = BASE_API_LINK,
        data: dict | None = None,
        json: dict | None = None,
    ) -> dict | None:
        session = await self.create_client_session()
        try:
            async with session.post(
                url=base_api_link + endpoint,
                data=data,
                json=json,
            ) as res:
                logger.debug(
                    "POST request: %s, data: %s json: %s",
                    endpoint,
                    data if data else "none",
                    json if json else "none",
                )
                res.raise_for_status()
                return await res.json()
        except aiohttp.ClientResponseError as e:
            self._error_status_code_handler(endpoint, e.status)

    async def _connect_to_ws(self, endpoint: str):
        # Refer to futures_orderbook.md file inside experimental folder
        raise NotImplementedError
