from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from robinhood.robinhood_errors import TokenExtractionError
from robinhood.sync_robinhood_class import Robinhood
from tests.support import build_robinhood_client


class FakeBrowser:
    windows_db_path = Path("unused")
    linux_db_path = Path("unused")
    mac_db_path = Path("unused")
    token: str | None = "browser-token"
    acc_id = "ACC123"

    def __init__(self) -> None:
        self._file_to_stat_check = Path("unused")
        self._extracted_token = self.token
        self.get_token_mock = Mock(return_value=self.token)
        self.last_accessed_greater_than_n_days_mock = Mock(return_value=False)
        self.open_and_close_browser_mock = Mock()

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


class TestCoreRobinhoodInit:
    @pytest.fixture(autouse=True)
    def _set_client_tracker(self, sync_client_tracker) -> None:
        self.track_client = sync_client_tracker

    def test_init_extracts_token_from_browser_and_creates_cache(self) -> None:
        config_dir = Path("/tmp/meow-config")
        http_client = Mock()
        cache = Mock()

        with (
            patch(
                "robinhood.core._core_robinhood.set_up",
                return_value=config_dir,
            ) as mock_set_up,
            patch(
                "robinhood.core._core_robinhood.OptionCache",
                return_value=cache,
            ) as mock_option_cache,
            patch(
                "robinhood.core._core_robinhood.RobinhoodAsyncHTTPClient",
                return_value=http_client,
            ) as mock_http_client,
        ):
            client = Robinhood(
                config_path="/tmp",
                browser_type=FakeBrowser,
                logging_level=None,
            )

        self.track_client(client)
        assert "ACC123" == client.acc_id
        assert isinstance(client.browser_type, FakeBrowser)
        assert cache is client._db_cache
        client.browser_type.get_token_mock.assert_not_called()
        mock_set_up.assert_called_once_with(Path("/tmp"))
        mock_option_cache.assert_called_once_with(
            config_dir / "meow-meow-hood.db",
            True,
        )
        mock_http_client.assert_called_once_with("browser-token", None)
        assert http_client is client._async_http_client

    def test_init_skips_cache_setup_when_cache_is_disabled(self) -> None:
        with (
            patch("robinhood.core._core_robinhood.set_up") as mock_set_up,
            patch(
                "robinhood.core._core_robinhood.OptionCache"
            ) as mock_option_cache,
        ):
            client = Robinhood(
                browser_type=FakeBrowser,
                enable_cache=False,
                logging_level=None,
            )

        self.track_client(client)
        assert client._db_cache is None
        mock_set_up.assert_not_called()
        mock_option_cache.assert_not_called()

    def test_init_raises_when_browser_returns_no_token(self) -> None:
        class EmptyBrowser(FakeBrowser):
            token = None

        with (
            patch(
                "robinhood.core._core_robinhood.RobinhoodAsyncHTTPClient"
            ) as mock_http_client,
            pytest.raises(TokenExtractionError, match="Bearer token"),
        ):
            Robinhood(
                browser_type=EmptyBrowser,
                enable_cache=False,
                logging_level=None,
            )

        mock_http_client.assert_not_called()

    def test_refresh_access_token_opens_stale_browser_and_updates_http_token(
        self,
    ) -> None:
        browser = FakeBrowser()
        browser.last_accessed_greater_than_n_days_mock.return_value = True
        http_client = SimpleNamespace(
            access_token="old-token",
            update_session_token=Mock(),
            session=object(),
            close=Mock(),
        )
        client = build_robinhood_client(http_client=http_client, db_cache=None)
        client.browser_type = browser
        self.track_client(client)

        with patch(
            "robinhood.core._core_robinhood._refresh_access_token",
            return_value="new-token",
        ) as mock_refresh:
            client.refresh_access_token(time_until_close=3, headless=False)

        browser.open_and_close_browser_mock.assert_called_once_with(
            retries=3,
            time_until_close=3,
            headless=False,
        )
        mock_refresh.assert_called_once_with("old-token", browser)
        http_client.update_session_token.assert_called_once_with("new-token")
        assert "new-token" == http_client.access_token
        assert http_client.session is None

    def test_refresh_access_token_can_skip_browser_open(self) -> None:
        browser = FakeBrowser()
        browser.last_accessed_greater_than_n_days_mock.return_value = True
        http_client = SimpleNamespace(
            access_token="old-token",
            update_session_token=Mock(),
            session=None,
            close=Mock(),
        )
        client = build_robinhood_client(http_client=http_client, db_cache=None)
        client.browser_type = browser
        self.track_client(client)

        with patch(
            "robinhood.core._core_robinhood._refresh_access_token",
            return_value=None,
        ):
            client.refresh_access_token(auto_open_browser=False)

        browser.open_and_close_browser_mock.assert_not_called()
        http_client.update_session_token.assert_not_called()
        assert "old-token" == http_client.access_token

    def test_return_access_token_expiry_reads_http_client_token(self) -> None:
        http_client = SimpleNamespace(access_token="token", close=Mock())
        client = build_robinhood_client(http_client=http_client, db_cache=None)
        self.track_client(client)

        with patch(
            "robinhood.core._core_robinhood._return_access_token_expiry",
            return_value=123,
        ) as mock_expiry:
            result = client.get_access_token_expiry()

        assert 123 == result
        mock_expiry.assert_called_once_with("token")
