"""Tests for structured logging + secret redaction (SPEC 9.4)."""

from __future__ import annotations

import logging
from pathlib import Path

from texttocad import logging_setup


def _fresh_logger():
    # Reset the module-level guard so each test configures a clean logger.
    logging_setup._CONFIGURED = False
    logger = logging.getLogger("texttocad")
    logger.handlers.clear()
    return logger


def test_setup_returns_logger_and_is_idempotent(tmp_path: Path):
    _fresh_logger()
    a = logging_setup.setup_logging(log_dir=tmp_path)
    n_handlers = len(a.handlers)
    b = logging_setup.setup_logging(log_dir=tmp_path)
    assert a is b
    # Second call must not add more handlers (idempotent).
    assert len(b.handlers) == n_handlers
    assert n_handlers >= 1


def test_redaction_filter_masks_secrets(caplog):
    filt = logging_setup._RedactionFilter()
    record = logging.LogRecord(
        name="texttocad",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="using api_key=sk-abcdefghijklmnopqrstuvwx and token=ghp_%s" % ("A" * 30),
        args=(),
        exc_info=None,
    )
    assert filt.filter(record) is True
    assert "[REDACTED]" in record.getMessage()
    assert "sk-abcdefghijklmnopqrstuvwx" not in record.getMessage()


def test_redaction_leaves_clean_message_untouched():
    filt = logging_setup._RedactionFilter()
    record = logging.LogRecord(
        name="texttocad",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hardware probe: RAM=16.0 GB tier=7b",
        args=(),
        exc_info=None,
    )
    filt.filter(record)
    assert record.getMessage() == "hardware probe: RAM=16.0 GB tier=7b"


def test_log_file_created(tmp_path: Path):
    _fresh_logger()
    logger = logging_setup.setup_logging(log_dir=tmp_path)
    logger.info("hello world")
    for h in logger.handlers:
        h.flush()
    assert (tmp_path / "texttocad.log").exists()
