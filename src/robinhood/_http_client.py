import logging

import requests

from .constants import (
    BASE_API_BONFIRE_LINK,
    BASE_API_LINK,
    MAX_LIMIT,
    PARAM_LIMIT,
    RESULTS,
)


class RobinhoodHTTPClient:
    def __init__(
        self,
        token: str,
        user_agent: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.session = requests.Session()
        self.logger = logger
        self.session.headers["Authorization"] = f"Bearer {token}"
        if user_agent:
            self.session.headers["User-Agent"] = user_agent

    def close(self) -> None:
        self.session.close()

    def _page_get(self, endpoint: str, results: list[dict]) -> list[dict]:
        while True:
            res = self.session.get(url=endpoint)
            if res.status_code != 200:
                print(res.status_code)
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
        params: dict | None = None,
    ) -> list[dict]:
        if self.logger:
            self.logger.debug(
                "GET request: %s, Params length: %d",
                endpoint,
                len(params) if params else 0,
            )
        res = self.session.get(
            url=BASE_API_LINK + endpoint, params=params, timeout=5
        )
        if res.status_code != 200:
            print(res.status_code)
            return []
        res_json = res.json()
        next_link: str | None = res_json.get("next")
        limit: int | None = params.get(PARAM_LIMIT) if params else None
        if not next_link:
            return res_json.get(RESULTS, [res_json])
        if limit and limit != MAX_LIMIT:
            return res_json.get(RESULTS, [res_json])
        return self._page_get(next_link, results=res_json.get(RESULTS, []))

    def _post(self, endpoint: str, data: dict | None = None) -> dict | None:
        raise NotImplementedError
        res = self.session.post(url=BASE_API_BONFIRE_LINK + endpoint, json=data)
        if res.status_code != 200:
            print(res.status_code)
            return None
        return res.json()
