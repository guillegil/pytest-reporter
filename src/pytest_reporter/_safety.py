"""Crash-safety guard helpers for Reporter hookimpls.

Each hookimpl body delegates its real work through ``guard`` or ``guard_void``.
On any genuine internal exception the helpers emit a ``UserWarning`` and return a
hook-appropriate safe default so the user's pytest session continues uninterrupted.

Control-flow / outcome exceptions are always re-raised:
- ``KeyboardInterrupt`` and ``SystemExit`` (not ``Exception`` subclasses; re-raised
  explicitly for clarity and to guard against future ``except BaseException`` edits).
- ``_pytest.outcomes.OutcomeException`` (base of ``Skipped``, ``Failed``, ``Exit``,
  ``XFailed``). These ARE ``Exception`` subclasses so a naive broad ``except``
  would silently convert a skipped test into an internal error — exactly the bug
  this module exists to prevent.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import TypeVar

from _pytest.outcomes import OutcomeException

T = TypeVar("T")


def _format(hook_name: str, exc: Exception) -> str:
    """Build the canonical warning message for a caught hook exception.

    Args:
        hook_name: The pytest hook name that raised (e.g. ``pytest_sessionstart``).
        exc: The caught exception instance.

    Returns:
        A formatted string identifying the reporter, hook, exception type and message.
    """
    return f"pytest-reporter: {hook_name} failed and was skipped: {type(exc).__name__}: {exc}"


def guard(hook_name: str, fn: Callable[[], T], *, default: T) -> T:
    """Run *fn* inside a control-flow-safe try/except.

    On success returns ``fn()`` unchanged.  On a caught internal ``Exception``
    emits a ``UserWarning`` and returns *default* so the hook degrades gracefully
    without aborting the pytest session.

    Control-flow exceptions (``KeyboardInterrupt``, ``SystemExit``,
    ``OutcomeException``) are always re-raised before the broad catch.

    Args:
        hook_name: Name of the hook being guarded, used in the warning message.
        fn: Zero-argument callable wrapping the hook's real body.
        default: Value returned when *fn* raises an internal exception.

    Returns:
        The return value of ``fn()`` on success, or *default* on failure.
    """
    try:
        return fn()
    except (KeyboardInterrupt, SystemExit):
        raise
    except OutcomeException:  # Skipped / Failed / Exit / XFailed — pytest control flow
        raise
    except Exception as exc:  # noqa: BLE001
        warnings.warn(_format(hook_name, exc), stacklevel=2)
        return default


def guard_void(hook_name: str, fn: Callable[[], None]) -> None:
    """Convenience wrapper over :func:`guard` for ``-> None`` hookimpls.

    Avoids the ``default=None`` noise at every call site while keeping
    ``mypy --strict`` happy (no ``T | None`` inference issues).

    Args:
        hook_name: Name of the hook being guarded, used in the warning message.
        fn: Zero-argument callable wrapping the hook's real body.
    """
    guard(hook_name, fn, default=None)
