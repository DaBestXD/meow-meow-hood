import unittest
from pathlib import Path
from unittest.mock import patch

from robinhood.browser_functions.token_functions import (
    _refresh_access_token,
    return_access_token_expiry,
)
from tests.support import build_test_jwt


class TestTokenFunctions(unittest.TestCase):
    def test_return_access_token_expiry_decodes_jwt_payload(self):
        token = build_test_jwt(exp=1234567890)

        self.assertEqual(1234567890, return_access_token_expiry(token))

    def test_refresh_access_token_returns_none_when_token_is_current(self):
        with (
            patch(
                "robinhood.browser_functions.token_functions."
                "return_access_token_expiry",
                return_value=200,
            ),
            patch(
                "robinhood.browser_functions.token_functions.time.time",
                return_value=100,
            ),
            patch(
                "robinhood.browser_functions.token_functions."
                "check_if_modified_date_within_range"
            ) as mock_check_modified,
            patch(
                "robinhood.browser_functions.token_functions.get_token"
            ) as mock_get_token,
        ):
            result = _refresh_access_token(
                "bearer-token",
                Path("/tmp/test.env"),
                write_env=True,
            )

        self.assertIsNone(result)
        mock_check_modified.assert_not_called()
        mock_get_token.assert_not_called()

    def test_refresh_access_token_recovers_expired_token(self):
        env_path = Path("/tmp/test.env")
        with (
            patch(
                "robinhood.browser_functions.token_functions."
                "return_access_token_expiry",
                return_value=50,
            ),
            patch(
                "robinhood.browser_functions.token_functions.time.time",
                return_value=100,
            ),
            patch(
                "robinhood.browser_functions.token_functions."
                "check_if_modified_date_within_range",
                return_value=False,
            ),
            patch(
                "robinhood.browser_functions.token_functions.get_token",
                return_value=("new-token", "ACC123"),
            ) as mock_get_token,
        ):
            result = _refresh_access_token(
                "expired-token",
                env_path,
                write_env=False,
            )

        self.assertEqual("new-token", result)
        mock_get_token.assert_called_once_with(
            env_path=env_path,
            write_env=False,
            open_browser=True,
        )

    def test_refresh_access_token_raises_when_browser_auth_is_stale(self):
        with (
            patch(
                "robinhood.browser_functions.token_functions."
                "return_access_token_expiry",
                return_value=50,
            ),
            patch(
                "robinhood.browser_functions.token_functions.time.time",
                return_value=100,
            ),
            patch(
                "robinhood.browser_functions.token_functions."
                "check_if_modified_date_within_range",
                return_value=True,
            ),
            patch(
                "robinhood.browser_functions.token_functions.get_token"
            ) as mock_get_token,
        ):
            with self.assertRaisesRegex(RuntimeError, "Token is expired"):
                _refresh_access_token(
                    "expired-token",
                    Path("/tmp/test.env"),
                    write_env=True,
                )

        mock_get_token.assert_not_called()


if __name__ == "__main__":
    unittest.main()
