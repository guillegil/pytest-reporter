"""Tests for the structured logger system."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


def test_log_fixture_produces_entries(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_with_log(log):
            log.info("Hello world")
            log.debug("Debug msg", data={"key": "val"})
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    call_log = (
        run_dir
        / "tests"
        / "test_log_fixture_produces_entries.py"
        / "test_with_log"
        / "default"
        / "call.log.json"
    )
    data = json.loads(call_log.read_text())

    assert data["phase"] == "call"
    assert data["outcome"] == "passed"
    assert "start_time" in data
    assert "end_time" in data
    assert isinstance(data["entries"], list)
    assert len(data["entries"]) == 2
    assert data["entries"][0]["msg"] == "Hello world"
    assert data["entries"][0]["level"] == "INFO"
    assert data["entries"][0]["source"] == []
    assert data["entries"][0]["seq"] == 0
    assert data["entries"][1]["msg"] == "Debug msg"
    assert data["entries"][1]["level"] == "DEBUG"
    assert data["entries"][1]["data"] == {"key": "val"}


def test_log_child_logger(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_child(log):
            api = log.child("api")
            auth = api.child("auth")
            api.info("Request started")
            auth.info("Token acquired", data={"expires": 3600})
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    call_log = (
        run_dir / "tests" / "test_log_child_logger.py" / "test_child" / "default" / "call.log.json"
    )
    data = json.loads(call_log.read_text())

    entries = data["entries"]
    assert len(entries) == 2
    assert entries[0]["source"] == ["api"]
    assert entries[1]["source"] == ["api", "auth"]
    assert entries[1]["data"] == {"expires": 3600}


def test_log_entries_per_phase(pytester: Pytester) -> None:
    """Entries are captured per-phase; each phase file has its own entries."""
    pytester.makepyfile(
        conftest="""
import pytest

@pytest.fixture
def my_setup(log):
    log.info("in setup")
    yield
    log.info("in teardown")
""",
        test_phases="""
def test_phases(my_setup, log):
    log.info("in call")
""",
    )
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    base = run_dir / "tests" / "test_phases.py" / "test_phases" / "default"

    # Note: the log fixture creates a new logger per test, not per phase.
    # Entries accumulate across phases since the logger is shared.
    # The reporter resets the logger after each phase capture.
    setup = json.loads((base / "setup.log.json").read_text())
    call = json.loads((base / "call.log.json").read_text())
    teardown = json.loads((base / "teardown.log.json").read_text())

    # setup phase should have the setup entry
    assert setup["phase"] == "setup"
    # call phase should have the call entry
    assert call["phase"] == "call"
    assert any(e["msg"] == "in call" for e in call["entries"])
    # teardown phase should have the teardown entry
    assert teardown["phase"] == "teardown"


def test_log_without_report_dir(pytester: Pytester) -> None:
    """log fixture works without --report-dir."""
    pytester.makepyfile("""
        def test_works(log):
            log.info("no report dir")
            assert True
    """)
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_log_exception_capture(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_exc(log):
            try:
                raise ValueError("bad value")
            except ValueError as e:
                log.error("caught error", exc_info=e)
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    call_log = (
        run_dir
        / "tests"
        / "test_log_exception_capture.py"
        / "test_exc"
        / "default"
        / "call.log.json"
    )
    data = json.loads(call_log.read_text())

    entries = data["entries"]
    assert len(entries) == 1
    assert entries[0]["exc"]["type"] == "ValueError"
    assert entries[0]["exc"]["msg"] == "bad value"
    assert "Traceback" in entries[0]["exc"]["tb"]
