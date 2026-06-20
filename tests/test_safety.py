"""Unit tests for the _safety guard helper (no pytester needed)."""

from __future__ import annotations

import warnings

import pytest

# These tests run in-process; _safety must be importable once it exists.
# Until task 1.2 creates the module, these will fail with ImportError — that
# is the expected RED state.
from pytest_reporter._safety import guard, guard_void


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _returns(value: object) -> object:
    """Helper: a callable that returns a fixed value."""
    return guard("test_hook", lambda: value, default="WRONG")


def _raises(exc: BaseException) -> None:
    """Helper: a callable that raises exc."""
    raise exc


# ---------------------------------------------------------------------------
# (a) Normal return passthrough
# ---------------------------------------------------------------------------


def test_guard_passthrough_value() -> None:
    """guard() returns the fn() result unchanged when no exception occurs."""
    result = guard("hook", lambda: 42, default=0)
    assert result == 42


def test_guard_void_passthrough() -> None:
    """guard_void() calls fn() normally and returns None."""
    called: list[bool] = []
    guard_void("hook", lambda: called.append(True))
    assert called == [True]


# ---------------------------------------------------------------------------
# (b) Exception caught → UserWarning emitted + default returned
# ---------------------------------------------------------------------------


def test_guard_catches_runtime_error_and_warns() -> None:
    """RuntimeError is caught; UserWarning is emitted; default is returned."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = guard("pytest_sessionstart", lambda: (_ for _ in ()).throw(RuntimeError("boom")), default="safe")
    assert result == "safe"
    assert len(caught) == 1
    w = caught[0]
    assert issubclass(w.category, UserWarning)
    assert "pytest-reporter" in str(w.message)
    assert "pytest_sessionstart" in str(w.message)
    assert "RuntimeError" in str(w.message)
    assert "boom" in str(w.message)


def test_guard_catches_os_error_and_warns() -> None:
    """OSError is caught; default returned; warning contains hook + exc info."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        def _fn() -> None:
            raise OSError("disk full")

        result = guard("pytest_sessionfinish", _fn, default=None)
    assert result is None
    assert len(caught) == 1
    msg = str(caught[0].message)
    assert "pytest_sessionfinish" in msg
    assert "OSError" in msg
    assert "disk full" in msg


def test_guard_void_catches_exception_and_warns() -> None:
    """guard_void catches an Exception and emits UserWarning; returns None."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = guard_void("pytest_runtest_logreport", lambda: (_ for _ in ()).throw(ValueError("bad")))
    assert result is None
    assert len(caught) == 1
    assert "ValueError" in str(caught[0].message)


def test_warning_message_format() -> None:
    """Warning message must follow the exact format from the design."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        guard("my_hook", lambda: (_ for _ in ()).throw(TypeError("oops")), default=None)
    msg = str(caught[0].message)
    # Design mandates: "pytest-reporter: {hook_name} failed and was skipped: {ExcType}: {exc}"
    assert msg == "pytest-reporter: my_hook failed and was skipped: TypeError: oops"


# ---------------------------------------------------------------------------
# (c) KeyboardInterrupt re-raised
# ---------------------------------------------------------------------------


def test_guard_reraises_keyboard_interrupt() -> None:
    """KeyboardInterrupt must propagate — never be swallowed."""
    with pytest.raises(KeyboardInterrupt):
        guard("hook", lambda: (_ for _ in ()).throw(KeyboardInterrupt()), default=None)


# ---------------------------------------------------------------------------
# (d) SystemExit re-raised
# ---------------------------------------------------------------------------


def test_guard_reraises_system_exit() -> None:
    """SystemExit must propagate — never be swallowed."""
    with pytest.raises(SystemExit):
        guard("hook", lambda: (_ for _ in ()).throw(SystemExit(1)), default=None)


# ---------------------------------------------------------------------------
# (e) OutcomeException (Skipped) re-raised
# ---------------------------------------------------------------------------


def test_guard_reraises_skipped() -> None:
    """pytest.skip() (Skipped, an OutcomeException) must propagate unchanged."""
    with pytest.raises(BaseException) as exc_info:
        guard("hook", lambda: pytest.skip("not ready"), default=None)
    # The exception must be the Skipped type, not a UserWarning or generic error
    assert type(exc_info.value).__name__ == "Skipped"


def test_guard_reraises_outcome_exception_failed() -> None:
    """pytest.fail() (Failed OutcomeException) must propagate unchanged."""
    with pytest.raises(BaseException) as exc_info:
        guard("hook", lambda: pytest.fail("broken"), default=None)
    assert type(exc_info.value).__name__ == "Failed"


def test_guard_void_reraises_skipped() -> None:
    """guard_void also re-raises OutcomeException (via guard internally)."""
    with pytest.raises(BaseException) as exc_info:
        guard_void("hook", lambda: pytest.skip("skipping"))
    assert type(exc_info.value).__name__ == "Skipped"
