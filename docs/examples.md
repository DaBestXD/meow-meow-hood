# MEOW-MEOW-HOOD API

## Examples

This library is optimized for mass option data extraction
through batched API requests and a local SQLITE database.
With cache enabled:

Minimal working example:

```python
  # Example with context manager
  with Robinhood() as rh:
    spy_quote = rh.get_stock_quotes("SPY")
    # Returns list of FullQuote objects, data class that stores
    # information such as bid/ask price bid/ask size, etc...
    print(spy_quote.ask_price)
  # With no context manager
  rh = Robinhood()
  spy_dates = rh.get_expiration_dates("SPY")
  rh.close()
```

Example for extracting options:

```python
  with Robinhood() as rh:
    # Get expiration dates for symbol
    spy_dates = rh.get_expiration_dates("SPY")
    # returns a list of strs(Dates are in yyyy-mm-dd format)
    # Make OptionRequest class
    # Parameters:
    #   symbol, expiration date(Optional), option type(Optional),
    #   and strike_price(Optional)
    # [WARNING] An OptionRequest with only symbol as the field will load
    # every option for every expiration date for that symbol
    # Recommended to use at least an expiration date for fast responses
    spy_option_req = OptionRequest(symbol="SPY",exp_date=spy_dates[0])
    spy_option_data: dict[OptionRequest, list[OptionGreekData]]
    spy_option_data = rh.get_option_greeks_batch_request(spy_option_req)
    # With multiple OptionRequests
    qqq_dates = rh.get_expiration_dates("QQQ")
    qqq_option_req = OptionRequest("QQQ", qqq_dates[0])
    # Batch request able to take in a list of OptionRequests
    opt_greeks = rh.get_option_greeks_batch_request([spy_option_req, qqq_option_req])

```

Cache example:

```python
  with Robinhood(cache=True) as rh:
    symbol_only_request = OptionRequest(symbol="SPY")
    full_sync = rh.get_option_greeks_batch_request(symbol_only_request)
    # First run will take a while to load every option for every
    # expiration date, but the symbol will be cached for the rest
    # of the trading day.
```
