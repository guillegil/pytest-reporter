"""Tests for the 'pytest-verify installed but outdated' diagnostic warning."""

from __future__ import annotations

from pytest_reporter.reporter import _verify_outdated_warning


def test_warns_when_installed_but_helper_missing() -> None:
    """Installed pytest-verify without get_check_results is the silent-loss case."""
    msg = _verify_outdated_warning(None, verify_installed=True)
    assert msg is not None
    assert "get_check_results" in msg


def test_no_warning_when_helper_present() -> None:
    """A working get_check_results means nothing to warn about."""
    assert _verify_outdated_warning(lambda _item: [], verify_installed=True) is None


def test_no_warning_when_not_installed() -> None:
    """pytest-verify simply absent is benign — no checks are expected."""
    assert _verify_outdated_warning(None, verify_installed=False) is None


def test_warning_surfaced_during_session(pytester: object) -> None:
    """When the reporter runs with an outdated pytest-verify, a warning is shown."""
    pytester.makeconftest(  # type: ignore[attr-defined]
        """
        import pytest_reporter.reporter as r
        r.get_check_results = None
        r._VERIFY_INSTALLED = True
        """
    )
    pytester.makepyfile("def test_ok(): assert True")  # type: ignore[attr-defined]
    result = pytester.runpytest_subprocess("--report-dir=reports")  # type: ignore[attr-defined]
    combined = result.stdout.str() + result.stderr.str()
    assert "get_check_results" in combined
