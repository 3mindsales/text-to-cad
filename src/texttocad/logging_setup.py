"""Structured logging setup.

Rules (SPEC 9.4): no secrets in logs, and no logic-revealing stack traces on the
user-facing surface. This module configures a console handler for developers and,
optionally, a rotating file handler under the config directory. API keys / tokens
must never be passed to the logger by callers — there is a light redaction filter
as a defensive backstop.
"""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|authorization|bearer|password)\s*[=:]\s*\S+"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]

_CONFIGURED = False


class _RedactionFilter(logging.Filter):
    """Best-effort redaction so a stray secret never lands in a log line."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # pragma: no cover - defensive
            return True
        redacted = msg
        for pat in _SECRET_PATTERNS:
            redacted = pat.sub("[REDACTED]", redacted)
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True


def setup_logging(level: int = logging.INFO, log_dir: Path | None = None) -> logging.Logger:
    """Configure root logging once; return the app logger."""
    global _CONFIGURED
    logger = logging.getLogger("texttocad")
    if _CONFIGURED:
        return logger

    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S")
    redactor = _RedactionFilter()

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.addFilter(redactor)
    logger.addHandler(console)

    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            fileh = RotatingFileHandler(
                log_dir / "texttocad.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
            )
            fileh.setFormatter(fmt)
            fileh.addFilter(redactor)
            logger.addHandler(fileh)
        except OSError:
            logger.warning("Could not open log file in %s; console logging only", log_dir)

    logger.propagate = False
    _CONFIGURED = True
    return logger
