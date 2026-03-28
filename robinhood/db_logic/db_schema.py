MAIN_TABLE = """
    CREATE TABLE IF NOT EXISTS main_stock_info(
        symbol TEXT PRIMARY KEY NOT NULL,
        chain_id TEXT NOT NULL
    )
"""
EXPIRATION_DATES_TABLE = """
    CREATE TABLE IF NOT EXISTS expiration_dates(
        symbol TEXT NOT NULL,
        exp_date TEXT NOT NULL,
        PRIMARY KEY (symbol,exp_date),
        FOREIGN KEY (symbol) REFERENCES Main_Stock_Info(symbol)
    )
"""
OPTION_IDS_TABLE = """
    CREATE TABLE IF NOT EXISTS option_ids(
        option_id TEXT PRIMARY KEY,
        strike_price REAL,
        exp_date TEXT,
        option_type TEXT,
        symbol TEXT,
        FOREIGN KEY (symbol) REFERENCES Main_Stock_Info(symbol)
    )
"""
OPTION_GREEK_DATA_TABLE = """
    CREATE TABLE IF NOT EXISTS option_greek_data(
        option_id TEXT PRIMARY KEY,
        ask_price TEXT NOT NULL,
        ask_size TEXT NOT NULL,
        bid_price TEXT NOT NULL,
        bid_size TEXT NOT NULL,
        last_trade_price TEXT NOT NULL,
        last_trade_size TEXT NOT NULL,
        mark_price TEXT NOT NULL,
        open_interest TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        volume TEXT NOT NULL,
        symbol TEXT NOT NULL,
        delta TEXT NOT NULL,
        gamma TEXT NOT NULL,
        implied_volatility TEXT NOT NULL,
        rho TEXT NOT NULL,
        theta TEXT NOT NULL,
        vega TEXT NOT NULL,
        FOREIGN KEY (symbol) REFERENCES Main_Stock_Info(symbol)
    )
"""
