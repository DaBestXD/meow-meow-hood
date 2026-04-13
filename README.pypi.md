# Meow-Meow-Hood API

A Robinhood API wrapper for fast option market data

## Installation

`uv add meow-meow-hood`\
`pip install meow-meow-hood`

## Why?

If you're using Robinhood as a broker still...\
And if you want to view option market data at a reasonable speed.
This was made for fun.

## Authentication

Ensure you are logged in locally to Robinhood on either:

- Chrome
- Firefox

It works by extracting the locally stored access token from the browser folder.\
By default it will automatically try to extract the token, this can be disabled
on class creation.\
You will need to pass in the access token manually if extract_token is disabled.\
Config folder is created at the cwd labeled `.meow-meow-hood`.\
Ensure you select the correct browser on class creation current default is Chrome.\
Use either `Chrome()` or `Firefox()` for the `browser=` parameter.\
If cache enabled db file is placed inside this folder. Same for extract_token.

```python
Robinhood(extract_token=False, access_token="...")
```

## Usage

JSON responses are returned as named data classes for easier parsing.\
Examples: `FullQuote`, `OptionInstrument`, `OptionGreekData`, etc.\

```python
@dataclass(frozen=True, slots=True)
class FullQuote(ApiPayloadMixin):
    ask_price: float
    ask_size: int
    bid_price: float
    bid_size: int
    ...
```

(*Refer to robinhood/api_dataclasses.py
for full implementation details.*)

`OptionRequest` is the main class when requesting option data.

```python
OptionRequest(
    *,
    symbol: str,
    exp_date: str | None = None,
    option_type: Literal['call', 'put'] | None = None,
    strike_price: float | None = None
)
```

Example:

```python
# With context manager
with Robinhood() as rh:
  spy_dates: list[str] = rh.get_expiration_dates("SPY")
  spy_request1 = OptionRequest(symbol="SPY", exp_date=spy_dates[0])
  spy_option_data = rh.get_option_greeks_batch_request(spy_request1)
  for option_request, options in spy_option_data.items():
    print(option_request, len(options))

# No context manager
rh = Robinhood()
spy_quote: FullQuote = rh.get_stock_quotes("SPY")
print(spy_quote.ask_price)
rh.close()


```

## Local caching

This library uses a local SQLite database to cache option
instruments and reduce the amount of requests made per call.\
Cache is validated with a TTL of the next day at 9:30 EDT.\
*See /docs/design_notes.md for more details*

Example where caching improves speed.

```python
with Robinhood(enable_cache = True) as rh:
  dates = rh.get_expiration_dates("SPY")
  strike_map = rh.get_strike_prices(symbol="SPY",exp_date=dates[0])
  call_request = OptionRequest(
    symbol="SPY",
    exp_date=dates[0],
    option_type="call",
  )
  strikes = strike_map[call_request]
  spy_option_list = []
  # Generate a list of OptionRequests you want to view
  for s in strikes:
    opt_req = OptionRequest(symbol="SPY",exp_date=dates[0],strike_price=s)
    spy_option_list.append(opt_req)

  while True:
    option_data = rh.get_option_greeks_batch_request(spy_option_list)
    for option_request, options in option_data.items():
      option = options[0]
      print(option_request.strike_price, option.ask_price, option.bid_price)
    # Delay should be added to avoid rate limit
    time.sleep(0.25)


```

## Trust Me Bro Benchmarks

Benchmark summary for 10 symbols[^benchmark-symbols] and the second nearest
expiration date across 10 runs(~1.6k options returned per run).

| Metric | Cold Cache | Warm Cache | Improvement |
| --- | ---: | ---: | ---: |
| Average `get_expiration_dates` time | 0.06957s | 0.00013s | 99.81% |
| Average `get_strike_prices` time | 0.31505s | 0.00029s | 99.91% |
| Average `get_option_greeks_batch_request` time | 3.48793s | 1.18787s | 65.94% |
| Average total time per run | 7.33413s | 1.19204s | 83.75% |

`Cold cache` represents a run without any cached option data. `Warm cache`
represents a run with cache hits.

[^benchmark-symbols]: SPY, TSLA, QQQ, NVDA, GOOG, MSFT, AMZN, TSM, META, JPM

## TODO log

See /docs/todo.md for planned features.
