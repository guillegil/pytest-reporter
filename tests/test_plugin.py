"""Integration tests for pytest-reporter using pytester."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


def test_report_not_created_without_flag(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
    assert not (pytester.path / "report.json").exists()


def test_report_created_with_flag(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report=report.json")
    result.assert_outcomes(passed=1)

    report_path = pytester.path / "report.json"
    assert report_path.exists()

    data = json.loads(report_path.read_text())
    assert data["total"] == 1
    assert data["passed"] == 1
    assert data["failed"] == 0
    assert data["results"][0]["outcome"] == "passed"


def test_report_captures_failure(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_fail():
            assert 1 == 2
    """)
    result = pytester.runpytest("--report=report.json")
    result.assert_outcomes(failed=1)

    data = json.loads((pytester.path / "report.json").read_text())
    assert data["failed"] == 1
    assert data["results"][0]["outcome"] == "failed"
    assert data["results"][0]["longrepr"] is not None


def test_report_captures_skip(pytester: Pytester) -> None:
    pytester.makepyfile("""
        import pytest

        @pytest.mark.skip(reason="not ready")
        def test_skip():
            pass
    """)
    result = pytester.runpytest("--report=report.json")
    result.assert_outcomes(skipped=1)

    data = json.loads((pytester.path / "report.json").read_text())
    assert data["skipped"] == 1


def test_report_terminal_summary(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report=report.json")
    result.stdout.fnmatch_lines(["*Report written to*report.json*"])
