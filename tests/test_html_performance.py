"""Load and scroll cost of the HTML report.

The report data is a JSON block that the page reads with ``JSON.parse``:
browsers parse that several times faster than the same data as a JavaScript
object literal (measured in Chromium: a 7 MB report went from 1.8 s to 0.9 s
before the page was interactive, with 4x CPU throttling). Like the other HTML
tests, these inspect the output; the timings were measured in Chromium.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from pytest_reporter._html_builder import build_html_report
from pytest_reporter._html_builder._css import CSS
from pytest_reporter._html_builder._js import JS

if TYPE_CHECKING:
    from pytest import Pytester

_BLOCK = re.compile(r'<script type="application/json" id="report-data">(.*?)</script>', re.DOTALL)


def test_data_is_a_json_block_read_with_json_parse() -> None:
    html = build_html_report({"tests": [], "title": "x"})
    m = _BLOCK.search(html)
    assert m is not None
    assert json.loads(m.group(1)) == {"tests": [], "title": "x"}
    # Compact separators: no padding spaces in megabytes of data.
    assert m.group(1) == '{"tests":[],"title":"x"}'
    assert "const DATA = JSON.parse(document.getElementById('report-data').textContent);" in JS
    assert "const DATA = {" not in html
    # The block comes before the script that reads it.
    assert html.index('id="report-data"') < html.index("const DATA = JSON.parse")


def test_no_angle_bracket_reaches_the_data_block() -> None:
    nasty = "<!--<script></script></script><b>"
    html = build_html_report({"tests": [], "note": nasty})
    m = _BLOCK.search(html)
    assert m is not None
    assert "<" not in m.group(1)
    assert json.loads(m.group(1))["note"] == nasty


def test_report_data_round_trips_through_a_run(pytester: Pytester) -> None:
    pytester.makepyfile(
        """
        def test_logs(log):
            log.info("</script><!--<script>")
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    html = (runs[0] / "report.html").read_text(encoding="utf-8")
    m = _BLOCK.search(html)
    assert m is not None
    assert "</script><!--<script>" in json.dumps(json.loads(m.group(1)))


def test_controls_never_transition_all() -> None:
    assert not re.search(r"transition:\s*all\b", CSS)
    assert "--t-control: color 0.15s" in CSS


def test_sticky_bars_are_solid_without_backdrop_blur() -> None:
    assert "--c-header-bg: var(--c-surface);" in CSS
    for selector in (".header {", ".tabs {"):
        rule = CSS[CSS.index(selector) : CSS.index("}", CSS.index(selector))]
        assert "backdrop-filter" not in rule
        assert "background: var(--c-header-bg);" in rule


def test_tree_scroller_contains_its_screen_reader_labels() -> None:
    rule = CSS[CSS.index(".tree-content {") : CSS.index("}", CSS.index(".tree-content {"))]
    assert "position: relative;" in rule
    assert "overflow-y: auto;" in rule
