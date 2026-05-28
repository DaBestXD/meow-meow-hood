# Examples

This page shows common workflows for the sync and async clients.

## Before You Start

These examples assume one of the following is true:

- you are already logged in to Robinhood in a local Chrome or Firefox profile
- you plan to pass an `access_token` yourself

When `extract_token=True` (the default), the client checks local browser storage
for a valid session token. Use a context manager when possible so the HTTP
session and SQLite cache close automatically.

## Create A Sync Client

```python
from robinhood import Robinhood

with Robinhood() as rh:
    print("Client is ready")
```

This creates a `Robinhood` client with browser token discovery and local cache
support enabled by default.

## Create An Async Client

```python
import asyncio

from robinhood import AsyncRobinhood


async def main() -> None:
    async with AsyncRobinhood() as rh:
        quote = await rh.get_stock_quotes("SPY")
        if quote is not None:
            print(quote.ask_price)


asyncio.run(main())
```

`AsyncRobinhood` exposes the same public workflows as `Robinhood`, but its
methods must be awaited.

## Create A Client Without A Context Manager

```python
from robinhood import Robinhood

rh = Robinhood()
try:
    quote = rh.get_stock_quotes("SPY")
    if quote is not None:
        print(quote)
finally:
    rh.close()
```

`get_stock_quotes("SPY")` returns an `InstrumentQuote` object or `None`.

## Use A Manual Access Token

```python
from robinhood import Robinhood

with Robinhood(extract_token=False, access_token="...") as rh:
    quote = rh.get_stock_quotes("SPY")
    if quote is not None:
        print(quote.last_trade_price)
```

This skips browser token extraction and uses the supplied bearer token.

## Store Config Files In A Custom Directory

```python
from pathlib import Path

from robinhood import Robinhood

with Robinhood(config_path=Path.home() / ".config") as rh:
    quote = rh.get_stock_quotes("SPY")
    if quote is not None:
        print(quote.symbol)
```

The client stores `.env` and `meow-meow-hood.db` inside a `.meow-meow-config`
directory under the provided path.

## Disable The Local Cache

```python
from robinhood import Robinhood

with Robinhood(enable_cache=False) as rh:
    quote = rh.get_stock_quotes("SPY")
    if quote is not None:
        print(quote.bid_price, quote.ask_price)
```

This avoids opening the local SQLite cache while still using the HTTP client.
It is highly recommended to use the local cache you will avoid most rate limits
that would occur without the local cache.

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

For a single symbol, `get_stock_quotes()` returns one `InstrumentQuote` or `None`.

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

## Look Up Index Metadata

```python
from robinhood import Robinhood

with Robinhood() as rh:
    index = rh.get_index_info("SPX")
    if index is not None:
        print(index.symbol)
        print(index.simple_name)
```

For a single symbol, `get_index_info()` returns one `IndexInfo` or `None`.

## Check An Index Quote

```python
from robinhood import Robinhood

with Robinhood() as rh:
    quote = rh.get_index_quotes("SPX")
    if quote is not None:
        print(quote.symbol)
        print(quote.value)
```

For a single symbol, `get_index_quotes()` returns one `IndexQuote` or `None`.

## View A Stock Order Book

```python
from robinhood import Robinhood

with Robinhood() as rh:
    orderbook = rh.get_orderbook("SPY")
    if orderbook is not None:
        print(orderbook.bids[0])
        print(orderbook.asks[0])
```

`get_orderbook()` returns an `OrderBook` with bids and asks, or `None`.

## Get Expiration Dates

```python
from robinhood import Robinhood

with Robinhood() as rh:
    dates = rh.get_expiration_dates("SPY")
    if dates:
        print(dates[0])
        print(dates[:3])
```

This returns a `list[str]` of expiration dates in `YYYY-MM-DD` format, or
`None`.

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

## View Option Chain Metadata

```python
from robinhood import Robinhood

with Robinhood() as rh:
    chain = rh.get_option_chain_data("SPY")
    if chain is not None:
        print(chain.id)
        print(chain.symbol)
        print(chain.expiration_dates[:3])
```

For a single symbol, `get_option_chain_data()` returns one `OptionChain` or
`None`.

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

This returns option greek data grouped by each input request.

## Fetch Option Greeks Without Cache Lookups

```python
from robinhood import OptionRequest, Robinhood

with Robinhood() as rh:
    dates = rh.get_expiration_dates("SPY")
    if not dates:
        raise RuntimeError("No expiration dates returned for SPY")

    request = OptionRequest(symbol="SPY", exp_date=dates[0], option_type="call")
    greeks_by_request = rh.no_db_option_greeks_batch_request([request])
    print(len(greeks_by_request[request]))
```

This returns a `dict[OptionRequest, list[OptionGreekData]]` without using cached
option instrument ids.

## Use The Local Cache

Cache support is enabled by default.

```python
from robinhood import OptionRequest, Robinhood

with Robinhood(enable_cache=True) as rh:
    dates = rh.get_expiration_dates("SPY")
    if not dates:
        raise RuntimeError("No expiration dates returned for SPY")

    request = OptionRequest(symbol="SPY", exp_date=dates[0])
    greeks_by_request = rh.get_option_greeks_batch_request(request)
    print(len(greeks_by_request[request]))
```

Broad requests will be cached for increased speed.

- `OptionRequest(symbol="SPY")`
- `OptionRequest(symbol="SPY", exp_date="2026-04-17")`

## View Futures Product Metadata

```python
from robinhood import Robinhood

with Robinhood() as rh:
    product = rh.get_future_info("/ES")
    if product is not None:
        print(product.id)
        print(product.displaySymbol)
```

`get_future_info()` returns one `FuturesProduct` for a root symbol, or `None`.

## View Active Futures Contracts

```python
from robinhood import Robinhood

with Robinhood() as rh:
    product = rh.get_future_info("/ES")
    if product is not None:
        contracts = rh.get_active_contracts_for_id(product.id)
        if contracts:
            print(contracts[0].id)
            print(contracts[0].displaySymbol)
```

`get_active_contracts_for_id()` returns a sorted `list[FuturesContract]` or
`None`.

## Fetch A Futures Quote

```python
from robinhood import Robinhood

with Robinhood() as rh:
    product = rh.get_future_info("/ES")
    if product is not None:
        quote = rh.get_future_quote(product.activeFuturesContractId)
        if quote is not None:
            print(quote.symbol)
            print(quote.last_trade_price)
```

For a single contract id, `get_future_quote()` returns one `FuturesQuote` or
`None`.

## View Current Stock Positions

```python
from robinhood import Robinhood

with Robinhood() as rh:
    positions = rh.get_account_stock_positions()
    if positions:
        for position in positions:
            print(position.symbol, position.quantity)
```

This returns a `list[StockPosition]` or `None`.

## View Current Option Positions

```python
from robinhood import Robinhood

with Robinhood() as rh:
    positions = rh.get_account_option_positions()
    if positions:
        for position in positions:
            print(position.chain_symbol, position.quantity)
```

This returns a `list[OptionPosition]` or `None`.

## Review Stock Order History

```python
from robinhood import Robinhood

with Robinhood() as rh:
    orders = rh.get_stock_order_history()
    if orders:
        for order in orders[:5]:
            print(order.symbol, order.side, order.state)
```

This returns a `list[StockOrder]` or `None`.

## Review Option Order History

```python
from robinhood import Robinhood

with Robinhood() as rh:
    orders = rh.get_option_order_history()
    if orders:
        for order in orders[:5]:
            print(order.chain_symbol, order.direction, order.state)
```

This returns a `list[OptionOrderHistory]` or `None`.

## View Your Watchlists

```python
from robinhood import Robinhood

with Robinhood() as rh:
    watchlists = rh.get_watchlists()
    if watchlists:
        for watchlist in watchlists:
            print(watchlist.name, len(watchlist.items))
```

This returns a `list[WatchList]` or `None`.

## Refresh A Saved Browser Token

```python
from robinhood import Robinhood

with Robinhood() as rh:
    rh.refresh_access_token()
    quote = rh.get_stock_quotes("SPY")
    if quote is not None:
        print(quote.symbol)
```

`refresh_access_token()` updates the active client token when a refreshed token
is available. This function needs to be tested.

## Run A Read-Only Cache Query

```python
from robinhood import Robinhood

with Robinhood(enable_cache=True) as rh:
    rows = rh.execute_custom_sql(
        "SELECT symbol, exp_date FROM expiration_dates WHERE symbol = :symbol",
        {"symbol": "SPY"},
    )
    print(rows or [])
```

`execute_custom_sql()` returns a list of SQLite rows or `None` when the cache is
disabled.

## Place A Limit Stock Order

```python
from robinhood import Robinhood

with Robinhood() as rh:
    response = rh.place_limit_stock_order(
        symbol="SPY",
        side="buy",
        price=500.00,
        quantity=1,
        time_in_force="gfd",
    )
    if response is not None:
        print(response.id, response.state)
```

`place_limit_stock_order()` returns a `StockOrderResponse` or `None`.

## Place A Market Stock Order

```python
from robinhood import Robinhood

with Robinhood() as rh:
    response = rh.place_market_stock_order(
        symbol="SPY",
        side="buy",
        dollar_based_amount=10.00,
        time_in_force="gfd",
    )
    if response is not None:
        print(response.id, response.state)
```

`place_market_stock_order()` returns a `StockOrderResponse` or `None`.

## Place A Single-Leg Option Order

```python
from robinhood import OptionRequest, Robinhood

with Robinhood() as rh:
    leg = OptionRequest(
        symbol="SPY",
        exp_date="2026-04-17",
        option_type="call",
        strike_price=500.0,
        position_effect="open",
        side="buy",
    )
    response = rh.place_option_order(
        option_legs=[leg],
        order_type="debit",
        quantity=1,
        limit_price=1.50,
    )
    if response is not None:
        print(response.id, response.strategy)
```

`place_option_order()` returns an `OptionOrderResponse` or `None`.

## Place A Two-Leg Option Spread

```python
from robinhood import OptionRequest, Robinhood

with Robinhood() as rh:
    long_call = OptionRequest(
        symbol="SPY",
        exp_date="2026-04-17",
        option_type="call",
        strike_price=500.0,
        position_effect="open",
        side="buy",
    )
    short_call = OptionRequest(
        symbol="SPY",
        exp_date="2026-04-17",
        option_type="call",
        strike_price=505.0,
        position_effect="open",
        side="sell",
    )
    response = rh.place_option_order(
        option_legs=[long_call, short_call],
        order_type="debit",
        quantity=1,
        limit_price=1.25,
    )
    if response is not None:
        print(response.id, response.strategy)
```

Multi-leg option orders return an `OptionOrderResponse` or `None`.

## Place A Multi-Leg Ratio Order

```python
from robinhood import OptionRequest, Robinhood

with Robinhood() as rh:
    leg1 = OptionRequest(
        symbol="SPY",
        exp_date="2026-04-17",
        option_type="call",
        strike_price=500.0,
        position_effect="open",
        side="buy",
    )
    leg2 = OptionRequest(
        symbol="SPY",
        exp_date="2026-04-17",
        option_type="call",
        strike_price=510.0,
        position_effect="open",
        side="sell",
    )

    option_legs = (leg1 * 2) + (leg2 * 1)
    response = rh.place_option_order(
        option_legs=option_legs,
        order_type="debit",
        quantity=1,
        limit_price=2.00,
    )
    if response is not None:
        print(response.id, response.strategy)
```

Ratio option orders use repeated `OptionRequest` legs and return an
`OptionOrderResponse` or `None`.
