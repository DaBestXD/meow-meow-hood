# Observed Rate Limits

| Endpoint | Observed Limit |
| --- | --- |
| /accounts/ | 100* req/s |
| /arsenal/v1/futures/contracts/ | 100* req/s |
| /arsenal/v1/futures/products/ | 100* req/s |
| /discovery/lists/default/ | 3 req/s |
| /discovery/lists/items/ | 3 req/s |
| /indexes/ | 100* req/s |
| /instruments/ | 100* req/s |
| /marketdata/futures/quotes/v1/ | 100* req/s |
| /marketdata/indexes/values/v1/ | 100* req/s |
| /marketdata/options/ | 100* req/s |
| /marketdata/pricebook/snapshots/{instrument_id}/ | 100* req/s |
| /options/chains/ | <1 req/s (429 at 1 req/s) |
| /options/chains/{symbol}/ | 4 req/s |
| /options/instruments/ | 60 req/s |
| /options/orders/ | 3 req/s |
| /options/positions/ | 4 req/s |
| /orders/ | 15 req/s |
| /positions/ | 100* req/s |
| /quotes/ | 100* req/s |

* 100 was the highest amount before ending the test early.
