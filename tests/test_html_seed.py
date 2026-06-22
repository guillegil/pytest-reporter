"""Slice C — RNG seed exposed in Run Information via hook + fixture.

Scenarios:
  2a: no report_seed, no pytest_strategy -> 'Not Provided' in Seed row
  2c/2d: conftest sets report_seed["value"] = 42 -> report shows '42' in mono
  2e: pytest_reporter_seed hook raises -> report generated, shows 'Not Provided'

Note: pytest.warns does NOT cross the pytester subprocess boundary.
"""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_dir(pytester: Pytester) -> pathlib.Path:
    runs_dir = pytester.path / "reports" / "runs"
    runs = sorted(runs_dir.iterdir())
    assert len(runs) == 1, f"Expected 1 run dir, got {len(runs)}"
    return runs[0]


def _report_html(pytester: Pytester) -> str:
    return (_run_dir(pytester) / "report.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Scenario 2a: no seed source -> 'Not Provided'
# ---------------------------------------------------------------------------


def test_seed_not_provided_when_no_source(pytester: Pytester) -> None:
    """When no report_seed and no pytest_strategy installed, DATA.seed must be null."""
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _report_html(pytester)

    # Seed row must exist (the JS label 'Seed' is always in the JS source)
    assert "Seed" in html, "report.html must contain a 'Seed' row"
    # DATA.seed must be null (not a string) when no seed was provided
    assert '"seed": null' in html, (
        "DATA.seed must be null in embedded JSON when no seed is provided"
    )
    # 'Not Provided' appears literally in the JS source as the string to render
    assert "Not Provided" in html, (
        "'Not Provided' string literal must be present in JS source for null seed"
    )


# ---------------------------------------------------------------------------
# Scenario 2c/2d: manual seed via report_seed fixture
# ---------------------------------------------------------------------------


def test_seed_from_fixture(pytester: Pytester) -> None:
    """When report_seed['value'] = 42 is set, DATA.seed must be '42' in embedded JSON."""
    pytester.makepyfile("""
        def test_with_seed(report_seed):
            report_seed["value"] = 42
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _report_html(pytester)

    assert "Seed" in html, "report.html must contain a 'Seed' row"
    # DATA.seed must be the string "42" (not null) in the embedded JSON
    assert '"seed": "42"' in html, (
        "DATA.seed must be '42' in embedded JSON when report_seed['value'] = 42"
    )
    # CSS class for monospace rendering must exist in the JS
    assert "report-info-value mono" in html, (
        "JS must render the seed value with class 'report-info-value mono'"
    )


# ---------------------------------------------------------------------------
# Scenario 2e: hook raises -> graceful 'Not Provided', no crash
# ---------------------------------------------------------------------------


def test_seed_hook_raises_no_crash(pytester: Pytester) -> None:
    """When pytest_reporter_seed hook raises, report still generates with 'Not Provided'."""
    pytester.makeconftest("""
        def pytest_reporter_seed():
            raise RuntimeError("injected seed failure")
    """)
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    # Report must be generated (no crash)
    run_dir = _run_dir(pytester)
    assert (run_dir / "report.html").exists(), "report.html must be generated despite hook failure"

    html = _report_html(pytester)
    assert "Seed" in html, "Seed row must still be present"
    # DATA.seed must be null when the hook raises (no seed resolved)
    assert '"seed": null' in html, "DATA.seed must be null when pytest_reporter_seed hook raises"


# ---------------------------------------------------------------------------
# Structural: hookspec exists
# ---------------------------------------------------------------------------


def test_hookspec_pytest_reporter_seed_exists() -> None:
    """pytest_reporter_seed hookspec must be defined in _hookspecs.py."""
    from pathlib import Path

    src = Path(__file__).parent.parent / "src" / "pytest_reporter" / "_hookspecs.py"
    text = src.read_text(encoding="utf-8")
    assert "pytest_reporter_seed" in text, "_hookspecs.py must define pytest_reporter_seed"
    assert "firstresult=True" in text, "pytest_reporter_seed must be firstresult=True"


# ---------------------------------------------------------------------------
# Structural: report_seed fixture exists in plugin.py
# ---------------------------------------------------------------------------


def test_report_seed_fixture_exists() -> None:
    """report_seed session fixture must be defined in plugin.py."""
    from pathlib import Path

    src = Path(__file__).parent.parent / "src" / "pytest_reporter" / "plugin.py"
    text = src.read_text(encoding="utf-8")
    assert "report_seed" in text, "plugin.py must define the report_seed fixture"
    assert "seed_store" in text, "plugin.py must reference seed_store on the reporter"
