from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests
import snappy

from .constants import ACCOUNT_NUMBER, API_ACCOUNT, RESULTS

HOME_DIR = Path.home()
FIRE_MAC = HOME_DIR / Path("Library/Application Support/Firefox/Profiles/")
FIRE_WINDOWS = HOME_DIR / Path("AppData/Roaming/Mozilla/Firefox/Profiles/")
FIRE_LINUX = HOME_DIR / Path(".mozilla/firefox/")
CHROME_MAC = HOME_DIR / Path(
    "Library/Application Support/Google/Chrome/Default/Local Storage/leveldb"
)
CHROME_WINDOWS = HOME_DIR / Path(
    "AppData/Local/Google/Chrome/User Data/Default/Local Storage/leveldb"
)
CHROME_LINUX = HOME_DIR / Path(
    ".config/google-chrome/Default/Local Storage/leveldb"
)
DB_PATH = Path("storage/default/https+++robinhood.com/ls/data.sqlite")


@dataclass(frozen=True)
class Browser:
    linux: str
    mac: str
    windows: str


@dataclass(frozen=True)
class Chrome(Browser):
    linux: str = "google-chrome"
    mac: str = "Google Chrome"
    windows: str = "chrome.exe"


@dataclass(frozen=True)
class Firefox(Browser):
    linux: str = "firefox"
    mac: str = "firefox"
    windows: str = "firefox.exe"


def auto_open_browser(browser: Browser, wait_time: int = 10) -> None:
    """
    This function should only need to be run once a month.
    Opening the browser is necessary for freshing the bearer token.
    pkill/taskKill is the easiest way to clean up the open browser
    though not ideal as it closes all the entire browser
    """
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-a", browser.mac, "https://robinhood.com"])
        time.sleep(wait_time)
        # osascript is used instead of pkill
        # to avoid high cpu usage from reportcrash
        subprocess.run(
            ["osascript", "-e", f'tell application "{browser.mac}" to quit'],
            check=False,
        )
    elif sys.platform == "win32":
        subprocess.Popen(
            ["cmd", "/c", "start", browser.windows, "https://robinhood.com"]
        )
        time.sleep(wait_time)
        subprocess.run(["taskKill", "/IM", browser.windows, "/F"])
    elif sys.platform == "linux":
        subprocess.Popen(["xdg-open", "https://robinhood.com"])
        time.sleep(wait_time)
        subprocess.run(["pkill", "-f", browser.linux], check=False)
    return None


def _firefox_db_parse(f: Path) -> str | None:
    """
    Parse the firefox local storage file for the web:atuh_sate blob
    then decode with snappy.
    """
    for n in f.iterdir():
        if not n.is_dir():
            continue
        db_file_path = "file:" + str(n / DB_PATH) + "?immutable=1"
        try:
            with sqlite3.connect(db_file_path, uri=True) as con:
                cur = con.cursor()
                cur.execute(
                    "SELECT value FROM data WHERE key = 'web:auth_state'"
                )
                bearer_access_check: tuple[bytes] | None = cur.fetchone()
                if not bearer_access_check:
                    continue
                blob = snappy.decompress(bearer_access_check[0])
                if isinstance(blob, str):
                    return None
                auth_dict: dict[str, str] = json.loads(blob.decode())
                access_token = auth_dict.get("access_token")
                return access_token
        except sqlite3.OperationalError:
            continue
    return None


def _chrome_db_parse(f: Path) -> str | None:
    """
    Current parser uses the robinhood leveldb folder
    and the reads the log file for the bearer token.
    Incase of chrome profile recursively call the function twice
    File path: IndexedDB --> robinhood.leveldb dir --> 00001.log file
    """
    for n in f.iterdir():
        if ".log" not in n.name:
            continue
        try:
            with open(n, "rb") as k:
                dump = k.read().decode(errors="ignore")
                token = re.search(
                    r'"access_token":"([^"]+)"',
                    dump,
                )
                return token.group(1) if token else None
        except FileNotFoundError:
            return None


# Add retry for 50X errors
def get_acc_id(bearer_token: str) -> str | int:
    headers = {"authorization": f"Bearer {bearer_token}"}
    r = requests.get(API_ACCOUNT, headers=headers)
    if r.status_code == 200:
        assert r.json()[RESULTS][0][ACCOUNT_NUMBER], (
            "Json structure has changed :("
        )
        return r.json()[RESULTS][0][ACCOUNT_NUMBER]
    else:
        return r.status_code


def get_token(
    env_path: str | os.PathLike[str],
    browser: Browser = Firefox(),
    write_env: bool = True,
    open_browser: bool = True,
) -> tuple[str, str]:
    """
    Browser should be whichever you are logged into robinhood.
    Auto_open_browser will only run if get_acc_id returns 403
    Returns access_token and account_number
    """
    bearer_token = None
    if sys.platform == "darwin":
        if isinstance(browser, Firefox):
            bearer_token = _firefox_db_parse(FIRE_MAC)
        elif isinstance(browser, Chrome):
            bearer_token = _chrome_db_parse(CHROME_MAC)
    elif sys.platform == "linux":
        if isinstance(browser, Firefox):
            bearer_token = _firefox_db_parse(FIRE_LINUX)
        elif isinstance(browser, Chrome):
            bearer_token = _chrome_db_parse(CHROME_LINUX)
    elif sys.platform == "win32":
        if isinstance(browser, Firefox):
            bearer_token = _firefox_db_parse(FIRE_WINDOWS)
        elif isinstance(browser, Chrome):
            bearer_token = _chrome_db_parse(CHROME_WINDOWS)
    else:
        raise OSError("Platform not supported")

    assert bearer_token, """
        Unable to find bearer_token make sure you are logged into robinhood
        on the selected browser.
    """

    account_number = get_acc_id(bearer_token)
    if account_number == 403 and open_browser:
        auto_open_browser(browser)
        return get_token(env_path, browser, write_env, (not open_browser))

    assert isinstance(account_number, str), "Unable to find account_number"

    if write_env:
        with open(env_path, "w") as f:
            f.write(f"BEARER_TOKEN={bearer_token}\n")
            f.write(f"ACCOUNT_NUMBER={account_number}")

    return bearer_token, account_number
