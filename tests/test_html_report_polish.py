"""Visual polish iteration on the HTML report.

Covers:
  - Class-based tests grouped under a class node in the Tests tree
    (file -> class -> method), instead of a repeated inline eyebrow.
  - Human-readable timestamps (formatTimestamp) in the Report tab + header.
  - Human-readable total duration (formatDuration) in the Report tab + header,
    not raw seconds.

JS is NOT executed by the suite, so these assert on the embedded JS/CSS source
(consistent with the rest of the HTML tests). Real visual validation is done by
regenerating the example report and eyeballing it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


def _gen(pytester: Pytester, body: str) -> str:
    pytester.makepyfile(body)
    pytester.runpytest("--report-dir=reports")
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    assert len(runs) == 1
    return (runs[0] / "report.html").read_text(encoding="utf-8")


_PLAIN = """
    def test_simple():
        assert True
"""

_CLASS = """
    class TestPowerSupply:
        def test_voltage_ok(self):
            assert True
        def test_current_ok(self):
            assert True
"""


# ── Human-readable dates ────────────────────────────────────────────────


def test_format_timestamp_helper_present(pytester: Pytester) -> None:
    html = _gen(pytester, _PLAIN)
    assert "function formatTimestamp" in html, "JS must define formatTimestamp helper"
    # Full weekday + month name tables must be present for legible dates.
    for name in ("Monday", "Wednesday", "Sunday", "January", "June", "December"):
        assert name in html, f"formatTimestamp must include '{name}' for legible dates"


def test_report_and_header_use_format_timestamp(pytester: Pytester) -> None:
    html = _gen(pytester, _PLAIN)
    assert "formatTimestamp(DATA.timestamp)" in html, (
        "Report tab and header must render the timestamp via formatTimestamp"
    )


# ── Human-readable durations everywhere ─────────────────────────────────


def test_report_and_header_use_format_duration(pytester: Pytester) -> None:
    html = _gen(pytester, _PLAIN)
    # The raw "DATA.duration + 's'" rendering must be gone in both spots.
    assert "DATA.duration + 's'" not in html, "Report Duration row must not show raw seconds"
    assert "${DATA.duration}s" not in html, "Header must not show raw seconds"
    assert "formatDuration(DATA.duration)" in html, (
        "Report tab and header must render duration via formatDuration"
    )


# ── Tree class grouping (no repeated eyebrow) ───────────────────────────


def test_tree_groups_class_based_tests(pytester: Pytester) -> None:
    html = _gen(pytester, _CLASS)
    assert "_isClass" in html, "buildTree must group class-based tests under a class node"
    assert "tree-class" in html, "JS/CSS must render a class node (tree-class) in the tree"
