"""Pytester integration tests for crash-safety guard on Reporter hookimpls.

All T1-T8 tests are expected to FAIL (RED) until Phase 2 (reporter.py refactor)
is complete. The tests are written against the POST-refactor API where each hook
delegates to a _do_<hookname> private method.

Warning-assertion strategy: pytest.warns / recwarn do NOT cross the pytester
subprocess boundary. Warnings are asserted via result.stdout.str() parsing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


# ---------------------------------------------------------------------------
# T1: Injected exception in pytest_sessionstart → session continues + warning
# ---------------------------------------------------------------------------


def test_injected_exception_sessionstart_warns_and_continues(pytester: Pytester) -> None:
    """REQ-1 + REQ-5: RuntimeError in _do_sessionstart → no INTERNALERROR, warning emitted.

    Uses runpytest_subprocess() for true process isolation so the warning appears
    in the subprocess stdout/stderr rather than leaking into the outer pytest session.
    """
    pytester.makeconftest("""
        from pytest_reporter.reporter import Reporter

        def _bad_sessionstart(self, session):
            raise RuntimeError("boom sessionstart")

        def pytest_configure(config):
            Reporter._do_sessionstart = _bad_sessionstart
    """)
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest_subprocess("--report-dir=reports", "-W", "always")
    output = result.stdout.str() + result.stderr.str()
    # Must not abort with INTERNALERROR
    assert "INTERNALERROR" not in output
    assert result.ret != 3
    # Warning must be present in output
    assert "pytest-reporter: pytest_sessionstart failed and was skipped" in output
    assert "RuntimeError" in output
    assert "boom sessionstart" in output


# ---------------------------------------------------------------------------
# T2: Injected exception in pytest_runtest_logreport → session still exits 0
# ---------------------------------------------------------------------------


def test_injected_exception_logreport_warns_and_continues(pytester: Pytester) -> None:
    """REQ-1 + REQ-5: RuntimeError in _do_runtest_logreport → no INTERNALERROR, warning.

    Uses runpytest_subprocess() for true process isolation.
    """
    pytester.makeconftest("""
        from pytest_reporter.reporter import Reporter

        def _bad_logreport(self, report):
            raise RuntimeError("boom logreport")

        def pytest_configure(config):
            Reporter._do_runtest_logreport = _bad_logreport
    """)
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest_subprocess("--report-dir=reports", "-W", "always")
    output = result.stdout.str() + result.stderr.str()
    assert "INTERNALERROR" not in output
    assert result.ret != 3
    assert "pytest-reporter: pytest_runtest_logreport failed and was skipped" in output
    assert "RuntimeError" in output


# ---------------------------------------------------------------------------
# T3: Injected exception in _do_sessionfinish outer layer → session ends cleanly
# ---------------------------------------------------------------------------


def test_injected_exception_sessionfinish_warns_and_continues(pytester: Pytester) -> None:
    """REQ-1 + REQ-5: RuntimeError in _do_sessionfinish → no INTERNALERROR, warning emitted.

    Uses runpytest_subprocess() for true process isolation to avoid class-level
    mutation leaking into subsequent in-process pytester tests.
    """
    pytester.makeconftest("""
        from pytest_reporter.reporter import Reporter

        def _bad_sessionfinish(self, session, exitstatus):
            raise RuntimeError("boom sessionfinish")

        def pytest_configure(config):
            Reporter._do_sessionfinish = _bad_sessionfinish
    """)
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest_subprocess("--report-dir=reports", "-W", "always")
    output = result.stdout.str() + result.stderr.str()
    assert "INTERNALERROR" not in output
    assert result.ret != 3
    assert "pytest-reporter: pytest_sessionfinish failed and was skipped" in output


# ---------------------------------------------------------------------------
# T4: Control-flow — pytest.skip() not swallowed (REQ-2)
# ---------------------------------------------------------------------------


def test_skip_propagates_through_reporter(pytester: Pytester) -> None:
    """REQ-2: A test that calls pytest.skip() still reports as skipped, not error."""
    pytester.makepyfile("""
        import pytest

        def test_skipped():
            pytest.skip("skipping this")
    """)
    result = pytester.runpytest("--report-dir=reports")
    stdout = result.stdout.str()
    assert "INTERNALERROR" not in stdout
    result.assert_outcomes(skipped=1)


# ---------------------------------------------------------------------------
# T5: Control-flow — pytest.fail() not swallowed (REQ-2)
# ---------------------------------------------------------------------------


def test_fail_propagates_through_reporter(pytester: Pytester) -> None:
    """REQ-2: A test that calls pytest.fail() still reports as failed, not error."""
    pytester.makepyfile("""
        import pytest

        def test_failing():
            pytest.fail("broken")
    """)
    result = pytester.runpytest("--report-dir=reports")
    stdout = result.stdout.str()
    assert "INTERNALERROR" not in stdout
    result.assert_outcomes(failed=1)


# ---------------------------------------------------------------------------
# T6: Protocol default=None — test still runs when pytest_runtest_protocol guard fires
# ---------------------------------------------------------------------------


def test_protocol_guard_default_none_lets_pytest_run_test(pytester: Pytester) -> None:
    """REQ-3: When run_with_retries raises, guard returns None so pytest runs its protocol.

    The test must still produce a definite outcome (passed or failed), proving
    the 'default=None' design choice is correct — NOT True (which would silently
    mark the test as handled and skip pytest's own protocol).
    """
    pytester.makeconftest("""
        import pytest
        from pytest_reporter import _retry

        original_run = _retry.run_with_retries

        def _bad_run(reporter, item, nextitem):
            raise RuntimeError("boom protocol")

        _retry.run_with_retries = _bad_run
    """)
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    stdout = result.stdout.str()
    assert "INTERNALERROR" not in stdout
    # The test must still have an outcome — not silently skipped
    outcomes = result.parseoutcomes()
    total = sum(outcomes.get(k, 0) for k in ("passed", "failed", "error", "skipped"))
    assert total >= 1, f"No test outcomes recorded: {outcomes}"


# ---------------------------------------------------------------------------
# T7: Class-based / unittest.TestCase tests run cleanly with --report-dir (REQ-4)
# ---------------------------------------------------------------------------


def test_class_based_unittest_with_report_dir(pytester: Pytester) -> None:
    """REQ-4: unittest.TestCase and plain class tests produce valid reports, no INTERNALERROR."""
    pytester.makepyfile("""
        import unittest

        class TestUnittestStyle(unittest.TestCase):
            def test_one(self):
                self.assertEqual(1, 1)

            def test_two(self):
                self.assertTrue(True)

        class TestPlainClass:
            def test_three(self):
                assert 3 == 3
    """)
    result = pytester.runpytest("--report-dir=reports")
    stdout = result.stdout.str()
    assert "INTERNALERROR" not in stdout
    result.assert_outcomes(passed=3)

    # Run folder must exist
    runs = list((pytester.path / "reports" / "runs").iterdir())
    assert len(runs) == 1
    run_dir = runs[0]
    assert (run_dir / "report.html").exists()

    # No path component may contain '::' (Windows illegal)
    for p in run_dir.rglob("*"):
        relative = str(p.relative_to(run_dir))
        for component in relative.split("/"):
            assert "::" not in component, f"Path component contains '::': {component!r} in {p}"


# ---------------------------------------------------------------------------
# T8: Mixed function-based + class-based in same file — both produce entries
# ---------------------------------------------------------------------------


def test_mixed_function_and_class_based_tests(pytester: Pytester) -> None:
    """REQ-4: Function-based and class-based tests in the same file both get report entries."""
    pytester.makepyfile("""
        import unittest

        def test_function():
            assert True

        class TestClassBased(unittest.TestCase):
            def test_method(self):
                self.assertTrue(True)
    """)
    result = pytester.runpytest("--report-dir=reports")
    stdout = result.stdout.str()
    assert "INTERNALERROR" not in stdout
    result.assert_outcomes(passed=2)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    assert len(runs) == 1
    run_dir = runs[0]

    # Find tests directory entries
    tests_root = run_dir / "tests"
    assert tests_root.exists()

    # Both function and class-based test directories must exist without '::'
    all_dirs = [p for p in tests_root.rglob("*") if p.is_dir()]
    for d in all_dirs:
        for component in str(d.relative_to(tests_root)).split("/"):
            assert "::" not in component, f"Path component contains '::': {component!r}"
