"""Failure triage: retries, expected fails and status colours in the HTML report.

- A retry attempt's procedure has its own checks, so a failed attempt never
  reads as passed; a phase that failed outside its steps says so.
- The Failures list is grouped by file, and each retried run says whether it
  failed every try or passed in the end.
- An xfail-marked run that failed as expected is an "Expected fail", with the
  mark's reason, not a plain skip.
- Retried is the accent colour (amber is Skipped's), and the pass rate is green
  only when nothing failed.

Like the other HTML tests, these inspect the embedded data and the inline JS/CSS
source; the report's JS is not executed here.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from pytest_reporter._collector import DataCollector

if TYPE_CHECKING:
    from pytest import Pytester

requires_stepdoc_and_verifier = pytest.mark.skipif(
    importlib.util.find_spec("stepdoc") is None
    or importlib.util.find_spec("pytest_verifier") is None,
    reason="stepdoc and pytest-verifier are not both installed",
)

_DATA_BLOCK = '<script type="application/json" id="report-data">'


def _run_dir(pytester: Pytester) -> Path:
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    assert len(runs) == 1
    return runs[0]


def _html(pytester: Pytester) -> str:
    return (_run_dir(pytester) / "report.html").read_text(encoding="utf-8")


def _data(pytester: Pytester) -> dict[str, Any]:
    html = _html(pytester)
    start = html.index(_DATA_BLOCK) + len(_DATA_BLOCK)
    return json.loads(html[start : html.index("</script>", start)])  # type: ignore[no-any-return]


def _js(html: str) -> str:
    m = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    assert m
    return m.group(1)


def _run(data: dict[str, Any], name: str) -> dict[str, Any]:
    test = next(t for t in data["tests"] if t["aggregate"]["function_name"] == name)
    return test["runs"][0]  # type: ignore[no-any-return]


def _checks(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for n in nodes:
        if n.get("kind") == "check":
            out.append(n)
        out += _checks(n.get("substeps", []))
    return out


# --- Retry procedures ---------------------------------------------------------


@requires_stepdoc_and_verifier
def test_retry_attempt_procedure_has_its_own_checks(pytester: Pytester) -> None:
    """Each retry's procedure.json holds the checks that attempt made.

    stepdoc keeps one recorder across the reporter's retries; until stepdoc
    places a rerun's checks in its own steps, they land in the first attempt's
    steps and this xfails.
    """
    pytester.makepyfile(
        test_gain="""
        from stepdoc import step

        def test_gain(verify):
            with step("Measure gain"):
                verify.greater(14.0, 20.0, name="Gain")
        """
    )
    pytester.runpytest("--report-dir=reports", "--report-retries=1").assert_outcomes(failed=1)
    base = _run_dir(pytester) / "tests" / "test_gain.py" / "test_gain" / "default"
    first = json.loads((base / "procedure.json").read_text())
    retry = json.loads((base / "retries" / "01" / "procedure.json").read_text())
    assert [c["outcome"] for c in _checks(first["steps"])] == ["failed"]
    if not _checks(retry["steps"]):
        pytest.xfail("this stepdoc places a rerun's checks in the first run's steps")
    assert [c["outcome"] for c in _checks(retry["steps"])] == ["failed"]
    assert retry["steps"][0]["outcome"] == "failed"


def test_procedure_phase_never_reads_better_than_it_went(pytester: Pytester) -> None:
    pytester.makepyfile("def test_a():\n    pass\n")
    pytester.runpytest("--report-dir=reports")
    js = _js(_html(pytester))
    assert "isBad(phase.outcome) && inSection.length > 0 && !isBad(outcome)" in js
    assert "if (outside) outcome = phase.outcome;" in js
    assert "' outside these steps'" in js
    assert ".procedure-outside {" in _html(pytester)


# --- Failures list and retries -------------------------------------------------


def test_failures_grouped_by_file_with_retry_chips(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_red="""
        import pytest

        @pytest.mark.parametrize("n", [1, 2])
        def test_sweep(n):
            assert False, "out of range"
        """
    )
    pytester.runpytest("--report-dir=reports", "--report-retries=1").assert_outcomes(failed=2)
    data = _data(pytester)
    run = _run(data, "test_sweep")
    assert run["retries"]["history"] == ["failed", "failed"]
    html = _html(pytester)
    js = _js(html)
    # Grouped by file, runs of one test failing for one reason on one row
    assert "className:'failures-group'" in js
    assert "item.test.base_nodeid + '\\u0000' + failedPhase(item.run) + '\\u0000' + reason" in js
    # Retried runs say how their tries went
    assert "function retryVerdict(" in js
    assert "'failed ' + failed + '/' + tries" in js
    assert "'passed on try ' + tries + ' of ' + tries + ' (flaky)'" in js
    assert "retryChip(first)" in js
    assert "' passed only on a retry'" in js
    assert ".retry-chip.consistent" in html and ".retry-chip.flaky" in html


def test_retried_is_accent_and_pass_rate_has_no_amber(pytester: Pytester) -> None:
    pytester.makepyfile("def test_a():\n    pass\n")
    pytester.runpytest("--report-dir=reports")
    html = _html(pytester)
    retried = re.search(r"\.tree-badge\.retried \{(.*?)\}", html, re.DOTALL)
    assert retried and "--c-accent" in retried.group(1) and "skipped" not in retried.group(1)
    assert ".summary-hero-pct.warn" not in html
    assert "agg.failed + agg.error === 0 ? 'good' : 'neutral'" in _js(html)
    # Shape as well as hue: skipped is a ring, error a square
    assert re.search(r"\.status-dot\.skipped \{[^}]*inset 0 0 0 2px", html)
    assert re.search(r"\.status-dot\.error \{[^}]*border-radius: 2px", html)


# --- Expected fails -------------------------------------------------------------


def test_xfail_runs_carry_their_mark(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_x="""
        import pytest

        @pytest.mark.xfail(reason="known issue #THERM-445")
        def test_known():
            assert False

        @pytest.mark.xfail(reason="flaky fixture")
        def test_lucky():
            pass

        def test_imperative():
            pytest.xfail("not on this board")

        @pytest.mark.skip(reason="no board")
        def test_skip():
            pass
        """
    )
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(xfailed=2, xpassed=1, skipped=1)
    data = _data(pytester)
    assert _run(data, "test_known")["xfail"] == {
        "outcome": "xfailed",
        "reason": "known issue #THERM-445",
    }
    assert _run(data, "test_known")["outcome"] == "skipped"  # the counters stay pytest's
    assert _run(data, "test_lucky")["xfail"] == {"outcome": "xpassed", "reason": "flaky fixture"}
    assert _run(data, "test_imperative")["xfail"] == {
        "outcome": "xfailed",
        "reason": "not on this board",
    }
    assert _run(data, "test_skip")["xfail"] is None
    js = _js(_html(pytester))
    assert "xfailed:'Expected fail'" in js
    assert "function shownOutcome(" in js
    assert "'Expected to fail'" in js
    assert "' expected fail' + (xfailCount === 1 ? '' : 's')" in js


def _phase(when: str, outcome: str, wasxfail: str | None = None) -> Any:  # noqa: ANN401
    report = SimpleNamespace(
        nodeid="t.py::test_a", when=when, outcome=outcome, duration=0.0, longrepr=None
    )
    if wasxfail is not None:
        report.wasxfail = wasxfail
    return report


def test_xfail_reason_drops_the_verifier_summary() -> None:
    """pytest-verifier adds its checks summary to an xfail reason; the Checks tab has it."""
    collector = DataCollector()
    collector.record_phase(_phase("setup", "passed"))
    reason = "pad needs replacement [1 of 1 checks failed: VRM — expected < 60.0°C, got 78°C]"
    collector.record_phase(_phase("call", "skipped", reason))
    assert collector.get_xfail("t.py::test_a") == {
        "outcome": "xfailed",
        "reason": "pad needs replacement",
    }


def test_strict_xpass_is_no_expected_fail() -> None:
    collector = DataCollector()
    collector.record_phase(_phase("setup", "passed"))
    collector.record_phase(_phase("call", "failed"))
    assert collector.get_xfail("t.py::test_a") is None
