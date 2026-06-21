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
    # Leaf steps have no substeps key or empty list
    assert data["steps"][0].get("substeps", []) == []
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


def test_nesting_too_deep_clamps_not_raises(pytester: Pytester) -> None:
    """Nesting deeper than 3 must CLAMP (not raise ProcedureNestingError)."""
    pytester.makepyfile("""
        from pytest_reporter import step
        import json

        def test_deep():
            with step("Level 1"):
                with step("Level 2"):
                    with step("Level 3"):
                        step("would-be-L4")  # must clamp, not raise
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)  # no exception => test passes


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
    assert step_data.get("substeps", []) == []
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
        node, _pushed = tracker.enter_step_cm(fmt.mono("cmd"))
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
        sub, _pushed = tracker.enter_step_cm(fmt.mono("inner"))
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


# ---------------------------------------------------------------------------
# Phase 1.1 (3-levels): Recursive ProcedureNodeJson type tests — RED before GREEN
# ---------------------------------------------------------------------------


class TestRecursiveNodeType:
    """ProcedureNodeJson must be recursive (substeps: list[ProcedureNodeJson])."""

    def test_procedure_node_json_is_importable(self) -> None:
        """ProcedureNodeJson must exist in _types."""
        from pytest_reporter._types import ProcedureNodeJson  # noqa: F401

    def test_step_json_is_alias_for_node(self) -> None:
        """StepJson must be an alias for ProcedureNodeJson (same object)."""
        from pytest_reporter._types import ProcedureNodeJson, StepJson

        assert StepJson is ProcedureNodeJson

    def test_substep_json_is_alias_for_node(self) -> None:
        """SubstepJson must be an alias for ProcedureNodeJson (same object)."""
        from pytest_reporter._types import ProcedureNodeJson, SubstepJson

        assert SubstepJson is ProcedureNodeJson

    def test_procedure_json_steps_uses_node(self) -> None:
        """ProcedureJson.steps annotation must be list[ProcedureNodeJson]."""
        from pytest_reporter._types import ProcedureJson, ProcedureNodeJson

        # Check __annotations__ to avoid TYPE_CHECKING-only resolution issues.
        annotations = ProcedureJson.__annotations__
        assert "steps" in annotations
        # The annotation string should reference ProcedureNodeJson.
        # Under from __future__ import annotations, annotations are strings.
        ann = annotations["steps"]
        node_name = ProcedureNodeJson.__name__
        assert node_name in str(ann)

    def test_node_has_substeps_annotation(self) -> None:
        """ProcedureNodeJson must have a 'substeps' annotation (recursive)."""
        from pytest_reporter._types import ProcedureNodeJson

        # Check __annotations__ directly — get_type_hints fails because Segment
        # is TYPE_CHECKING-only; we just need substeps to be declared.
        annotations = ProcedureNodeJson.__annotations__
        assert "substeps" in annotations


# ---------------------------------------------------------------------------
# Phase 2.1: Canonical 3-level fixture test — RED before GREEN
# ---------------------------------------------------------------------------


class TestCanonicalThreeLevelFixture:
    """Canonical fixture: exact tree shape and dotted numbers."""

    def _make_tracker(self) -> object:
        from pytest_reporter._procedure import ProcedureTracker, _set_tracker

        t = ProcedureTracker()
        _set_tracker(t)
        return t

    def test_canonical_tree_and_numbers(self) -> None:
        """The canonical 3-level fixture must produce the exact tree and numbers."""
        from pytest_reporter._procedure import ProcedureTracker, _set_tracker, step, substep

        tracker = ProcedureTracker()
        _set_tracker(tracker)

        with step("S"):
            step("A")
            substep("B")
            substep("C")
            step("D")
            substep("E")
        step("Another step")
        substep("Another substep")

        data = tracker.serialize()
        steps = data["steps"]

        # Top-level: 2 steps
        assert len(steps) == 2, f"Expected 2 top-level steps, got {len(steps)}"
        assert steps[0]["number"] == "1"
        assert steps[0]["description"] == "S"
        assert steps[1]["number"] == "2"
        assert steps[1]["description"] == "Another step"

        # Step 1 (S) has 2 children: A (1.1) and D (1.2)
        s1_children = steps[0]["substeps"]
        assert len(s1_children) == 2
        assert s1_children[0]["number"] == "1.1"
        assert s1_children[0]["description"] == "A"
        assert s1_children[1]["number"] == "1.2"
        assert s1_children[1]["description"] == "D"

        # 1.1 (A) has 2 children: B (1.1.1) and C (1.1.2)
        a_children = s1_children[0]["substeps"]
        assert len(a_children) == 2
        assert a_children[0]["number"] == "1.1.1"
        assert a_children[0]["description"] == "B"
        assert a_children[1]["number"] == "1.1.2"
        assert a_children[1]["description"] == "C"

        # 1.2 (D) has 1 child: E (1.2.1)
        d_children = s1_children[1]["substeps"]
        assert len(d_children) == 1
        assert d_children[0]["number"] == "1.2.1"
        assert d_children[0]["description"] == "E"

        # Step 2 (Another step) has 1 child: Another substep (2.1)
        s2_children = steps[1]["substeps"]
        assert len(s2_children) == 1
        assert s2_children[0]["number"] == "2.1"
        assert s2_children[0]["description"] == "Another substep"


# ---------------------------------------------------------------------------
# Phase 2.2: Parenting-case unit tests — RED before GREEN
# ---------------------------------------------------------------------------


class TestParentingCases:
    """Each parenting rule tested in isolation."""

    def _tracker(self) -> object:
        from pytest_reporter._procedure import ProcedureTracker, _set_tracker

        t = ProcedureTracker()
        _set_tracker(t)
        return t

    def test_step_at_root_is_l1(self) -> None:
        """step() at root → L1 (top-level steps list)."""
        from pytest_reporter._procedure import ProcedureTracker, step

        tracker = self._tracker()
        assert isinstance(tracker, ProcedureTracker)
        step("top")
        data = tracker.serialize()
        assert len(data["steps"]) == 1
        assert data["steps"][0]["description"] == "top"
        assert data["steps"][0]["number"] == "1"

    def test_step_inside_cm_is_l2(self) -> None:
        """step() inside CM → L2 child of CM node."""
        from pytest_reporter._procedure import ProcedureTracker, step

        tracker = self._tracker()
        assert isinstance(tracker, ProcedureTracker)
        with step("parent"):
            step("child")
        data = tracker.serialize()
        assert len(data["steps"]) == 1
        assert data["steps"][0]["substeps"][0]["description"] == "child"
        assert data["steps"][0]["substeps"][0]["number"] == "1.1"

    def test_step_inside_nested_cm_is_l3(self) -> None:
        """step() inside nested CM (depth 2) → L3 child."""
        from pytest_reporter._procedure import ProcedureTracker, step

        tracker = self._tracker()
        assert isinstance(tracker, ProcedureTracker)
        with step("L1"):
            with step("L2"):
                step("L3")
        data = tracker.serialize()
        l2 = data["steps"][0]["substeps"][0]
        assert l2["number"] == "1.1"
        assert l2["description"] == "L2"
        l3 = l2["substeps"][0]
        assert l3["number"] == "1.1.1"
        assert l3["description"] == "L3"

    def test_substep_at_root_no_prior_step_promotes(self) -> None:
        """substep() at root with no prior step → promotes to L1 step."""
        from pytest_reporter._procedure import ProcedureTracker, substep

        tracker = self._tracker()
        assert isinstance(tracker, ProcedureTracker)
        substep("orphan")
        data = tracker.serialize()
        assert len(data["steps"]) == 1
        assert data["steps"][0]["description"] == "orphan"
        assert data["steps"][0]["number"] == "1"

    def test_substep_at_root_with_prior_step_is_l2(self) -> None:
        """substep() at root with a prior step → L2 child of last L1 step."""
        from pytest_reporter._procedure import ProcedureTracker, step, substep

        tracker = self._tracker()
        assert isinstance(tracker, ProcedureTracker)
        step("T")
        substep("S")
        data = tracker.serialize()
        assert data["steps"][0]["substeps"][0]["description"] == "S"
        assert data["steps"][0]["substeps"][0]["number"] == "1.1"

    def test_substep_inside_cm_depth1_is_l3(self) -> None:
        """substep() inside CM-depth1 → L3 child of last L2 step."""
        from pytest_reporter._procedure import ProcedureTracker, step, substep

        tracker = self._tracker()
        assert isinstance(tracker, ProcedureTracker)
        with step("L1"):
            step("L2")
            substep("L3")
        data = tracker.serialize()
        l2 = data["steps"][0]["substeps"][0]
        assert l2["number"] == "1.1"
        l3 = l2["substeps"][0]
        assert l3["number"] == "1.1.1"
        assert l3["description"] == "L3"

    def test_substep_inside_cm_depth2_clamps_to_l3_sibling(self) -> None:
        """substep() inside CM-depth2 after an existing L3 step → clamp to L3 sibling."""
        from pytest_reporter._procedure import ProcedureTracker, step, substep

        tracker = self._tracker()
        assert isinstance(tracker, ProcedureTracker)
        with step("L1"):
            with step("L2"):
                step("L3a")  # first L3 child of L2
                substep("would-be-L4")  # after L3a exists, substep must clamp to L3 sibling
        data = tracker.serialize()
        l1 = data["steps"][0]
        l2 = l1["substeps"][0]
        assert l2["number"] == "1.1"
        assert l2["description"] == "L2"
        # L2 should have 2 children: L3a and the clamped node (L3 sibling)
        assert len(l2["substeps"]) == 2
        l3a = l2["substeps"][0]
        assert l3a["number"] == "1.1.1"
        assert l3a["description"] == "L3a"
        clamped = l2["substeps"][1]
        assert clamped["number"] == "1.1.2"
        assert clamped["description"] == "would-be-L4"
        # L3a must have no children (no L4 was created)
        assert l3a.get("substeps", []) == []

    def test_l4_clamp_via_step_inside_3deep_cm(self) -> None:
        """step() inside 3-deep CM (would be L4) → clamps to L3 sibling, no exception."""
        from pytest_reporter._procedure import ProcedureTracker, step

        tracker = self._tracker()
        assert isinstance(tracker, ProcedureTracker)
        with step("L1"):
            with step("L2"):
                with step("L3"):
                    step("would-be-L4-clamps-to-L3-sibling")  # len(cm_stack)==3 → clamp

        data = tracker.serialize()
        l1 = data["steps"][0]
        assert l1["number"] == "1"
        assert l1["description"] == "L1"
        l2 = l1["substeps"][0]
        assert l2["number"] == "1.1"
        assert l2["description"] == "L2"
        # L3 is child of L2, and the clamped node is a sibling of L3 (also child of L2)
        assert len(l2["substeps"]) == 2
        l3 = l2["substeps"][0]
        assert l3["number"] == "1.1.1"
        assert l3["description"] == "L3"
        clamped = l2["substeps"][1]
        assert clamped["number"] == "1.1.2"
        assert clamped["description"] == "would-be-L4-clamps-to-L3-sibling"


# ---------------------------------------------------------------------------
# Phase 2.3: _StepProxy pop-and-re-record regression — RED before GREEN
# ---------------------------------------------------------------------------


class TestStepProxyNoduplication:
    """_StepProxy.__enter__ must not duplicate nodes."""

    def test_with_step_no_duplication_in_substeps(self) -> None:
        """with step('X') must record 'X' exactly once in parent's substeps."""
        from pytest_reporter._procedure import ProcedureTracker, _set_tracker, step

        tracker = ProcedureTracker()
        _set_tracker(tracker)

        with step("X"):
            pass

        data = tracker.serialize()
        assert len(data["steps"]) == 1
        assert data["steps"][0]["description"] == "X"

    def test_with_step_inside_cm_no_duplication(self) -> None:
        """with step() inside a CM step must not duplicate in parent substeps."""
        from pytest_reporter._procedure import ProcedureTracker, _set_tracker, step

        tracker = ProcedureTracker()
        _set_tracker(tracker)

        with step("L1"):
            with step("L2"):
                pass

        data = tracker.serialize()
        assert len(data["steps"]) == 1
        l1 = data["steps"][0]
        assert len(l1["substeps"]) == 1
        assert l1["substeps"][0]["description"] == "L2"


# ---------------------------------------------------------------------------
# Phase 2.4: Serialize-time numbering — RED before GREEN
# ---------------------------------------------------------------------------


class TestSerializeTimeNumbering:
    """Numbers must be absent pre-serialize and correct post-serialize."""

    def test_numbers_absent_in_raw_node(self) -> None:
        """Nodes have no 'number' key until serialize() is called."""
        from pytest_reporter._procedure import ProcedureTracker, _set_tracker

        tracker = ProcedureTracker()
        _set_tracker(tracker)

        node = tracker.record_step("a step")
        # Before serialize, number must NOT be in the node
        assert "number" not in node

    def test_numbers_correct_after_serialize(self) -> None:
        """After serialize(), all nodes have correct dotted numbers."""
        from pytest_reporter._procedure import ProcedureTracker, _set_tracker, step, substep

        tracker = ProcedureTracker()
        _set_tracker(tracker)

        step("First")
        substep("Child1")
        substep("Child2")
        step("Second")

        data = tracker.serialize()
        assert data["steps"][0]["number"] == "1"
        assert data["steps"][0]["substeps"][0]["number"] == "1.1"
        assert data["steps"][0]["substeps"][1]["number"] == "1.2"
        assert data["steps"][1]["number"] == "2"


# ---------------------------------------------------------------------------
# Phase 3.1: Regression tests — auto-nest behaviors must stay green
# ---------------------------------------------------------------------------


class TestAutoNestRegressions:
    """Auto-nest behaviors from procedure-auto-nest must remain intact."""

    def _tracker(self) -> object:
        from pytest_reporter._procedure import ProcedureTracker, _set_tracker

        t = ProcedureTracker()
        _set_tracker(t)
        return t

    def test_plain_with_step_substep_shape(self) -> None:
        """Plain with step('X'): substep('Y') → step '1' with substep '1.1'."""
        from pytest_reporter._procedure import ProcedureTracker, step, substep

        tracker = self._tracker()
        assert isinstance(tracker, ProcedureTracker)
        with step("X"):
            substep("Y")
        data = tracker.serialize()
        assert len(data["steps"]) == 1
        assert data["steps"][0]["number"] == "1"
        assert data["steps"][0]["description"] == "X"
        subs = data["steps"][0]["substeps"]
        assert len(subs) == 1
        assert subs[0]["number"] == "1.1"
        assert subs[0]["description"] == "Y"

    def test_substep_before_step_promotes_root(self) -> None:
        """substep() with no steps at root → promotes, no exception."""
        from pytest_reporter._procedure import ProcedureTracker, substep

        tracker = self._tracker()
        assert isinstance(tracker, ProcedureTracker)
        substep("orphan-root")
        data = tracker.serialize()
        assert len(data["steps"]) == 1
        assert data["steps"][0]["description"] == "orphan-root"

    def test_step_inside_cm_is_always_child(self) -> None:
        """step() inside open CM → always recorded as deeper child, not top-level."""
        from pytest_reporter._procedure import ProcedureTracker, step

        tracker = self._tracker()
        assert isinstance(tracker, ProcedureTracker)
        with step("outer"):
            step("inner")
        data = tracker.serialize()
        assert len(data["steps"]) == 1  # only 1 top-level
        assert data["steps"][0]["substeps"][0]["description"] == "inner"

    def test_last_step_wins_for_substep_attachment(self) -> None:
        """Two steps then substep → substep attaches to the SECOND step."""
        from pytest_reporter._procedure import ProcedureTracker, step, substep

        tracker = self._tracker()
        assert isinstance(tracker, ProcedureTracker)
        step("first")
        step("second")
        substep("child")
        data = tracker.serialize()
        assert len(data["steps"]) == 2
        # First step has no substeps (key absent or empty in new tracker)
        assert data["steps"][0].get("substeps", []) == []
        # Second step has the substep
        assert len(data["steps"][1]["substeps"]) == 1
        assert data["steps"][1]["substeps"][0]["description"] == "child"

    def test_fmt_segments_at_depth3(self) -> None:
        """fmt.mono() description at L3 must produce description_segments on the node."""
        import pytest_reporter.fmt as fmt
        from pytest_reporter._procedure import ProcedureTracker, _set_tracker, step

        tracker = ProcedureTracker()
        _set_tracker(tracker)

        with step("L1"):
            with step("L2"):
                step(fmt.mono("L3-mono"))

        data = tracker.serialize()
        l1 = data["steps"][0]
        l2 = l1["substeps"][0]
        # L3 node: should be a sibling of L2 due to clamp
        # Actually under the algorithm:
        # with step("L1"): pushes L1; with step("L2"): L2 is child of L1, push L2
        # step(fmt.mono("L3-mono")): len(_cm_stack)==2 → would be L3 but that's >=3?
        # No: len(cm_stack)==2, record_step clamp is len>=3, so L3 is fine
        # L3 is a child of L2
        l3 = l2["substeps"][0]
        assert l3["description"] == "L3-mono"
        assert "description_segments" in l3
        assert l3["description_segments"] == [{"text": "L3-mono", "style": "mono"}]
