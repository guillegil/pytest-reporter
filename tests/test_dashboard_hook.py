"""Pytester integration tests for the pytest_reporter_dashboard hook + fixture.

Tests DG-4: config embedded in DATA.dashboard in report.html.
Phase 2, Task 2.1 (RED then GREEN after hook is wired).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


# ---------------------------------------------------------------------------
# Helpers (copied from test_metadata.py pattern)
# ---------------------------------------------------------------------------


def _extract_report_data(html: str) -> dict:  # type: ignore[type-arg]
    """Extract the embedded DATA dict from report.html."""
    match = re.search(r"const DATA = (\{.*?\});\s*\n", html, re.DOTALL)
    assert match, "Could not find 'const DATA = ...' in report.html"
    raw = match.group(1).replace("<\\/", "</")
    return json.loads(raw)  # type: ignore[no-any-return]


def _get_report_html(pytester: Pytester) -> str:
    """Return the content of report.html from the most recent run."""
    runs = list((pytester.path / "reports" / "runs").iterdir())
    assert runs, "No run directory found under reports/runs/"
    run_dir = sorted(runs)[-1]
    report_path = run_dir / "report.html"
    assert report_path.exists(), f"report.html not found in {run_dir}"
    return report_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Task 2.1 — hook with one group embeds DATA.dashboard with groups list
# ---------------------------------------------------------------------------


def test_dashboard_hook_embeds_config(pytester: Pytester) -> None:
    """conftest declares pytest_reporter_dashboard → DATA.dashboard has groups, is_default=False."""
    pytester.makeconftest("""
        def pytest_reporter_dashboard():
            return [{"path": "tests", "depth": 1}]
    """)
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _get_report_html(pytester)
    data = _extract_report_data(html)

    assert "dashboard" in data, "DATA.dashboard key missing from embedded JSON"
    dashboard = data["dashboard"]
    assert dashboard["is_default"] is False, (
        f"Expected is_default=False when hook provides config; got {dashboard['is_default']!r}"
    )
    assert len(dashboard["groups"]) == 1
    group = dashboard["groups"][0]
    assert group["path"] == ["tests"]
    assert group["depth"] == 1


# ---------------------------------------------------------------------------
# Task 2.1 — no hook → DATA.dashboard.is_default = True
# ---------------------------------------------------------------------------


def test_no_dashboard_hook_is_default(pytester: Pytester) -> None:
    """Without any dashboard hook/fixture, DATA.dashboard.is_default=True."""
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _get_report_html(pytester)
    data = _extract_report_data(html)

    assert "dashboard" in data, "DATA.dashboard key missing from embedded JSON"
    dashboard = data["dashboard"]
    assert dashboard["is_default"] is True, (
        f"Expected is_default=True when no hook; got {dashboard['is_default']!r}"
    )
    assert dashboard["groups"] == []


# ---------------------------------------------------------------------------
# report_dashboard fixture — fixture-provided groups appear in DATA.dashboard
# ---------------------------------------------------------------------------


def test_report_dashboard_fixture(pytester: Pytester) -> None:
    """report_dashboard fixture contributes groups to DATA.dashboard."""
    pytester.makeconftest("""
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def _set_dashboard(report_dashboard):
            report_dashboard.append({"path": "integration", "depth": 2})
    """)
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _get_report_html(pytester)
    data = _extract_report_data(html)

    assert "dashboard" in data
    dashboard = data["dashboard"]
    assert dashboard["is_default"] is False
    assert any(g["path"] == ["integration"] for g in dashboard["groups"]), (
        f"Expected group with path=['integration']; got {dashboard['groups']!r}"
    )


# ---------------------------------------------------------------------------
# report_dashboard fixture — usable WITHOUT --report-dir (no crash)
# ---------------------------------------------------------------------------


def test_report_dashboard_fixture_without_report_dir(pytester: Pytester) -> None:
    """report_dashboard fixture without --report-dir returns a usable list (no crash)."""
    pytester.makepyfile("""
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def _write(report_dashboard):
            report_dashboard.append({"path": "ctec"})

        def test_pass():
            assert True
    """)
    result = pytester.runpytest()
    assert result.ret == 0, f"Expected exit 0; got {result.ret}\n{result.stdout.str()}"
    result.stdout.no_fnmatch_line("*AttributeError*")
    result.stdout.no_fnmatch_line("*RuntimeError*")


# ---------------------------------------------------------------------------
# Raising hook must not abort report generation
# ---------------------------------------------------------------------------


def test_raising_dashboard_hook_does_not_abort_report(pytester: Pytester) -> None:
    """A conftest dashboard hook that raises must not abort report.html generation."""
    pytester.makeconftest("""
        def pytest_reporter_dashboard():
            raise RuntimeError("deliberate dashboard hook failure")
    """)
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    assert runs
    run_dir = sorted(runs)[-1]
    assert (run_dir / "report.html").exists(), "report.html must still be written on hook failure"
