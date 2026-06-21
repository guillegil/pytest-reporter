"""Tests for the procedure system (step/substep)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


def test_step_plain_call(pytester: Pytester) -> None:
    pytester.makepyfile("""
        from pytest_reporter import step

        def test_steps():
            step("Fetch data")
            step("Process data")
            step("Verify results")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    proc = (
        run_dir / "tests" / "test_step_plain_call.py" / "test_steps" / "default" / "procedure.json"
    )
    data = json.loads(proc.read_text())

    assert len(data["steps"]) == 3
    assert data["steps"][0]["number"] == "1"
    assert data["steps"][0]["description"] == "Fetch data"
    assert data["steps"][0]["outcome"] == "passed"
    assert data["steps"][1]["number"] == "2"
    assert data["steps"][2]["number"] == "3"


def test_step_with_substep(pytester: Pytester) -> None:
    pytester.makepyfile("""
        from pytest_reporter import step, substep

        def test_substeps():
            step("Setup")
            substep("Connect to DB")
            substep("Load fixtures")
            step("Execute")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    proc = (
        run_dir
        / "tests"
        / "test_step_with_substep.py"
        / "test_substeps"
        / "default"
        / "procedure.json"
    )
    data = json.loads(proc.read_text())

    assert len(data["steps"]) == 2
    step1 = data["steps"][0]
    assert step1["number"] == "1"
    assert len(step1["substeps"]) == 2
    assert step1["substeps"][0]["number"] == "1.1"
    assert step1["substeps"][0]["description"] == "Connect to DB"
    assert step1["substeps"][1]["number"] == "1.2"


def test_step_context_manager(pytester: Pytester) -> None:
    pytester.makepyfile("""
        from pytest_reporter import step

        def test_cm():
            step("First")
            with step("Second"):
                step("Sub A")
                step("Sub B")
            step("Third")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    proc = (
        run_dir
        / "tests"
        / "test_step_context_manager.py"
        / "test_cm"
        / "default"
        / "procedure.json"
    )
    data = json.loads(proc.read_text())

    assert len(data["steps"]) == 3
    assert data["steps"][0]["number"] == "1"
    assert data["steps"][0]["substeps"] == []
    assert data["steps"][1]["number"] == "2"
    assert data["steps"][1]["description"] == "Second"
    assert len(data["steps"][1]["substeps"]) == 2
    assert data["steps"][1]["substeps"][0]["number"] == "2.1"
    assert data["steps"][1]["substeps"][1]["number"] == "2.2"
    assert data["steps"][2]["number"] == "3"


def test_step_cm_with_timing(pytester: Pytester) -> None:
    pytester.makepyfile("""
        import time
        from pytest_reporter import step

        def test_timing():
            with step("Slow step"):
                time.sleep(0.05)
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    proc = (
        run_dir
        / "tests"
        / "test_step_cm_with_timing.py"
        / "test_timing"
        / "default"
        / "procedure.json"
    )
    data = json.loads(proc.read_text())

    step_data = data["steps"][0]
    assert step_data["duration_seconds"] >= 0.04
    assert step_data["start_time"] != step_data["end_time"]


def test_substep_before_step_promotes(pytester: Pytester) -> None:
    """substep() with no active step must NOT raise — it promotes to a top-level step."""
    pytester.makepyfile("""
        from pytest_reporter import substep

        def test_promote():
            substep("No step yet")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    proc = (
        run_dir
        / "tests"
        / "test_substep_before_step_promotes.py"
        / "test_promote"
        / "default"
        / "procedure.json"
    )
    data = json.loads(proc.read_text())

    assert len(data["steps"]) == 1
    assert data["steps"][0]["number"] == "1"
    assert data["steps"][0]["description"] == "No step yet"
    assert data["steps"][0]["outcome"] == "passed"


def test_substep_promotion_numbering(pytester: Pytester) -> None:
    """Orphan substep -> step '1'; subsequent step() -> '2'; substep attaches to '2' (last wins)."""
    pytester.makepyfile("""
        from pytest_reporter import step, substep

        def test_numbering():
            substep("A")
            step("B")
            substep("C")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    proc = (
        run_dir
        / "tests"
        / "test_substep_promotion_numbering.py"
        / "test_numbering"
        / "default"
        / "procedure.json"
    )
    data = json.loads(proc.read_text())

    assert len(data["steps"]) == 2
    assert data["steps"][0]["number"] == "1"
    assert data["steps"][0]["description"] == "A"
    assert data["steps"][1]["number"] == "2"
    assert data["steps"][1]["description"] == "B"
    # "C" attaches to the last-recorded step ("B", _steps[-1])
    assert len(data["steps"][1]["substeps"]) == 1
    assert data["steps"][1]["substeps"][0]["description"] == "C"


def test_cm_step_inside_cm_demotes_regression(pytester: Pytester) -> None:
    """plain step() inside an open with step(): must demote to substep (regression guard)."""
    pytester.makepyfile("""
        from pytest_reporter import step

        def test_demote():
            with step("L1"):
                step("inner")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    proc = (
        run_dir
        / "tests"
        / "test_cm_step_inside_cm_demotes_regression.py"
        / "test_demote"
        / "default"
        / "procedure.json"
    )
    data = json.loads(proc.read_text())

    assert len(data["steps"]) == 1
    assert data["steps"][0]["number"] == "1"
    assert data["steps"][0]["description"] == "L1"
    assert len(data["steps"][0]["substeps"]) == 1
    assert data["steps"][0]["substeps"][0]["description"] == "inner"


def test_nesting_too_deep_raises(pytester: Pytester) -> None:
    pytester.makepyfile("""
        from pytest_reporter import step

        def test_deep():
            with step("Level 1"):
                with step("Level 2"):
                    with step("Level 3"):
                        pass
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*ProcedureNestingError*"])


def test_no_procedure(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_empty():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    proc = run_dir / "tests" / "test_no_procedure.py" / "test_empty" / "default" / "procedure.json"
    data = json.loads(proc.read_text())
    assert data["steps"] == []


def test_procedure_resets_per_test(pytester: Pytester) -> None:
    pytester.makepyfile("""
        from pytest_reporter import step

        def test_first():
            step("Step A")
            step("Step B")

        def test_second():
            step("Step X")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=2)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    proc1 = (
        run_dir
        / "tests"
        / "test_procedure_resets_per_test.py"
        / "test_first"
        / "default"
        / "procedure.json"
    )
    proc2 = (
        run_dir
        / "tests"
        / "test_procedure_resets_per_test.py"
        / "test_second"
        / "default"
        / "procedure.json"
    )
    d1 = json.loads(proc1.read_text())
    d2 = json.loads(proc2.read_text())

    assert len(d1["steps"]) == 2
    assert len(d2["steps"]) == 1
    assert d2["steps"][0]["number"] == "1"  # counter reset


def test_step_with_check_descriptor(pytester: Pytester) -> None:
    """step(check=...) stores the descriptor on the step itself."""
    pytester.makepyfile("""
        from pytest_reporter import step

        def test_check():
            descriptor = {
                "check_type": "approx",
                "name": "Voltage",
                "description": "Verify voltage == 3.3V \\u00b1 0.05V",
                "actual": 3.31,
                "expected": 3.3,
                "abs_tol": 0.05,
                "passed": True,
            }
            step("Measure output", check=descriptor)
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    run_dir = runs[0]
    proc = (
        run_dir
        / "tests"
        / "test_step_with_check_descriptor.py"
        / "test_check"
        / "default"
        / "procedure.json"
    )
    data = json.loads(proc.read_text())

    assert len(data["steps"]) == 1
    step_data = data["steps"][0]
    assert step_data["description"] == "Measure output"
    # check is inline on the step, not a substep
    assert step_data["substeps"] == []
    assert step_data["check"]["check_type"] == "approx"
    assert step_data["check"]["passed"] is True
