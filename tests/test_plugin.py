"""Integration tests for pytest-reporter using pytester."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


def test_no_report_without_flag(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
    assert not (pytester.path / "reports").exists()


def test_report_dir_created(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)
    reports = pytester.path / "reports"
    assert reports.exists()
    assert (reports / "runs").exists()
    # 01_latest is a hard copy of the most recent run
    assert (reports / "01_latest").is_dir()
    assert not (reports / "01_latest").is_symlink()
    assert not (reports / "02_latest_failures").exists()


def test_run_directory_structure(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    # Find the run directory
    runs = list((pytester.path / "reports" / "runs").iterdir())
    assert len(runs) == 1
    run_dir = runs[0]

    assert (run_dir / "report.html").exists()
    assert (run_dir / "junit.xml").exists()
    assert (run_dir / "pytest.log").exists()
    assert (run_dir / "failures").is_dir()
    assert (run_dir / "tests").is_dir()


def test_per_test_files(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_example():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]

    # Find the test function dir
    test_dir = run_dir / "tests" / "test_per_test_files.py" / "test_example"
    assert test_dir.exists()
    assert (test_dir / "test.log.json").exists()
    assert (test_dir / "default").is_dir()
    assert (test_dir / "default" / "parameters.json").exists()
    assert (test_dir / "default" / "procedure.json").exists()
    assert (test_dir / "default" / "setup.log.json").exists()
    assert (test_dir / "default" / "call.log.json").exists()
    assert (test_dir / "default" / "teardown.log.json").exists()
    assert (test_dir / "default" / "artifacts").is_dir()


def test_test_log_json_content(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    test_dir = run_dir / "tests" / "test_test_log_json_content.py" / "test_pass"
    data = json.loads((test_dir / "test.log.json").read_text())

    assert data["function_name"] == "test_pass"
    assert data["total_runs"] == 1
    assert data["passed"] == 1
    assert data["failed"] == 0
    assert len(data["runs"]) == 1
    assert data["runs"][0]["run_id"] == "default"
    assert data["runs"][0]["outcome"] == "passed"


def test_parametrize_run_numbering(pytester: Pytester) -> None:
    pytester.makepyfile("""
        import pytest

        @pytest.mark.parametrize("x", [1, 2, 3])
        def test_param(x):
            assert x > 0
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=3)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    test_dir = run_dir / "tests" / "test_parametrize_run_numbering.py" / "test_param"

    assert (test_dir / "01").is_dir()
    assert (test_dir / "02").is_dir()
    assert (test_dir / "03").is_dir()
    assert not (test_dir / "default").exists()

    # Check parameters.json
    params = json.loads((test_dir / "01" / "parameters.json").read_text())
    assert params["parametrize_id"] is not None
    assert "x" in params["params"]

    # Check aggregate
    agg = json.loads((test_dir / "test.log.json").read_text())
    assert agg["total_runs"] == 3
    assert agg["passed"] == 3


def test_failure_logs(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_fail():
            assert 1 == 2
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(failed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    failures = list((run_dir / "failures").iterdir())
    assert len(failures) == 1
    assert "error.log" in failures[0].name
    content = failures[0].read_text()
    assert "assert 1 == 2" in content


def test_skip_captured(pytester: Pytester) -> None:
    pytester.makepyfile("""
        import pytest

        @pytest.mark.skip(reason="not ready")
        def test_skip():
            pass
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(skipped=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    test_dir = run_dir / "tests" / "test_skip_captured.py" / "test_skip"
    agg = json.loads((test_dir / "test.log.json").read_text())
    assert agg["skipped"] == 1


def test_html_report_is_self_contained(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    html = (runs[0] / "report.html").read_text()
    assert "<!DOCTYPE html>" in html
    assert "<style>" in html
    assert "<script>" in html
    # No external CDN references
    assert "cdn" not in html.lower()
    assert "test_pass" in html


def test_junit_xml(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_pass():
            assert True

        def test_fail():
            assert False
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1, failed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    xml_content = (runs[0] / "junit.xml").read_text()
    assert '<?xml' in xml_content
    assert 'testsuites' in xml_content
    assert 'failures="1"' in xml_content


def test_terminal_summary(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.stdout.fnmatch_lines(["*Report*"])
    result.stdout.fnmatch_lines(["*HTML*report.html*"])
    result.stdout.fnmatch_lines(["*JUnit*junit.xml*"])


def test_latest_copy_mirrors_run(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    reports = pytester.path / "reports"
    latest = reports / "01_latest"
    # 01_latest is a real directory copy, not a symlink
    assert latest.is_dir()
    assert not latest.is_symlink()
    assert (latest / "report.html").exists()

    # Confirm contents match the most recent run
    runs = sorted((reports / "runs").iterdir())
    assert (latest / "report.html").read_bytes() == (runs[-1] / "report.html").read_bytes()

    # 02_latest_failures is no longer created
    assert not (reports / "02_latest_failures").exists()


def test_latest_copy_replaced_on_rerun(pytester: Pytester) -> None:
    """A second run replaces the previous 01_latest copy in place."""
    import time

    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    pytester.runpytest("--report-dir=reports")
    # Sleep past the per-second timestamp granularity so the second run
    # creates a distinct runs/ subfolder.
    time.sleep(1.1)
    pytester.runpytest("--report-dir=reports")

    reports = pytester.path / "reports"
    runs = sorted((reports / "runs").iterdir())
    assert len(runs) == 2

    latest = reports / "01_latest"
    assert latest.is_dir()
    assert not latest.is_symlink()
    # 01_latest mirrors the most recent run, not the older one
    assert (latest / "report.html").read_bytes() == (runs[-1] / "report.html").read_bytes()
    assert (latest / "report.html").read_bytes() != (runs[0] / "report.html").read_bytes()
