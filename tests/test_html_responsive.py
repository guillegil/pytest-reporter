"""Phones and touch screens in the HTML report.

On phones the Tests tab shows the test list or one test at a time; touch
screens get 44px targets; tab strips scroll sideways. Like the other HTML
tests, these inspect the source; the flows were driven in Chromium with
emulated phones and tablets (touch input).
"""

from __future__ import annotations

import re

from pytest_reporter._html_builder._css import CSS
from pytest_reporter._html_builder._js import JS


def _block(css: str, at_rule: str) -> str:
    start = css.index(at_rule)
    depth, i = 0, css.index("{", start)
    for j in range(i, len(css)):
        depth += {"{": 1, "}": -1}.get(css[j], 0)
        if depth == 0:
            return css[i : j + 1]
    raise AssertionError(at_rule)


def test_touch_screens_get_44px_targets() -> None:
    coarse = _block(CSS, "@media (pointer: coarse)")
    for selector in (".tab-btn", ".sub-tab-btn", ".run-pill", ".filter-btn", ".tree-row"):
        assert selector in coarse
    assert "min-height: 44px" in coarse
    assert ".tree-expand-btn, .theme-toggle { min-width: 44px; min-height: 44px; }" in coarse


def test_no_control_under_24px() -> None:
    assert ".filter-btn, .filter-chip, .session-log-level-btn { min-height: 24px; }" in CSS
    assert ".tree-expand-btn { min-width: 24px; min-height: 24px;" in CSS


def test_phone_shows_list_or_detail() -> None:
    assert ".tests-layout.show-detail .tree-panel { display: none; }" in CSS
    assert ".tests-layout.show-detail .detail-panel { display: block; }" in CSS
    # The old stacked layout (tree capped at 45vh above the detail) is gone.
    assert "max-height: 45vh" not in CSS
    assert "function showDetailPane(on)" in JS
    assert "className:'detail-back'" in JS
    assert "'All tests'" in JS
    # Opening a test from the tree or the failures list shows its detail.
    assert len(re.findall(r"showDetailPane\(true\)", JS)) >= 2


def test_tab_strips_scroll_instead_of_wrapping() -> None:
    assert ".tab-btn, .sub-tab-btn { white-space: nowrap; flex-shrink: 0; }" in CSS
    assert re.search(r"\.tabs, \.sub-tabs \{\s*overflow-x: auto;", CSS)
