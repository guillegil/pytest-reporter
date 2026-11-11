"""The Procedure sub-tab shows Setup / Call / Teardown tabs.

stepdoc puts the steps fixtures ran in Setup (S1…) and Teardown (T1…) and the
test's own in the procedure section. The Procedure sub-tab shows them as three
tabs, like the phase logs on the Summary sub-tab, opening on the phase that
failed when it has steps, else on Call.

Like the other HTML tests, these inspect the inline JS/CSS source; the
report's JS is not executed here.
"""

from __future__ import annotations

import pathlib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


def _report_html(pytester: Pytester) -> str:
    pytester.makepyfile("def test_ok():\n    pass\n")
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    return (pathlib.Path(runs[0]) / "report.html").read_text(encoding="utf-8")


def _function(js: str, name: str) -> str:
    start = js.index(f"function {name}(")
    end = js.index("\nfunction ", start + 1)
    return js[start:end]


def _js(html: str) -> str:
    m = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    assert m
    return m.group(1)


def test_procedure_has_a_tab_per_phase(pytester: Pytester) -> None:
    js = _js(_report_html(pytester))
    assert (
        "const PROC_SECTIONS = [['setup','Setup','setup'], ['procedure','Call','call'], "
        "['teardown','Teardown','teardown']];" in js
    )
    render = _function(js, "renderProcedure")
    assert "role:'tablist', 'aria-label':'Procedure phases'" in render
    assert "role:'tab'" in render and "role:'tabpanel'" in render
    assert "wireTablist(bar, '.phase-tab-btn'" in render, "arrow keys move between the tabs"
    assert "'No steps in ' + pair[1].toLowerCase()" in render, "an empty phase says so"


def test_procedure_opens_on_the_failed_phase_else_call(pytester: Pytester) -> None:
    render = _function(_js(_report_html(pytester)), "renderProcedure")
    assert "phaseOfInterest(run)" in render
    assert "p[2] === interest && bySection[p[0]].length > 0" in render
    assert "bySection.procedure.length > 0 ? 1" in render


def test_each_tab_shows_its_worst_outcome_and_step_count(pytester: Pytester) -> None:
    js = _js(_report_html(pytester))
    assert "const PROC_RANK = {error:5, failed:4, unknown:3, passed:2, skipped:1, info:0};" in js
    render = _function(js, "renderProcedure")
    assert "procOutcome(inSection)" in render
    assert "count + (count === 1 ? ' step' : ' steps')" in render


def test_retry_attempts_use_the_same_tabs(pytester: Pytester) -> None:
    js = _js(_report_html(pytester))
    assert "renderProcedure(proc, run)" in js
    assert "renderProcedure(attempt.procedure, attempt)" in js


def test_procedure_panels_are_uncapped_and_all_print(pytester: Pytester) -> None:
    html = _report_html(pytester)
    assert ".procedure-tab-panel { max-height: none; overflow: visible; }" in html
    assert ".procedure-tabs .phase-tabs-bar { display: none; }" in html
    assert "content: attr(data-phase);" in html
