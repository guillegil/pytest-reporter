"""Copy-command feature — "run only this test" box in the detail header.

When a test is selected in the Tests tab, the detail header shows the exact
pytest command to run that single test (``pytest "<nodeid>"``) below the file
path.  Clicking (or Enter/Space) copies it to the clipboard.

All assertions work against the inline JS/CSS source embedded in report.html
and against the embedded DATA JSON.  No DOM execution — we inspect the source
text for structural guarantees (see memory: HTML/JS is not executed in tests).
"""

from __future__ import annotations

import pathlib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


def _run_dir(pytester: Pytester) -> pathlib.Path:
    runs_dir = pytester.path / "reports" / "runs"
    runs = sorted(runs_dir.iterdir())
    assert len(runs) == 1, f"Expected 1 run dir, got {len(runs)}"
    return runs[0]


def _report_html(pytester: Pytester) -> str:
    return (_run_dir(pytester) / "report.html").read_text(encoding="utf-8")


def _js_block(html: str) -> str:
    m = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    assert m, "No <script> block found in report.html"
    return m.group(1)


def test_copy_helpers_present(pytester: Pytester) -> None:
    """The clipboard helper + command builder must exist at module scope."""
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    js = _js_block(_report_html(pytester))

    assert "function copyToClipboard(" in js, "copyToClipboard helper must be defined"
    assert "navigator.clipboard" in js, "must use the modern clipboard API"
    assert "document.execCommand('copy')" in js, "must provide an execCommand fallback"
    assert "function testCommand(" in js, "testCommand builder must be defined"
    assert "'pytest \"'" in js, 'command must be built as: pytest "<nodeid>"'


def test_command_uses_run_nodeid(pytester: Pytester) -> None:
    """The command box must render from the run's full nodeid and update per run."""
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    js = _js_block(_report_html(pytester))

    # command element is injected in the detail header
    assert "detail-cmd" in js, "detail-cmd command box must be rendered in the header"
    assert "detail-cmd-code" in js, "command text element must have class detail-cmd-code"
    # built from the selected run's nodeid, updated in showRunDetail
    assert "testCommand(run.nodeid)" in js, "command must update from the selected run's nodeid"


def test_command_box_is_accessible(pytester: Pytester) -> None:
    """The command box must be keyboard-operable (role=button, tabindex, Enter/Space)."""
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    js = _js_block(_report_html(pytester))

    assert "role:'button'" in js or 'role:"button"' in js, "command box must expose role=button"
    assert "tabindex:'0'" in js or 'tabindex:"0"' in js, "command box must be focusable"
    assert "'Enter'" in js, "command box must handle Enter to copy"
    assert "keydown" in js, "command box must wire a keydown handler"


def test_parametrized_nodeid_available_in_data(pytester: Pytester) -> None:
    """Parametrized runs must carry the full nodeid (with [id]) so the command is exact."""
    pytester.makepyfile("""
        import pytest

        @pytest.mark.parametrize("n", [1, 2])
        def test_p(n):
            assert n
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=2)

    html = _report_html(pytester)

    # The embedded DATA must contain the parametrized nodeids so the copy command
    # can reproduce the exact single-test invocation.
    assert "test_p[1]" in html, "parametrized nodeid test_p[1] must be embedded in DATA"
    assert "test_p[2]" in html, "parametrized nodeid test_p[2] must be embedded in DATA"


def test_copy_command_css_present(pytester: Pytester) -> None:
    """CSS must style the command box (.detail-cmd) with a copy affordance."""
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _report_html(pytester)

    assert ".detail-cmd" in html, "CSS must define the .detail-cmd rule"
    assert ".detail-cmd.copied" in html or ".detail-cmd:hover" in html, (
        "CSS must provide a visual copy affordance (hover/copied state)"
    )
