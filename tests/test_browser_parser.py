import json
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import snappy

from robinhood.browser_functions.browser_token_parser import (
    DB_PATH,
    Chrome,
    Firefox,
    _close_process,
    _decode_jwt,
    _get_firefox_profile_token_and_id,
    _parse_log_file_for_path_token_id,
    get_acc_id,
)
from robinhood.robinhood_errors import AuthenticationError, TokenExtractionError
from tests.support import build_test_jwt


def write_chrome_log(root: Path, *tokens: str) -> Path:
    log_file = root / "000001.log"
    log_file.write_text(
        "".join(f'[\\"access_token\\",\\"{token}\\"]' for token in tokens)
    )
    return log_file


def write_firefox_auth_state(profile_root: Path, token: str) -> Path:
    profile_path = profile_root / "profile.default-release"
    sqlite_path = profile_path / DB_PATH
    sqlite_path.parent.mkdir(parents=True)
    con = sqlite3.connect(sqlite_path)
    try:
        con.execute("CREATE TABLE data (key TEXT, value BLOB)")
        con.execute(
            "INSERT INTO data VALUES (?, ?)",
            (
                "web:auth_state",
                snappy.compress(json.dumps({"access_token": token}).encode()),
            ),
        )
        con.commit()
    finally:
        con.close()
    return profile_path


class TestBrowserTokenParser:
    def test_decode_jwt_returns_payload(self) -> None:
        token = build_test_jwt(exp=1234567890)

        assert {"exp": 1234567890} == _decode_jwt(token)

    @patch("robinhood.browser_functions.browser_token_parser.get_acc_id")
    def test_chrome_log_file_path_returns_log_with_valid_token(
        self, mock_get_acc_id: Mock, tmp_path: Path
    ) -> None:
        expired_token = build_test_jwt(exp=int(time.time()) - 60)
        valid_token = build_test_jwt(exp=int(time.time()) + 3600)
        log_file = write_chrome_log(
            tmp_path, "not-a-jwt", expired_token, valid_token
        )
        mock_get_acc_id.return_value = "ACC123"

        parsed_log_file, parsed_token, parsed_acc_id = (
            _parse_log_file_for_path_token_id(tmp_path)
        )

        assert log_file == parsed_log_file
        assert valid_token == parsed_token
        assert "ACC123" == parsed_acc_id
        mock_get_acc_id.assert_called_once_with(valid_token)

    @patch(
        "robinhood.browser_functions.browser_token_parser.get_acc_id",
        side_effect=AuthenticationError("invalid"),
    )
    def test_chrome_log_file_path_raises_when_only_token_is_rejected(
        self, _mock_get_acc_id: Mock, tmp_path: Path
    ) -> None:
        valid_token = build_test_jwt(exp=int(time.time()) + 3600)
        write_chrome_log(tmp_path, valid_token)

        with pytest.raises(TokenExtractionError):
            _parse_log_file_for_path_token_id(tmp_path)

    @patch("robinhood.browser_functions.browser_token_parser.get_acc_id")
    def test_chrome_get_token_skips_rejected_tokens(
        self, mock_get_acc_id: Mock, tmp_path: Path
    ) -> None:
        rejected_token = build_test_jwt(exp=int(time.time()) + 3600)
        valid_token = build_test_jwt(exp=int(time.time()) + 7200)
        log_file = write_chrome_log(tmp_path, rejected_token, valid_token)
        mock_get_acc_id.side_effect = [
            "ACC123",
            AuthenticationError("invalid"),
            "ACC123",
        ]

        with (
            patch(
                "robinhood.browser_functions.browser_token_parser.sys.platform",
                "darwin",
            ),
            patch(
                "robinhood.browser_functions.browser_token_parser.CHROME_MAC",
                tmp_path,
            ),
        ):
            browser = Chrome()

        assert log_file == browser._file_to_stat_check
        assert valid_token == browser.get_token()

    @patch("robinhood.browser_functions.browser_token_parser.get_acc_id")
    def test_firefox_profile_path_returns_profile_with_valid_token(
        self, mock_get_acc_id: Mock, tmp_path: Path
    ) -> None:
        valid_token = build_test_jwt(exp=int(time.time()) + 3600)
        profile_path = write_firefox_auth_state(tmp_path, valid_token)
        mock_get_acc_id.return_value = "ACC123"

        parsed_profile_path, parsed_token, parsed_acc_id = (
            _get_firefox_profile_token_and_id(tmp_path)
        )

        assert profile_path == parsed_profile_path
        assert valid_token == parsed_token
        assert "ACC123" == parsed_acc_id
        mock_get_acc_id.assert_called_once_with(valid_token)

    def test_firefox_profile_path_raises_for_stale_token(
        self, tmp_path: Path
    ) -> None:
        expired_token = build_test_jwt(exp=int(time.time()) - 60)
        write_firefox_auth_state(tmp_path, expired_token)

        with pytest.raises(TokenExtractionError, match="stale token"):
            _get_firefox_profile_token_and_id(tmp_path)

    @patch("robinhood.browser_functions.browser_token_parser.get_acc_id")
    def test_firefox_get_token_returns_validated_token(
        self, mock_get_acc_id: Mock, tmp_path: Path
    ) -> None:
        valid_token = build_test_jwt(exp=int(time.time()) + 3600)
        profile_path = write_firefox_auth_state(tmp_path, valid_token)
        mock_get_acc_id.return_value = "ACC123"

        browser = Firefox.__new__(Firefox)
        browser.db_path = profile_path / DB_PATH

        assert valid_token == browser.get_token()
        mock_get_acc_id.assert_called_once_with(valid_token)

    @patch(
        "robinhood.browser_functions.browser_token_parser.get_acc_id",
        side_effect=AuthenticationError("invalid"),
    )
    def test_firefox_get_token_can_return_none_for_rejected_token(
        self, _mock_get_acc_id: Mock, tmp_path: Path
    ) -> None:
        valid_token = build_test_jwt(exp=int(time.time()) + 3600)
        profile_path = write_firefox_auth_state(tmp_path, valid_token)
        browser = Firefox.__new__(Firefox)
        browser.db_path = profile_path / DB_PATH

        assert browser.get_token(raise_err_on_stale_token=False) is None

    def test_last_accessed_greater_than_n_days_uses_stat_file(
        self, tmp_path: Path
    ) -> None:
        stat_file = tmp_path / "auth.log"
        stat_file.write_text("auth")
        old_time = (datetime.now(timezone.utc) - timedelta(days=3)).timestamp()
        os.utime(stat_file, (old_time, old_time))
        browser = Chrome.__new__(Chrome)
        browser._file_to_stat_check = stat_file

        assert browser.last_accessed_greater_than_n_days(days=1)
        assert not browser.last_accessed_greater_than_n_days(days=7)

    @patch("robinhood.browser_functions.browser_token_parser.requests.get")
    def test_get_acc_id_returns_account_number_on_success(
        self, mock_get: Mock
    ) -> None:
        mock_get.return_value = Mock(
            status_code=200,
            json=Mock(return_value={"results": [{"account_number": "ABC123"}]}),
        )

        assert "ABC123" == get_acc_id("bearer-token")
        mock_get.assert_called_once()

    @patch("robinhood.browser_functions.browser_token_parser.requests.get")
    def test_get_acc_id_raises_authentication_error_on_failure(
        self, mock_get: Mock
    ) -> None:
        mock_get.return_value = Mock(status_code=403)

        with pytest.raises(AuthenticationError, match="403"):
            get_acc_id("bearer-token")

    @patch("robinhood.browser_functions.browser_token_parser.requests.get")
    def test_get_acc_id_retries_server_errors(self, mock_get: Mock) -> None:
        mock_get.side_effect = [
            Mock(status_code=500),
            Mock(
                status_code=200,
                json=Mock(
                    return_value={"results": [{"account_number": "ABC123"}]}
                ),
            ),
        ]

        assert "ABC123" == get_acc_id("bearer-token")
        assert 2 == mock_get.call_count

    @patch("robinhood.browser_functions.browser_token_parser.subprocess.run")
    def test_close_process_uses_matching_windows_browser_name(
        self, mock_run: Mock
    ) -> None:
        proc = Mock()

        with patch(
            "robinhood.browser_functions.browser_token_parser.sys.platform",
            "win32",
        ):
            _close_process(proc, is_firefox=False)

        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["args"] == [
            "taskkill",
            "/IM",
            "chrome.exe",
            "/T",
            "/F",
        ]
        proc.wait.assert_called_once_with(timeout=5)

    @patch("robinhood.browser_functions.browser_token_parser._close_process")
    @patch("robinhood.browser_functions.browser_token_parser.subprocess.Popen")
    @patch("robinhood.browser_functions.browser_token_parser.time.sleep")
    def test_chrome_open_and_close_browser_uses_selected_profile(
        self,
        mock_sleep: Mock,
        mock_popen: Mock,
        mock_close_process: Mock,
        tmp_path: Path,
    ) -> None:
        stat_file = tmp_path / "000001.log"
        stat_file.write_text("auth")
        proc = Mock()
        mock_popen.return_value = proc
        browser = Chrome.__new__(Chrome)
        browser.application_path = Path("/Applications/Google Chrome")
        browser.data_dir = tmp_path / "User Data"
        browser.profile_dir = "Profile 1"
        browser.path_to_profile_dir = browser.data_dir / browser.profile_dir
        browser.chrome_log_file_path = stat_file

        with (
            patch(
                "robinhood.browser_functions.browser_token_parser.sys.platform",
                "linux",
            ),
            patch(
                "robinhood.browser_functions.browser_token_parser.os.environ",
                {},
            ),
        ):
            browser.open_and_close_browser(time_until_close=1, headless=True)

        args = mock_popen.call_args.args[0]
        assert "--headless=new" in args
        assert f"--user-data-dir={browser.data_dir}" in args
        assert f"--profile-directory={browser.profile_dir}" in args
        mock_sleep.assert_called_once_with(1)
        mock_close_process.assert_called_once_with(proc, is_firefox=False)
