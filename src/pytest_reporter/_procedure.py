"""Procedure system -- step/substep tracking for test procedures."""

from __future__ import annotations

import traceback
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from pytest_reporter.fmt import Segment

from pytest_reporter.fmt import FormattedText as _FormattedText


class ProcedureError(Exception):
    """Raised when no active procedure tracker is found (via _get_tracker)."""


class ProcedureNestingError(Exception):
    """Raised when nesting exceeds two levels."""


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _duration(start: str, end: str) -> float:
    s = datetime.fromisoformat(start.replace("Z", "+00:00"))
    e = datetime.fromisoformat(end.replace("Z", "+00:00"))
    return round((e - s).total_seconds(), 6)


def _make_exc(exc: BaseException) -> dict[str, str]:
    return {
        "type": type(exc).__name__,
        "msg": str(exc),
        "tb": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    }


def normalize(description: str | _FormattedText) -> list[Segment] | None:
    """Decide whether *description* produces ``description_segments``.

    Returns ``None`` when no segments key should be stored (plain str, or a
    ``FormattedText`` whose every segment has ``style == None``).  Returns the
    segment list when at least one segment has a non-``None`` style.

    Args:
        description: Either a plain ``str`` or a ``FormattedText``.

    Returns:
        ``list[Segment]`` when styled segments are present; ``None`` otherwise.
    """
    if isinstance(description, str):
        return None
    if any(s["style"] is not None for s in description):
        return list(description)
    return None


def _display(description: str | _FormattedText) -> str:
    """Return the display string for *description*.

    For a plain ``str`` this is the string itself.  For a ``FormattedText``
    this is the concatenation of all segment ``text`` fields.

    Args:
        description: Either a plain ``str`` or a ``FormattedText``.

    Returns:
        A plain string suitable for ``node["description"]``.
    """
    if isinstance(description, str):
        return description
    return "".join(s["text"] for s in description)


def _attach_segments(node: dict[str, Any], description: str | _FormattedText) -> None:
    """Attach ``description_segments`` to *node* when styled segments are present.

    Attaches ``node["description_segments"]`` ONLY when ``normalize`` returns a
    non-``None`` list.  Plain descriptions produce no key — byte-identical to
    pre-change behaviour.

    Args:
        node: The step or substep dict being constructed.
        description: The original description value (str or FormattedText).
    """
    segs = normalize(description)
    if segs is not None:
        node["description_segments"] = segs


class ProcedureTracker:
    """Tracks steps and substeps for a single test run."""

    def __init__(self) -> None:
        self._steps: list[dict[str, Any]] = []
        self._step_counter: int = 0
        self._depth: int = 0
        self._inside_cm: bool = False

    def reset(self) -> None:
        self._steps.clear()
        self._step_counter = 0
        self._depth = 0
        self._inside_cm = False

    def record_step(
        self,
        description: str | _FormattedText,
        *,
        check: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a step. If inside a CM step, becomes a substep.

        When *check* is provided (a check descriptor dict), it is
        stored directly on the step/substep entry as inline metadata.
        The step does NOT evaluate the check.

        Args:
            description: Plain string or ``FormattedText`` from ``fmt.text``/``fmt.mono``.
            check: Optional check descriptor dict (presentation only).

        Returns:
            The step or substep dict that was recorded.
        """
        now = _now()
        display = _display(description)
        if self._inside_cm and self._steps:
            # Inside a with-step context -> becomes substep
            parent = self._steps[-1]
            sub_count = len(parent["substeps"]) + 1
            sub: dict[str, Any] = {
                "number": f"{parent['number']}.{sub_count}",
                "description": display,
                "outcome": "passed",
                "start_time": now,
                "end_time": now,
                "duration_seconds": 0.0,
                "exc": None,
            }
            if check is not None:
                sub["check"] = check
            _attach_segments(sub, description)
            parent["substeps"].append(sub)
            return sub
        else:
            self._step_counter += 1
            s: dict[str, Any] = {
                "number": str(self._step_counter),
                "description": display,
                "outcome": "passed",
                "start_time": now,
                "end_time": now,
                "duration_seconds": 0.0,
                "exc": None,
                "substeps": [],
            }
            if check is not None:
                s["check"] = check
            _attach_segments(s, description)
            self._steps.append(s)
            return s

    def record_substep(self, description: str | _FormattedText) -> dict[str, Any]:
        """Record an explicit substep under the most-recently-recorded step.

        If no step has been recorded yet, the call is promoted to a
        top-level step (preserve, never drop) instead of raising.

        Args:
            description: Plain string or ``FormattedText``.

        Returns:
            The substep (or promoted step) dict.
        """
        if not self._steps:
            # No active step: promote to a top-level step (preserve, never drop).
            return self.record_step(description)
        now = _now()
        display = _display(description)
        parent = self._steps[-1]
        sub_count = len(parent["substeps"]) + 1
        sub: dict[str, Any] = {
            "number": f"{parent['number']}.{sub_count}",
            "description": display,
            "outcome": "passed",
            "start_time": now,
            "end_time": now,
            "duration_seconds": 0.0,
            "exc": None,
        }
        _attach_segments(sub, description)
        parent["substeps"].append(sub)
        return sub

    def enter_step_cm(self, description: str | _FormattedText) -> dict[str, Any]:
        """Enter a step context manager.

        Args:
            description: Plain string or ``FormattedText``.

        Returns:
            The step or substep dict.
        """
        self._depth += 1
        if self._depth > 2:
            self._depth -= 1
            raise ProcedureNestingError(
                f"Maximum procedure nesting depth is 2, attempted depth {self._depth + 1}"
            )

        now = _now()
        display = _display(description)
        if self._depth == 1:
            # Top-level step
            self._step_counter += 1
            s: dict[str, Any] = {
                "number": str(self._step_counter),
                "description": display,
                "outcome": "passed",
                "start_time": now,
                "end_time": now,
                "duration_seconds": 0.0,
                "exc": None,
                "substeps": [],
            }
            _attach_segments(s, description)
            self._steps.append(s)
            self._inside_cm = True
            return s
        else:
            # Depth 2 -> substep under current step
            parent = self._steps[-1]
            sub_count = len(parent["substeps"]) + 1
            sub: dict[str, Any] = {
                "number": f"{parent['number']}.{sub_count}",
                "description": display,
                "outcome": "passed",
                "start_time": now,
                "end_time": now,
                "duration_seconds": 0.0,
                "exc": None,
            }
            _attach_segments(sub, description)
            parent["substeps"].append(sub)
            return sub

    def exit_step_cm(self, step_data: dict[str, Any], exc: BaseException | None) -> None:
        """Exit a step context manager.

        Args:
            step_data: The dict returned by ``enter_step_cm``.
            exc: Exception if the block raised, else ``None``.
        """
        now = _now()
        step_data["end_time"] = now
        step_data["duration_seconds"] = _duration(step_data["start_time"], now)

        if exc is not None:
            step_data["outcome"] = "failed"
            step_data["exc"] = _make_exc(exc)
            # If substep failed, mark parent step failed too
            if self._depth == 2 and self._steps:
                self._steps[-1]["outcome"] = "failed"

        self._depth -= 1
        if self._depth == 0:
            self._inside_cm = False

    def serialize(self) -> dict[str, Any]:
        return {"steps": list(self._steps)}


# --- Module-level active tracker ---

_active_tracker: ProcedureTracker | None = None


def _set_tracker(tracker: ProcedureTracker | None) -> None:
    global _active_tracker
    _active_tracker = tracker


def _get_tracker() -> ProcedureTracker:
    if _active_tracker is None:
        raise ProcedureError("No active procedure tracker -- are you inside a test?")
    return _active_tracker


class _StepProxy:
    """Returned by step(). Supports use as both a plain call result and context manager."""

    def __init__(
        self,
        description: str | _FormattedText,
        *,
        check: dict[str, Any] | None = None,
    ) -> None:
        self._description = description
        self._check = check
        self._step_data: dict[str, Any] | None = None
        self._tracker = _get_tracker()
        self._used_as_cm = False
        # Record immediately as plain step (if used as CM, __enter__ overrides)
        self._step_data = self._tracker.record_step(description, check=check)

    def __enter__(self) -> dict[str, Any]:
        self._used_as_cm = True
        # The step was already recorded via record_step; but that was a plain step.
        # We need to undo that and use the CM path instead.
        # Remove the last recorded step and re-enter as CM
        tracker = self._tracker
        # Remove the just-recorded step (it was recorded in __init__)
        if tracker._steps and tracker._steps[-1] is self._step_data:
            tracker._steps.pop()
            tracker._step_counter -= 1
        elif self._step_data is not None:
            # It was recorded as a substep inside a parent — remove it
            if tracker._steps:
                parent = tracker._steps[-1]
                subs = parent.get("substeps", [])
                if subs and subs[-1] is self._step_data:
                    subs.pop()

        self._step_data = tracker.enter_step_cm(self._description)
        return self._step_data

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        tb: Any,  # noqa: ANN401
    ) -> Literal[False]:
        self._tracker.exit_step_cm(self._step_data, exc_val)  # type: ignore[arg-type]
        return False  # Do not swallow exceptions


def step(
    description: str | _FormattedText,
    *,
    check: dict[str, Any] | None = None,
) -> _StepProxy:
    """Record a test procedure step. Can be used as a plain call or context manager.

    Plain call::

        step("Do something")
        step(fmt.text("Set ", fmt.mono("Pulse.Enable"), " to 1"))

    Context manager::

        with step("Do something"):
            step("Sub-action")  # becomes substep

    With a check descriptor (presentation only -- does NOT evaluate)::

        step("Verify voltage", check=verify.approx(3.3, 3.3, name="PSU output", units="V"))

    Args:
        description: Plain string or ``FormattedText`` from ``fmt.text``/``fmt.mono``.
        check: Optional check descriptor (stored inline; never evaluated by the reporter).

    Returns:
        A :class:`_StepProxy` usable as a plain call result or context manager.
    """
    return _StepProxy(description, check=check)


def substep(description: str | _FormattedText) -> None:
    """Record an explicit substep under the most recent step.

    Args:
        description: Plain string or ``FormattedText`` from ``fmt.text``/``fmt.mono``.
    """
    _get_tracker().record_substep(description)
