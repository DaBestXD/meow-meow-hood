from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
RESULTS = "results"
ACCOUNT_NUMBER = "account_number"
BASE_API_LINK = "https://api.robinhood.com"
API_ACCOUNT = BASE_API_LINK + "/accounts/"
API_OPTIONS_INSTRUMENTS = "/options/instruments/"
API_OPTION_CHAINS = "/options/chains/"
API_QUOTES = "/quotes/"
PARAM_SYMBOLS = "symbols"
PARAM_OPTION_TYPE = "type"
PARAM_CHAIN_ID = "chain_id"
PARAM_EXPIRATION_DATE = "expiration_dates"
PARAM_LIMIT = "page_size"
MAX_LIMIT = 100
