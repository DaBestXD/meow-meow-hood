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
