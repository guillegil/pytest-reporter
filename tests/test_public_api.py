"""Tests for pytest_reporter public API exports.

These are direct import tests (NOT pytester subprocess) that verify
the public names are accessible.
"""

from __future__ import annotations

import pytest

import pytest_reporter


def test_all_names_the_public_api() -> None:
    assert pytest_reporter.__all__ == ["ReportTabs"]
    from pytest_reporter import ReportTabs  # noqa: F401 - import is the assertion


@pytest.mark.parametrize("name", ["Logger", "ReportLogger"])
def test_removed_logger_names_point_to_logging(name: str) -> None:
    """The 0.3 logger classes are gone: importing them says what to use."""
    with pytest.raises(ImportError, match=r"logging\.getLogger"):
        getattr(pytest_reporter, name)
