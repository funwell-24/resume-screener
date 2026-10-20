"""
Logging setup — called ONCE at app startup.

Features:
    - Idempotent: repeated calls don't add duplicate handlers.
    - Environment override: LOG_LEVEL env var wins over config.
    - File rotation: writes to logs/app.log, rotating at 5 MB × 3 backups.
      Console handler stays at WARNING by default (so the CLI isn't spammed)
      but DEBUG goes to the file for post-mortem.

Call from `app.py`, `scripts/*.py`, or any entry point:
    from src.utils import setup_logging
    setup_logging()
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import settings


_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-24s | %(message)s"
_DATE_FORMAT = "%H:%M:%S"

# Tracks whether setup_logging has already run this process.
_CONFIGURED = False


def _resolve_level(level: str | None) -> int:
    """Determine effective log level: arg > env > settings."""
    chosen = (level or os.environ.get("LOG_LEVEL") or settings.LOG_LEVEL or "INFO")
    return getattr(logging, chosen.upper(), logging.INFO)


def _console_level(base: int) -> int:
    """
    Console handler default: INFO in scripts, WARNING in production app.

    Controlled by APP_ENV env var: 'dev' → INFO, otherwise → WARNING.
    """
    env = os.environ.get("APP_ENV", "dev").lower()
    if env in {"prod", "production"}:
        return logging.WARNING
    return base


def setup_logging(level: str | None = None) -> None:
    """
    Configure root logging. Safe to call multiple times.

    Parameters
    ----------
    level : str | None
        e.g. "DEBUG", "INFO". Falls back to LOG_LEVEL env var, then
        settings.LOG_LEVEL.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    effective_level = _resolve_level(level)

    root = logging.getLogger()
    root.setLevel(effective_level)

    # ---- Console handler --------------------------------------------
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(_console_level(effective_level))
    console.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    root.addHandler(console)

    # ---- File handler (rotating) ------------------------------------
    # File lives in project root / logs/
    log_dir = Path(settings.PROJECT_ROOT) / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=5 * 1024 * 1024,   # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(effective_level)
        file_handler.setFormatter(
            logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)
        )
        root.addHandler(file_handler)
    except OSError as exc:
        # Logging failure must never crash the app
        logging.getLogger(__name__).warning(
            "Could not set up file logging: %s", exc
        )

    # ---- Quiet noisy third-party libraries --------------------------
    for noisy in (
        "urllib3", "requests", "matplotlib", "PIL",
        "asyncio", "fitz", "sentence_transformers",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Alias for logging.getLogger — for consistent import style."""
    return logging.getLogger(name)