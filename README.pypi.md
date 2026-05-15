# Meow-Meow-Hood API

A Python wrapper around Robinhood's private API with a focus on option market
data, local option metadata caching, and simple sync or async clients.

## Installation

Requires Python 3.11 or newer.

```bash
uv add meow-meow-hood
# or
pip install meow-meow-hood
```

Import from the `robinhood` package:

```python
from robinhood import OptionRequest, Robinhood
```

## Authentication And Config

By default, `Robinhood()` tries to find a locally stored Robinhood browser token.
You must already be logged in to Robinhood in a local Chrome or Firefox profile.

The client creates a config directory named `.meow-meow-config` under
`config_path`, which defaults to the current working directory. Generated files
are stored there:

- `.env` stores `BEARER_TOKEN` and `ACCOUNT_NUMBER` when token extraction writes
  credentials.
- `meow-meow-hood.db` stores the local SQLite option metadata cache when
  `enable_cache=True`.

Useful setup options:

```python
from pathlib import Path

from robinhood import Robinhood

with Robinhood(extract_token=False, access_token="...") as rh:
    quote = rh.get_stock_quotes("SPY")

with Robinhood(config_path=Path.home() / ".config") as rh:
    quote = rh.get_stock_quotes("SPY")
```

If a saved token is rejected and `open_browser=True`, the refresh flow may open
Chrome and Firefox briefly to refresh local auth state. This can close existing
browser windows, so set `open_browser=False` when that behavior is not desired.

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

JSON responses are normalized into dataclasses such as `FullQuote`,
`OptionChain`, `OptionGreekData`, `StockPosition`, and `WatchList`.

## Local Caching

The local SQLite cache stores option chain metadata, expiration dates, option
instrument ids, and sync rows. It reduces the number of Robinhood API calls
needed before fetching live option greek data.

Cache TTLs expire at the next trading day open, `9:30 AM America/New_York`.
Broad option requests are the most cache-friendly:

- `OptionRequest(symbol="SPY")`
- `OptionRequest(symbol="SPY", exp_date="2026-04-17")`

Requests narrowed by `option_type` or `strike_price` can reuse cached
instrument ids, but they do not create their own sync rows yet.

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

## Return Values And Errors

Many read methods return `None` when Robinhood returns no usable data. Batch
option methods generally return a dictionary keyed by `OptionRequest`, with an
empty list for requests that could not be resolved.

HTTP behavior to expect:

- `401` and `403` raise `RuntimeError` with an invalid-token message.
- `429` and `5xx` currently raise `NotImplementedError`.
- Other unexpected statuses are logged by the HTTP layer.

Trading helpers can raise package errors such as `MalformedOrderError`,
`InstruemtNotFoundError`, or `AccountIdNotFoundError` when an order cannot be
validated locally before submission.

## More Documentation

- Examples: `docs/examples.md`
- API reference: `docs/api_reference.md`
- Cache schema: `docs/db_schema.md`
- Design notes: `docs/design_notes.md`
- TODO log: `docs/todo.md`

## Development

```bash
python -m unittest discover -s tests
ruff check .
ruff format --check .
pyright
python -m benchmarks.benchmark_api_requests
```

## License And Versioning

The project is MIT licensed. The current package version is declared in
`pyproject.toml`.
