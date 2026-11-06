"""Finishing details of the HTML report (the polish pass).

Like the other HTML tests, these inspect the source; each behaviour was also
driven in Chromium (keyboard, mouse, phone width, both themes).
"""

from __future__ import annotations

import re

from pytest_reporter._html_builder._css import CSS
from pytest_reporter._html_builder._js import JS


def _rule(selector: str) -> str:
    start = CSS.index(selector)
    return CSS[start : CSS.index("}", start)]


def test_every_counter_card_has_a_second_line() -> None:
    # Total says what it counts, so the figures line up across the row.
    assert "val === 1 ? 'run' : 'runs'" in JS


def test_run_count_is_pluralised() -> None:
    assert "agg.total_runs === 1 ? ' run' : ' runs'" in JS
    assert "' entry' : ' entries'" in JS


def test_cut_tree_names_have_the_full_name_on_hover() -> None:
    assert "title: segs.join(' / ')" in JS
    assert "{className:'tree-name', title: displayName}" in JS


def test_the_selected_run_pill_is_never_hidden_behind_show_more() -> None:
    assert "Show ${rest.length} more" in JS
    assert "'Show fewer'" in JS
    assert "if (rest.includes(selectedRun)) setExpanded(true);" in JS
    assert "more.click()" in JS
    # The old cryptic "3p/1f/0s/0e" counts are gone.
    assert "p/${rc.failed}f" not in JS


def test_lightbox_is_a_dialog_that_holds_and_returns_focus() -> None:
    body = JS[JS.index("function openLightbox") :]
    body = body[: body.index("\n}\n")]
    assert "role:'dialog'" in body and "'aria-modal':'true'" in body
    assert "'aria-label':'Close image'" in body
    assert "close.focus();" in body
    assert "opener.focus()" in body
    assert "e.key === 'Tab'" in body


def test_image_artifacts_open_from_the_keyboard() -> None:
    assert "card.setAttribute('role', 'button');" in JS
    assert "card.tabIndex = 0;" in JS
    assert '.artifact-card[role="button"]:focus-visible' in CSS


def test_text_fields_show_a_solid_focus_ring() -> None:
    for selector in (".search-input:focus {", ".log-search:focus {", ".session-log-search:focus {"):
        rule = _rule(selector)
        assert "outline: 2px solid var(--c-accent);" in rule
        assert "outline: none" not in rule


def test_session_log_search_opens_matching_sections() -> None:
    assert "if (q && has) setDisclosure(sec, true);" in JS
    assert not re.search(r"el\('button', \{className:'session-log-action-btn'\}", JS)


def test_report_rows_keep_label_and_value_apart() -> None:
    row = _rule(".report-info-row {")
    assert "gap: 16px;" in row
    assert "flex-shrink: 0;" in _rule(".report-info-label {")
