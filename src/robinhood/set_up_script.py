import logging
from pathlib import Path

DEFAULT_CONFIG_NAME = ".meow-meow-config"
logger = logging.getLogger(__name__)


def set_up(
    config_dir: Path = Path.cwd(),
    config_name: str = DEFAULT_CONFIG_NAME,
) -> Path:
    config_dir = config_dir / config_name
    try:
        config_dir.mkdir(parents=True, exist_ok=False)
        logger.debug("Creating config folder in %s", str(config_dir))
    except FileExistsError:
        logger.debug("Config folder already exists skipping...")
        pass
    return config_dir


if __name__ == "__main__":
    set_up()
