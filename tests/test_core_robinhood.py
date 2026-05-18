import asyncio
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from robinhood.sync_robinhood_class import Robinhood


class TestCoreRobinhoodInit(unittest.TestCase):
    def close_client_loop(self, client: Robinhood) -> None:
        if not client.event_loop.is_closed():
            client.event_loop.close()

    def test_init_uses_explicit_token_without_setup_when_requested(self):
        with (
            patch("robinhood.core._core_robinhood.set_up") as mock_set_up,
            patch("robinhood.core._core_robinhood.get_token") as mock_get_token,
            patch(
                "robinhood.core._core_robinhood.get_acc_id"
            ) as mock_get_acc_id,
        ):
            client = Robinhood(
                access_token="direct-token",
                extract_token=False,
                enable_cache=False,
                logging_level=None,
            )

        self.addCleanup(self.close_client_loop, client)
        self.assertEqual("direct-token", client._async_http_client.access_token)
        self.assertIsNone(client._db_cache)
        self.assertIsNone(client.env_path)
        mock_set_up.assert_not_called()
        mock_get_token.assert_not_called()
        mock_get_acc_id.assert_not_called()

    def test_init_uses_env_token_and_account_id(self):
        config_dir = Path("/tmp/meow-config")
        http_client = Mock()

        with (
            patch(
                "robinhood.core._core_robinhood.set_up",
                return_value=config_dir,
            ) as mock_set_up,
            patch("robinhood.core._core_robinhood.load_dotenv") as mock_load,
            patch(
                "robinhood.core._core_robinhood.os.getenv",
                return_value="env-token",
            ) as mock_getenv,
            patch(
                "robinhood.core._core_robinhood.get_acc_id",
                return_value="ACC123",
            ) as mock_get_acc_id,
            patch("robinhood.core._core_robinhood.get_token") as mock_get_token,
            patch(
                "robinhood.core._core_robinhood.RobinhoodAsyncHTTPClient",
                return_value=http_client,
            ) as mock_http_client,
        ):
            client = Robinhood(
                config_path="/tmp",
                enable_cache=False,
                logging_level=None,
            )

        self.addCleanup(self.close_client_loop, client)
        self.assertEqual("ACC123", client.user_id)
        self.assertEqual(config_dir / ".env", client.env_path)
        self.assertIs(http_client, client._async_http_client)
        mock_set_up.assert_called_once_with(Path("/tmp"))
        mock_load.assert_called_once_with(dotenv_path=config_dir / ".env")
        mock_getenv.assert_called_once_with("BEARER_TOKEN")
        mock_get_acc_id.assert_called_once_with("env-token")
        mock_get_token.assert_not_called()
        mock_http_client.assert_called_once_with("env-token", None)

    def test_init_extracts_browser_token_after_invalid_env_account(self):
        config_dir = Path("/tmp/meow-config")

        with (
            patch(
                "robinhood.core._core_robinhood.set_up",
                return_value=config_dir,
            ),
            patch("robinhood.core._core_robinhood.load_dotenv"),
            patch(
                "robinhood.core._core_robinhood.os.getenv",
                return_value="env-token",
            ),
            patch(
                "robinhood.core._core_robinhood.get_acc_id",
                return_value=403,
            ),
            patch(
                "robinhood.core._core_robinhood.get_token",
                return_value=("browser-token", "ACC123"),
            ) as mock_get_token,
            patch(
                "robinhood.core._core_robinhood.RobinhoodAsyncHTTPClient"
            ) as mock_http_client,
        ):
            client = Robinhood(
                config_path="/tmp",
                enable_cache=False,
                open_browser=False,
                write_env=False,
                logging_level=None,
            )

        self.addCleanup(self.close_client_loop, client)
        self.assertEqual("ACC123", client.user_id)
        mock_get_token.assert_called_once_with(
            env_path=config_dir / ".env",
            open_browser=False,
            write_env=False,
        )
        mock_http_client.assert_called_once_with("browser-token", None)

    def test_init_raises_when_no_token_is_available(self):
        loop = asyncio.new_event_loop()
        self.addCleanup(loop.close)

        with (
            patch(
                "robinhood.core._core_robinhood.asyncio.new_event_loop",
                return_value=loop,
            ),
            patch(
                "robinhood.core._core_robinhood.set_up",
                return_value=Path("/tmp/meow-config"),
            ),
            patch("robinhood.core._core_robinhood.load_dotenv"),
            patch(
                "robinhood.core._core_robinhood.os.getenv",
                return_value=None,
            ),
            patch("robinhood.core._core_robinhood.get_token") as mock_get_token,
            patch(
                "robinhood.core._core_robinhood.RobinhoodAsyncHTTPClient"
            ) as mock_http_client,
        ):
            with self.assertRaisesRegex(RuntimeError, "Bearer token"):
                Robinhood(
                    extract_token=False,
                    enable_cache=False,
                    logging_level=None,
                )

        mock_get_token.assert_not_called()
        mock_http_client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
