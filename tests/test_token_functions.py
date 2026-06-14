import os
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from robinhood.browser_functions.token_functions import (
    _refresh_access_token,
    _return_access_token_expiry,
)
from robinhood.robinhood_errors import TokenExtractionError
from tests.support import build_test_jwt


class FakeBrowser:
    windows_db_path = Path("unused")
    linux_db_path = Path("unused")
    mac_db_path = Path("unused")
    acc_id = "ACC123"

    def __init__(
        self,
        open_browser_on_stale_token: bool | Path = False,
        token: str | None = "new-token",
    ) -> None:
        stat_file = (
            open_browser_on_stale_token
            if isinstance(open_browser_on_stale_token, Path)
            else Path("unused")
        )
        self._file_to_stat_check = stat_file
        self._extracted_token = token or ""
        self.get_token_mock = Mock(return_value=token)
        self.open_and_close_browser_mock = Mock()
        self.last_accessed_greater_than_n_days_mock = Mock(return_value=False)

    def get_token(self) -> str | None:
        return self.get_token_mock()

    def open_and_close_browser(
        self,
        retries: int = 3,
        time_until_close: float = 10,
        *,
        headless: bool = True,
    ) -> None:
        self.open_and_close_browser_mock(
            retries=retries,
            time_until_close=time_until_close,
            headless=headless,
        )

    def last_accessed_greater_than_n_days(self, days: int = 1) -> bool:
        return bool(self.last_accessed_greater_than_n_days_mock(days=days))


class TestTokenFunctions:
    def test_return_access_token_expiry_decodes_jwt_payload(self) -> None:
        token = build_test_jwt(exp=1234567890)

        assert 1234567890 == _return_access_token_expiry(token)

    def test_refresh_access_token_returns_none_when_token_is_current(
        self, tmp_path: Path
    ) -> None:
        browser = FakeBrowser(tmp_path / "auth.log")

        with (
            patch(
                "robinhood.browser_functions.token_functions."
                "_return_access_token_expiry",
                return_value=200,
            ),
            patch(
                "robinhood.browser_functions.token_functions.time.time",
                return_value=100,
            ),
        ):
            result = _refresh_access_token("bearer-token", browser)

        assert result is None
        browser.get_token_mock.assert_not_called()

    def test_refresh_access_token_recovers_expired_token(
        self, tmp_path: Path
    ) -> None:
        stat_file = tmp_path / "auth.log"
        stat_file.write_text("auth")
        now = int(time.time())
        os.utime(stat_file, (now, now))
        browser = FakeBrowser(stat_file, token="new-token")

        with patch(
            "robinhood.browser_functions.token_functions."
            "_return_access_token_expiry",
            return_value=now - 1,
        ):
            result = _refresh_access_token(
                "expired-token",
                browser,
                max_day_without_access=7,
            )

        assert "new-token" == result
        browser.get_token_mock.assert_called_once_with()

    def test_refresh_access_token_treats_exp_equal_now_as_expired(
        self, tmp_path: Path
    ) -> None:
        stat_file = tmp_path / "auth.log"
        stat_file.write_text("auth")
        now = int(time.time())
        os.utime(stat_file, (now, now))
        browser = FakeBrowser(stat_file, token="new-token")

        with (
            patch(
                "robinhood.browser_functions.token_functions."
                "_return_access_token_expiry",
                return_value=now,
            ),
            patch(
                "robinhood.browser_functions.token_functions.time.time",
                return_value=now,
            ),
        ):
            result = _refresh_access_token(
                "expired-token",
                browser,
                max_day_without_access=7,
            )

        assert "new-token" == result
        browser.get_token_mock.assert_called_once_with()

    def test_refresh_access_token_raises_when_browser_cannot_extract_token(
        self, tmp_path: Path
    ) -> None:
        stat_file = tmp_path / "auth.log"
        stat_file.write_text("auth")
        now = int(time.time())
        os.utime(stat_file, (now, now))
        browser = FakeBrowser(stat_file, token=None)

        with (
            patch(
                "robinhood.browser_functions.token_functions."
                "_return_access_token_expiry",
                return_value=now - 1,
            ),
            pytest.raises(
                TokenExtractionError,
                match="unable to retrieve token",
            ),
        ):
            _refresh_access_token("expired-token", browser)

        browser.get_token_mock.assert_called_once_with()

    def test_refresh_access_token_raises_when_browser_auth_is_too_old(
        self, tmp_path: Path
    ) -> None:
        stat_file = tmp_path / "auth.log"
        stat_file.write_text("auth")
        old_time = int(time.time()) - (10 * 24 * 60 * 60)
        os.utime(stat_file, (old_time, old_time))
        browser = FakeBrowser(stat_file)

        with (
            patch(
                "robinhood.browser_functions.token_functions."
                "_return_access_token_expiry",
                return_value=int(time.time()) - 1,
            ),
            pytest.raises(RuntimeError, match="Token is expired"),
        ):
            _refresh_access_token(
                "expired-token",
                browser,
                max_day_without_access=7,
            )

        browser.get_token_mock.assert_not_called()
