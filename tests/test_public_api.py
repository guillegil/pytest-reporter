"""Tests for pytest_reporter public API exports.

These are direct import tests (NOT pytester subprocess) that verify
the public names are accessible and correctly aliased.
"""

from __future__ import annotations

import pytest_reporter


def test_report_logger_importable() -> None:
    """ReportLogger must be importable directly from pytest_reporter."""
    from pytest_reporter import ReportLogger  # noqa: F401 — import is the assertion


def test_logger_importable() -> None:
    """Logger must be importable directly from pytest_reporter."""
    from pytest_reporter import Logger  # noqa: F401 — import is the assertion


def test_report_logger_is_logger_alias() -> None:
    """ReportLogger must be the same object as Logger (alias, not a copy)."""
    from pytest_reporter import Logger, ReportLogger

    assert ReportLogger is Logger, "ReportLogger must be the same class object as Logger"


def test_report_logger_in_all() -> None:
    """'ReportLogger' must appear in pytest_reporter.__all__."""
    assert "ReportLogger" in pytest_reporter.__all__, (
        f"'ReportLogger' not found in __all__: {pytest_reporter.__all__}"
    )


def test_logger_in_all() -> None:
    """'Logger' must appear in pytest_reporter.__all__."""
    assert "Logger" in pytest_reporter.__all__, (
        f"'Logger' not found in __all__: {pytest_reporter.__all__}"
    )


def test_report_logger_can_instantiate_and_log() -> None:
    """ReportLogger instances must have the full logging API."""
    from pytest_reporter import ReportLogger

    log = ReportLogger()
    log.info("hello from public api test")
    log.debug("debug message", {"key": "value"})
    log.warning("warning message")

    serialized = log.serialize()
    entries = serialized["entries"]
    assert len(entries) == 3, f"Expected 3 entries, got {len(entries)}"
    assert entries[0]["msg"] == "hello from public api test"
    assert entries[0]["level"] == "INFO"
    assert entries[1]["data"] == {"key": "value"}
    assert entries[2]["level"] == "WARNING"


def test_report_logger_child() -> None:
    """ReportLogger.child() must create a child logger with a correct source path."""
    from pytest_reporter import ReportLogger

    root = ReportLogger()
    child = root.child("subsystem")
    child.info("message from child")

    entries = root.serialize()["entries"]
    assert len(entries) == 1
    assert entries[0]["source"] == ["subsystem"]
