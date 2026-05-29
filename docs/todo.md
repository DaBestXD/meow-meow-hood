# TODO list

## Priority TODO

- Add better http error handling and add generic error messages to functions

- Add ability to store equity information into db for long term storage

- Add function to export data to a csv file or json

## Codebase todo's

- `src/robinhood/core/_trading_impl.py`
  - Replace broad order exception handling with more specific error handling.

- `src/robinhood/browser_functions/browser_token_parser.py`
  - Open the configured browser on Linux instead of relying on `xdg-open`.

- `src/robinhood/db_logic/option_cache.py`
  - Add option type synchronization support.

## Maybe TODO

- Add futures endpoint

- Add futures buying/selling endpoint

- Add support for robinhood stock screener
