import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

from robinhood.browser_token_parser import (
    Firefox,
    _chrome_db_parse,
    get_acc_id,
    get_token,
)


class TestBrowserTokenParser(unittest.TestCase):
    def test_chrome_db_parse_extracts_access_token_from_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "000001.log"
            log_file.write_text('{"access_token":"token-123"}')

            token = _chrome_db_parse(Path(temp_dir))

        self.assertEqual("token-123", token)

    def test_chrome_db_parse_returns_none_without_log_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            token = _chrome_db_parse(Path(temp_dir))

        self.assertIsNone(token)

    @patch("robinhood.browser_token_parser.requests.get")
    def test_get_acc_id_returns_account_number_on_success(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=Mock(return_value={"results": [{"account_number": "ABC123"}]}),
        )

        account_number = get_acc_id("bearer-token")

        self.assertEqual("ABC123", account_number)
        mock_get.assert_called_once()

    @patch("robinhood.browser_token_parser.requests.get")
    def test_get_acc_id_returns_status_code_on_failure(self, mock_get):
        mock_get.return_value = Mock(status_code=403)

        status_code = get_acc_id("bearer-token")

        self.assertEqual(403, status_code)

    @patch("robinhood.browser_token_parser.auto_open_browser")
    @patch("robinhood.browser_token_parser.get_acc_id")
    @patch("robinhood.browser_token_parser._firefox_db_parse")
    def test_get_token_reads_browser_token_without_writing_env(
        self,
        mock_firefox_parse,
        mock_get_acc_id,
        mock_auto_open_browser,
    ):
        env_path = Path("/tmp/test.env")
        mock_firefox_parse.return_value = "bearer-token"
        mock_get_acc_id.return_value = "ACC123"

        with (
            patch("builtins.open", mock_open()) as mock_file,
            patch("robinhood.browser_token_parser.sys.platform", "darwin"),
        ):
            result = get_token(
                env_path=env_path,
                browser=Firefox(),
                write_env=False,
                open_browser=False,
            )

        self.assertEqual(("bearer-token", "ACC123"), result)
        mock_get_acc_id.assert_called_once_with("bearer-token")
        mock_auto_open_browser.assert_not_called()
        mock_file.assert_not_called()

    @patch("robinhood.browser_token_parser.auto_open_browser")
    @patch("robinhood.browser_token_parser.get_acc_id")
    @patch("robinhood.browser_token_parser._firefox_db_parse")
    def test_get_token_retries_after_403_response(
        self,
        mock_firefox_parse,
        mock_get_acc_id,
        mock_auto_open_browser,
    ):
        env_path = Path("/tmp/test.env")
        mock_firefox_parse.return_value = "bearer-token"
        mock_get_acc_id.side_effect = [403, "ACC123"]

        with patch("robinhood.browser_token_parser.sys.platform", "darwin"):
            result = get_token(
                env_path=env_path,
                browser=Firefox(),
                write_env=False,
                open_browser=True,
            )

        self.assertEqual(("bearer-token", "ACC123"), result)
        mock_auto_open_browser.assert_called_once_with(Firefox())
        self.assertEqual(2, mock_get_acc_id.call_count)

    @patch("builtins.open", new_callable=mock_open)
    @patch("robinhood.browser_token_parser.get_acc_id", return_value="ACC123")
    @patch("robinhood.browser_token_parser._firefox_db_parse")
    def test_get_token_writes_env_file_when_enabled(
        self,
        mock_firefox_parse,
        _mock_get_acc_id,
        mock_file,
    ):
        env_path = Path("/tmp/test.env")
        mock_firefox_parse.return_value = "bearer-token"

        with patch("robinhood.browser_token_parser.sys.platform", "darwin"):
            get_token(
                env_path=env_path,
                browser=Firefox(),
                write_env=True,
                open_browser=False,
            )

        mock_file.assert_called_once_with(env_path, "w")
        handle = mock_file()
        handle.write.assert_any_call("BEARER_TOKEN=bearer-token\n")
        handle.write.assert_any_call("ACCOUNT_NUMBER=ACC123")

    def test_get_token_raises_for_unsupported_platform(self):
        with patch("robinhood.browser_token_parser.sys.platform", "amigaos"):
            with self.assertRaises(OSError):
                get_token(
                    env_path=Path("/tmp/test.env"),
                    write_env=False,
                    open_browser=False,
                )


if __name__ == "__main__":
    unittest.main()
