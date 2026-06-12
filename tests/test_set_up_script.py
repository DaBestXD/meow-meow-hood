from robinhood.utils.set_up_script import DEFAULT_CONFIG_NAME, set_up


class TestSetUpScript:
    def test_set_up_creates_default_config_dir(self, tmp_path):
        result = set_up(tmp_path)

        assert tmp_path / DEFAULT_CONFIG_NAME == result
        assert result.is_dir()

    def test_set_up_returns_existing_config_dir_without_error(self, tmp_path):
        existing_dir = tmp_path / ".custom-config"
        existing_dir.mkdir()

        result = set_up(tmp_path, ".custom-config")

        assert existing_dir == result
        assert result.is_dir()
