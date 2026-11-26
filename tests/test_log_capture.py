"""Python logging records in the phase logs (``_log_capture``)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import Pytester


def _phase(pytester: Pytester, test: str, when: str, sub: str = "default") -> list[dict[str, Any]]:
    run_dir = next((pytester.path / "reports" / "runs").iterdir())
    path: Path = next((run_dir / "tests").rglob(f"{test}/{sub}/{when}.log.json"))
    entries: list[dict[str, Any]] = json.loads(path.read_text())["entries"]
    return entries


def test_records_go_to_the_phase_that_logged_them(pytester: Pytester) -> None:
    pytester.makepyfile("""
        import logging
        import pytest

        log = logging.getLogger("bench.psu")

        @pytest.fixture
        def psu():
            log.info("power on")
            yield
            log.info("power off")

        def test_measure(psu):
            log.info("measured %.1f V", 3.3)
    """)
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)

    setup = _phase(pytester, "test_measure", "setup")
    call = _phase(pytester, "test_measure", "call")
    teardown = _phase(pytester, "test_measure", "teardown")
    assert [e["msg"] for e in setup] == ["power on"]
    assert [e["msg"] for e in call] == ["measured 3.3 V"]
    assert [e["msg"] for e in teardown] == ["power off"]
    entry = call[0]
    assert entry["level"] == "INFO"
    assert entry["source"] == ["bench", "psu"]
    assert entry["seq"] == 0
    assert entry["t"].endswith("Z")
    assert entry["data"] is None
    assert entry["exc"] is None


def test_root_logger_has_an_empty_source(pytester: Pytester) -> None:
    pytester.makepyfile("""
        import logging

        def test_root():
            logging.warning("from root")
    """)
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    assert _phase(pytester, "test_root", "call")[0]["source"] == []


def test_extra_fields_are_the_data_and_exceptions_are_kept(pytester: Pytester) -> None:
    pytester.makepyfile("""
        import logging

        log = logging.getLogger("t")

        def test_data():
            log.info("connected", extra={"port": 5025, "where": ("lab", 3)})
            try:
                1 / 0
            except ZeroDivisionError:
                log.exception("failed")
    """)
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    connected, failed = _phase(pytester, "test_data", "call")
    assert connected["data"] == {"port": 5025, "where": ["lab", 3]}
    assert failed["level"] == "ERROR"
    assert failed["exc"]["type"] == "ZeroDivisionError"
    assert "Traceback" in failed["exc"]["tb"]


def test_default_level_is_info(pytester: Pytester) -> None:
    pytester.makepyfile("""
        import logging

        def test_levels():
            logging.getLogger("t").debug("hidden")
            logging.getLogger("t").info("shown")
    """)
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    assert [e["msg"] for e in _phase(pytester, "test_levels", "call")] == ["shown"]


def test_report_log_level_wins(pytester: Pytester) -> None:
    pytester.makeini("""
        [pytest]
        log_level = WARNING
        report_log_level = DEBUG
    """)
    pytester.makepyfile("""
        import logging

        def test_levels():
            logging.getLogger("t").debug("debug")
    """)
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    assert [e["msg"] for e in _phase(pytester, "test_levels", "call")] == ["debug"]


def test_pytest_log_level_is_followed(pytester: Pytester) -> None:
    pytester.makepyfile("""
        import logging

        def test_levels():
            logging.getLogger("t").info("info")
            logging.getLogger("t").warning("warning")
    """)
    pytester.runpytest("--report-dir=reports", "--log-level=WARNING").assert_outcomes(passed=1)
    assert [e["msg"] for e in _phase(pytester, "test_levels", "call")] == ["warning"]


def test_bad_level_is_a_usage_error(pytester: Pytester) -> None:
    pytester.makeini("""
        [pytest]
        report_log_level = LOUD
    """)
    pytester.makepyfile("def test_x(): pass")
    result = pytester.runpytest("--report-dir=reports")
    assert result.ret != 0
    result.stderr.fnmatch_lines(["*report_log_level*LOUD*"])


def test_root_level_is_restored_after_each_phase(pytester: Pytester) -> None:
    pytester.makepyfile("""
        import logging

        def test_first():
            assert logging.getLogger().level == logging.INFO

        def test_after():
            pass

        def teardown_module():
            pass
    """)
    pytester.makeconftest("""
        import logging

        def pytest_runtest_logfinish(nodeid):
            assert logging.getLogger().level == logging.WARNING, nodeid
    """)
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=2)


def test_each_retry_attempt_has_its_own_records(pytester: Pytester) -> None:
    pytester.makepyfile("""
        import logging
        import pytest

        runs = []

        @pytest.fixture
        def counter():
            logging.getLogger("t").info("setup %d", len(runs) + 1)
            yield

        def test_flaky(counter):
            runs.append(1)
            logging.getLogger("t").info("attempt %d", len(runs))
            assert len(runs) > 1
    """)
    pytester.runpytest("--report-dir=reports", "--report-retries=1").assert_outcomes(passed=1)
    assert [e["msg"] for e in _phase(pytester, "test_flaky", "setup")] == ["setup 1"]
    assert [e["msg"] for e in _phase(pytester, "test_flaky", "call")] == ["attempt 1"]
    retry = _phase(pytester, "test_flaky", "call", "default/retries/01")
    assert [e["msg"] for e in retry] == ["attempt 2"]
    retry_setup = _phase(pytester, "test_flaky", "setup", "default/retries/01")
    assert [e["msg"] for e in retry_setup] == ["setup 2"]


def test_logs_show_in_the_html_report(pytester: Pytester) -> None:
    pytester.makepyfile("""
        import logging

        def test_html():
            logging.getLogger("bench").info("visible in the report")
    """)
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    run_dir = next((pytester.path / "reports" / "runs").iterdir())
    assert "visible in the report" in (run_dir / "report.html").read_text(encoding="utf-8")


def test_removed_fixtures_say_what_to_use(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_old(log):
            pass

        def test_old_session(session_log):
            pass
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(errors=2)
    result.stdout.fnmatch_lines(["*`log` fixture was removed*logging.getLogger*"])
    result.stdout.fnmatch_lines(["*`session_log` fixture was removed*"])


def test_no_handler_without_report_dir(pytester: Pytester) -> None:
    pytester.makepyfile("""
        import logging

        def test_handlers():
            names = [type(h).__module__ for h in logging.getLogger().handlers]
            assert "pytest_reporter._log_capture" not in names
    """)
    pytester.runpytest().assert_outcomes(passed=1)
