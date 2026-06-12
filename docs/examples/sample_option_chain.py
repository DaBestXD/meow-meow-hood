import argparse
import time
from bisect import bisect_left

from robinhood import OptionGreekData, OptionRequest, Robinhood, RobinhoodError
from robinhood.robinhood_errors import EndpointNotFoundError


def cmd_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(__name__)
    parser.add_argument("-s", "--symbol", type=str, default="SPY")
    parser.add_argument("-d", "--date", type=int, default=0)
    parser.add_argument("-r", "--range", type=int, default=10)
    parser.add_argument("-de", "--delay", type=float, default=0.25)
    return parser.parse_args()


def return_date(rh: Robinhood, symbol: str, selection: int) -> str:
    dates = rh.get_expiration_dates(symbol)
    if not dates:
        raise ValueError("Dates returned none")
    return dates[selection]


def main() -> None:
    args = cmd_args()
    rh = Robinhood()
    symbol = str(args.symbol).upper()
    selected_date = return_date(rh, symbol, int(args.date))
    strikes = rh.get_strike_prices(symbol=symbol, exp_date=selected_date)
    if strikes is None:
        raise ValueError("Strikes returned none")
    if isinstance(strikes, tuple):
        strike_lists = strikes
    else:
        strike_lists = (strikes, strikes)
    main_loop(
        rh,
        strike_lists,
        symbol,
        int(args.range),
        selected_date,
        args.delay,
    )


def option_range(
    quote_price: float,
    call_strikes: list[float],
    put_strikes: list[float],
    symbol: str,
    date: str,
    strike_range: int,
) -> tuple[list[OptionRequest], list[OptionRequest]]:
    call_idx = bisect_left(call_strikes, quote_price)
    put_idx = bisect_left(put_strikes, quote_price)
    call_slice = slice(call_idx - strike_range, call_idx + strike_range)
    put_slice = slice(put_idx - strike_range, put_idx + strike_range)
    call_side = [
        OptionRequest(
            symbol=symbol, exp_date=date, option_type="call", strike_price=s
        )
        for s in call_strikes[call_slice]
    ]
    put_side = [
        OptionRequest(
            symbol=symbol, exp_date=date, option_type="put", strike_price=s
        )
        for s in put_strikes[put_slice]
    ]
    return call_side, put_side


def format_text(op_req: OptionRequest, op_greek: OptionGreekData) -> str:
    return (
        f"{op_req.strike_price:>8.1f} "
        f"{op_greek.bid_price:>8.2f} "
        f"{op_greek.ask_price:>8.2f} "
        f"{op_greek.implied_volatility:>8.2%} "
        f"{op_greek.volume:>10}"
    )


def main_loop(
    rh: Robinhood,
    strikes: tuple[list[float], list[float]],
    symbol: str,
    strike_range: int,
    date: str,
    delay: float,
) -> None:
    try:
        print("\033[2J\033[H", end="")
        while True:
            quote = rh.get_stock_quotes(symbol)
            if not quote:
                return None
            call_side, put_side = option_range(
                quote.last_trade_price,
                strikes[0],
                strikes[1],
                symbol,
                date,
                strike_range,
            )
            total_list = call_side + put_side
            vals = rh.get_option_greeks_batch_request(total_list)
            print(f"{symbol} price: {quote.last_trade_price} exp_date: {date}")
            print(f"{delay=}")
            print(
                f"{'Call':>8} {'Bid':>8} {'Ask':>8} {'IV':>8} {'Volume':>10}",
                f"{'Put':>8} {'Bid':>8} {'Ask':>8} {'IV':>8} {'Volume':>10}",
            )
            for call_req, put_req in zip(call_side, put_side, strict=False):
                call, put = vals[call_req][0], vals[put_req][0]
                print(
                    f"{format_text(call_req, call)} {format_text(put_req, put)}"
                )
            time.sleep(delay)
            print("\033[2J\033[H", end="")
    except (KeyboardInterrupt, RobinhoodError) as e:
        if isinstance(e, EndpointNotFoundError):
            print(e)
        rh.close()
        print("Exiting...")


if __name__ == "__main__":
    main()
