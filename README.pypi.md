# Meow-Meow-Hood API

A Python wrapper around Robinhood's private API with a focus on option market
data, local option metadata caching, and simple sync or async clients.

## Installation

Requires Python 3.11+

```bash
uv add meow-meow-hood
# or
pip install meow-meow-hood
```

Import from the `robinhood` package:

```python
from robinhood import AsyncRobinhood, Firefox, OptionRequest, Robinhood
```

## Authentication And Config

By default, `Robinhood()` reads a locally stored Robinhood browser token from
your default Chrome profile. You must already be logged in to Robinhood in the
selected local browser profile.

The client creates a config directory named `.meow-meow-config` under
`config_path`, which defaults to the current working directory. When
`enable_cache=True`, the local SQLite option metadata cache is stored there as
`meow-meow-hood.db`.

Authentication setup options:

```python
from pathlib import Path

from robinhood import Firefox, Robinhood

# Use Firefox instead of the default Chrome profile.
with Robinhood(browser_type=Firefox) as rh:
    quote = rh.get_stock_quotes("SPY")

# Store cache files outside the current working directory.
with Robinhood(config_path=Path.home() / ".config") as rh:
    quote = rh.get_stock_quotes("SPY")
```

`refresh_access_token()` can briefly open the selected browser when local auth
state is stale. Use `auto_open_browser=False` when that behavior is not desired.

```python
from robinhood import Robinhood

with Robinhood() as rh:
    rh.refresh_access_token(auto_open_browser=False)
    print(rh.get_access_token_expiry())
```

## Quickstart

```python
from robinhood import OptionRequest, Robinhood

with Robinhood() as rh:
    quote = rh.get_stock_quotes("SPY")
    if quote is not None:
        print(quote.bid_price, quote.ask_price)

    dates = rh.get_expiration_dates("SPY")
    if not dates:
        raise RuntimeError("No SPY expiration dates returned")

    request = OptionRequest(symbol="SPY", exp_date=dates[0])
    greeks_by_request = rh.get_option_greeks_batch_request(request)

    for greek in greeks_by_request[request][:3]:
        print(greek.symbol, greek.delta, greek.mark_price)
```

JSON responses are normalized into dataclasses such as `InstrumentQuote`,
`OptionChain`, `OptionGreekData`, `StockPosition`, and `WatchList`.

## Local Caching

The local SQLite cache stores option chain metadata, expiration dates, option
instrument ids, and sync rows. It reduces the number of Robinhood API calls
needed before fetching live option greek data.

Cache TTLs expire at the next trading day open, `9:30 AM America/New_York`.
Broad option requests are the most cache-friendly:

- `OptionRequest(symbol="SPY")`
- `OptionRequest(symbol="SPY", exp_date="2026-04-17")`

```python
from robinhood import OptionRequest, Robinhood

with Robinhood(enable_cache=True) as rh:
    dates = rh.get_expiration_dates("SPY")
    if not dates:
        raise RuntimeError("No SPY expiration dates returned")

    request = OptionRequest(symbol="SPY", exp_date=dates[0])
    greeks_by_request = rh.get_option_greeks_batch_request(request)
    print(len(greeks_by_request[request]))
```

See [Database Schema](https://github.com/DaBestXD/meow-meow-hood/blob/main/docs/db_schema.md)
and [Design Notes](https://github.com/DaBestXD/meow-meow-hood/blob/main/docs/design_notes.md)
for cache internals.

## Return Values And Errors

Many read methods return `None` when Robinhood returns no usable data. Batch
option methods generally return a dictionary keyed by `OptionRequest`, with an
empty list for requests that could not be resolved.

HTTP behavior to expect:

- `401` and `403` raise `AuthenticationError` with an invalid-token message.
- `429` and `5xx` currently raise `NotImplementedError`.
- Other unexpected statuses are logged by the HTTP layer.

Trading helpers can raise package errors such as `MalformedOrderError`,
`InstrumentNotFoundError`, or `AccountIdNotFoundError` when an order cannot be
validated locally before submission.

## More Examples

Beginner and workflow examples live in
[docs/examples.md](https://github.com/DaBestXD/meow-meow-hood/blob/main/docs/examples.md).

```bash
uv run python docs/examples/sample_option_chain.py
# or
python docs/examples/sample_option_chain.py
```

## API Reference

See [docs/api_reference.md](https://github.com/DaBestXD/meow-meow-hood/blob/main/docs/api_reference.md)
for a compact overview of the public clients, dataclasses, return types, and
setup parameters.

## TODO Log

See [docs/todo.md](https://github.com/DaBestXD/meow-meow-hood/blob/main/docs/todo.md)
for planned features.
