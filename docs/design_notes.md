# Design Notes

## Caching Strategy

I chose to only cache Option Requests of Symbol, or Symbol + exp_date\
Symbol + exp_date + option_type will probably be added next.
Each option request is cached with a TTL that lasts until the
next trading day open time(9:30 EDT).\
Afterwards each cache hit will have to re-sync to maintain up to date
option information.\
Information that is cached is option metadata that decreases the amount of API
requests required.
Example of the normal route to get option market data:

```python
a

```

## Option Request

```python
OptionRequest(*,symbol, exp_date, option_type, strike_price)
```

Db caching will only occur for option requests with symbol only,
or symbol + exp_date only.\
