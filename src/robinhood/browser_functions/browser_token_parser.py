"""Helpers for extracting Robinhood tokens from local browser profiles."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import requests
import snappy

from robinhood.constants import (
    ACCOUNT_NUMBER,
    API_ACCOUNT,
    BASE_API_LINK,
    RESULTS,
)
from robinhood.robinhood_errors import AuthenticationError, TokenExtractionError

logger = logging.getLogger(__name__)

CHROME_DB_NAME = Path("https_robinhood.com_0.indexeddb.leveldb")
HOME_DIR = Path.home()
FIRE_MAC = HOME_DIR / Path("Library/Application Support/Firefox/Profiles/")
FIRE_WINDOWS = HOME_DIR / Path("AppData/Roaming/Mozilla/Firefox/Profiles/")
FIRE_LINUX = HOME_DIR / Path(".mozilla/firefox/")
CHROME_MAC = (
    HOME_DIR
    / Path("Library/Application Support/Google/Chrome/Default/IndexedDB")
    / CHROME_DB_NAME
)
CHROME_WINDOWS = (
    HOME_DIR
    / Path("AppData/Local/Google/Chrome/User Data/Default/IndexedDB")
    / CHROME_DB_NAME
)
CHROME_LINUX = (
    HOME_DIR / Path(".config/google-chrome/Default/IndexedDB") / CHROME_DB_NAME
)
DB_PATH = Path("storage/default/https+++robinhood.com/ls/data.sqlite")


class Browser(Protocol):
    """Executable names for a supported browser on each platform."""

    windows_db_path: Path
    linux_db_path: Path
    mac_db_path: Path
    _file_to_stat_check: Path
    acc_id: str
    _extracted_token: str

    def open_and_close_browser(
        self,
        retries: int = 3,
        time_until_close: float = 10,
        *,
        headless: bool = True,
    ) -> None: ...

    def get_token(self) -> str | None: ...

    def last_accessed_greater_than_n_days(self, days: int = 1) -> bool: ...


class Firefox:
    """
    Firefox executable names for supported platforms.
    Includes the file path to the Firefox IndexedDB/local storage and the
    path to the Firefox executable.
    Also has functions to open and close browser to keep session alive.
    """

    def __init__(self, raise_err_on_stale_token: bool = True) -> None:
        self.windows_db_path: Path = FIRE_WINDOWS
        self.linux_db_path: Path = FIRE_LINUX
        self.mac_db_path: Path = FIRE_MAC

        if sys.platform == "win32":
            self.firefox_profile_path, self._extracted_token, self.acc_id = (
                _get_firefox_profile_token_and_id(
                    self.windows_db_path,
                    raise_err_on_stale_token,
                )
            )
            self.application_path = Path(
                r"C:\Program Files\Mozilla Firefox\firefox.exe"
            )

        elif sys.platform == "darwin":
            self.firefox_profile_path, self._extracted_token, self.acc_id = (
                _get_firefox_profile_token_and_id(
                    self.mac_db_path,
                    raise_err_on_stale_token,
                )
            )
            self.application_path = Path(
                "/Applications/Firefox.app/Contents/MacOS/firefox"
            )

        elif sys.platform == "linux":
            self.firefox_profile_path, self._extracted_token, self.acc_id = (
                _get_firefox_profile_token_and_id(
                    self.linux_db_path,
                    raise_err_on_stale_token,
                )
            )
            self.application_path = Path("/usr/bin/firefox")

        else:
            raise RuntimeError(f"unsupported platform: {sys.platform}")
        self.db_path = self.firefox_profile_path / DB_PATH
        self._file_to_stat_check = self.db_path

    def __repr__(self) -> str:
        vals = ", ".join([f"{k}={v}" for k, v in self.__dict__.items()])
        return f"{self.__class__.__name__}({vals})"

    def __str__(self) -> str:
        return self.__repr__()

    def get_token(self, raise_err_on_stale_token: bool = True) -> str | None:
        """
        Parse the firefox local storage file for the web:atuh_sate blob
        then decode with snappy.
        """
        db_file_path = "file:" + str(self.db_path) + "?immutable=1"
        con = sqlite3.connect(db_file_path, uri=True)
        try:
            cur = con.cursor()
            cur.execute("SELECT value FROM data WHERE key = 'web:auth_state'")
            bearer_access_check: tuple[bytes] | None = cur.fetchone()
            if not bearer_access_check:
                logger.debug("No token was returned for 'web:auth_state'")
                return None
            blob = snappy.decompress(bearer_access_check[0])
            if isinstance(blob, str):
                logger.debug("Snappy returned str not bytes")
                return None
            auth_dict: dict[str, str] = json.loads(blob.decode())
            access_token = auth_dict.get("access_token")
            logger.debug(
                "Found firefox auth token: %s",
                access_token[:7] if access_token else None,
            )
            if access_token:
                exp_date = _decode_jwt(access_token).get("exp", 0)
                if exp_date < int(time.time()):
                    logger.warning(
                        "Found firefox auth token expired: %s", access_token[:7]
                    )
                    return None
                logger.debug("Found firefox auth token: %s", access_token[:7])
                try:
                    self.acc_id = get_acc_id(access_token)
                except AuthenticationError:
                    if not raise_err_on_stale_token:
                        return None
                    raise
            return access_token
        finally:
            con.close()

    def open_and_close_browser(
        self,
        retries: int = 3,
        time_until_close: float = 10,
        headless: bool = True,
    ) -> None:
        """
        (Warning) If firefox is already open will cause error if headless
        (Warning) If not running headless and firefox is open will not close
                  firefox, so in long running scripts can accumulate many tabs.

        Attempt to open Firefox retrying up to three times.
        Raises RuntimeError after exhausting all retries
        """
        if retries <= 0:
            raise RuntimeError("blocking io error occurred too many times")

        args = [str(self.application_path)]
        env = os.environ.copy()
        if headless:
            env.update(
                {
                    "MOZ_HEADLESS": "1",
                    "MOZ_DISABLE_GPU": "1",
                    "MOZ_WEBRENDER": "0",
                }
            )
            args.extend(
                [
                    "-headless",
                    "-no-remote",
                    "-profile",
                    str(self.firefox_profile_path),
                ]
            )
        args.append("https://robinhood.com")
        logger.debug(
            "Pre-open time: %s",
            datetime.fromtimestamp(self.db_path.stat().st_mtime),
        )
        try:
            proc: subprocess.Popen[bytes]

            if sys.platform == "win32":
                proc = subprocess.Popen(
                    args,
                    env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                firefox_check = subprocess.run(
                    ["pgrep", "-fl", "Firefox|firefox"],
                    capture_output=True,
                )
                if firefox_check.returncode == 0:
                    raise RuntimeError(
                        "Firefox is already open, close and run again"
                    )
                proc = subprocess.Popen(
                    args,
                    env=env,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

        except BlockingIOError:
            logger.warning("Blocking error trying again")
            return self.open_and_close_browser(
                retries=retries - 1,
                time_until_close=time_until_close,
            )

        try:
            time.sleep(time_until_close)
        finally:
            _close_process(proc, is_firefox=True)
            logger.debug(
                "Post-open time: %s",
                datetime.fromtimestamp(self.db_path.stat().st_mtime),
            )
        return None

    def last_accessed_greater_than_n_days(self, days: int = 1) -> bool:
        last_accessed = self._file_to_stat_check.stat().st_mtime
        last_mod = (
            datetime.now(timezone.utc)
            - datetime.fromtimestamp(last_accessed, timezone.utc)
        ).days
        return last_mod > days


class Chrome:
    """
    Google Chrome executable names for supported platforms.
    Includes the file path to the chrome IndexedDB and the
    path to the chrome executable.
    Also has functions to open and close browser to keep session alive
    """

    def __init__(self, profile_dir: str = "Default") -> None:
        self.windows_db_path: Path = CHROME_WINDOWS
        self.linux_db_path: Path = CHROME_LINUX
        self.mac_db_path: Path = CHROME_MAC
        self.profile_dir: str = profile_dir

        if sys.platform == "win32":
            self.chrome_log_file_path, self._extracted_token, self.acc_id = (
                _parse_log_file_for_path_token_id(self.windows_db_path)
            )
            self.application_path = Path(
                r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            )
            app_data = os.environ.get("LOCALAPPDATA")
            if not app_data:
                raise RuntimeError("app_data cannot be none")
            self.data_dir = Path(app_data) / "Google/Chrome/User Data"

        elif sys.platform == "darwin":
            self.chrome_log_file_path, self._extracted_token, self.acc_id = (
                _parse_log_file_for_path_token_id(self.mac_db_path)
            )
            self.application_path = Path(
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            )
            self.data_dir = (
                HOME_DIR / "Library/Application Support/Google/Chrome"
            )

        elif sys.platform.startswith("linux"):
            self.chrome_log_file_path, self._extracted_token, self.acc_id = (
                _parse_log_file_for_path_token_id(self.linux_db_path)
            )
            self.application_path = Path("/usr/bin/google-chrome")
            self.data_dir = HOME_DIR / ".config/google-chrome"

        else:
            raise RuntimeError(f"unsupported platform: {sys.platform}")

        self.path_to_profile_dir = self.data_dir / self.profile_dir
        self._file_to_stat_check = self.chrome_log_file_path

    def __repr__(self) -> str:
        vals = ", ".join([f"{k}={v}" for k, v in self.__dict__.items()])
        return f"{self.__class__.__name__}({vals})"

    def __str__(self) -> str:
        return self.__repr__()

    def get_token(self) -> str | None:
        """
        Current parser uses the robinhood leveldb folder
        and the reads the log file for the bearer token.
        Incase of chrome profile recursively call the function twice
        File path: IndexedDB --> robinhood.leveldb dir --> 00XXX.log file
        """
        dump = self._file_to_stat_check.read_bytes().decode(errors="ignore")
        tokens = re.findall(
            r'\\"access_token\\",\\"([^\\"]+)',
            dump,
        )
        for t in tokens:
            try:
                payload = _decode_jwt(t)
            except Exception:
                continue
            if payload.get("exp", 0) > int(time.time()):
                try:
                    self.acc_id = get_acc_id(t)
                except AuthenticationError:
                    logger.debug("Found stale token skipping...")
                    continue
                logger.debug("Found chrome auth token: %s", t[:7])
                return t
        return None

    def open_and_close_browser(
        self,
        retries: int = 3,
        time_until_close: float = 10,
        *,
        headless: bool = True,
    ) -> None:
        """
        Attempt to open browser will retries 3 times
        then raises RuntimeError
        """
        if retries <= 0:
            raise RuntimeError("blocking io error occurred too many times")

        env = os.environ.copy()
        logger.debug(
            "Pre-open time: %s",
            datetime.fromtimestamp(self.chrome_log_file_path.stat().st_mtime),
        )
        try:
            args = [
                str(self.application_path),
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={self.data_dir}",
                f"--profile-directory={self.profile_dir}",
                "https://robinhood.com",
            ]
            if headless:
                args.insert(1, "--headless=new")
                args.insert(2, "--disable-gpu")
            proc: subprocess.Popen[bytes]
            if sys.platform == "win32":
                proc = subprocess.Popen(
                    args,
                    env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                )
            else:
                proc = subprocess.Popen(
                    args,
                    env=env,
                    start_new_session=True,
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                )
        except BlockingIOError:
            logger.warning("Blocking error trying again")
            return self.open_and_close_browser(
                retries=retries - 1,
            )

        try:
            time.sleep(time_until_close)
        finally:
            _close_process(proc, is_firefox=False)
            logger.debug(
                "Post-open time: %s",
                datetime.fromtimestamp(
                    self.chrome_log_file_path.stat().st_mtime
                ),
            )
            if sys.platform == "darwin":
                _close_firefox_profile_lock(self.path_to_profile_dir)
        return None

    def last_accessed_greater_than_n_days(self, days: int = 1) -> bool:
        last_accessed = self._file_to_stat_check.stat().st_mtime
        last_mod = (
            datetime.now(timezone.utc)
            - datetime.fromtimestamp(last_accessed, timezone.utc)
        ).days
        return last_mod > days


def _close_process(
    proc: subprocess.Popen[bytes],
    *,
    is_firefox: bool,
) -> None:
    if sys.platform == "win32":
        if is_firefox:
            args = ["taskkill", "/IM", "firefox.exe", "/T", "/F"]
        else:
            args = ["taskkill", "/IM", "chrome.exe", "/T", "/F"]
        subprocess.run(
            args=args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return None

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            proc.kill()
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.wait()
    return None


def _close_firefox_profile_lock(profile_path: Path) -> None:
    lock_path = profile_path / ".parentlock"

    result = subprocess.run(
        ["lsof", "-t", str(lock_path)],
        text=True,
        check=False,
        capture_output=True,
    )

    for raw_pid in result.stdout.splitlines():
        raw_pid = raw_pid.strip()
        if not raw_pid:
            continue

        pid = int(raw_pid)
        logger.warning("Terminating Firefox profile lock holder pid=%s", pid)

        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue

        time.sleep(2)

        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue

        logger.warning("Force killing Firefox profile lock holder pid=%s", pid)
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return None


def _get_firefox_profile_token_and_id(
    f: Path,
    raise_err_on_stale_token: bool = True,
) -> tuple[Path, str, str]:
    """
    Parses firefox profiles folder for a valid token then returns the
    profile filepath.
    """
    for n in f.iterdir():
        if not n.is_dir():
            continue
        db_file_path = "file:" + str(n / DB_PATH) + "?immutable=1"
        try:
            con = sqlite3.connect(db_file_path, uri=True)
            try:
                cur = con.cursor()
                cur.execute(
                    "SELECT value FROM data WHERE key = 'web:auth_state'"
                )
                bearer_access_check: tuple[bytes] | None = cur.fetchone()
                if not bearer_access_check:
                    continue
                blob = snappy.decompress(bearer_access_check[0])
                if isinstance(blob, str):
                    raise RuntimeError
                auth_dict: dict[str, str] = json.loads(blob.decode())
                access_token = auth_dict["access_token"]
                jwt = _decode_jwt(access_token)
                if jwt["exp"] < int(time.time()):
                    logger.warning("Stale token was retrieved in %s", n)
                    if raise_err_on_stale_token:
                        raise TokenExtractionError("stale token was retrieved")
                # run a test to see if the token is valid
                id = get_acc_id(access_token)
                return n, access_token, id
            finally:
                con.close()
        except sqlite3.OperationalError:
            continue
    raise TokenExtractionError("unable to find a valid token")


def _parse_log_file_for_path_token_id(db_path: Path) -> tuple[Path, str, str]:
    """
    Returns Path to .log file, token, and account id
    """
    for n in db_path.iterdir():
        if ".log" not in n.name:
            continue
        dump = n.read_bytes().decode(errors="ignore")
        tokens = re.findall(
            r'\\"access_token\\",\\"([^\\"]+)',
            dump,
        )
        for t in tokens:
            try:
                payload = _decode_jwt(t)
            except Exception:
                continue
            if payload.get("exp", 0) > int(time.time()):
                try:
                    id = get_acc_id(t)
                except AuthenticationError:
                    continue
                return n, t, id
    raise TokenExtractionError("unable to find a valid token")


def _decode_jwt(payload: str) -> dict[str, Any]:
    # idk how this would happen but better safe than sorry
    # and make easier debugging in the event this happens
    if not isinstance(payload, str):
        raise ValueError(
            f"payload {payload} was of type {type(payload)} not str"
        )
    payload_b64 = payload.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    decoded_payload: dict[str, Any] = json.loads(
        base64.urlsafe_b64decode(payload_b64).decode()
    )
    return decoded_payload


def get_acc_id(bearer_token: str, retries: int = 3) -> str:
    """
    Return the account number for a bearer token or the HTTP status code.
    uses: https://api.robinhood.com/account/ returns the first account found
    Raises AuthenticationError if status_code is not 200 or above 500
    """
    if retries <= 0:
        raise RuntimeError("Failed to get account id after 3 retries")
    headers = {"authorization": f"Bearer {bearer_token}"}
    r = requests.get(BASE_API_LINK + API_ACCOUNT, headers=headers)
    if r.status_code == 200:
        # returns the first account back
        acc_num = r.json()[RESULTS][0][ACCOUNT_NUMBER]
        logger.debug("Account number returned 200 with %s", acc_num)
        return acc_num
    elif r.status_code >= 500:
        logger.debug("Robinhood returned %d retrying...", r.status_code)
        return get_acc_id(bearer_token, retries - 1)
    else:
        raise AuthenticationError(f"token return {r.status_code} invalid token")
