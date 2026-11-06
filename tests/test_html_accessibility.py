"""Keyboard and screen-reader support in the HTML report.

The test tree follows the WAI-ARIA tree pattern, tab sets are real tablists,
toggles expose their state, status colours have text, and the page has
landmarks. Like the other HTML tests, these inspect the inline source; the
report's JS is not executed here (it was checked in Chromium by hand).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


def _report_html(pytester: Pytester) -> str:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.parametrize("n", [1, 2])
        def test_sweep(n):
            assert n == 1

        def test_ok(log):
            log.table([{"a": 1}, {"a": 2}], name="rows")
        """
    )
    pytester.runpytest("--report-dir=reports")
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    return (runs[0] / "report.html").read_text(encoding="utf-8")


def _js(html: str) -> str:
    m = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    assert m
    return m.group(1)


def test_page_has_landmarks_and_labelled_tabs(pytester: Pytester) -> None:
    html = _report_html(pytester)
    assert '<header class="header">' in html
    assert '<main id="main"' in html
    assert 'class="skip-link" href="#main"' in html
    for tab in ("summary", "tests", "session-logs", "report"):
        assert f'aria-controls="tab-{tab}"' in html
        assert f'aria-labelledby="tabbtn-{tab}"' in html


def test_tree_follows_the_tree_pattern(pytester: Pytester) -> None:
    js = _js(_report_html(pytester))
    assert "role:'tree', 'aria-label':'Tests'" in js
    assert "role: 'treeitem', 'aria-level': String(depth + 1)" in js
    assert "role:'treeitem', 'aria-level': String(depth + 1), 'aria-selected':'false'" in js
    assert "function onTreeKeydown(" in js
    for key in ("'ArrowDown'", "'ArrowUp'", "'ArrowLeft'", "'ArrowRight'", "'Home'", "'End'"):
        assert f"case {key}" in js
    assert "function ensureTreeTabStop(" in js
    assert "row.setAttribute('aria-expanded'" in js


def test_tab_sets_and_toggles_expose_state(pytester: Pytester) -> None:
    js = _js(_report_html(pytester))
    assert "function wireTablist(" in js
    assert "role:'tablist', 'aria-label':'Run details'" in js
    assert "role:'tablist', 'aria-label':'Phase logs'" in js
    assert "function makeRunPill(" in js
    assert "'aria-pressed': on ? 'true' : 'false'" in js
    assert "function wireDisclosure(" in js
    assert "function activateOnKey(" in js


def test_status_has_text_and_icons_are_hidden(pytester: Pytester) -> None:
    html = _report_html(pytester)
    js = _js(html)
    assert "function srText(" in js
    assert ".sr-only {" in html
    assert "<svg width=" not in js, "every inline icon SVG must be aria-hidden"
    assert "function announce(" in js


def test_html_artifacts_are_sized_from_their_rows(pytester: Pytester) -> None:
    js = _js(_report_html(pytester))
    assert "contentDocument" not in js, "a data: frame is cross-origin; its height can't be read"
    assert "function artifactRowCount(" in js
    assert "title:a.name" in js
