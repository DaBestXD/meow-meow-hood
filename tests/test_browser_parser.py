import base64
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

from robinhood.browser_token_parser import (
    Chrome,
    Firefox,
    _chrome_db_parse,
    auto_open_browser,
    get_acc_id,
    get_token,
)


def _build_test_jwt(*, exp: int) -> str:
    payload = json.dumps({"exp": exp}, separators=(",", ":")).encode()
    payload_b64 = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"header.{payload_b64}.signature"


class TestBrowserTokenParser(unittest.TestCase):
    def test_chrome_db_parse_extracts_valid_access_token_from_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "000001.log"
            valid_token = _build_test_jwt(exp=int(time.time()) + 3600)
            log_file.write_text(
                '[\\"access_token\\",\\"' + valid_token + '\\"]'
            )

            token = _chrome_db_parse(Path(temp_dir))

        self.assertEqual(valid_token, token)

    def test_chrome_db_parse_skips_malformed_and_expired_tokens(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "000001.log"
            expired_token = _build_test_jwt(exp=int(time.time()) - 60)
            valid_token = _build_test_jwt(exp=int(time.time()) + 3600)
            log_file.write_text(
                '[\\"access_token\\",\\"not-a-jwt\\"]'
                '[\\"access_token\\",\\"'
                + expired_token
                + '\\"]'
                '[\\"access_token\\",\\"'
                + valid_token
                + '\\"]'
            )

            token = _chrome_db_parse(Path(temp_dir))

        self.assertEqual(valid_token, token)

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

    @patch("robinhood.browser_token_parser._chrome_db_parse")
    @patch("robinhood.browser_token_parser._firefox_db_parse")
    @patch("robinhood.browser_token_parser.get_acc_id")
    @patch("robinhood.browser_token_parser.auto_open_browser")
    def test_get_token_reads_browser_token_without_writing_env(
        self,
        mock_auto_open_browser,
        mock_get_acc_id,
        mock_firefox_parse,
        mock_chrome_parse,
    ):
        env_path = Path("/tmp/test.env")
        mock_chrome_parse.return_value = None
        mock_firefox_parse.return_value = "bearer-token"
        mock_get_acc_id.return_value = "ACC123"

        with (
            patch("builtins.open", mock_open()) as mock_file,
            patch("robinhood.browser_token_parser.sys.platform", "darwin"),
        ):
            result = get_token(
                env_path=env_path,
                write_env=False,
                open_browser=False,
            )

        self.assertEqual(("bearer-token", "ACC123"), result)
        self.assertEqual(2, mock_get_acc_id.call_count)
        mock_chrome_parse.assert_called_once()
        mock_firefox_parse.assert_called_once()
        mock_auto_open_browser.assert_not_called()
        mock_file.assert_not_called()

    @patch("robinhood.browser_token_parser._chrome_db_parse")
    @patch("robinhood.browser_token_parser._firefox_db_parse")
    @patch("robinhood.browser_token_parser.get_acc_id")
    @patch("robinhood.browser_token_parser.auto_open_browser")
    def test_get_token_retries_after_403_response(
        self,
        mock_auto_open_browser,
        mock_get_acc_id,
        mock_firefox_parse,
        mock_chrome_parse,
    ):
        env_path = Path("/tmp/test.env")
        mock_chrome_parse.return_value = None
        mock_firefox_parse.return_value = "bearer-token"
        mock_get_acc_id.side_effect = [403, 403, "ACC123", "ACC123"]

        with patch("robinhood.browser_token_parser.sys.platform", "darwin"):
            result = get_token(
                env_path=env_path,
                write_env=False,
                open_browser=True,
            )

        self.assertEqual(("bearer-token", "ACC123"), result)
        self.assertEqual(
            [call.args[0] for call in mock_auto_open_browser.call_args_list],
            [Firefox(), Chrome()],
        )
        self.assertEqual(4, mock_get_acc_id.call_count)

    @patch("builtins.open", new_callable=mock_open)
    @patch("robinhood.browser_token_parser.get_acc_id", return_value="ACC123")
    @patch("robinhood.browser_token_parser._chrome_db_parse", return_value=None)
    @patch("robinhood.browser_token_parser._firefox_db_parse")
    def test_get_token_writes_env_file_when_enabled(
        self,
        mock_firefox_parse,
        _mock_chrome_parse,
        _mock_get_acc_id,
        mock_file,
    ):
        env_path = Path("/tmp/test.env")
        mock_firefox_parse.return_value = "bearer-token"

        with patch("robinhood.browser_token_parser.sys.platform", "darwin"):
            get_token(
                env_path=env_path,
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

    @patch("robinhood.browser_token_parser.time.sleep")
    @patch("robinhood.browser_token_parser.subprocess.run")
    @patch("robinhood.browser_token_parser.subprocess.Popen")
    def test_auto_open_browser_uses_xdg_open_on_linux(
        self,
        mock_popen,
        mock_run,
        mock_sleep,
    ):
        with patch("robinhood.browser_token_parser.sys.platform", "linux"):
            auto_open_browser(Firefox(), wait_time=1)

        mock_popen.assert_called_once_with(
            ["xdg-open", "https://robinhood.com"]
        )
        mock_sleep.assert_called_once_with(1)
        mock_run.assert_called_once_with(
            ["pkill", "-f", "firefox"], check=False
        )


if __name__ == "__main__":
    unittest.main()
