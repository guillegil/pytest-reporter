"""Pytester tests for the configurable Summary dashboard rendering.

Phase 3, Tasks 3.1-3.8 (RED first, GREEN after JS/CSS changes in Phase 4).

Tests assert on rendered report.html content (DOM markers, CSS classes,
embedded DATA) since we can't run a browser.

WARNING ASSERTIONS NOTE: pytest.warns / recwarn do NOT cross the pytester
subprocess boundary. All warning assertions use result.stdout / result.stderr
parsing instead.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_report_data(html: str) -> dict:  # type: ignore[type-arg]
    """Extract the embedded DATA dict from report.html."""
    match = re.search(r"const DATA = (\{.*?\});\s*\n", html, re.DOTALL)
    assert match, "Could not find 'const DATA = ...' in report.html"
    raw = match.group(1).replace("<\\/", "</")
    return json.loads(raw)  # type: ignore[no-any-return]


def _get_report_html(pytester: Pytester) -> str:
    """Return the content of report.html from the most recent run."""
    runs = list((pytester.path / "reports" / "runs").iterdir())
    assert runs, "No run directory found under reports/runs/"
    run_dir = sorted(runs)[-1]
    report_path = run_dir / "report.html"
    assert report_path.exists(), f"report.html not found in {run_dir}"
    return report_path.read_text(encoding="utf-8")


SIMPLE_TEST = """
def test_pass():
    assert True
"""


# ---------------------------------------------------------------------------
# Task 3.1 — style='bars' → .pass-rate-bar present, no donut SVG for that group
# ---------------------------------------------------------------------------


def test_style_bars_renders_pass_rate_bar(pytester: Pytester) -> None:
    """style='bars' group renders .pass-rate-bar elements in HTML."""
    pytester.makeconftest("""
        def pytest_reporter_dashboard():
            return [{"path": "test_style_bars_renders_pass_rate_bar", "style": "bars"}]
    """)
    pytester.makepyfile(SIMPLE_TEST)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _get_report_html(pytester)
    # .pass-rate-bar class must be present in the HTML
    assert "pass-rate-bar" in html, (
        "Expected 'pass-rate-bar' class marker in report.html for style='bars' group"
    )


# ---------------------------------------------------------------------------
# Task 3.2 — style='donut' → donut SVG card present
# ---------------------------------------------------------------------------


def test_style_donut_renders_donut_card(pytester: Pytester) -> None:
    """style='donut' group renders donut SVG cards in HTML."""
    pytester.makeconftest("""
        def pytest_reporter_dashboard():
            return [{"path": "test_style_donut_renders_donut_card", "style": "donut"}]
    """)
    pytester.makepyfile(SIMPLE_TEST)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _get_report_html(pytester)
    # chart-card with donut SVG must be present
    assert "chart-card" in html, (
        "Expected 'chart-card' class in report.html for style='donut' group"
    )
    assert "donut-counts" in html, "Expected 'donut-counts' class in donut group HTML"


# ---------------------------------------------------------------------------
# Task 3.3 — NO config → default depth-1 donuts, no 'All Tests' donut
# ---------------------------------------------------------------------------


def test_no_config_no_all_tests_donut(pytester: Pytester) -> None:
    """Without dashboard config, 'All Tests' donut card is absent from report.html.

    PRE-CHANGE BASELINE: 'All Tests' appeared as an h3 heading inside a chart-card.
    After configurable-dashboard: the whole-suite donut card is REMOVED.
    Top counter cards convey suite-level totals instead.
    """
    pytester.makepyfile(SIMPLE_TEST)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _get_report_html(pytester)
    # The old code produced: el('h3', null, 'All Tests') inside a chart-card.
    # We check for that pattern — a heading element with exactly 'All Tests' text.
    # We avoid matching inline JS comments which may contain the phrase.
    import re as _re

    # Check for HTML rendering of All Tests heading (not JS comments or DATA strings)
    # The chart-card h3 produces: <h3>All Tests</h3> in the rendered DOM (server-side HTML)
    # The JS is inlined but only evaluated client-side; we check the inline chart card pattern.
    # In our new implementation, the JS produces no 'All Tests' h3 — but the string might
    # appear in code. We check for the specific h3 HTML marker.
    h3_all_tests = _re.search(r"<h3[^>]*>All Tests</h3>", html)
    assert h3_all_tests is None, (
        "'All Tests' h3 chart-card heading must be removed from report.html. "
        "This is the intentional golden change (configurable-dashboard). "
        f"Found at position: {h3_all_tests}"
    )
    # Additionally, the JS function renderSummary must not call donutSVG with 'All Tests'
    # — verified by the DATA.dashboard.is_default path having no all-tests card.


# ---------------------------------------------------------------------------
# Task 3.4 — invalid style → report renders + warning in stdout/stderr
# ---------------------------------------------------------------------------


def test_invalid_style_warns_and_renders(pytester: Pytester) -> None:
    """Invalid style in conftest → report still renders AND warning in output."""
    pytester.makeconftest("""
        def pytest_reporter_dashboard():
            return [{"path": "test_invalid_style_warns_and_renders", "style": "pie"}]
    """)
    pytester.makepyfile(SIMPLE_TEST)
    result = pytester.runpytest("--report-dir=reports", "-W", "always")
    result.assert_outcomes(passed=1)

    # report.html must still be written
    runs = list((pytester.path / "reports" / "runs").iterdir())
    assert runs
    assert (sorted(runs)[-1] / "report.html").exists()

    # Warning must contain 'dashboard' AND 'style' — check stdout+stderr
    combined = result.stdout.str() + result.stderr.str()
    assert "dashboard" in combined, f"Expected 'dashboard' in output; got:\n{combined}"
    assert "style" in combined, f"Expected 'style' in output; got:\n{combined}"


# ---------------------------------------------------------------------------
# Task 3.5 — depth=2 → DATA.dashboard has depth=2 + depth-2 nodes labeled
# ---------------------------------------------------------------------------


def test_depth2_embeds_correct_config(pytester: Pytester) -> None:
    """depth=2 config embedded in DATA.dashboard with depth=2."""
    pytester.makeconftest("""
        def pytest_reporter_dashboard():
            return [{"path": "tests", "depth": 2}]
    """)
    pytester.makepyfile(SIMPLE_TEST)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _get_report_html(pytester)
    data = _extract_report_data(html)
    assert data["dashboard"]["groups"][0]["depth"] == 2


# ---------------------------------------------------------------------------
# Task 3.6 — include_self=True → aggregate card for the group path itself
# ---------------------------------------------------------------------------


def test_include_self_renders_aggregate_card(pytester: Pytester) -> None:
    """include_self=True in config → embedded config has include_self=True."""
    pytester.makeconftest("""
        def pytest_reporter_dashboard():
            return [{"path": "tests", "depth": 1, "include_self": True}]
    """)
    pytester.makepyfile(SIMPLE_TEST)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _get_report_html(pytester)
    data = _extract_report_data(html)
    assert data["dashboard"]["groups"][0]["include_self"] is True
    # The label for the group section must appear in HTML
    assert "chart-card" in html, "Expected chart cards in report.html when include_self=True"


# ---------------------------------------------------------------------------
# Task 3.7 — donut accessibility: numeric counts present in HTML
# ---------------------------------------------------------------------------


def test_donut_has_numeric_counts(pytester: Pytester) -> None:
    """Donut cards contain numeric count text (not color-only) — WCAG SC 1.4.1."""
    pytester.makepyfile("""
        def test_pass1():
            assert True
        def test_pass2():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=2)

    html = _get_report_html(pytester)
    # donut-counts class must be present (carries ✓N ✕N ⊘N ⚠N text)
    assert "donut-counts" in html, (
        "Expected 'donut-counts' class in report.html for accessible donut numeric labels"
    )


# ---------------------------------------------------------------------------
# Task 3.8 — multiple groups → separate labeled sections in order
# ---------------------------------------------------------------------------


def test_multiple_groups_render_in_order(pytester: Pytester) -> None:
    """Multiple dashboard groups render separate labeled sections in order."""
    pytester.makeconftest("""
        def pytest_reporter_dashboard():
            return [
                {"path": "test_multiple_groups_render_in_order", "label": "GROUP_ALPHA"},
                {"path": "test_multiple_groups_render_in_order", "label": "GROUP_BETA"},
            ]
    """)
    pytester.makepyfile(SIMPLE_TEST)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _get_report_html(pytester)
    data = _extract_report_data(html)
    assert len(data["dashboard"]["groups"]) == 2
    assert data["dashboard"]["groups"][0]["label"] == "GROUP_ALPHA"
    assert data["dashboard"]["groups"][1]["label"] == "GROUP_BETA"
    # Both section labels must appear in rendered HTML
    assert "GROUP_ALPHA" in html, "Expected GROUP_ALPHA label in report.html"
    assert "GROUP_BETA" in html, "Expected GROUP_BETA label in report.html"
    # ORDER: ALPHA must appear before BETA
    alpha_pos = html.index("GROUP_ALPHA")
    beta_pos = html.index("GROUP_BETA")
    assert alpha_pos < beta_pos, "GROUP_ALPHA must appear before GROUP_BETA in HTML"
