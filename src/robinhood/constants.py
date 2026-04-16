from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
# Json filtering keys
STRIKE_PRICE = "strike_price"
EXPIRATION_DATES = "expiration_dates"
RESULTS = "results"
NEXT = "next"
ACCOUNT_NUMBER = "account_number"
BASE_API_LINK = "https://api.robinhood.com"
BASE_API_BONFIRE_LINK = "https://bonfire.robinhood.com"
API_ACCOUNT = BASE_API_LINK + "/accounts/"
API_OPTIONS_INSTRUMENTS = "/options/instruments/"
API_GET_WSS_URL = "/marketdata/token/v1/"
API_INDEXES = "/indexes/"
API_ORDERBOOK = "/marketdata/pricebook/snapshots/"
API_INSTRUMENTS = "/instruments/"
API_OPTION_CHAINS = "/options/chains/"
API_MARKET_DATA = "/marketdata/"
API_OPTIONS_GREEKS_DATA = "/marketdata/options/"
API_QUOTES = "/quotes/"
API_INDEX_QUOTE = "/marketdata/indexes/values/v1/"
API_POSITIONS_NON_OPTIONS = "/positions/"
API_POSITIONS_OPTIONS = "/options/positions/"
API_NON_OPTION_ORDER_HISTORY = "/orders/"
API_OPTION_ORDER_HISTORY = "/options/orders/"
API_WATCHLIST_DEFAULT = "/discovery/lists/default/"
API_WATCHLIST = "/discovery/lists/"
API_WATCHLIST_ITEMS = "/discovery/lists/items/"
PARAM_ACCOUNT_NUMBER = "account_number"
PARAM_SYMBOLS = "symbols"
PARAM_OPTION_TYPE = "type"
PARAM_ID = "ids"
PARAM_OPTION_IDS = "ids"
PARAM_OPTION_STRIKE_PRICE = "strike_price"
PARAM_OPTION_STATE = "state"
PARAM_TRADABLE_CHAIN_ID = "tradable_chain_id"
PARAM_CHAIN_ID = "chain_id"
PARAM_EXPIRATION_DATE = "expiration_dates"
PARAM_LIMIT = "page_size"
PARAM_LIST_ID = "list_id"
PARAM_LOAD_ALL_ATTRIBUTES = "load_all_attributes"
PARAM_NON_ZERO = "nonzero"
PARAM_SESSION_ID = "session_id"
PARAM_SESSION_TYPE = "session_type"
MAX_LIMIT = 100
DEFAULT_DB_PATH = Path("./").resolve().parent
DEFAULT_ENV_PATH = Path("./").resolve().parent
# Set of keys to extract from json payload
STOCK_INFO_NON_FLOAT_KEYS = {
    "id",
    "url",
    "quote",
    "fundamentals",
    "market",
    "name",
    "tradeable",
    "symbol",
    "country",
    "type",
    "tradable_chain_id",
    "short_selling_tradability",
}
STOCK_INFO_FLOAT_KEYS = {
    "margin_initial_ratio",
    "maintenance_ratio",
    "day_trade_ratio",
    "min_tick_size",
}
STOCK_POSITION_NON_FLOAT_KEYS = {
    "symbol",
    "type",
    "instrument_id",
}
STOCK_POSITION_FLOAT_KEYS = {
    "quantity",
    "clearing_average_cost",
}
OPTION_GREEK_DATA_NON_FLOAT_KEYS = {
    "instrument",
    "instrument_id",
    "previous_close_date",
    "updated_at",
    "symbol",
    "occ_symbol",
    "state",
    "pricing_model",
}
OPTION_GREEK_DATA_FLOAT_KEYS = {
    "adjusted_mark_price",
    "adjusted_mark_price_round_down",
    "ask_price",
    "bid_price",
    "break_even_price",
    "high_price",
    "last_trade_price",
    "low_price",
    "mark_price",
    "previous_close_price",
    "chance_of_profit_long",
    "chance_of_profit_short",
    "delta",
    "gamma",
    "implied_volatility",
    "rho",
    "theta",
    "vega",
    "high_fill_rate_buy_price",
    "high_fill_rate_sell_price",
    "low_fill_rate_buy_price",
    "low_fill_rate_sell_price",
}
OPTION_GREEK_DATA_INT_KEYS = {
    "ask_size",
    "bid_size",
    "last_trade_size",
    "open_interest",
    "volume",
}

FULL_QUOTE_NON_FLOAT_KEYS = {
    "symbol",
    "updated_at",
    "instrument_id",
    "state",
}

FULL_QUOTE_FLOAT_KEYS = {
    "ask_price",
    "bid_price",
    "last_trade_price",
    "last_extended_hours_trade_price",
    "last_non_reg_trade_price",
    "previous_close",
    "adjusted_previous_close",
}

FULL_QUOTE_INT_KEYS = {
    "ask_size",
    "bid_size",
}
OPTION_CHAIN_NON_FLOAT_KEYS = {
    "id",
    "symbol",
    "can_open_position",
    "cash_component",
    "expiration_dates",
    "underlying_instruments",
    "min_ticks",
    "min_ticks_multileg",
    "late_close_state",
    "extended_hours_state",
    "underlyings",
    "settle_on_open",
}
OPTION_CHAIN_FLOAT_KEYS = {
    "trade_value_multiplier",
}
OPTION_CHAIN_INT_KEYS = {
    "sellout_time_to_expiration",
}
OPTION_INSTRUMENT_NON_FLOAT_KEYS = {
    "chain_id",
    "chain_symbol",
    "created_at",
    "expiration_date",
    "id",
    "issue_date",
    "min_ticks",
    "rhs_tradability",
    "state",
    "tradability",
    "type",
    "updated_at",
    "url",
    "sellout_datetime",
    "long_strategy_code",
    "short_strategy_code",
    "underlying_type",
}
OPTION_INSTRUMENT_FLOAT_KEYS = {
    "strike_price",
}

OPTION_POSITION_NON_FLOAT_KEYS = {
    "account",
    "account_number",
    "chain_id",
    "chain_symbol",
    "clearing_direction",
    "clearing_intraday_direction",
    "created_at",
    "expiration_date",
    "id",
    "opened_at",
    "option",
    "option_id",
    "type",
    "updated_at",
    "url",
}

OPTION_POSITION_FLOAT_KEYS = {
    "average_price",
    "clearing_cost_basis",
    "clearing_intraday_cost_basis",
    "clearing_intraday_running_quantity",
    "clearing_running_quantity",
    "intraday_average_open_price",
    "intraday_quantity",
    "pending_assignment_quantity",
    "pending_buy_quantity",
    "pending_exercise_quantity",
    "pending_expiration_quantity",
    "pending_expired_quantity",
    "pending_sell_quantity",
    "quantity",
    "trade_value_multiplier",
}
STOCK_ORDER_NON_FLOAT_KEYS = {
    "id",
    "instrument_id",
    "side",
    "type",
    "state",
    "created_at",
    "updated_at",
    "last_transaction_at",
}

STOCK_ORDER_FLOAT_KEYS = {
    "quantity",
    "average_price",
    "fees",
}
OPTION_ORDER_LEG_NON_FLOAT_KEYS = {
    "side",
    "expiration_date",
    "option_type",
}

OPTION_ORDER_LEG_FLOAT_KEYS = {
    "strike_price",
}

OPTION_ORDER_LEG_INT_KEYS = {
    "ratio_quantity",
}


OPTION_ORDER_NON_FLOAT_KEYS = {
    "id",
    "chain_symbol",
    "direction",
    "state",
    "strategy",
    "created_at",
    "updated_at",
}

OPTION_ORDER_FLOAT_KEYS = {
    "quantity",
}

OPTION_STRATEGY_NON_FLOAT_KEYS = {
    "object_id",
    "open_price_direction",
    "name",
    "chain_symbol",
}

FUTURE_NON_FLOAT_KEYS = {"symbol", "object_id", "name"}
FUTURE_FLOAT_KEYS = {"future_margin_requirement"}
INDEX_NON_FLOAT_KEYS = {"name", "symbol", "object_id"}
INDEX_FLOAT_KEYS = {
    "high",
    "low",
    "high_52_weeks",
    "low_52_weeks",
}
INSTRUMENTS_FLOAT_KEYS = {
    "high",
    "low",
    "average_volume",
    "volume",
    "high_52_weeks",
    "low_52_weeks",
    "market_cap",
    "pe_ratio",
}
INSTRUMENTS_NON_FLOAT_KEYS = {
    "name",
    "symbol",
    "object_id",
}

CURRENCY_PAIR_NON_FLOAT_KEYS = {"name", "symbol", "object_id"}
CURRENCY_PAIR_FLOAT_KEYS = {"market_cap", "high_52_weeks", "low_52_weeks"}
