import sys

from loguru import logger

__version__ = "0.1.0"

_loguru_config = {
    "handlers": [
        {
            "sink": sys.stdout,
            "format": "{level: <4} | {message}",
            "colorize": True,
        }
    ],
}
logger.configure(**_loguru_config)
