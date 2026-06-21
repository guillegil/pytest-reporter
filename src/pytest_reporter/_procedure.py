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
    """Retained for import back-compat.

    Previously raised when nesting exceeded depth 2.  The depth-overflow path now
    CLAMPS instead of raising; this class is kept only for back-compat imports.
    It is still raised by ``_get_tracker`` when no active tracker exists.
    """


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


def _make_node(
    description: str | _FormattedText,
    *,
    check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a bare procedure node dict.

    Does NOT assign ``number`` — that is computed at serialize time.
    Attaches ``description_segments`` when styled segments are present.

    Args:
        description: Plain string or FormattedText.
        check: Optional check descriptor dict (presentation only).

    Returns:
        A node dict ready for appending to a parent's ``substeps`` list.
    """
    now = _now()
    node: dict[str, Any] = {
        "description": _display(description),
        "outcome": "passed",
        "start_time": now,
        "end_time": now,
        "duration_seconds": 0.0,
        "exc": None,
    }
    if check is not None:
        node["check"] = check
    _attach_segments(node, description)
    return node


def _assign_numbers(nodes: list[dict[str, Any]], prefix: str = "") -> None:
    """Recursively assign dotted ``number`` fields at serialize time.

    Args:
        nodes: List of sibling nodes.
        prefix: Parent number prefix (empty string at root).
    """
    for i, node in enumerate(nodes):
        num = f"{prefix}{i + 1}" if not prefix else f"{prefix}.{i + 1}"
        node["number"] = num
        children = node.get("substeps")
        if children:
            _assign_numbers(children, num)


class ProcedureTracker:
    """Tracks steps and substeps for a single test run using a parent-stack model.

    The tracker maintains a ``_cm_stack`` of open context-manager nodes.
    The current parent is always ``_cm_stack[-1]`` (or ``_root`` when the stack
    is empty).  Numbers are NOT assigned during recording; ``serialize()`` does
    a single recursive walk to assign dotted numbers.

    Max rendered depth is 3 (N.N.N).  Calls that would produce depth 4 are
    *clamped* — the node is attached as a sibling at depth 3 (no exception raised).
    """

    def __init__(self) -> None:
        # Synthetic root node whose 'substeps' list IS the top-level step list.
        self._root: dict[str, Any] = {"substeps": []}
        # Stack of open CM nodes (pushed on __enter__, popped on __exit__).
        self._cm_stack: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Reset tracker state for a new test run."""
        self._root = {"substeps": []}
        self._cm_stack = []

    def _current_parent(self) -> dict[str, Any]:
        """Return the node whose ``substeps`` list is the current append target."""
        return self._cm_stack[-1] if self._cm_stack else self._root

    def record_step(
        self,
        description: str | _FormattedText,
        *,
        check: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a step node under the current parent.

        Depth clamp: if ``len(_cm_stack) >= 3`` (would create L4), the node is
        instead appended to ``_cm_stack[-2]["substeps"]`` — making it a sibling
        of the current CM node at depth 3.  No exception is raised.

        When *check* is provided (a check descriptor dict), it is stored directly
        on the step/substep entry as inline metadata.  The step does NOT evaluate
        the check.

        Args:
            description: Plain string or ``FormattedText``.
            check: Optional check descriptor dict (presentation only).

        Returns:
            The node dict that was recorded.
        """
        node = _make_node(description, check=check)

        if len(self._cm_stack) >= 3:
            # Clamp: would be L4 → attach as L3 sibling under _cm_stack[-2].
            clamp_parent = self._cm_stack[-2]
            clamp_parent.setdefault("substeps", []).append(node)
        else:
            parent = self._current_parent()
            parent.setdefault("substeps", []).append(node)

        return node

    def record_substep(self, description: str | _FormattedText) -> dict[str, Any]:
        """Record an explicit substep under the most-recently-recorded step.

        Rules:
        - If no step recorded at the current level → promote to a step at that
          level (preserve, never drop).
        - Otherwise attach under the last child of the current parent.
        - If attaching under that last child would produce depth 4
          (``len(_cm_stack) >= 2``) → clamp to a sibling at the current level.

        Args:
            description: Plain string or ``FormattedText``.

        Returns:
            The substep (or promoted step) dict.
        """
        parent = self._current_parent()
        children = parent.get("substeps", [])

        if not children:
            # No steps at this level → promote to a step here.
            return self.record_step(description)

        # Last step at this level is the attach target.
        target = children[-1]

        # Depth check: if attaching under target would create L4 → clamp.
        # len(_cm_stack) >= 2 means: current level is already L2 (inside one CM),
        # so target is L2 and its child would be L3; L3's child would be L4.
        # But we only clamp when target itself is at L3, which means cm_stack depth >= 2.
        if len(self._cm_stack) >= 2:
            # Attaching under target (L3) → L4: clamp to sibling instead.
            node = _make_node(description)
            children.append(node)
            return node

        # Safe to attach under target.
        node = _make_node(description)
        target.setdefault("substeps", []).append(node)
        return node

    def enter_step_cm(
        self,
        description: str | _FormattedText,
        *,
        check: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Enter a step context manager.

        Creates a node via the same ``record_step`` rule (including clamp), then
        pushes it onto ``_cm_stack`` — unless the node was clamped (to keep depth ≤ 3).

        Args:
            description: Plain string or ``FormattedText``.
            check: Optional check descriptor dict (presentation only).

        Returns:
            ``(node, pushed)`` — the node dict and a bool indicating whether it
            was pushed onto the cm_stack (False when clamped).
        """
        was_clamped = len(self._cm_stack) >= 3
        node = self.record_step(description, check=check)
        if not was_clamped:
            self._cm_stack.append(node)
            return node, True
        # Clamped: do NOT push — depth would exceed 3.
        return node, False

    def exit_step_cm(
        self,
        step_data: dict[str, Any],
        exc: BaseException | None,
        pushed: bool,
    ) -> None:
        """Exit a step context manager.

        Records end timing and propagates failure to open ancestor CM nodes.

        Args:
            step_data: The node dict returned by ``enter_step_cm``.
            exc: Exception if the block raised, else ``None``.
            pushed: Whether this node was pushed onto the CM stack (from enter).
        """
        now = _now()
        step_data["end_time"] = now
        step_data["duration_seconds"] = _duration(step_data["start_time"], now)

        if exc is not None:
            step_data["outcome"] = "failed"
            step_data["exc"] = _make_exc(exc)
            # Propagate failure to all open CM ancestors.
            for ancestor in self._cm_stack:
                if ancestor is not step_data:
                    ancestor["outcome"] = "failed"

        if pushed:
            self._cm_stack.pop()

    def serialize(self) -> dict[str, Any]:
        """Serialize the procedure tree to a JSON-compatible dict.

        Assigns dotted ``number`` fields via a recursive post-order walk before
        returning.  The raw node dicts (in ``_root["substeps"]``) are mutated
        in place to add ``number``.

        Returns:
            ``{"steps": [...]}`` with all nodes numbered.
        """
        steps = self._root.get("substeps", [])
        _assign_numbers(steps)
        return {"steps": steps}


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
        self._tracker = _get_tracker()
        self._pushed = False
        # Capture the actual parent's substeps list BEFORE recording, so __enter__
        # can remove the node from the correct list (avoids duplication).
        parent = self._tracker._current_parent()
        self._parent_children: list[dict[str, Any]] = parent.setdefault("substeps", [])
        # Record immediately as a plain step.
        self._step_data = self._tracker.record_step(description, check=check)

    def __enter__(self) -> dict[str, Any]:
        tracker = self._tracker
        # Pop-and-re-record: remove the plain node from the parent's substeps list,
        # then re-create it via enter_step_cm (which also pushes the CM stack).
        if self._parent_children and self._parent_children[-1] is self._step_data:
            self._parent_children.pop()
        # Re-create via the CM entry path.
        self._step_data, self._pushed = tracker.enter_step_cm(self._description, check=self._check)
        return self._step_data

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        tb: Any,  # noqa: ANN401
    ) -> Literal[False]:
        self._tracker.exit_step_cm(self._step_data, exc_val, self._pushed)
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
            step("Sub-action")  # becomes child at depth+1

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
