"""The pass rate leaves skipped runs out and counts runs marked xfail.

``counted = passed + failed + error + xfailed`` and ``rate = passed / counted``,
where ``passed`` already holds non-strict xpasses and a strict xpass is a failure.
The counters come from ``test.log.json`` (``xfailed`` and ``xpassed`` are subsets
of ``skipped`` and ``passed``); the rate is computed by ``passRate`` in the report's
JS, which runs under Node here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import TYPE_CHECKING, Any

import pytest

from pytest_reporter._html_builder._js import JS

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import Pytester

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

SUITE = """
import pytest

def test_pass_a():
    pass

def test_pass_b():
    pass

def test_fail():
    assert False

def test_skip():
    pytest.skip("not here")

@pytest.mark.skip(reason="never")
def test_skip_mark():
    pass

@pytest.fixture
def broken():
    raise RuntimeError("setup")

def test_error(broken):
    pass

@pytest.mark.xfail(reason="known bug")
def test_xfailed():
    assert False

@pytest.mark.xfail(reason="fixed?")
def test_xpassed():
    pass

@pytest.mark.xfail(reason="fixed?", strict=True)
def test_xpassed_strict():
    pass
"""


def _aggregates(pytester: Pytester) -> dict[str, dict[str, Any]]:
    run = sorted((pytester.path / "reports" / "runs").iterdir())[-1]
    found: dict[str, dict[str, Any]] = {}
    path: Path
    for path in (run / "tests").rglob("test.log.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        found[data["function_name"]] = data
    return found


def _js(script: str) -> Any:  # noqa: ANN401
    functions = []
    for name in ("passRate", "rateText"):
        start = JS.index(f"function {name}(")
        functions.append(JS[start : JS.index("\nfunction ", start + 1)])
    out = subprocess.run(
        ["node", "-"],
        input="\n".join([*functions, script]),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_aggregate_counts_xfailed_and_xpassed(pytester: Pytester) -> None:
    pytester.makepyfile(test_suite=SUITE)
    pytester.runpytest("--report-dir=reports")
    agg = _aggregates(pytester)

    def counts(name: str) -> tuple[int, ...]:
        a = agg[name]
        return (a["passed"], a["failed"], a["skipped"], a["errors"], a["xfailed"], a["xpassed"])

    assert counts("test_pass_a") == (1, 0, 0, 0, 0, 0)
    assert counts("test_skip") == (0, 0, 1, 0, 0, 0)
    assert counts("test_skip_mark") == (0, 0, 1, 0, 0, 0)
    assert counts("test_error") == (0, 0, 0, 1, 0, 0)
    # pytest's own outcomes stay as they were: xfailed is skipped, xpassed passed.
    assert counts("test_xfailed") == (0, 0, 1, 0, 1, 0)
    assert counts("test_xpassed") == (1, 0, 0, 0, 0, 1)
    assert counts("test_xpassed_strict") == (0, 1, 0, 0, 0, 0)


@requires_node
def test_pass_rate_leaves_skipped_out() -> None:
    out = _js("""
      const base = {passed: 3, failed: 2, error: 1, skipped: 0, xfailed: 0, xpassed: 1};
      console.log(JSON.stringify({
        // 3 / 6: skipped runs change nothing
        none: passRate(base),
        many: passRate({...base, skipped: 50}),
        // the suite above: passed 3 (incl. 1 xpass), failed 2 (incl. strict), error 1,
        // skipped 3 (incl. 1 xfail) -> 3 / (3 + 2 + 1 + 1)
        suite: passRate({passed: 3, failed: 2, error: 1, skipped: 3, xfailed: 1, xpassed: 1}),
        allSkipped: passRate({passed: 0, failed: 0, error: 0, skipped: 4}),
        allSkippedText: rateText(passRate({passed: 0, failed: 0, error: 0, skipped: 4})),
        // aggregates written before xfailed existed
        old: passRate({passed: 1, failed: 1, error: 0, skipped: 2}),
      }));
    """)
    assert out == {
        "none": 50,
        "many": 50,
        "suite": 43,
        "allSkipped": None,
        "allSkippedText": "—",
        "old": 50,
    }


def test_every_pass_rate_uses_pass_rate() -> None:
    """The hero, donut counts, pass-rate bars and group labels share one formula."""
    assert JS.count("passRate(") >= 5
    assert "a.passed / total" not in JS
    assert "agg.passed / total" not in JS
    assert "counts.passed / total" not in JS
