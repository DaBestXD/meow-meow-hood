from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from robinhood.api_dataclasses import (
    OptionChain,
    OptionInstrument,
    OptionRequest,
    StockInfo,
)

from .db_schema import (
    EXPIRATION_DATES_TABLE,
    MAIN_TABLE,
    OPTION_CHAIN_SYNC_TABLE,
    OPTION_EXPIRATION_SYNC_TABLE,
    OPTION_GREEK_DATA_TABLE,
    OPTION_IDS_INDEX,
    OPTION_IDS_TABLE,
)


class OptionCache:
    def __init__(self, db_path: Path, prune_expired: bool = True) -> None:
        self.db_path = db_path
        self.con = sqlite3.connect(db_path)
        self.init_db()
        self.prune_expired() if prune_expired else None

    def close(self) -> None:
        self.con.close()

    def init_db(self) -> None:
        self.con.execute(MAIN_TABLE)
        self.con.execute(OPTION_IDS_TABLE)
        self.con.execute(EXPIRATION_DATES_TABLE)
        self.con.execute(OPTION_GREEK_DATA_TABLE)
        self.con.execute(OPTION_EXPIRATION_SYNC_TABLE)
        self.con.execute(OPTION_CHAIN_SYNC_TABLE)
        self.con.execute(OPTION_IDS_INDEX)
        self.con.commit()

    @staticmethod
    def next_trading_day_timestamp() -> int:
        """Next trading day is 9:30 EDT"""
        plus_one = (datetime.now(ZoneInfo("America/New_York"))) + timedelta(
            days=1
        )
        next_day = plus_one.replace(hour=9, minute=30, second=0, microsecond=0)
        return int(next_day.timestamp())

    @staticmethod
    def now_edt_timestamp() -> int:
        return int((datetime.now(ZoneInfo("America/New_York"))).timestamp())

    @staticmethod
    def _is_cachable_option_request(option_request: OptionRequest) -> bool:
        """
        Helper function to check if option request is cachable.
        Cachable if no strike_price and no option_type.
        """
        if option_request.strike_price:
            return False
        if option_request.option_type:
            return False
        return True

    def insert_stock_info(self, stock_info: StockInfo) -> None:
        """Insert stock_info: symbol, id, and chain_id into main_stock_info"""
        query = """
            INSERT OR REPLACE INTO main_stock_info
            VALUES(:symbol, :id, :chain_id)
        """
        args = {
            "symbol": stock_info.symbol,
            "id": stock_info.id,
            "chain_id": stock_info.tradable_chain_id or "",
        }
        self.con.execute(query, args)
        self.con.commit()

    def execute_query_with_args(
        self, query: str, args: list[dict[str, Any]] | dict[str, Any]
    ) -> list[Any]:
        """
        Use if you need to execute a custom sql query
        Use a list of args if you need to use ``executemany()``
        """
        if isinstance(args, list):
            cur = self.con.executemany(query, args)
        else:
            cur = self.con.execute(query, args)
        return cur.fetchall()

    def prune_expired(self) -> None:
        """Clean up columns where exp_date is no longer valid(EDT is used)"""
        today_et = datetime.now(ZoneInfo("America/New_York")).date()
        args = {"today_et": today_et}
        query = "DELETE FROM expiration_dates WHERE exp_date < :today_et"
        self.con.execute(query, args)
        query = "DELETE FROM option_ids WHERE exp_date < :today_et"
        self.con.execute(query, args)
        query = "DELETE FROM option_expiration_sync WHERE exp_date < :today_et"
        self.con.execute(query, args)
        self.con.commit()

    def is_option_chain_synced(self, symbol: str) -> bool:
        """
        Return whether cached option-chain data for symbol is still fresh.
        """
        query = """
            SELECT time_to_live FROM option_chain_sync
            WHERE symbol = :symbol
        """
        args = {"symbol": symbol}
        cur: sqlite3.Cursor = self.con.execute(query, args)
        time_to_live: tuple[int] | None = cur.fetchone()
        if time_to_live is None:
            return False
        return time_to_live[0] >= self.now_edt_timestamp()

    def insert_option_chain(self, option_chain: OptionChain) -> None:
        """Inserts/Updates expiration dates for a symbol"""
        query = """
            INSERT OR REPLACE INTO expiration_dates
            VALUES(:symbol, :exp_date)
        """
        args = [
            {"symbol": option_chain.symbol, "exp_date": d}
            for d in option_chain.expiration_dates
        ]
        self.con.executemany(query, args)
        self.con.commit()

    def sync_option_chain(self, symbol: str) -> None:
        """
        Syncs a symbol for a trading day.
        This is used for ``fetch_expiration_dates_for_symbol()``
        """
        query = """
            INSERT OR REPLACE INTO option_chain_sync
            VALUES (:symbol, :time_to_live)
        """
        args = {
            "symbol": symbol,
            "time_to_live": self.next_trading_day_timestamp(),
        }
        self.con.execute(query, args)
        self.con.commit()

    def fetch_expiration_dates_for_symbol(self, symbol: str) -> list[str]:
        """DB caching method for option chain functions"""
        if not self.is_option_chain_synced(symbol):
            return []
        query = "SELECT exp_date FROM expiration_dates WHERE symbol = :symbol"
        args = {"symbol": symbol}
        cur = self.con.execute(query, args)
        return [d[0] for d in cur.fetchall() if d]

    def get_chain_id(self, symbol: str) -> str:
        """Return chain_id from symbol returns ``""`` if no match"""
        if not self.is_option_chain_synced(symbol):
            return ""
        query = "SELECT chain_id FROM main_stock_info WHERE symbol = :symbol"
        args = {"symbol": symbol}
        cur = self.con.execute(query, args)
        return c[0] if (c := cur.fetchone()) else ""

    def map_option_request_to_ids(
        self, option_request: OptionRequest
    ) -> dict[OptionRequest, list[str]]:
        """Map an option requests back to its cached option id"""
        query_mods: list[str] = ["symbol = :symbol"]
        args: dict[str, float | str] = {"symbol": option_request.symbol}
        if option_request.exp_date:
            query_mods.append("exp_date = :exp_date")
            args["exp_date"] = option_request.exp_date
        if option_request.option_type:
            query_mods.append("option_type = :option_type")
            args["option_type"] = option_request.option_type
        if option_request.strike_price:
            query_mods.append("strike_price = :strike_price")
            args["strike_price"] = option_request.strike_price
        query = "SELECT option_id FROM option_ids WHERE " + " AND ".join(
            query_mods
        )
        cur = self.con.execute(query, args)
        return {option_request: [o[0] for o in cur.fetchall() if o]}

    def fetch_strike_prices(self, option_request: OptionRequest) -> list[float]:
        """
        Returns list of strike prices as floats
        OptionRequest can use option_type and exp_date to filter further
        Returned list is ordered in ascending order
        """
        query = """
            SELECT strike_price FROM option_ids
            WHERE symbol = :symbol
            AND exp_date = :exp_date
            AND option_type = :option_type
            ORDER BY strike_price
        """
        args = {
            "symbol": option_request.symbol,
            "exp_date": option_request.exp_date or "",
            "option_type": option_request.option_type or "",
        }
        cur = self.con.execute(query, args)
        return [row[0] for row in cur.fetchall()]

    def sync_option_request_full(
        self,
        option_request: OptionRequest,
        option_instruments: list[OptionInstrument],
    ):
        """Main syncing function for option instruments"""
        # Note for Trent: you need the dates part
        # if the option request is symbol only
        dates: set[str] = {oi.expiration_date for oi in option_instruments}
        ttl = self.next_trading_day_timestamp()
        query = """
            INSERT OR REPLACE INTO option_expiration_sync
            VALUES(:symbol, :exp_date, :time_to_live)
        """
        args = [
            {
                "symbol": option_request.symbol,
                "exp_date": date,
                "time_to_live": ttl,
            }
            for date in dates
        ]
        self.con.executemany(query, args)
        self.con.commit()

    def insert_option_instrument(
        self, option_instruments: list[OptionInstrument]
    ) -> None:
        """Inserts list of option instruments into the option_ids table"""
        query = """
            INSERT OR REPLACE INTO option_ids
            VALUES(:option_id, :strike_price, :exp_date, :option_type, :symbol)
        """
        args = [
            {
                "option_id": o.id,
                "strike_price": o.strike_price,
                "exp_date": o.expiration_date,
                "option_type": o.type,
                "symbol": o.chain_symbol,
            }
            for o in option_instruments
        ]
        self.con.executemany(query, args)
        self.con.commit()

    # Current caching strategy Symbol only, or Symbol and exp_date
    # TODO option type sync later
    def sync_option_request_dispatch(
        self,
        option_request: OptionRequest,
        option_instruments: list[OptionInstrument],
    ) -> None:
        """
        Ensures only Symbol, and Symbol + exp_date OptionRequests are cached.
        """
        if option_request.strike_price:
            # Do not sync anything just store the Option Instruments
            return None
        if option_request.option_type:
            # For now do not sync anything
            return None
        # Only possible combinations left are Symbol and Symbol + exp_date
        self.sync_option_request_full(option_request, option_instruments)
        return None

    def is_option_request_synced(self, option_request: OptionRequest) -> bool:
        """
        Checks if the current EDT timestamp is less than the TTL.
        Cache is valid for one trading day. Narrower requests reuse
        that TTL instead of forcing a resync intraday.
        This will only be an issue for new options are added intraday.
        """
        if option_request.exp_date:
            query = """
                SELECT time_to_live FROM option_expiration_sync
                WHERE symbol = :symbol
                AND exp_date = :exp_date
            """
            args = {
                "symbol": option_request.symbol,
                "exp_date": option_request.exp_date,
            }
            ttl: tuple[int] | None = (self.con.execute(query, args)).fetchone()
            if not ttl:
                return False
            return ttl[0] >= self.now_edt_timestamp()
        query = """
            SELECT time_to_live FROM option_chain_sync
            WHERE symbol = :symbol
        """
        args = {"symbol": option_request.symbol}
        ttl: tuple[int] | None = (self.con.execute(query, args)).fetchone()
        if not ttl:
            return False
        return ttl[0] >= self.now_edt_timestamp()
