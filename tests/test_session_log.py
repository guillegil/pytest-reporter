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


def test_session_log_with_entries(pytester: Pytester) -> None:
    pytester.makepyfile(
        conftest="""
import pytest

@pytest.fixture(scope="session")
def instrument(session_log):
    tb = session_log.child("testbench")
    tb.info("Discovering instruments")
    psu = tb.child("psu")
    psu.info("Connected", data={"model": "Keysight E36312A"})
    yield "instrument"
    tb.info("Disconnecting")
""",
        test_session="""
def test_uses_instrument(instrument):
    assert instrument == "instrument"
""",
    )
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    data = json.loads((runs[0] / "session.log.json").read_text())

    entries = data["entries"]
    assert len(entries) >= 2
    assert entries[0]["source"] == ["testbench"]
    assert entries[0]["msg"] == "Discovering instruments"
    assert entries[1]["source"] == ["testbench", "psu"]
    assert entries[1]["msg"] == "Connected"
    assert entries[1]["data"]["model"] == "Keysight E36312A"


def test_session_log_independent_from_test_log(pytester: Pytester) -> None:
    """session_log and log fixtures produce separate outputs."""
    pytester.makepyfile(
        conftest="""
import pytest

@pytest.fixture(scope="session")
def setup_once(session_log):
    session_log.info("session setup")
    yield
""",
        test_independent="""
def test_a(setup_once, log):
    log.info("test log entry")
""",
    )
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    session_data = json.loads((runs[0] / "session.log.json").read_text())
    # Session log should have the session entry
    assert any(e["msg"] == "session setup" for e in session_data["entries"])
    # Session log should NOT have the test entry
    assert not any(e["msg"] == "test log entry" for e in session_data["entries"])
