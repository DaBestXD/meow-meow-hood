# API Reference

This is a compact overview of the public API exported from the `robinhood`
package. See [examples](./examples.md) for copy-paste workflows.

## Clients

| Class | Use Case |
| --- | --- |
| `Robinhood` | Synchronous client. Use with `with Robinhood() as rh:` when possible. |
| `AsyncRobinhood` | Async client. Use with `async with AsyncRobinhood() as rh:` and `await` public methods. |

Both clients share the same constructor parameters:

| Parameter | Default | Description |
| --- | --- | --- |
| `config_path` | `Path.cwd()` | Parent directory where `.meow-meow-config` is created. |
| `extract_token` | `True` | Read a Robinhood token from local browser storage. |
| `write_env` | `True` | Persist `BEARER_TOKEN` and `ACCOUNT_NUMBER` to `.env` after token extraction. |
| `open_browser` | `True` | Open browsers during refresh when the saved token is rejected. |
| `user_agent` | `None` | Optional `User-Agent` header for HTTP requests. |
| `enable_cache` | `True` | Enable the local SQLite option metadata cache. |
| `prune_expired_options` | `True` | Remove expired option rows when opening the cache. |
| `logging_level` | `logging.INFO` | Logging level passed to the package logger setup. |
| `log_handler` | package default | Optional logging handler override. |
| `access_token` | `None` | Manually supplied bearer token. |

## Market Data

| Method | Return Type |
| --- | --- |
| `get_stock_quotes(symbols)` | `InstrumentQuote`, `list[InstrumentQuote]`, or `None` |
| `get_stock_info(symbols)` | `StockInfo`, `list[StockInfo]`, or `None` |
| `get_index_quotes(symbols)` | `IndexQuote`, `list[IndexQuote]`, or `None` |
| `get_index_info(symbols)` | `IndexInfo`, `list[IndexInfo]`, or `None` |
| `get_orderbook(symbol)` | `OrderBook` or `None` |
| `get_future_info(symbol)` | `FuturesProduct` or `None` |
| `get_all_futures_products()` | `list[FuturesProduct]` or `None` |
| `get_active_contracts_for_id(id)` | `list[FuturesContract]` or `None` |
| `get_future_quote(ids)` | `FuturesQuote`, `list[FuturesQuote]`, or `None` |

## Options

| Method | Return Type |
| --- | --- |
| `get_expiration_dates(symbol)` | `list[str]` or `None` |
| `get_strike_prices(symbol=..., exp_date=...)` | `dict[OptionRequest, list[float]]` |
| `get_option_chain_data(symbol)` | `OptionChain`, `list[OptionChain]`, or `None` |
| `get_option_greeks_batch_request(option_requests)` | `dict[OptionRequest, list[OptionGreekData]]` |
| `no_db_option_greeks_batch_request(option_requests)` | `dict[OptionRequest, list[OptionGreekData]]` |

`OptionRequest` is the main option filter. `symbol` is required. `exp_date`,
`option_type`, `strike_price`, `position_effect`, and `side` are optional.
Keywords args are enforced:

`OptionRequest(symbol='blah', exp_date='date', ...)`

if you do not provide a keyword arg an error will be raised.

> [!WARNING]
> When using symbol only `OptionRequest(symbol="SPY)` this will load all options
for the given symbol.

## Account And Orders

| Method | Return Type |
| --- | --- |
| `get_account_stock_positions()` | `list[StockPosition]` or `None` |
| `get_account_option_positions()` | `list[OptionPosition]` or `None` |
| `get_stock_order_history()` | `list[StockOrder]` or `None` |
| `get_option_order_history()` | `list[OptionOrderHistory]` or `None` |
| `get_watchlists()` | `list[WatchList]` or `None` |
| `place_limit_stock_order(...)` | `StockOrderResponse` or `None` |
| `place_market_stock_order(...)` | `StockOrderResponse` or `None` |
| `place_option_order(...)` | `OptionOrderResponse` or `None` |

## Utility Methods

| Method | Description |
| --- | --- |
| `close()` | Close the HTTP session, cache connection, and event loop. |
| `open_browser(browser, wait_time=10, days=1)` | Open Robinhood in a browser when local auth state is stale. |
| `refresh_access_token()` | Refresh the active bearer token when a refreshed browser token is available. |
| `execute_custom_sql(query, args)` | Execute a cache SQL query when the cache is enabled. |

## Return Values And Errors

Read methods generally return `None` when no usable data is returned. Option
batch methods usually keep the input request as the dictionary key and use an
empty list when no matching option data is found.

HTTP `401` and `403` responses raise `AuthenticationError`. HTTP `429` and
`5xx` responses currently raise `NotImplementedError`. Trading helpers can
raise package exceptions from `robinhood.errors` when an order cannot be
validated locally.
Better http error handling will be added.
