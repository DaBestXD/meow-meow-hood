from pathlib import Path

DEFAULT_CONFIG_NAME = ".meow-meow-config"


def set_up(
    config_dir: Path = Path.cwd(),
    config_name: str = DEFAULT_CONFIG_NAME,
) -> Path:
    config_dir = config_dir / config_name
    try:
        config_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        pass
    return config_dir


if __name__ == "__main__":
    set_up()
