"""Tests for session-level logging."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


def test_session_log_json_created(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    session_log = run_dir / "session.log.json"
    assert session_log.exists()
    data = json.loads(session_log.read_text())
    assert data["phase"] == "session"
    assert "start_time" in data
    assert "end_time" in data
    assert "duration_seconds" in data
    assert isinstance(data["entries"], list)


def test_session_log_empty_when_unused(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    data = json.loads((runs[0] / "session.log.json").read_text())
    assert data["entries"] == []


def test_session_log_has_records_from_outside_tests(pytester: Pytester) -> None:
    """Logging outside any test phase (here: a plugin hook) goes to the session log."""
    pytester.makepyfile(
        conftest="""
import logging

def pytest_sessionstart(session):
    logging.getLogger("testbench.psu").warning("Connected", extra={"model": "E36312A"})

def pytest_collection_finish(session):
    logging.getLogger("testbench").warning("Collected")
""",
        test_session="""
def test_pass():
    pass
""",
    )
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    entries = json.loads((runs[0] / "session.log.json").read_text())["entries"]
    by_msg = {e["msg"]: e for e in entries}
    assert by_msg["Collected"]["source"] == ["testbench"]
    assert by_msg["Connected"]["source"] == ["testbench", "psu"]
    assert by_msg["Connected"]["level"] == "WARNING"
    assert by_msg["Connected"]["data"] == {"model": "E36312A"}


def test_session_log_independent_from_test_log(pytester: Pytester) -> None:
    """Records of a test phase never reach the session log."""
    pytester.makepyfile(
        conftest="""
import logging

def pytest_collection_finish(session):
    logging.getLogger("session").warning("session setup")
""",
        test_independent="""
import logging

def test_a():
    logging.getLogger("t").warning("test log entry")
""",
    )
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    session_data = json.loads((runs[0] / "session.log.json").read_text())
    assert any(e["msg"] == "session setup" for e in session_data["entries"])
    assert not any(e["msg"] == "test log entry" for e in session_data["entries"])
