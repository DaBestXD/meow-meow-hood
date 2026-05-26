import uuid
from typing import overload


@overload
def uppercase_input(symbol: str) -> str: ...


@overload
def uppercase_input(symbol: list[str]) -> list[str]: ...


def uppercase_input(symbol: str | list[str]) -> str | list[str]:
    if isinstance(symbol, str):
        return symbol.upper()
    if isinstance(symbol, list):
        return [s.upper() for s in symbol]
    raise ValueError(f"incorrect type received: {type(symbol)}")


@overload
def normalize_future_input(symbol: str) -> str: ...
@overload
def normalize_future_input(symbol: list[str]) -> list[str]: ...


def normalize_future_input(symbol: str | list[str]) -> str | list[str]:
    if not symbol:
        raise ValueError("symbol cannot be none")
    if isinstance(symbol, str):
        symbol = "/" + symbol if symbol[0] != "/" else symbol
        return symbol.upper()
    if isinstance(symbol, list):
        return_list: list[str] = []
        for s in symbol:
            if not s:
                raise ValueError("symbol cannot be none")
            s = "/" + s if s[0] != "/" else s
            return_list.append(s.upper())
        return return_list
    raise ValueError(f"incorrect type received: {type(symbol)}")


def check_if_uuid4(input: str | list[str]) -> bool:
    try:
        if isinstance(input, list):
            for i in input:
                uuid.UUID(i, version=4)
        if isinstance(input, str):
            uuid.UUID(input, version=4)
        return True
    except ValueError:
        return False


@overload
def normalize_currency_input(symbols: list[str]) -> list[str]: ...
@overload
def normalize_currency_input(symbols: str) -> str: ...


def normalize_currency_input(
    symbols: str | list[str], currency_code: str = "USD"
) -> str | list[str]:
    if isinstance(symbols, str):
        symbols = symbols.upper().strip("-")
        if not symbols.endswith(currency_code):
            symbols = symbols + currency_code
        return symbols
    if isinstance(symbols, list):
        return_val: list[str] = []
        for s in symbols:
            s = s.upper().strip("-")
            if not s.endswith(currency_code):
                s = s + currency_code
            return_val.append(s)
        return return_val
    raise ValueError(f"incorrect type received: {type(symbols)}")
