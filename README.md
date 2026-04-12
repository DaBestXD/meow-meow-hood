![Poorly drawn Robinhood logo next to a cat](./docs/pictures/logo.png)

# Meow-Meow-Hood API

A Robinhood API wrapper for fast option market data

## Why?

If you're using Robinhood as a broker still...\
And if you want to view option market data at a reasonable speed.

## Authentication

Ensure you are logged in locally to Robinhood on either:

- Chrome
- Firefox

It works by extracting the locally stored access token from the browser folder.\
By default it will automatically try to extract the token, this can be disabled
on class creation.\
You will need to pass in the access token manually if auto login is disabled.

```python
Robinhood(auto_login=False, access_token="...")
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

(*Refer to the [robinhood/api_dataclasses.py](src/robinhood/api_dataclasses.py)
for full implementation details.*)\

`OptionRequest` is the main class when requesting option data.

```python
OptionRequest(
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
Cache is validated with a TTL of the next day at 9:30 EDT
