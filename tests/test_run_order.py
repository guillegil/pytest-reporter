"""Execution order: each run's position and the test that ran right before it.

A test that fails only after another one ran (state left behind in a fixture, a
device or a module) is found by looking at what ran before it. The reporter
notes the order in which runs start and, for each run, the last run of another
test function before it: the runs of a parametrized test that ran back to back
share the test that ran before the first of them. A run that a pytest-xdist
worker reports is ordered with the others of that worker.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from pytest_reporter._collector import DataCollector

if TYPE_CHECKING:
    from pytest import Pytester


def _item(nodeid: str, callspec_id: str | None = None) -> Any:  # noqa: ANN401
    """A stand-in for a collected item: what ``register_items`` reads."""
    item = SimpleNamespace(nodeid=nodeid, iter_markers=lambda *a: iter(()))
    if callspec_id is not None:
        item.callspec = SimpleNamespace(id=callspec_id, params={"n": callspec_id})
    return item


_DATA_BLOCK = '<script type="application/json" id="report-data">'


def _run_dir(pytester: Pytester) -> Path:
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    assert len(runs) == 1
    return runs[0]


def _html(pytester: Pytester) -> str:
    return (_run_dir(pytester) / "report.html").read_text(encoding="utf-8")


def _runs(pytester: Pytester) -> dict[str, dict[str, Any]]:
    html = _html(pytester)
    start = html.index(_DATA_BLOCK) + len(_DATA_BLOCK)
    data = json.loads(html[start : html.index("</script>", start)])
    return {r["nodeid"]: r for t in data["tests"] for r in t["runs"]}


def _test_log(pytester: Pytester, module: str, func: str) -> dict[str, Any]:
    path = _run_dir(pytester) / "tests" / f"{module}.py" / func / "test.log.json"
    return json.loads(path.read_text())  # type: ignore[no-any-return]


_TESTS = """
    import pytest

    def test_power_on():
        pass

    @pytest.mark.parametrize("v", [1, 2, 3])
    def test_ramp(v):
        pass

    def test_readback():
        pass
"""


def test_report_gives_each_run_its_order_and_previous_test(pytester: Pytester) -> None:
    pytester.makepyfile(test_bench=_TESTS)
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=5)
    runs = _runs(pytester)
    order = {nid: (r["order"], r["previous"], r["worker"]) for nid, r in runs.items()}
    assert order == {
        "test_bench.py::test_power_on": (1, None, None),
        # every run of the parametrized test ran after test_power_on
        "test_bench.py::test_ramp[1]": (2, "test_bench.py::test_power_on", None),
        "test_bench.py::test_ramp[2]": (3, "test_bench.py::test_power_on", None),
        "test_bench.py::test_ramp[3]": (4, "test_bench.py::test_power_on", None),
        # the run of test_ramp that ran last
        "test_bench.py::test_readback": (5, "test_bench.py::test_ramp[3]", None),
    }
    assert '"started_runs":5' in _html(pytester).replace(" ", "")


def test_test_log_json_has_order_and_previous_test(pytester: Pytester) -> None:
    pytester.makepyfile(test_bench=_TESTS)
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=5)
    first = _test_log(pytester, "test_bench", "test_power_on")["runs"][0]
    assert first["order"] == 1
    assert first["previous_test"] is None
    assert first["previous_nodeid"] is None
    assert "worker" not in first
    last = _test_log(pytester, "test_bench", "test_readback")["runs"][0]
    assert last["order"] == 5
    assert last["previous_test"] == "test_bench.py::test_ramp"
    assert last["previous_nodeid"] == "test_bench.py::test_ramp[3]"


def test_interleaved_runs_each_get_the_test_before_them(pytester: Pytester) -> None:
    # A conftest that runs the vectors of one test between the others
    pytester.makeconftest(
        """
        def pytest_collection_modifyitems(items):
            items.sort(key=lambda i: ["a[1]", "b", "a[2]"].index(i.name.replace("test_", "")))
        """
    )
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.parametrize("n", [1, 2])
        def test_a(n):
            pass

        def test_b():
            pass
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=3)
    runs = _runs(pytester)
    nid = "test_interleaved_runs_each_get_the_test_before_them.py::"
    assert runs[nid + "test_a[1]"]["previous"] is None
    assert runs[nid + "test_b"]["previous"] == nid + "test_a[1]"
    assert runs[nid + "test_a[2]"]["previous"] == nid + "test_b"


def test_retries_do_not_change_the_order(pytester: Pytester) -> None:
    pytester.makepyfile(
        """
        import itertools
        tries = itertools.count()

        def test_first():
            pass

        def test_flaky():
            assert next(tries) > 0

        def test_last():
            pass
        """
    )
    pytester.runpytest("--report-dir=reports", "--report-retries=2").assert_outcomes(passed=3)
    runs = _runs(pytester)
    nid = "test_retries_do_not_change_the_order.py::"
    assert [runs[nid + n]["order"] for n in ("test_first", "test_flaky", "test_last")] == [1, 2, 3]
    assert runs[nid + "test_last"]["previous"] == nid + "test_flaky"


def test_collector_keeps_an_order_per_xdist_worker() -> None:
    collector = DataCollector()
    collector.register_items(
        [_item("t.py::test_a[1]", "1"), _item("t.py::test_a[2]", "2"), _item("t.py::test_b")]
    )
    collector.record_start("t.py::test_a[1]", "gw0")
    collector.record_start("t.py::test_b", "gw1")
    collector.record_start("t.py::test_a[2]", "gw1")
    a1, b, a2 = (
        collector.get_order(n) for n in ("t.py::test_a[1]", "t.py::test_b", "t.py::test_a[2]")
    )
    assert (a1.position, a1.previous, a1.worker) == (1, None, "gw0")  # type: ignore[union-attr]
    assert (b.position, b.previous, b.worker) == (2, None, "gw1")  # type: ignore[union-attr]
    # test_a[1] ran in another process: on gw1, test_b ran before test_a[2]
    assert (a2.position, a2.previous) == (3, "t.py::test_b")  # type: ignore[union-attr]
    # A rerun starts again: it changes nothing
    collector.record_start("t.py::test_a[1]", "gw1")
    assert collector.get_order("t.py::test_a[1]") == a1
    assert collector.started_runs() == 3


def test_collector_order_without_a_start_is_none() -> None:
    collector = DataCollector()
    assert collector.get_order("t.py::test_x") is None
    # A node ID the collector does not know is ignored
    collector.record_start("t.py::test_x")
    assert collector.get_order("t.py::test_x") is None
    assert collector.started_runs() == 0


def test_summary_tab_shows_order_and_previous_test(pytester: Pytester) -> None:
    pytester.makepyfile("def test_ok():\n    pass\n")
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    html = _html(pytester)
    js = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    assert js
    code = js.group(1)
    assert "addRow('Order', order)" in code
    assert "addRow('Previous test', previousTestEl(run))" in code
    start = code.index("function previousTestEl(")
    body = code[start : code.index("\nfunction ", start + 1)]
    # The link opens the run that ran before, and text is never parsed as HTML
    assert "findRunByNodeid(run.previous)" in body
    assert "openRunInTests(target.test, target.run)" in body
    assert "innerHTML" not in body
    assert "None, it ran first" in body
