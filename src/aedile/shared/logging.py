import logging
import sys


def setup_logging(verbose: bool = False) -> None:
    """Configures the root logger to write plain text to stderr."""
    level = logging.DEBUG if verbose else logging.INFO

    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.setLevel(level)
        for h in root_logger.handlers:
            h.setLevel(level)
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    formatter = logging.Formatter("[Aedile] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)

    root_logger.setLevel(level)
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Returns a logger for the given module name."""
    return logging.getLogger(name)
