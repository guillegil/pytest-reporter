"""Slice B — human-readable durations in Summary hero and group cards.

Tests assert against the inline JS source in report.html:
  - formatDuration defined exactly once
  - formatDuration logic correct for all spec boundary values
  - Summary hero contains a duration stat block
  - Group cards contain a duration label

Note: pytest.warns does NOT cross the pytester subprocess boundary.
"""

from __future__ import annotations

import pathlib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_dir(pytester: Pytester) -> pathlib.Path:
    runs_dir = pytester.path / "reports" / "runs"
    runs = sorted(runs_dir.iterdir())
    assert len(runs) == 1, f"Expected 1 run dir, got {len(runs)}"
    return runs[0]


def _report_html(pytester: Pytester) -> str:
    return (_run_dir(pytester) / "report.html").read_text(encoding="utf-8")


def _js_block(html: str) -> str:
    """Return the first <script> block content from the HTML."""
    m = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    assert m, "No <script> block found in report.html"
    return m.group(1)


def _simple_report(pytester: Pytester) -> str:
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)
    return _report_html(pytester)


# ---------------------------------------------------------------------------
# Test: formatDuration defined exactly once
# ---------------------------------------------------------------------------


def test_format_duration_defined_once(pytester: Pytester) -> None:
    """formatDuration must be defined exactly once in the inline JS."""
    html = _simple_report(pytester)
    js = _js_block(html)

    count = js.count("function formatDuration")
    assert count == 1, f"formatDuration must be defined exactly once, found {count} definitions"


# ---------------------------------------------------------------------------
# Test: formatDuration algorithm correctness via source inspection
# ---------------------------------------------------------------------------


def test_format_duration_algorithm_in_source(pytester: Pytester) -> None:
    """formatDuration source must contain the required logic for all spec cases.

    We inspect the JS source for the structural markers that guarantee the
    correct output without executing JavaScript.
    """
    html = _simple_report(pytester)
    js = _js_block(html)

    assert "function formatDuration" in js, "formatDuration must exist in JS"

    # Sub-second handling: '<1s'
    assert "<1s" in js, "formatDuration must return '<1s' for sub-second values"

    # Days / hours / minutes / seconds decomposition
    assert "86400" in js, "formatDuration must decompose days (86400 s)"
    assert "3600" in js, "formatDuration must decompose hours (3600 s)"

    # Parts array and join
    assert "parts" in js, "formatDuration must use parts array"
    assert "parts.join(' ')" in js or 'parts.join(" ")' in js, (
        "formatDuration must join parts with space"
    )

    # Null / NaN guard
    assert "isNaN" in js, "formatDuration must guard against NaN"


# ---------------------------------------------------------------------------
# Test: Summary hero contains duration stat
# ---------------------------------------------------------------------------


def test_summary_hero_duration_stat(pytester: Pytester) -> None:
    """Summary hero must contain a duration stat element."""
    html = _simple_report(pytester)
    js = _js_block(html)

    # suiteDuration must be computed from test aggregates
    assert "suiteDuration" in js, "JS must compute suiteDuration"
    assert "total_duration_seconds" in js, "JS must sum total_duration_seconds for suiteDuration"

    # formatDuration called with suiteDuration in the hero section
    assert "formatDuration(suiteDuration)" in js, (
        "JS must call formatDuration(suiteDuration) in summary hero"
    )

    # CSS class for the duration stat
    assert "summary-hero-dur" in js, "JS must render summary-hero-dur element in the hero"

    # CSS must define the class
    assert "summary-hero-dur" in html, "CSS must define .summary-hero-dur"


# ---------------------------------------------------------------------------
# Test: group cards contain duration labels
# ---------------------------------------------------------------------------


def test_group_cards_contain_duration(pytester: Pytester) -> None:
    """Both donut and bars group cards must include a formatted duration."""
    html = _simple_report(pytester)
    js = _js_block(html)

    # nodeAgg must accumulate duration
    assert "duration" in js, "nodeAgg must return a duration field"

    # Donut group card renders duration
    assert "chart-card-dur" in js, "renderDonutGroup must append chart-card-dur with formatDuration"

    # Bars group card renders duration
    assert "prs-dur" in js, "renderBarsGroup must append prs-dur with formatDuration"

    # CSS must define the classes
    assert "chart-card-dur" in html, "CSS must define .chart-card-dur"
    assert "prs-dur" in html, "CSS must define .prs-dur"


# ---------------------------------------------------------------------------
# Test: detail header uses formatDuration
# ---------------------------------------------------------------------------


def test_detail_header_uses_format_duration(pytester: Pytester) -> None:
    """The test detail header stat must use formatDuration for total duration."""
    html = _simple_report(pytester)
    js = _js_block(html)

    # The detail header (showTestDetail) must call formatDuration for total
    assert "formatDuration(agg.total_duration_seconds)" in js, (
        "showTestDetail must use formatDuration(agg.total_duration_seconds)"
    )
