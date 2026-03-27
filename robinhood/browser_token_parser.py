import re
import requests
import subprocess
import sqlite3
import sys
import time
from enum import Enum
from pathlib import Path
from constants import API_ACCOUNT,ACCOUNT_NUMBER, RESULTS, PROJECT_DIR

class Browser(Enum):
    FIREFOX = 0
    CHROME = 1

HOME_DIR = Path.home()
FIRE_MAC = HOME_DIR / Path("Library/Application Support/Firefox/Profiles/")
FIRE_WINDOWS = HOME_DIR / Path("AppData/Roaming/Mozilla/Firefox/Profiles/")
FIRE_LINUX = HOME_DIR / Path(".mozilla/firefox/")
CHROME_MAC = HOME_DIR / Path("Library/Application Support/Google/Chrome")
CHROME_WINDOWS = HOME_DIR / Path("AppData/Local/Google/Chrome/User Data")
CHROME_LINUX = HOME_DIR / Path(".config/google-chrome/")

def open_browser(browser: str, wait_time = 5) -> None:
    """
    Opening the browser is necessary for freshing the bearer token
    pkill/taskKill is the easiest way to clean up the open browser
    though not ideal
    """
    subprocess.Popen(["open", "-a", browser, "https://robinhood.com"])
    time.sleep(wait_time)
    if sys.platform == "win32":
        subprocess.run(["taskKill", "/IM", browser, "/F"])
    else:
        subprocess.run(["pkill", "-f", browser])
    return None

def firefox_db_parse(f: Path) -> str | None:
    for n in f.iterdir():
        if not n.is_dir():
            continue
        db_file_path = "file:" + str(n / "cookies.sqlite") + "?immutable=1"
        with sqlite3.connect(db_file_path, uri=True) as con:
            cur = con.cursor()
            try:
                cur.execute(
                    "SELECT VALUE FROM 'moz_cookies' WHERE host = 'robinhood.com'"
                )
            except sqlite3.OperationalError:
                continue
            bearer_access_check: tuple[str] | None = cur.fetchone()
            if not bearer_access_check:
                continue
            return str(*bearer_access_check)
    return None

def chrome_db_parse(f: Path, profile: int = 0) -> str | None:
    if profile >= 2:
        return None
    profile_folder = Path("Default") if profile == 0 else Path(f"Profile {profile}")
    db_path = (f / profile_folder / "IndexedDB")
    for n in db_path.iterdir():
        if not "robinhood.com" in n.name:
            continue
        flog = [k for k in n.iterdir() if ".log" in k.name]
        if not flog:
            continue
        try:
            with open(flog[0], "rb") as l:
                dump = l.read().decode(errors="ignore")
                token = re.search(r'(?:read_only_secondary_access_token\\",\\")(.*)(?:\\",\\"scope)', dump)
                return token.group(1) if token else None
        except FileNotFoundError:
            return None
    return chrome_db_parse(f, profile=(profile+1))


# Add retry for 50X errors
def get_acc_id(bearer_token: str) -> str | None:
    headers = {"authorization": f"Bearer {bearer_token}"}
    r = requests.get(API_ACCOUNT, headers=headers)
    if r.status_code == 200:
        assert r.json()[RESULTS][0][ACCOUNT_NUMBER], (
            "Json structure has changed :("
        )
        return r.json()[RESULTS][0][ACCOUNT_NUMBER]
    else:
        return None


def get_token(browser: Browser = Browser.FIREFOX, write_env: bool = True, open_browser: bool = True) -> tuple[str,str]:
    bearer_token, account_number = None,None
    if sys.platform == "darwin":
        if browser == Browser.FIREFOX:
            bearer_token= firefox_db_parse(FIRE_MAC)
        elif browser == Browser.CHROME:
            bearer_token = chrome_db_parse(CHROME_MAC)
    elif sys.platform == "linux":
        if browser == Browser.FIREFOX:
            bearer_token = firefox_db_parse(FIRE_LINUX)
        elif browser == Browser.CHROME:
            bearer_token = chrome_db_parse(CHROME_LINUX)
    elif sys.platform == "win32":
        if browser == Browser.FIREFOX:
            bearer_token = firefox_db_parse(FIRE_WINDOWS)
        elif browser == Browser.CHROME:
            bearer_token = chrome_db_parse(CHROME_WINDOWS)
    else:
        raise OSError("Platform not supported")

    if open_browser and not(bearer_token and account_number):
        get_token(browser,write_env,(not open_browser))

    assert bearer_token, """
        Unable to find bearer_token make sure you are logged into robinhood
        on the selected browser.
    """

    account_number = get_acc_id(bearer_token)

    assert account_number, "Unable to find account_number"

    if write_env:
        with open(PROJECT_DIR / ".env", "w") as f:
            f.write(f"BEARER_TOKEN={bearer_token}\n")
            f.write(f"ACCOUNT_NUMBER={account_number}")

    return bearer_token, account_number

