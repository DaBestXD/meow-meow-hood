import argparse
import time
from bisect import bisect_left

from robinhood import OptionRequest, Robinhood
from robinhood.api_dataclasses import OptionGreekData


def cmd_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(__name__)
    parser.add_argument("-s", "--symbol", type=str)
    parser.add_argument("-d", "--date", type=int)
    parser.add_argument("-r", "--range", type=int)
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
    main_loop(rh, [*strikes.values()], symbol, int(args.range), selected_date)


def placeholder(
    quote_price: float,
    strikes: list[float],
    symbol: str,
    date: str,
    strike_range: int,
) -> tuple[list[OptionRequest], list[OptionRequest]]:
    idx = bisect_left(strikes, quote_price)
    option_slice = slice(idx - strike_range, idx + strike_range)
    call_side = [
        OptionRequest(
            symbol=symbol, exp_date=date, option_type="call", strike_price=s
        )
        for s in strikes[option_slice]
    ]
    put_side = [
        OptionRequest(
            symbol=symbol, exp_date=date, option_type="put", strike_price=s
        )
        for s in strikes[option_slice]
    ]
    return call_side, put_side


def format_text(op_req: OptionRequest, op_greek: OptionGreekData) -> str:
    vals: list[str] = [
        f"{op_req.strike_price:.1f}\t",
        f"{op_greek.bid_price:.2f}\t",
        f"{op_greek.ask_price:.2f}\t",
        f"{(op_greek.implied_volatility * 100):.2f}%\t",
        f"{op_greek.open_interest}\t",
    ]
    return " ".join(vals)


def main_loop(
    rh: Robinhood,
    strikes: list[list[float]],
    symbol: str,
    strike_range: int,
    date: str,
) -> None:
    try:
        print("\033[2J\033[H", end="")
        while True:
            quote = rh.get_stock_quotes(symbol)
            if not quote:
                return None
            call_side, put_side = placeholder(
                quote.last_trade_price,
                strikes[0],
                symbol,
                date,
                strike_range,
            )
            total_list = call_side + put_side
            vals = rh.get_option_greeks_batch_request(total_list)
            print(f"{symbol} price: {quote.last_trade_price} exp_date: {date}")
            print("Call\t Bid\t Ask\t IV\t OI\t Put\t Bid\t Ask\t IV\t OI")
            for i in range(len(call_side)):
                call_req, put_req = call_side[i], put_side[i]
                call, put = vals[call_req][0], vals[put_req][0]
                print(
                    f"{format_text(call_req, call)} {format_text(put_req, put)}"
                )
            time.sleep(1)
            print("\033[2J\033[H", end="")
    except KeyboardInterrupt:
        rh.close()
        print("Exiting...")


if __name__ == "__main__":
    main()
