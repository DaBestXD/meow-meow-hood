import requests
import asyncio
from db_logic.db_functions import init_db, db_loop
from constants import (
    API_OPTION_CHAINS,
    API_QUOTES,
    BASE_API_LINK,
    API_OPTIONS_INSTRUMENTS,
    MAX_LIMIT,
    PARAM_CHAIN_ID,
    PARAM_EXPIRATION_DATE,
    PARAM_LIMIT,
    PARAM_OPTION_TYPE,
    PARAM_SYMBOLS,
    RESULTS,
)
from browser_token_parser import get_token, get_acc_id
from api_dataclasses import FullQuote, OptionChain, OptionInstrument
from types import TracebackType
from typing import Callable, Literal
from api_warnings import LimitExceededWarning


class Robinhood:
    def __init__(
        self,
        token: str | None = None,
        auto_login: bool = True,
        db_enabled: bool = True,
    ) -> None:

        if token:
            self.user_id = get_acc_id(token)
            self.token = token
        elif auto_login:
            self.token, self.user_id = get_token()

        self.db_enabled = db_enabled
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
            }
        )
        if db_enabled:
            init_db()
            self.db_queue: asyncio.Queue[Callable] = asyncio.Queue()

    def __enter__(self) -> Robinhood:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.session.close()

    def close(self) -> None:
        self.session.close()
        return None

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
        self, endpoint: str, params: dict | None = None
    ) -> list[dict] | None:
        next_link = None
        res = self.session.get(
            url=BASE_API_LINK + endpoint, params=params, timeout=5
        )
        if res.status_code != 200:
            print(res.status_code)
            return None
        res_json = res.json()
        next_link = res_json.get("next")
        if not next_link:
            return [res_json]
        if params and params.get(PARAM_LIMIT) != MAX_LIMIT:
            return res_json[RESULTS]
        return self._page_get(next_link, results=res_json.get(RESULTS, []))

    def get_stock_quotes(self, symbol: list[str] | str) -> list[FullQuote]:
        """
        Returns a list of FullQuote dataclasses
        Example: stock = get_stock_quotes("SPY) --> stock[0].bid_price
        """
        symbol = [symbol] if isinstance(symbol, str) else symbol
        joined_symbol = ",".join(symbol)
        res_json = self._get(API_QUOTES, {PARAM_SYMBOLS: joined_symbol})
        if not res_json:
            return []
        return [FullQuote(*r) for r in res_json[0] if r]

    def get_option_data_at_date(
        self,
        option_chain_id: str,
        option_type: Literal["call", "put"],
        option_exp_date: str | None = None,
        limit: int = MAX_LIMIT,
    ) -> list[OptionInstrument] | OptionInstrument | None:
        if limit > MAX_LIMIT:
            limit = 100
        res_jon = self._get(
            endpoint=API_OPTIONS_INSTRUMENTS,
            params={
                PARAM_EXPIRATION_DATE: option_exp_date,
                PARAM_CHAIN_ID: option_chain_id,
                PARAM_OPTION_TYPE: option_type,
                PARAM_LIMIT: limit,
            },
        )
        if not res_jon:
            return None
        return (
            [OptionInstrument(**r) for r in res_jon]
            if len(res_jon) > 1
            else OptionInstrument(**res_jon[0])
        )

    def get_option_chain_data(self, symbol: str) -> OptionChain | None:
        res_json = self._get(API_OPTION_CHAINS + f"{symbol}/")
        if not res_json:
            return None
        return OptionChain(**res_json[0])
