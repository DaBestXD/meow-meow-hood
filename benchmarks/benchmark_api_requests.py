import logging
from decimal import Decimal
from pathlib import Path

from robinhood import OptionRequest, Robinhood

from .timing_helper import inline_timer, temp_cache

SYMBOLS: list[str] = [
    "SPY",
    "TSLA",
    "QQQ",
    "NVDA",
    "GOOG",
    "MSFT",
    "AMZN",
    "TSM",
    "META",
    "JPM",
]


OFF = 0
LOW = 1
MEDIUM = 2
HIGH = 3


def _run_helper(
    symbols: list[str],
    temp_path: Path,
    *,
    cache_enabled: bool,
    runs: int,
    verbose_level: int,
    logging_level: int = logging.INFO,
    title: str,
) -> Decimal:
    rh = Robinhood(
        config_path=temp_path,
        enable_cache=cache_enabled,
        logging_level=logging_level,
    )
    total_time = Decimal(0)
    dates_tt = Decimal(0)
    strike_tt = Decimal(0)
    option_tt = Decimal(0)
    if cache_enabled:
        for s in symbols:
            dates = rh.get_expiration_dates(s)
            if not dates:
                continue
            rh.get_strike_prices(symbol=s, exp_date=dates[1])
    for _ in range(runs):
        options_reqs: list[OptionRequest] = []
        for s in symbols:
            dates_time, dates = inline_timer(
                rh.get_expiration_dates,
                verbose=(verbose_level >= HIGH),
                symbol=s,
            )
            if not dates:
                continue
            strike_time, _ = inline_timer(
                rh.get_strike_prices,
                verbose=(verbose_level >= HIGH),
                symbol=s,
                exp_date=dates[1],
            )
            options_reqs.append(OptionRequest(symbol=s, exp_date=dates[1]))
            total_time += strike_time
            total_time += dates_time
            dates_tt += dates_time
            strike_tt += strike_time
        option_time, _ = inline_timer(
            rh.get_option_greeks_batch_request,
            verbose=(verbose_level >= HIGH),
            option_requests=options_reqs,
        )
        option_tt += option_time
        total_time += option_time
    rh.close()
    title = "~~" + title + "~~"
    if verbose_level >= LOW:
        print(title)
    if verbose_level >= MEDIUM:
        date_avg = dates_tt / (runs * len(symbols))
        strike_avg = strike_tt / (runs * len(symbols))
        option_avg = option_tt / (runs)
        print(f"Averge get_expiration_dates time: {(date_avg):.5f}s")
        print(f"Averge get_strike_prices time: {(strike_avg):.5f}s")
        print(
            f"Average get_option_greeks_batch_request time:{(option_avg):.5f}s"
        )
    if verbose_level >= LOW:
        print(f"Average time per run({runs} runs): {(total_time / runs):.5f}s")
        print("~" * len(title))
    return total_time / runs


@temp_cache
def bench_mark_main(
    temp_path: Path,
    runs: int,
    verbose_level: int,
    logging_level: int,
) -> Decimal:
    """
    Terrible placeholder for benchmarking
    """
    total_time = Decimal(0)
    no_cache_run = _run_helper(
        SYMBOLS,
        temp_path,
        cache_enabled=False,
        runs=runs,
        verbose_level=verbose_level,
        logging_level=logging_level,
        title="Cold_Cache_Run",
    )
    warm_cache_time = _run_helper(
        SYMBOLS,
        temp_path,
        cache_enabled=True,
        runs=runs,
        verbose_level=verbose_level,
        logging_level=logging_level,
        title="Warm_Cache_Run",
    )
    total_time += no_cache_run + warm_cache_time
    title = "~~Cold_Cache--vs--Warm_Cache~~"
    print(title)
    time_diff = no_cache_run - warm_cache_time
    diff_div = (time_diff / no_cache_run) * 100
    print(f"Number of symbols: {len(SYMBOLS)}")
    print(f"No_cache_run time per run({runs} runs): {(no_cache_run):.5}s")
    print(f"Warm_Cache time per run({runs} runs): {(warm_cache_time):.5}s")
    print(f"No_cache_run vs Warm_Cache diff({runs} runs): {(diff_div):.2f}%")
    print("~" * len(title))
    return total_time


if __name__ == "__main__":
    total_run_time, _ = inline_timer(
        bench_mark_main,
        runs=10,
        verbose_level=MEDIUM,
        logging_level=logging.CRITICAL,
    )
    print(f"Total run time: {(total_run_time):.5f} seconds")
