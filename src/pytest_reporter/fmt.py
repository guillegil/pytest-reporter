"""Typed formatting constructors for step/substep descriptions.

Public API
----------
- ``Segment``       — TypedDict with ``text: str`` and ``style: str | None``
- ``FormattedText`` — type alias for ``list[Segment]``
- ``mono(s)``       — wrap *s* in a monospace segment; empty string returns ``[]``
- ``text(*parts)``  — concatenate str/FormattedText parts into a flat ``FormattedText``

XSS contract
------------
Constructor output contains ONLY plain text strings.  It never introduces HTML
entities or tags; the downstream renderer is responsible for safe DOM insertion
via ``textContent`` (never ``innerHTML``).

Example::

    from pytest_reporter import fmt, step

    step(fmt.text("Set ", fmt.mono("Pulse.Enable"), " to 1"))
"""

from __future__ import annotations

from typing import TypedDict


class Segment(TypedDict):
    """A single run of text with optional inline style.

    Attributes:
        text: Plain text content — never HTML, never escaped.
        style: ``"mono"`` for monospace runs, ``None`` for plain runs.
    """

    text: str
    style: str | None


FormattedText = list[Segment]


def mono(s: str) -> FormattedText:
    """Return a ``FormattedText`` containing a single monospace segment.

    An empty string produces an empty list (no empty mono segment).

    Args:
        s: The text to wrap in monospace.

    Returns:
        A one-element list ``[{"text": s, "style": "mono"}]``, or ``[]`` when
        *s* is the empty string.

    Example::

        fmt.mono("Pulse.Enable")
        # → [{"text": "Pulse.Enable", "style": "mono"}]
    """
    if s == "":
        return []
    return [{"text": s, "style": "mono"}]


def text(*parts: str | FormattedText) -> FormattedText:
    """Concatenate *parts* into a flat ``FormattedText``.

    - A ``str`` part becomes a plain segment (``style: None``); empty strings
      are dropped (no empty plain segment).
    - A ``FormattedText`` part contributes its segments in order (spread, not
      nested).  Nested ``fmt.text(...)`` calls therefore flatten naturally.
    - No arguments returns ``[]``.

    Args:
        *parts: Any mix of plain strings and ``FormattedText`` lists.

    Returns:
        A flat ``list[Segment]`` with all parts concatenated in order.

    Example::

        fmt.text("Configure ", fmt.mono("Pulse.Enable"), " to 1")
        # → [
        #     {"text": "Configure ", "style": None},
        #     {"text": "Pulse.Enable", "style": "mono"},
        #     {"text": " to 1", "style": None},
        # ]
    """
    out: FormattedText = []
    for p in parts:
        if isinstance(p, str):
            if p != "":
                out.append({"text": p, "style": None})
        else:
            out.extend(p)
    return out
