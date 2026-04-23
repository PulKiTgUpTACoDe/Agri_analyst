"""Structured logging configuration."""
import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging for the application.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Root logger
    root = logging.getLogger()
    root.setLevel(log_level)

    # Clear existing handlers
    root.handlers.clear()

    # Console handler with structured format
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("langsmith").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)

    logging.getLogger("agri").info("Logging configured at %s level", level)
