"""Tests for the report metadata panel feature.

Covers pytest_reporter_metadata hook and report_metadata fixture.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_report_data(html: str) -> dict:  # type: ignore[type-arg]
    """Extract the embedded DATA dict from a report.html.

    The embed uses ``/*__REPORT_DATA__*/`` injection: the placeholder is
    replaced with ``const DATA = {...};``.  The JSON was produced with
    ``json.dumps(default=str)`` and has ``</`` escaped as ``<\\/``.
    Un-escape before parsing.
    """
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
# Task 5.1 — hook-only metadata appears in embedded JSON
# ---------------------------------------------------------------------------


def test_hook_only_metadata_in_data(pytester: Pytester) -> None:
    """Hook-returned metadata appears in data['system_metadata'] in the embed."""
    pytester.makeconftest("""
        def pytest_reporter_metadata():
            return {"DUT": {"Serial": "SN-001", "Firmware": "2.3.1"}}
    """)
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _get_report_html(pytester)
    data = _extract_report_data(html)
    assert "system_metadata" in data, "system_metadata key missing from embedded DATA"
    assert data["system_metadata"]["DUT"]["Serial"] == "SN-001"
    assert data["system_metadata"]["DUT"]["Firmware"] == "2.3.1"


# ---------------------------------------------------------------------------
# Task 5.2 — hook-only metadata rendered visually in HTML
# ---------------------------------------------------------------------------


def test_hook_only_metadata_rendered(pytester: Pytester) -> None:
    """Hook metadata produces a visible 'System Data' panel containing the values."""
    pytester.makeconftest("""
        def pytest_reporter_metadata():
            return {"DUT": {"Serial": "SN-001", "Firmware": "2.3.1"}}
    """)
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _get_report_html(pytester)
    assert "System Data" in html, "'System Data' heading not found in HTML"
    assert "SN-001" in html, "DUT Serial value not found in HTML"


# ---------------------------------------------------------------------------
# Task 5.3 — fixture-only metadata appears in embedded JSON (coerces int)
# ---------------------------------------------------------------------------


def test_fixture_only_metadata(pytester: Pytester) -> None:
    """Fixture-written metadata (including int value) is stringified in JSON."""
    pytester.makeconftest("""
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def _set_metadata(report_metadata):
            report_metadata.setdefault("CI", {})["job_id"] = 42
    """)
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _get_report_html(pytester)
    data = _extract_report_data(html)
    assert data["system_metadata"]["CI"]["job_id"] == "42", (
        f"Expected '42' (str), got {data['system_metadata']['CI']['job_id']!r}"
    )


# ---------------------------------------------------------------------------
# Task 5.4 — fixture overrides hook on collision; non-colliding hook key kept
# ---------------------------------------------------------------------------


def test_merge_fixture_overrides_hook(pytester: Pytester) -> None:
    """Fixture wins over hook on key collision; non-colliding hook keys survive."""
    pytester.makeconftest("""
        import pytest

        def pytest_reporter_metadata():
            return {"Env": {"mode": "staging", "region": "eu"}}

        @pytest.fixture(scope="session", autouse=True)
        def _override(report_metadata):
            report_metadata.setdefault("Env", {})["mode"] = "production"
    """)
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _get_report_html(pytester)
    data = _extract_report_data(html)
    env = data["system_metadata"]["Env"]
    assert env["mode"] == "production", f"Expected fixture to override hook; got {env['mode']!r}"
    assert env["region"] == "eu", f"Non-colliding hook key lost; got {env!r}"


# ---------------------------------------------------------------------------
# Task 5.5 — multi-conftest: last implementation wins per key
# ---------------------------------------------------------------------------


def test_multi_conftest_last_writer_wins(pytester: Pytester) -> None:
    """When two conftest files implement the hook, last writer wins per key."""
    # Root conftest returns the first value
    pytester.makeconftest("""
        def pytest_reporter_metadata():
            return {"Build": {"id": "100"}}
    """)
    # Sub-package conftest returns the second value
    sub = pytester.mkdir("sub")
    (sub / "conftest.py").write_text(
        'def pytest_reporter_metadata():\n    return {"Build": {"id": "200", "branch": "main"}}\n',
        encoding="utf-8",
    )
    (sub / "test_sub.py").write_text(
        "def test_pass():\n    assert True\n",
        encoding="utf-8",
    )

    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _get_report_html(pytester)
    data = _extract_report_data(html)
    build = data["system_metadata"]["Build"]
    assert build["id"] == "200", f"Expected last writer wins (200); got {build['id']!r}"
    assert build["branch"] == "main", f"Non-colliding key lost; got {build!r}"


# ---------------------------------------------------------------------------
# Task 5.6 — panel absent when no metadata
# ---------------------------------------------------------------------------


def test_panel_absent_when_no_metadata(pytester: Pytester) -> None:
    """When no hook and no fixture contribute data the panel is not rendered."""
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _get_report_html(pytester)
    data = _extract_report_data(html)
    assert data["system_metadata"] == {}, f"Expected empty dict; got {data['system_metadata']!r}"
    assert "System Data" not in html, "'System Data' heading must not appear when no metadata"


# ---------------------------------------------------------------------------
# Task 5.7 — report_metadata fixture usable WITHOUT --report-dir
# ---------------------------------------------------------------------------


def test_fixture_usable_without_report_dir(pytester: Pytester) -> None:
    """Requesting report_metadata without --report-dir returns a usable dict (no crash)."""
    pytester.makepyfile("""
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def _write(report_metadata):
            report_metadata.setdefault("CI", {})["build"] = "999"

        def test_pass():
            assert True
    """)
    result = pytester.runpytest()
    assert result.ret == 0, f"Expected exit 0; got {result.ret}\n{result.stdout.str()}"
    result.stdout.no_fnmatch_line("*AttributeError*")
    result.stdout.no_fnmatch_line("*RuntimeError*")


# ---------------------------------------------------------------------------
# Task 5.8 — non-string values coerced to str
# ---------------------------------------------------------------------------


def test_non_string_values_coerced(pytester: Pytester) -> None:
    """int, bool, float, and None hook values are stringified correctly."""
    pytester.makeconftest("""
        def pytest_reporter_metadata():
            return {"Stats": {"count": 5, "ok": True, "ratio": 0.99, "tag": None}}
    """)
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _get_report_html(pytester)
    # Verify the HTML is parseable as valid JSON embed
    data = _extract_report_data(html)
    stats = data["system_metadata"]["Stats"]
    assert stats["count"] == "5", f"Expected '5'; got {stats['count']!r}"
    assert stats["ok"] == "True", f"Expected 'True'; got {stats['ok']!r}"
    assert stats["ratio"] == "0.99", f"Expected '0.99'; got {stats['ratio']!r}"
    assert stats["tag"] == "None", f"Expected 'None'; got {stats['tag']!r}"


# ---------------------------------------------------------------------------
# Observer-Only: hook that raises must not abort report generation
# ---------------------------------------------------------------------------


def test_raising_hook_does_not_abort_report(pytester: Pytester) -> None:
    """A conftest hook that raises must NOT abort report.html generation.

    The reporter follows the observer-only principle: third-party hook failures
    are isolated so the HTML report is still produced with fixture-provided
    metadata intact.  The failing hook's data is silently dropped.

    Assertions:
    - The test session still completes (exit code 0 or 1 from test outcomes,
      NOT from an INTERNALERROR caused by an unguarded exception in
      pytest_sessionfinish).
    - report.html IS written (report generation degrades gracefully).
    - The session exit code is NOT 3 (INTERNALERROR code used by pytest when
      a hook raises inside sessionfinish).
    - The fixture-provided metadata (not from the failing hook) still appears
      in the embedded JSON.
    """
    pytester.makeconftest("""
        import pytest

        def pytest_reporter_metadata():
            raise RuntimeError("deliberate hook failure")

        @pytest.fixture(scope="session", autouse=True)
        def _write_meta(report_metadata):
            # Fixture metadata should still appear despite the hook crash.
            report_metadata.setdefault("CI", {})["status"] = "ok"
    """)
    pytester.makepyfile("""
        def test_p():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")

    # Test outcomes must be unaffected.
    result.assert_outcomes(passed=1)

    # report.html must be written — graceful degradation.
    runs = list((pytester.path / "reports" / "runs").iterdir())
    assert runs, "No run directory found under reports/runs/"
    run_dir = sorted(runs)[-1]
    report_path = run_dir / "report.html"
    assert report_path.exists(), (
        "report.html was NOT written — the raising hook aborted report generation"
    )

    # Fixture-provided metadata must still be in the report.
    html = report_path.read_text(encoding="utf-8")
    data = _extract_report_data(html)
    assert data["system_metadata"].get("CI", {}).get("status") == "ok", (
        f"Fixture metadata missing from report after hook failure: {data['system_metadata']!r}"
    )
