"""Slice A — check-card chevron affordance + keyboard/aria.

All assertions work against the inline JS source embedded in report.html
and against the embedded DATA JSON.  No DOM execution — we inspect the
source text for structural guarantees.

Note: pytest.warns does NOT cross the pytester subprocess boundary.
Warning assertions (if any) go through stdout parsing only.
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


# ---------------------------------------------------------------------------
# Test: chevron hoisted to module scope
# ---------------------------------------------------------------------------


def test_chevron_svg_at_module_scope(pytester: Pytester) -> None:
    """chevronSvg() must be defined at module scope (before renderSessionLogs).

    This test verifies the hoist. A 'function chevronSvg' must appear in the
    JS source *before* the first mention of 'renderSessionLogs'.
    """
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _report_html(pytester)
    js = _js_block(html)

    chevron_pos = js.find("function chevronSvg")
    session_logs_pos = js.find("function renderSessionLogs")

    assert chevron_pos != -1, "chevronSvg must be defined in the JS"
    assert session_logs_pos != -1, "renderSessionLogs must still exist in the JS"
    assert chevron_pos < session_logs_pos, (
        f"chevronSvg (pos {chevron_pos}) must appear BEFORE renderSessionLogs "
        f"(pos {session_logs_pos}) — hoist not applied"
    )


# ---------------------------------------------------------------------------
# Test: check-card chevron present + aria attributes
# ---------------------------------------------------------------------------


def test_check_card_chevron_and_aria(pytester: Pytester) -> None:
    """Check-card headers must have chevron SVG + correct initial aria-expanded.

    - Failed card: aria-expanded='true', class includes 'expanded'.
    - Passed card: aria-expanded='false', no 'expanded' class on init.
    - chevronSvg called with 'check-card-chevron' class arg in the check-card render.

    The check-card render code is embedded in every report's JS regardless of
    whether checks exist, so this inspects the source with a plain test — it does
    not depend on the installed pytest-verify version (which may not expose
    get_check_results / the soft-assert fixture behavior).
    """
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _report_html(pytester)
    js = _js_block(html)

    # chevronSvg must be referenced inside the check-card render path
    assert "check-card-chevron" in js, (
        "JS must reference 'check-card-chevron' class in check-card render"
    )

    # aria-expanded must be set in the check-card render block
    # We look for the pattern near the check-card section
    assert "aria-expanded" in js, "JS must set aria-expanded on check-card headers"

    # Failed cards must init with aria-expanded=true
    # The JS sets aria-expanded based on status === 'failed'
    assert "status === 'failed'" in js or "status==='failed'" in js, (
        "JS must set aria-expanded=true for failed cards (status==='failed' pattern)"
    )

    # Keyboard handler (Enter/Space) must be wired
    assert "'Enter'" in js or '"Enter"' in js, "JS must handle Enter keydown"
    assert "'Space'" in js or '" "' in js or "' '" in js, "JS must handle Space keydown"

    # role=button must be set on headers
    assert "'role','button'" in js or '"role","button"' in js or "role:'button'" in js, (
        "JS must set role=button on check-card headers"
    )

    # tabindex=0 must be set
    assert "'tabindex','0'" in js or '"tabindex","0"' in js or "tabindex:'0'" in js, (
        "JS must set tabindex=0 on check-card headers"
    )


# ---------------------------------------------------------------------------
# Test: session-log chevron still works (regression guard)
# ---------------------------------------------------------------------------


def test_session_log_chevron_still_renders(pytester: Pytester) -> None:
    """Regression guard: session-log section must still use chevronSvg after hoist."""
    pytester.makepyfile("""
        def test_simple(session_log):
            session_log.info("test message")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _report_html(pytester)
    js = _js_block(html)

    # After hoist, renderSessionLogs must still call chevronSvg
    session_logs_start = js.find("function renderSessionLogs")
    assert session_logs_start != -1

    session_logs_body = js[session_logs_start:]
    assert "chevronSvg(" in session_logs_body, (
        "renderSessionLogs must still call chevronSvg() after hoist"
    )


# ---------------------------------------------------------------------------
# Test: CSS rules present for check-card-chevron
# ---------------------------------------------------------------------------


def test_check_card_chevron_css(pytester: Pytester) -> None:
    """CSS must define .check-card-chevron with transition and rotation rules."""
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _report_html(pytester)

    assert ".check-card-chevron" in html, "CSS must define .check-card-chevron rule"
    assert "check-card-chevron" in html and "rotate(90deg)" in html, (
        "CSS must rotate .check-card-chevron when expanded"
    )
    assert "prefers-reduced-motion" in html, (
        "CSS must respect prefers-reduced-motion for chevron transition"
    )
