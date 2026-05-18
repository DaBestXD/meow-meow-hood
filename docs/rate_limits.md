# Observed Rate Limits

| Endpoint | Observed Limit |
| --- | --- |
| /accounts/ | 100* req/s (no 429 through cap) |
| /arsenal/v1/futures/contracts/ | 100* req/s (no 429 through cap) |
| /arsenal/v1/futures/products/ | 100* req/s (no 429 through cap) |
| /discovery/lists/default/ | 3 req/s |
| /discovery/lists/items/ | 3 req/s |
| /indexes/ | 100* req/s (no 429 through cap) |
| /instruments/ | 100* req/s (no 429 through cap) |
| /marketdata/futures/quotes/v1/ | 100* req/s (no 429 through cap) |
| /marketdata/indexes/values/v1/ | 100* req/s (no 429 through cap) |
| /marketdata/options/ | 100* req/s (no 429 through cap) |
| /marketdata/pricebook/snapshots/{instrument_id}/ | 100* req/s (no 429 through cap) |
| /options/chains/ | <1 req/s (429 at 1 req/s) |
| /options/chains/{symbol}/ | 4 req/s |
| /options/instruments/ | 60 req/s |
| /options/orders/ | 3 req/s |
| /options/positions/ | 4 req/s |
| /orders/ | 15 req/s |
| /positions/ | 100* req/s (no 429 through cap) |
| /quotes/ | 100* req/s (no 429 through cap) |

* 100 was the highest amount before ending the test early.
