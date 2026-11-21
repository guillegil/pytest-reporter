"""stepdoc pre-conditions (``stepdoc.precondition()``) in the procedure.

A pre-condition is a named state the system must be in before the test. stepdoc
records the block as a top-level step of the section ``precondition`` (``P1``,
entries ``P1.1``…), whichever phase it ran in. A test that uses a shared fixture
whose pre-condition an earlier test applied gets a reference to it: a step
without entries whose ``applied_in`` names that test.

The reporter writes them to ``procedure.json`` first, references before the
attempt's own, and the Procedure tab shows them as a group above the phase tabs.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from pytest_reporter._stepdoc import StepCollector

if TYPE_CHECKING:
    from pytest import Pytester


def _has_preconditions() -> bool:
    if importlib.util.find_spec("stepdoc") is None:
        return False
    return hasattr(importlib.import_module("stepdoc"), "precondition")


requires_preconditions = pytest.mark.skipif(
    not _has_preconditions(), reason="needs a stepdoc with stepdoc.precondition()"
)

_CONFTEST = """
    import pytest
    import stepdoc
    from stepdoc import step

    @pytest.fixture(scope="session")
    @stepdoc.precondition("System Mode A")
    def mode_a():
        with step("Put dev1 in mode A"):
            pass
        with step("Put dev2 in mode A"):
            pass
        yield
        with step("Leave mode A"):
            pass

    @pytest.fixture
    def warm():
        with stepdoc.precondition("Output warmed up"):
            with step("Run the output"):
                pass
        with step("Open the bench log"):
            pass
"""


def _run_dir(pytester: Pytester) -> Path:
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    assert len(runs) == 1
    return runs[0]


def _procedure(pytester: Pytester, module: str, func: str, *rest: str) -> dict[str, Any]:
    path = _run_dir(pytester) / "tests" / f"{module}.py" / func / "default"
    for part in rest:
        path = path / part
    return json.loads((path / "procedure.json").read_text())  # type: ignore[no-any-return]


def _lines(proc: dict[str, Any]) -> list[tuple[Any, ...]]:
    """(number, section, description, applied_in, numbers of the entries) per top-level step."""
    return [
        (
            n["number"],
            n["section"],
            n["description"],
            n.get("applied_in"),
            [c["number"] for c in n.get("substeps", [])],
        )
        for n in proc["steps"]
    ]


_DATA_BLOCK = '<script type="application/json" id="report-data">'


def _html(pytester: Pytester) -> str:
    return (_run_dir(pytester) / "report.html").read_text(encoding="utf-8")


def _data(html: str) -> dict[str, Any]:
    start = html.index(_DATA_BLOCK) + len(_DATA_BLOCK)
    return json.loads(html[start : html.index("</script>", start)])  # type: ignore[no-any-return]


def _js(html: str) -> str:
    m = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    assert m
    return m.group(1)


def _function(js: str, name: str) -> str:
    start = js.index(f"function {name}(")
    return js[start : js.index("\nfunction ", start + 1)]


# ---------------------------------------------------------------------------
# procedure.json
# ---------------------------------------------------------------------------


@requires_preconditions
def test_session_precondition_is_applied_once_and_referenced_after(pytester: Pytester) -> None:
    pytester.makeconftest(_CONFTEST)
    pytester.makepyfile(
        test_modes="""
        from stepdoc import step

        def test_one(mode_a):
            with step("Measure"):
                pass

        def test_two(mode_a):
            with step("Measure again"):
                pass
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=2)

    one = _procedure(pytester, "test_modes", "test_one")
    assert _lines(one) == [
        ("P1", "precondition", "System Mode A", None, ["P1.1", "P1.2"]),
        ("1", "procedure", "Measure", None, []),
    ]
    applied = one["steps"][0]
    assert applied["kind"] == "step" and applied["outcome"] == "passed"
    assert [c["section"] for c in applied["substeps"]] == ["precondition", "precondition"]

    two = _procedure(pytester, "test_modes", "test_two")
    assert _lines(two) == [
        ("P1", "precondition", "System Mode A", "test_modes.py::test_one", []),
        ("1", "procedure", "Measure again", None, []),
        ("T1", "teardown", "Leave mode A", None, []),
    ]
    reference = two["steps"][0]
    assert reference["outcome"] == "passed", "the status it got when it was applied"
    assert "substeps" not in reference
    assert reference["duration_seconds"] == 0.0
    assert reference["start_time"] == reference["end_time"]


@requires_preconditions
def test_references_come_before_the_tests_own_preconditions(pytester: Pytester) -> None:
    """stepdoc tells of a reference at the end of setup, after the test's own."""
    pytester.makeconftest(_CONFTEST)
    pytester.makepyfile(
        test_modes="""
        from stepdoc import step

        def test_one(mode_a):
            pass

        def test_two(warm, mode_a):
            with step("Measure"):
                pass
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=2)

    assert _lines(_procedure(pytester, "test_modes", "test_two")) == [
        ("P1", "precondition", "System Mode A", "test_modes.py::test_one", []),
        ("P2", "precondition", "Output warmed up", None, ["P2.1"]),
        ("S1", "setup", "Open the bench log", None, []),
        ("1", "procedure", "Measure", None, []),
        ("T1", "teardown", "Leave mode A", None, []),
    ]


@requires_preconditions
def test_a_precondition_written_inside_a_step_is_not_part_of_it(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_inner="""
        import stepdoc
        from stepdoc import step

        def test_it():
            with step("Prepare"):
                with stepdoc.precondition("Link up"):
                    with step("Wait for the link"):
                        pass
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    assert _lines(_procedure(pytester, "test_inner", "test_it")) == [
        ("P1", "precondition", "Link up", None, ["P1.1"]),
        ("1", "procedure", "Prepare", None, []),
    ]


@requires_preconditions
def test_each_retry_attempt_lists_the_preconditions(pytester: Pytester) -> None:
    pytester.makeconftest(_CONFTEST)
    pytester.makepyfile(
        test_modes="""
        from stepdoc import step

        CALLS = []

        def test_one(mode_a):
            pass

        def test_flaky(warm, mode_a):
            CALLS.append(1)
            with step("Measure"):
                pass
            assert len(CALLS) == 3

        def test_last(mode_a):
            pass
        """
    )
    pytester.runpytest("--report-dir=reports", "--report-retries=2").assert_outcomes(passed=3)

    # The function-scoped fixture applies its pre-condition again in every
    # attempt; the session fixture's is found established in every attempt.
    expected = [
        ("P1", "precondition", "System Mode A", "test_modes.py::test_one", []),
        ("P2", "precondition", "Output warmed up", None, ["P2.1"]),
        ("S1", "setup", "Open the bench log", None, []),
        ("1", "procedure", "Measure", None, []),
    ]
    assert _lines(_procedure(pytester, "test_modes", "test_flaky")) == expected
    assert _lines(_procedure(pytester, "test_modes", "test_flaky", "retries", "01")) == expected
    assert _lines(_procedure(pytester, "test_modes", "test_flaky", "retries", "02")) == expected


@requires_preconditions
def test_a_retry_of_the_test_that_applied_it_finds_it_established(pytester: Pytester) -> None:
    """The shared fixture is not run again for the retry: its pre-condition is a reference."""
    pytester.makeconftest(_CONFTEST)
    pytester.makepyfile(
        test_modes="""
        CALLS = []

        def test_flaky(mode_a):
            CALLS.append(1)
            assert len(CALLS) == 2

        def test_last(mode_a):
            pass
        """
    )
    pytester.runpytest("--report-dir=reports", "--report-retries=1").assert_outcomes(passed=2)

    first = _procedure(pytester, "test_modes", "test_flaky")
    assert _lines(first)[0] == ("P1", "precondition", "System Mode A", None, ["P1.1", "P1.2"])
    retry = _procedure(pytester, "test_modes", "test_flaky", "retries", "01")
    assert _lines(retry)[0] == (
        "P1",
        "precondition",
        "System Mode A",
        "test_modes.py::test_flaky",
        [],
    )


# ---------------------------------------------------------------------------
# The collector alone: any stepdoc, with or without pre-conditions
# ---------------------------------------------------------------------------


def _step(number: str, title: str, section: str | None, **more: Any) -> SimpleNamespace:  # noqa: ANN401
    step = SimpleNamespace(number=number, title=title, status="passed", entries=[], **more)
    if section is not None:
        step.section = section
    return step


def test_collector_orders_and_numbers_preconditions() -> None:
    """References first, then the attempt's own; the other sections keep their order."""
    item = SimpleNamespace(nodeid="t.py::test_x")
    collector = StepCollector()
    collector.begin(item.nodeid)
    own = _step("P1", "Own", "precondition", applied_in=None)
    own.entries.append(_step("P1.1", "Inner", "precondition"))
    steps = [
        _step("S1", "Fixture", "setup"),
        own,
        _step("P1", "Mode A", "precondition", applied_in="t.py::test_first"),
        _step("P2", "Mode B", "precondition", applied_in="t.py::test_second"),
        _step("1", "Measure", "procedure"),
    ]
    for step in steps:
        collector.started(item, step)  # type: ignore[arg-type]
        collector.finished(item, step)  # type: ignore[arg-type]

    nodes = collector.procedure(item.nodeid)["steps"]
    assert [(n["number"], n["description"], n.get("applied_in")) for n in nodes] == [
        ("P1", "Mode A", "t.py::test_first"),
        ("P2", "Mode B", "t.py::test_second"),
        ("P3", "Own", None),
        ("S1", "Fixture", None),
        ("1", "Measure", None),
    ]
    assert nodes[2]["substeps"][0]["number"] == "P3.1"
    assert "applied_in" not in nodes[2]


def test_collector_works_with_a_stepdoc_without_preconditions() -> None:
    """No ``applied_in`` attribute, no ``precondition`` section: as before."""
    item = SimpleNamespace(nodeid="t.py::test_x")
    collector = StepCollector()
    collector.begin(item.nodeid)
    for step in (_step("S1", "Fixture", "setup"), _step("1", "Measure", None)):
        collector.started(item, step)  # type: ignore[arg-type]
    nodes = collector.procedure(item.nodeid)["steps"]
    assert [(n["number"], n["section"]) for n in nodes] == [("S1", "setup"), ("1", "procedure")]
    assert all("applied_in" not in n for n in nodes)


# ---------------------------------------------------------------------------
# report.html
# ---------------------------------------------------------------------------


@requires_preconditions
def test_report_embeds_the_preconditions(pytester: Pytester) -> None:
    pytester.makeconftest(_CONFTEST)
    pytester.makepyfile(
        test_modes="""
        def test_one(mode_a):
            pass

        def test_two(mode_a):
            pass
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=2)
    data = _data(_html(pytester))
    runs = {r["nodeid"]: r for t in data["tests"] for r in t["runs"]}
    applied = runs["test_modes.py::test_one"]["procedure"]["steps"][0]
    assert (applied["number"], applied["section"]) == ("P1", "precondition")
    assert len(applied["substeps"]) == 2
    reference = runs["test_modes.py::test_two"]["procedure"]["steps"][0]
    assert reference["section"] == "precondition"
    # The reference names a run of the report by its node ID: the tab links to it
    assert reference["applied_in"] in runs


def test_procedure_tab_has_a_preconditions_group(pytester: Pytester) -> None:
    """The group sits above the Setup / Call / Teardown tabs, only when there is one."""
    pytester.makepyfile("def test_ok():\n    pass\n")
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    html = _html(pytester)
    js = _js(html)

    phases = _function(js, "renderProcedurePhases")
    assert "steps.filter(s => sectionOf(s) === 'precondition')" in phases
    assert (
        "if (preconditions.length > 0) "
        "wrap.appendChild(renderPreconditions(preconditions, generic));" in phases
    )
    assert phases.index("renderPreconditions(") < phases.index("wrap.appendChild(bar)")

    group = _function(js, "renderPreconditions")
    assert "'aria-label': 'Pre-conditions'" in group
    assert "createTextNode('Pre-conditions')" in group
    assert "s.applied_in ? renderEstablished(s, generic) : renderNode(s, 1, generic)" in group

    line = _function(js, "renderEstablished")
    assert "'already established, applied in '" in line
    assert "findRunByNodeid(node.applied_in)" in line
    assert "openRunInTests(target.test, target.run);" in line
    assert "showRunDetail(target.run, 'Procedure');" in line
    assert "'an earlier attempt of this test'" in line
    assert "innerHTML" not in line and "innerHTML" not in group

    assert ".procedure-pre {" in html
    assert ".proc-established .procedure-step-header { flex-wrap: wrap;" in html
