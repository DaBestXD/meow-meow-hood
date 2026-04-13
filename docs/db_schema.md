# Database Schema

This project keeps a local SQLite cache in `.meow-meow-config/meow-meow-hood.db`.
The cache stores option chain metadata, option instrument ids, and TTL rows that
determine when a symbol or expiration date needs to be refreshed.

## Entity Relationship Diagram

```mermaid
erDiagram
    MAIN_STOCK_INFO {
        TEXT symbol PK
        TEXT id
        TEXT chain_id
    }

    EXPIRATION_DATES {
        TEXT symbol PK
        TEXT exp_date PK
    }

    OPTION_IDS {
        TEXT option_id PK
        REAL strike_price
        TEXT exp_date
        TEXT option_type
        TEXT symbol FK
    }

    OPTION_CHAIN_SYNC {
        TEXT symbol PK
        INTEGER time_to_live
    }

    OPTION_EXPIRATION_SYNC {
        TEXT symbol PK
        TEXT exp_date PK
        INTEGER time_to_live
    }

    OPTION_GREEK_DATA {
        TEXT option_id PK
        TEXT symbol FK
        TEXT updated_at
        TEXT ask_price
        TEXT bid_price
        TEXT mark_price
        TEXT volume
        TEXT delta
        TEXT gamma
        TEXT implied_volatility
        TEXT rho
        TEXT theta
        TEXT vega
    }

    MAIN_STOCK_INFO ||--o{ EXPIRATION_DATES : has
    MAIN_STOCK_INFO ||--o{ OPTION_IDS : maps
    MAIN_STOCK_INFO ||--|| OPTION_CHAIN_SYNC : refreshes
    MAIN_STOCK_INFO ||--o{ OPTION_EXPIRATION_SYNC : scopes
    MAIN_STOCK_INFO ||--o{ OPTION_GREEK_DATA : owns
```

## Table Roles

- `main_stock_info`: one row per symbol. Stores the Robinhood instrument id and
  the option `chain_id` used to request option chains and instruments.
- `expiration_dates`: cached expiration dates for a symbol. Primary key is the
  pair `(symbol, exp_date)`.
- `option_ids`: cached option instrument ids and their lookup fields. This is
  the table used to answer broad `OptionRequest` lookups from cache.
- `option_chain_sync`: TTL row for symbol-level option chain data.
- `option_expiration_sync`: TTL row for symbol + expiration date cache entries.
- `option_greek_data`: schema placeholder for option greek snapshots. The table
  is created during DB initialization, but the current cache flow does not yet
  write to or read from it.

## Lookup Index

The cache defines one lookup index on `option_ids`:

```sql
CREATE INDEX idx_option_ids_lookup
ON option_ids(symbol, exp_date, option_type, strike_price);
```

That index matches the fields used when `OptionRequest` values are mapped back
to cached option ids.

## Cache Flow

```mermaid
flowchart TD
    A["Robinhood client"] --> B{"Request type"}
    B -->|"get_expiration_dates(symbol)"| C["option_chain_sync"]
    C -->|"TTL valid"| D["expiration_dates"]
    C -->|"TTL missing or expired"| E["Robinhood option chain API"]
    E --> F["main_stock_info / expiration_dates"]
    E --> G["option_chain_sync"]

    B -->|"get_strike_prices(symbol, exp_date)"| H["option_expiration_sync"]
    H -->|"TTL valid"| I["option_ids"]
    H -->|"TTL missing or expired"| J["Robinhood option instruments API"]
    J --> K["option_ids"]
    J --> L["option_expiration_sync"]

    B -->|"get_option_greeks_batch_request(...)"| M["option_ids"]
    M --> N["Robinhood option greeks API"]
```

## Practical Notes

- Cache TTLs are set to the next trading day open, `9:30 AM America/New_York`.
- Only broad requests are treated as cachable right now:
  `OptionRequest(symbol=...)` and `OptionRequest(symbol=..., exp_date=...)`.
- Requests narrowed by `option_type` or `strike_price` still reuse cached
  `option_ids`, but they do not create their own sync rows yet.
