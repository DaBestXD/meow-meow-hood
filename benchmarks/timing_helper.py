import tempfile
import time
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from textwrap import dedent
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def inline_timer(
    func: Callable[P, R],
    verbose: bool = False,
    *args: P.args,
    **kwargs: P.kwargs,
) -> tuple[Decimal, R]:
    start = Decimal(time.perf_counter())
    result: R = func(*args, **kwargs)
    total_time = Decimal(time.perf_counter()) - start
    if verbose:
        print(
            dedent(f"""
                Took {(total_time):.5f} seconds
                Function: {func.__getattribute__("__name__")}""")
        )
    return total_time, result


def temp_cache(func) -> Callable:
    def wrapper(*args, **kwargs):
        with tempfile.TemporaryDirectory() as tmpdir:
            return func(Path(tmpdir), *args, **kwargs)

    return wrapper
