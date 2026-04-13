# Examples

This page shows the most common things you can do with the library.

## Before You Start

These examples assume one of the following is true:

- you are already logged in to Robinhood in a local Chrome or Firefox profile
- you plan to pass an `access_token` yourself

When `extract_token=True` (the default), the client automatically checks Chrome
first and then Firefox for a valid local session token.

Imports used in the examples:

```python
from robinhood import OptionRequest, Robinhood
```

## Create A Client

Use a context manager when possible so the HTTP session and SQLite cache are
closed automatically.

```python
from robinhood import Robinhood

with Robinhood() as rh:
    print("Client is ready")
```

This creates a `Robinhood` client with automatic browser token discovery and
local cache support enabled by default.

## Create A Client Without A Context Manager

If you do not use `with`, call `close()` when you are done.

```python
from robinhood import Robinhood

rh = Robinhood()
quote = rh.get_stock_quotes("SPY")
print(quote)
rh.close()
```

`get_stock_quotes("SPY")` returns a `FullQuote` object or `None`.

## Fetch A Stock Quote

```python
from robinhood import Robinhood

with Robinhood() as rh:
    quote = rh.get_stock_quotes("SPY")
    if quote is not None:
        print(quote.ask_price)
        print(quote.bid_price)
        print(quote.last_trade_price)
```

For a single symbol, `get_stock_quotes()` returns one `FullQuote`.

## Fetch Stock Info

```python
from robinhood import Robinhood

with Robinhood() as rh:
    stock = rh.get_stock_info("SPY")
    if stock is not None:
        print(stock.symbol)
        print(stock.name)
        print(stock.tradable_chain_id)
```

`get_stock_info("SPY")` returns one `StockInfo` object or `None`.

## Get Expiration Dates

```python
from robinhood import Robinhood

with Robinhood() as rh:
    dates = rh.get_expiration_dates("SPY")
    if dates:
        print(dates[0])
        print(dates[:3])
```

This returns a `list[str]` of expiration dates in `YYYY-MM-DD` format.

## Get Strike Prices For One Expiration

```python
from robinhood import Robinhood

with Robinhood() as rh:
    dates = rh.get_expiration_dates("SPY")
    if not dates:
        raise RuntimeError("No expiration dates returned for SPY")

    strikes_by_request = rh.get_strike_prices(symbol="SPY", exp_date=dates[0])
    for option_request, strikes in strikes_by_request.items():
        print(option_request.option_type, strikes[:5])
```

This returns a `dict[OptionRequest, list[float]]` with separate keys for the
call side and put side of the selected expiration date.

## Build An OptionRequest

`OptionRequest` is the main filter object for option data.

```python
from robinhood import OptionRequest

request = OptionRequest(
    symbol="SPY",
    exp_date="2026-04-17",
    option_type="call",
    strike_price=500.0,
)

print(request)
```

You can make the request broad or narrow:

- `OptionRequest(symbol="SPY")` matches every cached or live option for `SPY`
- `OptionRequest(symbol="SPY", exp_date="2026-04-17")` matches one expiration
- adding `option_type` or `strike_price` narrows the result further

## Request Option Greeks For One OptionRequest

```python
from robinhood import OptionRequest, Robinhood

with Robinhood() as rh:
    dates = rh.get_expiration_dates("SPY")
    if not dates:
        raise RuntimeError("No expiration dates returned for SPY")

    request = OptionRequest(symbol="SPY", exp_date=dates[0])
    greeks_by_request = rh.get_option_greeks_batch_request(request)

    for greek in greeks_by_request[request][:3]:
        print(greek.symbol, greek.delta, greek.mark_price)
```

This returns a `dict[OptionRequest, list[OptionGreekData]]`.

## Request Option Greeks For Multiple Requests

```python
from robinhood import OptionRequest, Robinhood

with Robinhood() as rh:
    spy_dates = rh.get_expiration_dates("SPY")
    qqq_dates = rh.get_expiration_dates("QQQ")
    if not spy_dates or not qqq_dates:
        raise RuntimeError("Missing expiration dates for one of the symbols")

    requests = [
        OptionRequest(symbol="SPY", exp_date=spy_dates[0], option_type="put"),
        OptionRequest(symbol="QQQ", exp_date=qqq_dates[0], option_type="call"),
    ]

    greeks_by_request = rh.get_option_greeks_batch_request(requests)

    for option_request, greeks in greeks_by_request.items():
        print(option_request, len(greeks))
```

This is useful when you want to fetch several symbols or expirations in one
call and then inspect the result by request.

## Use The Local Cache

Cache support is enabled by default. A broad request can populate the local
SQLite cache and make later calls faster for the rest of the trading day.

```python
from robinhood import OptionRequest, Robinhood

with Robinhood(enable_cache=True) as rh:
    request = OptionRequest(symbol="SPY", exp_date="2026-04-17")
    greeks_by_request = rh.get_option_greeks_batch_request(request)
    print(len(greeks_by_request[request]))
```

Broad requests are the most cache-friendly:

- `OptionRequest(symbol="SPY")`
- `OptionRequest(symbol="SPY", exp_date="2026-04-17")`

Requests narrowed by `option_type` or `strike_price` can still use cached
instrument ids, but they do not create their own sync rows yet.
