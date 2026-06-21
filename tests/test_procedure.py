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
# Phase 2: Parser unit tests (no pytester) — RED before GREEN
# ---------------------------------------------------------------------------


class TestParseMarkup:
    """Unit tests for parse_markup() — PTF-1 / PTF-3 / PTF-4 / PTF-5 / PTF-6."""

    def test_plain_no_backticks(self) -> None:
        """PTF-1 / PTF-3: plain text with no backticks → single plain segment."""
        from pytest_reporter._markup import parse_markup

        segs = parse_markup("Configure timeout to 30")
        assert segs == [{"text": "Configure timeout to 30", "style": None}]

    def test_single_mono(self) -> None:
        """PTF-1: single backtick span → 3 segments, middle is mono."""
        from pytest_reporter._markup import parse_markup

        segs = parse_markup("Set `A` to 1")
        assert segs == [
            {"text": "Set ", "style": None},
            {"text": "A", "style": "mono"},
            {"text": " to 1", "style": None},
        ]

    def test_multiple_mono(self) -> None:
        """PTF-1: two backtick spans → 4 or more segments, both inner are mono."""
        from pytest_reporter._markup import parse_markup

        segs = parse_markup("Set `A` and `B`")
        assert segs == [
            {"text": "Set ", "style": None},
            {"text": "A", "style": "mono"},
            {"text": " and ", "style": None},
            {"text": "B", "style": "mono"},
        ]

    def test_unclosed_backtick(self) -> None:
        """PTF-5: single unmatched backtick → one plain segment including literal backtick."""
        from pytest_reporter._markup import parse_markup

        segs = parse_markup("Set `Pulse")
        assert segs == [{"text": "Set `Pulse", "style": None}]

    def test_odd_backticks_deterministic(self) -> None:
        """PTF-5: 3 backticks → first pair matched as mono; unmatched backtick + tail is plain."""
        from pytest_reporter._markup import parse_markup

        segs = parse_markup("a `b` c `d")
        assert segs == [
            {"text": "a ", "style": None},
            {"text": "b", "style": "mono"},
            {"text": " c `d", "style": None},
        ]

    def test_empty_backtick_pair(self) -> None:
        """PTF-6: empty backtick pair `` dropped — result is empty list."""
        from pytest_reporter._markup import parse_markup

        segs = parse_markup("``")
        assert segs == []

    def test_adjacent_backtick_pairs(self) -> None:
        """PTF-6: adjacent pairs `A``B` → A mono, B mono, no crash."""
        from pytest_reporter._markup import parse_markup

        segs = parse_markup("`A``B`")
        assert segs == [
            {"text": "A", "style": "mono"},
            {"text": "B", "style": "mono"},
        ]

    def test_html_inside_backticks(self) -> None:
        """PTF-4: HTML tag inside backticks → mono segment with raw text (no HTML)."""
        from pytest_reporter._markup import parse_markup

        segs = parse_markup("Send `</script>` now")
        assert segs == [
            {"text": "Send ", "style": None},
            {"text": "</script>", "style": "mono"},
            {"text": " now", "style": None},
        ]

    def test_html_outside_backticks(self) -> None:
        """PTF-4: HTML tag outside backticks → single plain segment with raw string."""
        from pytest_reporter._markup import parse_markup

        segs = parse_markup("Click <b>OK</b>")
        assert segs == [{"text": "Click <b>OK</b>", "style": None}]


# ---------------------------------------------------------------------------
# Phase 3: _attach_segments wiring tests — RED before GREEN
# ---------------------------------------------------------------------------


class TestAttachSegments:
    """Unit tests for _attach_segments wiring in ProcedureTracker — PTF-2 / PTF-3 / RI-1."""

    def _make_tracker(self) -> object:
        from pytest_reporter._procedure import ProcedureTracker, _set_tracker

        t = ProcedureTracker()
        _set_tracker(t)
        return t

    def test_plain_step_no_segments_key(self) -> None:
        """PTF-3 / RI-1: plain description → NO description_segments key in dict."""
        tracker = self._make_tracker()
        from pytest_reporter._procedure import ProcedureTracker

        assert isinstance(tracker, ProcedureTracker)
        node = tracker.record_step("plain description")
        assert "description_segments" not in node

    def test_mono_step_has_segments(self) -> None:
        """PTF-2: backtick description → description_segments present with correct list."""
        tracker = self._make_tracker()
        from pytest_reporter._procedure import ProcedureTracker

        assert isinstance(tracker, ProcedureTracker)
        node = tracker.record_step("Set `A` to 1")
        assert "description_segments" in node
        assert node["description_segments"] == [
            {"text": "Set ", "style": None},
            {"text": "A", "style": "mono"},
            {"text": " to 1", "style": None},
        ]

    def test_cm_step_has_segments(self) -> None:
        """PTF-1: CM step with backtick → node from enter_step_cm has segments."""
        tracker = self._make_tracker()
        from pytest_reporter._procedure import ProcedureTracker

        assert isinstance(tracker, ProcedureTracker)
        node = tracker.enter_step_cm("Set `A`")
        assert "description_segments" in node
        assert any(s["style"] == "mono" for s in node["description_segments"])

    def test_substep_has_segments(self) -> None:
        """PTF-1: substep with backtick → substep dict has description_segments."""
        tracker = self._make_tracker()
        from pytest_reporter._procedure import ProcedureTracker

        assert isinstance(tracker, ProcedureTracker)
        # Enter a CM step so we're inside one
        tracker.enter_step_cm("outer")
        # record_step inside CM becomes a substep
        sub = tracker.record_step("Load `reg`")
        assert "description_segments" in sub
        assert any(s["style"] == "mono" for s in sub["description_segments"])

    def test_promoted_substep_parses_once(self) -> None:
        """record_substep() promotes to record_step(); parse happens exactly once."""
        tracker = self._make_tracker()
        from pytest_reporter._procedure import ProcedureTracker

        assert isinstance(tracker, ProcedureTracker)
        # No steps yet → promotes to top-level step
        node = tracker.record_substep("Load `reg`")
        assert "description_segments" in node
        expected = [
            {"text": "Load ", "style": None},
            {"text": "reg", "style": "mono"},
        ]
        assert node["description_segments"] == expected

    def test_cm_depth2_substep_segments(self) -> None:
        """PTF-1: depth-2 substep in CM → substep dict has description_segments."""
        tracker = self._make_tracker()
        from pytest_reporter._procedure import ProcedureTracker

        assert isinstance(tracker, ProcedureTracker)
        tracker.enter_step_cm("outer")
        sub = tracker.enter_step_cm("inner `x`")
        assert "description_segments" in sub
        assert any(s["style"] == "mono" for s in sub["description_segments"])
