"""Markup parser for step/substep descriptions.

Parses backtick-delimited spans into ``Segment`` dicts suitable for
monospace rendering in the HTML Procedure tab.  All other formatting is
out of scope (Rule of Three).

Public API
----------
- ``Segment`` — TypedDict with ``text: str`` and ``style: str | None``
- ``parse_markup(text)`` — pure function, returns ``list[Segment]``

XSS contract
------------
Parser output contains ONLY plain text strings.  It never introduces HTML
entities or tags; the caller is responsible for safe DOM insertion via
``textContent`` (never ``innerHTML``).
"""

from __future__ import annotations

from typing import TypedDict


class Segment(TypedDict):
    """A single run of text with optional inline style.

    Attributes:
        text: Plain text content — never HTML, never escaped.
        style: ``"mono"`` for backtick-delimited runs, ``None`` for plain runs.
    """

    text: str
    style: str | None


def parse_markup(text: str) -> list[Segment]:
    """Parse backtick markup in *text* into a flat list of :class:`Segment` dicts.

    Algorithm (left-to-right scan):

    - On encountering a backtick, search forward for a matching closing backtick.
    - Non-empty inner text → emit a ``"mono"`` segment.
    - Empty inner text (``‌``‌``) → drop entirely (no empty mono segment).
    - No closing backtick (unclosed) → emit the backtick and remainder as a
      plain literal segment; parsing stops (no crash).
    - Plain characters accumulate into a ``None``-style segment.

    Determinism guarantees:

    - Plain-only input → ``[{text, None}]`` (single segment).
    - Adjacent pairs ``‌`A``B`‌`` → A mono, B mono; empty pair dropped.
    - Odd backticks → first complete pair(s) matched; unmatched tail is plain.
    - Output is ALWAYS plain text per segment — NEVER HTML.

    Args:
        text: Raw description string from ``step()`` or ``substep()``.

    Returns:
        A list of :class:`Segment` dicts.  May be empty when the entire input
        consists of empty backtick pairs.
    """
    segments: list[Segment] = []
    buf: list[str] = []  # accumulates the current plain run
    i, n = 0, len(text)

    while i < n:
        if text[i] == "`":
            close = text.find("`", i + 1)
            if close == -1:
                # UNCLOSED: the backtick + remainder are literal plain text (visible, no crash).
                buf.append(text[i:])
                i = n
                break
            inner = text[i + 1 : close]
            if inner != "":
                # Non-empty inner → flush plain buffer, emit mono segment.
                if buf:
                    segments.append({"text": "".join(buf), "style": None})
                    buf.clear()
                segments.append({"text": inner, "style": "mono"})
            # Empty `` → drop entirely (no segment, no crash).
            i = close + 1
        else:
            buf.append(text[i])
            i += 1

    if buf:
        segments.append({"text": "".join(buf), "style": None})

    return segments
