"""Failure-first triage in the HTML report.

A red run should lead straight to what broke: Summary lists the failures, the
counter cards filter the Tests tab, a test opens on its failing run and phase,
and a failed run starts with a strip saying where and why it failed.

Like the other HTML tests, these inspect the inline JS/CSS source and the
embedded data; the report's JS is not executed here.
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pytest import Pytester


def _report_html(pytester: Pytester) -> str:
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    assert len(runs) == 1
    return (pathlib.Path(runs[0]) / "report.html").read_text(encoding="utf-8")


def _js(html: str) -> str:
    m = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    assert m
    return m.group(1)


def _data(html: str) -> dict[str, Any]:
    m = re.search(r"const DATA = (\{.*?\});\n", html, re.DOTALL)
    assert m
    data: dict[str, Any] = json.loads(m.group(1).replace("<\\/", "</"))
    return data


def _run_red_suite(pytester: Pytester) -> str:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.parametrize("n", [1, 2, 3])
        def test_sweep(n):
            assert n != 2, f"value {n} out of range"

        def test_ok():
            pass
        """
    )
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=3, failed=1)
    return _report_html(pytester)


def test_failed_run_carries_the_reason_line(pytester: Pytester) -> None:
    """The data the failures list reads: a failed call phase with an "E" line."""
    data = _data(_run_red_suite(pytester))
    sweep = next(t for t in data["tests"] if t["aggregate"]["function_name"] == "test_sweep")
    failed = [r for r in sweep["runs"] if r["outcome"] == "failed"]
    assert len(failed) == 1
    assert sweep["runs"][0]["outcome"] == "passed", "the failing run is not the first one"
    longrepr = failed[0]["phases"]["call"]["longrepr"]
    assert any(
        re.match(r"^E\s", line) and "value 2 out of range" in line for line in longrepr.splitlines()
    )


def test_test_opens_on_its_failing_run_and_phase(pytester: Pytester) -> None:
    js = _js(_run_red_suite(pytester))
    assert "function firstFailingRun(" in js
    assert "const firstRun = initialRun || firstFailingRun(test);" in js
    assert "showRunDetail(test.runs[0])" not in js, "a test must not always open on run 01"
    assert "function phaseOfInterest(" in js
    assert "availablePhases.indexOf(phaseOfInterest(run))" in js
    assert "idx===activeIdx" in js


def test_failed_run_has_a_failure_strip(pytester: Pytester) -> None:
    html = _run_red_suite(pytester)
    js = _js(html)
    assert "function renderFailureStrip(" in js
    assert "if (isBad(run.outcome)) container.appendChild(renderFailureStrip(" in js
    assert "function failureReason(" in js
    assert "checks? failed" in js, "the pytest-verifier summary line is used as the reason"
    assert ".failure-strip {" in html


def test_summary_lists_failures_and_counters_filter(pytester: Pytester) -> None:
    html = _run_red_suite(pytester)
    js = _js(html)
    assert "function renderFailuresPanel(" in js
    assert "'Copy rerun command'" in js
    assert "openRunInTests(item.test, item.run)" in js
    assert "el(clickable ? 'button' : 'div', {className:'counter-card '" in js
    assert "function showTreeSubset(" in js
    assert ".failures-panel {" in html


def test_red_run_defaults_tree_to_failures(pytester: Pytester) -> None:
    js = _js(_run_red_suite(pytester))
    assert "activeFilters = new Set(['failed', 'error']);" in js
    assert "function refreshTree(" in js
    # Search and status filters combine; filter buttons expose their state.
    assert "testMatchesQuery(test, q)" in js
    assert "btn.setAttribute('aria-pressed'" in js
