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


# ---------------------------------------------------------------------------
# Phase 3 / 2.2: _attach_segments wiring tests — typed API (RED before GREEN)
# ---------------------------------------------------------------------------


class TestAttachSegments:
    """Unit tests for _attach_segments wiring in ProcedureTracker — typed fmt API."""

    def _make_tracker(self) -> object:
        from pytest_reporter._procedure import ProcedureTracker, _set_tracker

        t = ProcedureTracker()
        _set_tracker(t)
        return t

    def test_plain_step_no_segments_key(self) -> None:
        """str description → NO description_segments key in node (byte-identical)."""
        tracker = self._make_tracker()
        from pytest_reporter._procedure import ProcedureTracker

        assert isinstance(tracker, ProcedureTracker)
        node = tracker.record_step("plain description")
        assert "description_segments" not in node

    def test_fmt_mono_step_has_segments(self) -> None:
        """fmt.mono('x') → description_segments present in record_step node."""
        import pytest_reporter.fmt as fmt

        tracker = self._make_tracker()
        from pytest_reporter._procedure import ProcedureTracker

        assert isinstance(tracker, ProcedureTracker)
        node = tracker.record_step(fmt.mono("x"))
        assert "description_segments" in node
        assert node["description_segments"] == [{"text": "x", "style": "mono"}]
        assert node["description"] == "x"

    def test_fmt_text_step_has_segments(self) -> None:
        """fmt.text with mixed parts → description_segments in node."""
        import pytest_reporter.fmt as fmt

        tracker = self._make_tracker()
        from pytest_reporter._procedure import ProcedureTracker

        assert isinstance(tracker, ProcedureTracker)
        node = tracker.record_step(fmt.text("Set ", fmt.mono("A"), " to 1"))
        assert "description_segments" in node
        assert node["description_segments"] == [
            {"text": "Set ", "style": None},
            {"text": "A", "style": "mono"},
            {"text": " to 1", "style": None},
        ]
        assert node["description"] == "Set A to 1"

    def test_cm_step_has_segments(self) -> None:
        """fmt.mono via enter_step_cm → node has description_segments."""
        import pytest_reporter.fmt as fmt

        tracker = self._make_tracker()
        from pytest_reporter._procedure import ProcedureTracker

        assert isinstance(tracker, ProcedureTracker)
        node = tracker.enter_step_cm(fmt.mono("cmd"))
        assert "description_segments" in node
        assert node["description_segments"] == [{"text": "cmd", "style": "mono"}]
        assert node["description"] == "cmd"

    def test_substep_inside_cm_has_segments(self) -> None:
        """substep(fmt.mono('val')) inside CM step → substep node has description_segments."""
        import pytest_reporter.fmt as fmt

        tracker = self._make_tracker()
        from pytest_reporter._procedure import ProcedureTracker

        assert isinstance(tracker, ProcedureTracker)
        tracker.enter_step_cm("outer")
        # record_step inside CM becomes a substep
        sub = tracker.record_step(fmt.mono("val"))
        assert "description_segments" in sub
        assert sub["description_segments"] == [{"text": "val", "style": "mono"}]
        assert sub["description"] == "val"

    def test_promoted_substep_has_segments(self) -> None:
        """record_substep(fmt.mono('x')) with no parent → promotes; node has segments."""
        import pytest_reporter.fmt as fmt

        tracker = self._make_tracker()
        from pytest_reporter._procedure import ProcedureTracker

        assert isinstance(tracker, ProcedureTracker)
        node = tracker.record_substep(fmt.mono("x"))
        assert "description_segments" in node
        assert node["description_segments"] == [{"text": "x", "style": "mono"}]

    def test_cm_depth2_substep_segments(self) -> None:
        """depth-2 enter_step_cm(fmt.mono('inner')) → substep dict has description_segments."""
        import pytest_reporter.fmt as fmt

        tracker = self._make_tracker()
        from pytest_reporter._procedure import ProcedureTracker

        assert isinstance(tracker, ProcedureTracker)
        tracker.enter_step_cm("outer")
        sub = tracker.enter_step_cm(fmt.mono("inner"))
        assert "description_segments" in sub
        assert sub["description_segments"] == [{"text": "inner", "style": "mono"}]

    def test_all_plain_formatted_text_no_segments_key(self) -> None:
        """FormattedText with all-plain segments → NO description_segments (byte-identical)."""
        import pytest_reporter.fmt as fmt

        tracker = self._make_tracker()
        from pytest_reporter._procedure import ProcedureTracker

        assert isinstance(tracker, ProcedureTracker)
        node = tracker.record_step(fmt.text("hello", " world"))
        assert "description_segments" not in node
        assert node["description"] == "hello world"


# ---------------------------------------------------------------------------
# Phase 1.1: fmt constructor unit tests — RED before GREEN
# ---------------------------------------------------------------------------


class TestFmt:
    """Unit tests for fmt.mono and fmt.text constructors."""

    def test_mono_single_segment(self) -> None:
        """mono('Pulse.Enable') → [{text: 'Pulse.Enable', style: 'mono'}]."""
        import pytest_reporter.fmt as fmt

        result = fmt.mono("Pulse.Enable")
        assert result == [{"text": "Pulse.Enable", "style": "mono"}]

    def test_mono_empty_string(self) -> None:
        """mono('') → [] (empty string yields empty list)."""
        import pytest_reporter.fmt as fmt

        result = fmt.mono("")
        assert result == []

    def test_text_mixed_parts(self) -> None:
        """text('a', mono('b'), 'c') → 3 ordered segments."""
        import pytest_reporter.fmt as fmt

        result = fmt.text("Configure ", fmt.mono("X"), " to 1")
        assert result == [
            {"text": "Configure ", "style": None},
            {"text": "X", "style": "mono"},
            {"text": " to 1", "style": None},
        ]

    def test_text_no_parts(self) -> None:
        """text() → []."""
        import pytest_reporter.fmt as fmt

        result = fmt.text()
        assert result == []

    def test_text_nested_flattens(self) -> None:
        """nested text(text('a'), mono('b')) → flat list (spreads, not nests)."""
        import pytest_reporter.fmt as fmt

        inner = fmt.text(fmt.mono("A"), fmt.mono("B"))
        result = fmt.text("X", inner)
        assert result == [
            {"text": "X", "style": None},
            {"text": "A", "style": "mono"},
            {"text": "B", "style": "mono"},
        ]

    def test_text_only_plain(self) -> None:
        """text('only plain') → one plain segment with style None."""
        import pytest_reporter.fmt as fmt

        result = fmt.text("only plain")
        assert result == [{"text": "only plain", "style": None}]


# ---------------------------------------------------------------------------
# Phase 1.3: normalize and _display unit tests — RED before GREEN
# ---------------------------------------------------------------------------


class TestNormalize:
    """Unit tests for normalize() and _display() in _procedure."""

    def test_str_returns_none(self) -> None:
        """str description → normalize returns None (no segments)."""
        from pytest_reporter._procedure import normalize

        assert normalize("plain text") is None

    def test_all_plain_formatted_text_returns_none(self) -> None:
        """FormattedText with all-plain segments → normalize returns None."""
        import pytest_reporter.fmt as fmt
        from pytest_reporter._procedure import normalize

        ft = fmt.text("hello", " world")
        assert normalize(ft) is None

    def test_formatted_text_with_mono_returns_list(self) -> None:
        """FormattedText with a mono segment → normalize returns the list."""
        import pytest_reporter.fmt as fmt
        from pytest_reporter._procedure import normalize

        ft = fmt.mono("x")
        result = normalize(ft)
        assert result == [{"text": "x", "style": "mono"}]

    def test_display_str_returns_itself(self) -> None:
        """_display('text') → 'text' unchanged."""
        from pytest_reporter._procedure import _display

        assert _display("hello world") == "hello world"

    def test_display_formatted_text_joins_texts(self) -> None:
        """_display(FormattedText) → joined segment texts."""
        import pytest_reporter.fmt as fmt
        from pytest_reporter._procedure import _display

        ft = fmt.text("Set ", fmt.mono("Pulse.Enable"), " to 1")
        assert _display(ft) == "Set Pulse.Enable to 1"
