from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import APP_NAME, LOG_DIR


def configure_logging(level: int = logging.INFO) -> Path:
    """Configure application-wide logging and return the active log file path."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "desktop_ai_assistant.log"

    logger = logging.getLogger()
    logger.setLevel(level)

    if logger.handlers:
        return log_path

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(log_path, maxBytes=1_500_000, backupCount=3, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.info("%s logging initialized at %s", APP_NAME, log_path)
    return log_path


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger for the requested module."""
    return logging.getLogger(name)
