from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Callable, Literal
from robinhood.api_dataclasses import FullQuote, OptionChain, OptionInstrument
from .db_schema import (
    EXPIRATION_DATES_TABLE,
    MAIN_TABLE,
    OPTION_IDS_TABLE,
)

DB_PATH = Path(__file__).resolve().parents[1] / "robinhoodapi.db"


def db_event_queue(func: Callable, *args, **kwargs) -> None:
    func(*args, kwargs=kwargs)


def init_db(prune: bool = False) -> None:
    with sqlite3.connect(DB_PATH) as con:
        con.execute(MAIN_TABLE)
        con.execute(OPTION_IDS_TABLE)
        con.execute(EXPIRATION_DATES_TABLE)
        if prune:
            ...
        # prune old opt data
        con.commit()


def get_option_greeks_at_strike(
    symbol: str,
    strike_price: float,
    option_type: Literal["call", "put", "both"],
    exp_date: str
)-> list[str] | None:
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        query = """
            SELECT exp_date FROM expiration_dates
            WHERE symbol = :symbol AND exp_date = :exp_date
        """
        args = {"symbol": symbol, "exp_date" : exp_date}
        con.execute(query, args)
        dates: list[str] | None = cur.fetchall()
        if not dates:
            return None
        query = """
            SELECT option_id FROM option_ids WHERE strike_price = :strike_price
            AND exp_date = :expiration_dates
        """
        args: dict[str,str|float] = {"strike_price" : strike_price}
        if option_type != "both":
            query += " AND option_type = :option_type"
            args["option_type"] = option_type
        list_args = [args for d in dates]
        con.execute(query, args)
        cur.fetchall()

def add_symbol(option_chain: OptionChain) -> None:
    """Inputs stock information into main_stock_info and expiration_dates"""
    with sqlite3.connect(DB_PATH) as con:
        query = """
            INSERT OR IGNORE INTO main_stock_info (symbol, chain_id)
            VALUES (:symbol, :chain_id);
        """
        args = {"symbol": option_chain.symbol, "chain_id": option_chain.id}
        con.execute(query, args)
        query = """
            INSERT OR IGNORE INTO expiration_dates (symbol, exp_date)
            VALUES (:symbol, :exp_date)
        """
        args = [{"exp_date": d} for d in option_chain.expiration_dates]
        con.executemany(query, args)
        con.commit()


def add_options(options: list[OptionInstrument]):
    """Inserts option id data into option_ids table"""
    with sqlite3.connect(DB_PATH) as con:
        query = """
            INSERT OR IGNORE INTO option_ids (option_id, strike_price, exp_date, option_type, symbol)
            VALUES (:option_id, :strike_price, :exp_date, :option_type, :symbol)
        """
        args = [
            {
                "option_id": o.id,
                "strike_price": o.strike_price,
                "exp_date": o.expiration_date,
                "option_type": o.type,
                "symbol": o.chain_symbol,
            }
            for o in options
        ]
        con.executemany(query, args)
        con.commit()


# Clean up old option expiration dates, timezones ?
def clean_up_db(delete_option_greeks: bool = False) -> None:
    with sqlite3.connect(DB_PATH) as con:
        query = """
            DELETE FROM expiration_dates
            DELETE FROM option_ids
        """
        del_query = ""
        query += del_query if delete_option_greeks else ""
