"""Tests for the retry system."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


def test_retries_disabled_by_default(pytester: Pytester) -> None:
    """No retries when --report-retries is not specified."""
    pytester.makepyfile("""
        def test_fail():
            assert False
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(failed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    test_dir = run_dir / "tests" / "test_retries_disabled_by_default.py" / "test_fail" / "default"
    assert not (test_dir / "retries").exists()


def test_retry_passes_on_second_attempt(pytester: Pytester) -> None:
    """Test that fails first then passes on retry."""
    pytester.makepyfile("""
        _counter = 0

        def test_flaky():
            global _counter
            _counter += 1
            assert _counter >= 2
    """)
    result = pytester.runpytest("--report-dir=reports", "--report-retries=3")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    test_dir = run_dir / "tests" / "test_retry_passes_on_second_attempt.py" / "test_flaky" / "default"

    # Retries directory should exist
    retries_dir = test_dir / "retries"
    assert retries_dir.exists()
    assert (retries_dir / "01").is_dir()

    # Retry 01 should have phase logs
    assert (retries_dir / "01" / "call.log.json").exists()
    retry_call = json.loads((retries_dir / "01" / "call.log.json").read_text())
    assert retry_call["outcome"] == "passed"

    # Original call should have failed
    orig_call = json.loads((test_dir / "call.log.json").read_text())
    assert orig_call["outcome"] == "failed"

    # test.log.json should show final outcome as passed with retry info
    func_dir = test_dir.parent
    agg = json.loads((func_dir / "test.log.json").read_text())
    assert agg["passed"] == 1
    assert agg["failed"] == 0
    run_entry = agg["runs"][0]
    assert run_entry["outcome"] == "passed"
    assert "retries" in run_entry
    assert run_entry["retries"]["attempts"] == 1
    assert run_entry["retries"]["original_outcome"] == "failed"
    assert run_entry["retries"]["history"] == ["failed", "passed"]


def test_retry_all_fail(pytester: Pytester) -> None:
    """All retries fail — final outcome is failed."""
    pytester.makepyfile("""
        def test_always_fails():
            assert False
    """)
    result = pytester.runpytest("--report-dir=reports", "--report-retries=2")
    result.assert_outcomes(failed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    test_dir = run_dir / "tests" / "test_retry_all_fail.py" / "test_always_fails" / "default"

    retries_dir = test_dir / "retries"
    assert retries_dir.exists()
    assert (retries_dir / "01").is_dir()
    assert (retries_dir / "02").is_dir()

    func_dir = test_dir.parent
    agg = json.loads((func_dir / "test.log.json").read_text())
    assert agg["failed"] == 1
    run_entry = agg["runs"][0]
    assert run_entry["outcome"] == "failed"
    assert run_entry["retries"]["attempts"] == 2
    assert run_entry["retries"]["history"] == ["failed", "failed", "failed"]


def test_retry_no_parameters_json_in_retries(pytester: Pytester) -> None:
    """parameters.json should only be in the main run dir, not retries."""
    pytester.makepyfile("""
        _counter = 0

        def test_flaky():
            global _counter
            _counter += 1
            assert _counter >= 2
    """)
    result = pytester.runpytest("--report-dir=reports", "--report-retries=1")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    test_dir = run_dir / "tests" / "test_retry_no_parameters_json_in_retries.py" / "test_flaky" / "default"

    assert (test_dir / "parameters.json").exists()
    assert not (test_dir / "retries" / "01" / "parameters.json").exists()


def test_retry_procedure_per_attempt(pytester: Pytester) -> None:
    """Each retry gets its own procedure.json."""
    pytester.makepyfile("""
        from pytest_reporter import step

        _counter = 0

        def test_flaky():
            global _counter
            _counter += 1
            step("Attempt check")
            assert _counter >= 2
    """)
    result = pytester.runpytest("--report-dir=reports", "--report-retries=1")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    test_dir = run_dir / "tests" / "test_retry_procedure_per_attempt.py" / "test_flaky" / "default"

    # Original and retry both have procedure.json
    assert (test_dir / "procedure.json").exists()
    assert (test_dir / "retries" / "01" / "procedure.json").exists()


def test_retry_skipped_not_retried(pytester: Pytester) -> None:
    pytester.makepyfile("""
        import pytest

        @pytest.mark.skip(reason="not ready")
        def test_skip():
            pass
    """)
    result = pytester.runpytest("--report-dir=reports", "--report-retries=2")
    result.assert_outcomes(skipped=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    test_dir = run_dir / "tests" / "test_retry_skipped_not_retried.py" / "test_skip" / "default"
    assert not (test_dir / "retries").exists()


def test_retry_junit_xml_properties(pytester: Pytester) -> None:
    """JUnit XML includes retry properties for retried tests."""
    pytester.makepyfile("""
        _counter = 0

        def test_flaky():
            global _counter
            _counter += 1
            assert _counter >= 2
    """)
    result = pytester.runpytest("--report-dir=reports", "--report-retries=1")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    xml_content = (runs[0] / "junit.xml").read_text()
    assert 'name="retries"' in xml_content
    assert 'value="1"' in xml_content
    assert 'name="original_outcome"' in xml_content
    assert 'value="failed"' in xml_content


def test_retry_failure_log_only_original(pytester: Pytester) -> None:
    """failures/ dir only has the original failure, not retry failures."""
    pytester.makepyfile("""
        def test_always_fail():
            assert False
    """)
    result = pytester.runpytest("--report-dir=reports", "--report-retries=2")
    result.assert_outcomes(failed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    failures = list((runs[0] / "failures").iterdir())
    # Should only have 1 failure log (original), not 3
    assert len(failures) == 1


def test_retry_parametrized_independent(pytester: Pytester) -> None:
    """Each parametrized run is retried independently."""
    pytester.makepyfile("""
        import pytest

        _counters = {}

        @pytest.mark.parametrize("x", [1, 2])
        def test_param(x):
            _counters.setdefault(x, 0)
            _counters[x] += 1
            if x == 2:
                assert _counters[x] >= 2  # fails first, passes on retry
            else:
                assert True  # always passes
    """)
    result = pytester.runpytest("--report-dir=reports", "--report-retries=1")
    result.assert_outcomes(passed=2)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    test_dir = run_dir / "tests" / "test_retry_parametrized_independent.py" / "test_param"

    # Run 01 (x=1) should NOT have retries
    assert not (test_dir / "01" / "retries").exists()
    # Run 02 (x=2) SHOULD have retries
    assert (test_dir / "02" / "retries" / "01").is_dir()
