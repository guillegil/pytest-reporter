"""pytest-reporter with pytest-verifier: verification cards from report.verify_checks.

The reporter never imports pytest-verifier. It reads the checks pytest-verifier
puts on each phase report (``report.verify_checks``), so it works the same
whether pytest-verifier is installed or not, with retries and under xdist.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest import Pytester


requires_verifier = pytest.mark.skipif(
    importlib.util.find_spec("pytest_verifier") is None,
    reason="pytest-verifier is not installed",
)


def _run_dir(pytester: Pytester) -> Path:
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    assert len(runs) == 1
    return runs[0]


def _data(run_dir: Path) -> dict:  # type: ignore[type-arg]
    html = (run_dir / "report.html").read_text(encoding="utf-8")
    start = html.index("const DATA = ") + len("const DATA = ")
    end = html.index(";\n", start)
    return json.loads(html[start:end])  # type: ignore[no-any-return]


def _imported_modules(path: Path) -> set[str]:
    """Top-level module names a source file imports."""
    import ast

    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
    return names


def test_reporter_never_imports_verifier() -> None:
    """No module of the reporter imports pytest-verifier (or the old pytest_verify)."""
    src = Path(__file__).parent.parent / "src" / "pytest_reporter"
    for path in src.rglob("*.py"):
        imported = _imported_modules(path)
        assert not imported & {"pytest_verify", "pytest_verifier", "pytest_strategy"}, path.name


def test_reporter_runs_cleanly_without_checks(pytester: Pytester) -> None:
    """Tests without verifier checks produce every output and no checks.json."""
    pytester.makepyfile("""
        def test_simple_pass():
            assert True

        def test_simple_fail():
            assert False
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1, failed=1)

    run_dir = _run_dir(pytester)
    assert (run_dir / "report.html").exists()
    assert (run_dir / "junit.xml").exists()
    assert not list(run_dir.rglob("checks.json"))


def test_checks_read_from_report_attribute(pytester: Pytester) -> None:
    """Any plugin that sets report.verify_checks feeds the cards (no import needed)."""
    pytester.makeconftest("""
        import pytest

        @pytest.hookimpl(wrapper=True)
        def pytest_runtest_makereport(item, call):
            report = yield
            if report.when == "call":
                report.verify_checks = [{
                    "check_type": "equal", "name": "Reply", "description": "Verify 'Reply' == 'OK'",
                    "actual": "OK", "expected": "OK", "passed": True, "detail": "'OK' == 'OK'",
                    "phase": "call", "location": "test_x.py:2",
                }]
            return report
    """)
    pytester.makepyfile(test_x="def test_a():\n    pass\n")
    result = pytester.runpytest("--report-dir=reports", "-p", "no:pytest_verifier")
    result.assert_outcomes(passed=1)

    run_dir = _run_dir(pytester)
    checks = json.loads(next(run_dir.rglob("checks.json")).read_text())["checks"]
    assert [c["name"] for c in checks] == ["Reply"]
    run = _data(run_dir)["tests"][0]["runs"][0]
    assert run["check_results"][0]["detail"] == "'OK' == 'OK'"


@requires_verifier
def test_verification_cards_rendered(pytester: Pytester) -> None:
    """Checks of the real verify fixture reach checks.json and the HTML data."""
    pytester.makepyfile("""
        def test_with_verify(verify):
            with verify.section("3V3"):
                verify.approx(3.31, 3.3, abs_tol=0.05, name="Vout", units="V")
            verify.equal(1, 2, name="Fails")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(failed=1)

    run_dir = _run_dir(pytester)
    checks = json.loads(next(run_dir.rglob("checks.json")).read_text())["checks"]
    assert [(c["name"], c["passed"]) for c in checks] == [("Vout", True), ("Fails", False)]
    assert checks[0]["section"] == ["3V3"]
    assert checks[1]["detail"] == "expected 2, got 1"

    run = _data(run_dir)["tests"][0]["runs"][0]
    assert [c["name"] for c in run["check_results"]] == ["Vout", "Fails"]


@requires_verifier
def test_composite_children_stay_inside_parent(pytester: Pytester) -> None:
    """A composite's children are not listed as cards of their own."""
    pytester.makepyfile("""
        def test_all(verify):
            verify.all_satisfy([1, 2], lambda x: verify.greater(x, 0, name="pos"), name="all")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    run = _data(_run_dir(pytester))["tests"][0]["runs"][0]
    assert [c["check_type"] for c in run["check_results"]] == ["all_satisfy"]
    assert len(run["check_results"][0]["child_checks"]) == 2


@requires_verifier
def test_retry_attempts_keep_their_own_checks(pytester: Pytester) -> None:
    """The first attempt's checks are the run's; each retry has its checks.json."""
    pytester.makepyfile("""
        _n = 0

        def test_flaky(verify):
            global _n
            _n += 1
            verify.equal(_n, 2, name=f"attempt {_n}")
    """)
    result = pytester.runpytest("--report-dir=reports", "--report-retries=1")
    result.assert_outcomes(passed=1)

    run_dir = _run_dir(pytester)
    test_dir = run_dir / "tests" / "test_retry_attempts_keep_their_own_checks.py"
    test_dir = test_dir / "test_flaky" / "default"
    first = json.loads((test_dir / "checks.json").read_text())["checks"]
    retry = json.loads((test_dir / "retries" / "01" / "checks.json").read_text())["checks"]
    assert [c["name"] for c in first] == ["attempt 1"]
    assert [c["name"] for c in retry] == ["attempt 2"]

    run = _data(run_dir)["tests"][0]["runs"][0]
    assert [c["name"] for c in run["check_results"]] == ["attempt 1"]
    assert run["retry_attempts"][0]["check_results"][0]["name"] == "attempt 2"
