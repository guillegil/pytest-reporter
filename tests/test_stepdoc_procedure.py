"""Test procedures come from stepdoc's steps (``from stepdoc import step``).

pytest-reporter has no step API of its own. With stepdoc installed it follows
stepdoc's ``pytest_stepdoc_step_*`` hooks and writes each attempt's steps to
``procedure.json``. stepdoc stays optional: without it procedures are empty.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pytest import Pytester

requires_stepdoc = pytest.mark.skipif(
    importlib.util.find_spec("stepdoc") is None, reason="stepdoc is not installed"
)
requires_verifier = pytest.mark.skipif(
    importlib.util.find_spec("pytest_verifier") is None, reason="pytest-verifier is not installed"
)


def _run_dir(pytester: Pytester) -> Path:
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    assert len(runs) == 1
    return runs[0]


def _procedure(pytester: Pytester, module: str, func: str, *rest: str) -> dict[str, Any]:
    path = _run_dir(pytester) / "tests" / f"{module}.py" / func / "default"
    for part in rest:
        path = path / part
    return json.loads((path / "procedure.json").read_text())  # type: ignore[no-any-return]


_DATA_BLOCK = '<script type="application/json" id="report-data">'


def _data(pytester: Pytester) -> dict[str, Any]:
    html = (_run_dir(pytester) / "report.html").read_text(encoding="utf-8")
    start = html.index(_DATA_BLOCK) + len(_DATA_BLOCK)
    return json.loads(html[start : html.index("</script>", start)])  # type: ignore[no-any-return]


def _shape(nodes: list[dict[str, Any]]) -> list[Any]:
    """(number, kind, description, outcome) of each node, children nested."""
    out: list[Any] = []
    for n in nodes:
        row: tuple[Any, ...] = (n["number"], n["kind"], n["description"], n["outcome"])
        if n.get("substeps"):
            row += (_shape(n["substeps"]),)
        out.append(row)
    return out


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


def test_step_names_are_gone() -> None:
    """step/substep/fmt left pytest_reporter; importing them says where they went."""
    import pytest_reporter

    for name in ("step", "substep", "fmt", "FormattedText", "ProcedureError"):
        assert name not in pytest_reporter.__all__
        with pytest.raises(ImportError, match="stepdoc"):
            getattr(pytest_reporter, name)


def test_no_stepdoc_import_in_reporter() -> None:
    """stepdoc is optional: no module of the reporter imports it."""
    src = Path(__file__).parent.parent / "src" / "pytest_reporter"
    for path in src.rglob("*.py"):
        assert "stepdoc" not in _imported_modules(path), path.name


def test_empty_procedure_without_steps(pytester: Pytester) -> None:
    pytester.makepyfile(test_plain="def test_a():\n    assert True\n")
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    assert _procedure(pytester, "test_plain", "test_a") == {"steps": []}


@requires_stepdoc
def test_nested_steps_and_checks(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_steps="""
        from stepdoc import step

        def test_a():
            with step("Configure"):
                with step("Set level"):
                    pass
                assert 1 + 1 == 2
            with step("Measure"):
                pass
            step("Leaf check", check=True)
        """
    )
    pytester.makeini("[pytest]\nenable_assertion_pass_hook = true\n")
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)

    proc = _procedure(pytester, "test_steps", "test_a")
    assert proc["source"] == "stepdoc"
    assert _shape(proc["steps"]) == [
        (
            "1",
            "step",
            "Configure",
            "passed",
            [
                ("1.1", "step", "Set level", "passed"),
                ("1.2", "check", "Verify 1 + 1 == 2", "passed"),
            ],
        ),
        ("2", "step", "Measure", "passed"),
        ("3", "step", "Leaf check", "passed", [("3.1", "check", "Verify Leaf check", "passed")]),
    ]
    first = proc["steps"][0]
    assert first["section"] == "procedure"
    assert first["start_time"].endswith("Z") and first["duration_seconds"] >= 0

    # The same procedure is embedded in the HTML report.
    run = _data(pytester)["tests"][0]["runs"][0]
    assert _shape(run["procedure"]["steps"]) == _shape(proc["steps"])


@requires_stepdoc
def test_failed_step_has_outcome_and_exception(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_fail="""
        from stepdoc import step

        def test_a():
            with step("Outer"):
                with step("Inner"):
                    raise RuntimeError("boom")
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(failed=1)

    outer = _procedure(pytester, "test_fail", "test_a")["steps"][0]
    inner = outer["substeps"][0]
    assert (outer["outcome"], inner["outcome"]) == ("error", "error")
    assert inner["exc"] == {"type": "RuntimeError", "msg": "boom", "tb": ""}


@requires_stepdoc
def test_fixture_steps_go_to_setup_and_teardown(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_fx="""
        import pytest
        from stepdoc import step

        @pytest.fixture
        def dut():
            with step("Power on"):
                pass
            yield
            with step("Power off"):
                pass

        def test_a(dut):
            with step("Run"):
                pass
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)

    steps = _procedure(pytester, "test_fx", "test_a")["steps"]
    assert [(s["number"], s["section"], s["description"]) for s in steps] == [
        ("S1", "setup", "Power on"),
        ("1", "procedure", "Run"),
        ("T1", "teardown", "Power off"),
    ]


@requires_stepdoc
def test_actions_from_a_bridge(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_act="""
        import stepdoc
        from stepdoc import step

        def write(reg, value):
            stepdoc.record_action(reg, "write", value)

        def read(reg):
            stepdoc.record_action(reg, "read", 7)
            return 7

        def test_a():
            with step("Program"):
                write("dac.level", 12)
                assert read("adc.value") == 7
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)

    entries = _procedure(pytester, "test_act", "test_a")["steps"][0]["substeps"]
    assert entries[0]["kind"] == "action"
    assert entries[0]["description"] == "dac.level = 12"


@requires_stepdoc
def test_retry_attempts_have_their_own_steps(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_retry="""
        from stepdoc import step

        _n = 0

        def test_flaky():
            global _n
            _n += 1
            with step(f"Attempt {_n}"):
                assert _n >= 2
        """
    )
    pytester.runpytest("--report-dir=reports", "--report-retries=1").assert_outcomes(passed=1)

    first = _procedure(pytester, "test_retry", "test_flaky")["steps"]
    retry = _procedure(pytester, "test_retry", "test_flaky", "retries", "01")["steps"]
    assert [(s["number"], s["description"], s["outcome"]) for s in first] == [
        ("1", "Attempt 1", "failed")
    ]
    assert [(s["number"], s["description"], s["outcome"]) for s in retry] == [
        ("1", "Attempt 2", "passed")
    ]


@requires_stepdoc
def test_stepdoc_record_saved_in_run_folder(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_rec="""
        from stepdoc import step

        def test_a():
            with step("One"):
                pass
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    record = json.loads((_run_dir(pytester) / "stepdoc.json").read_text())
    assert record["tests"][0]["steps"][0]["title"] == "One"


@requires_stepdoc
def test_user_stepdoc_options_are_kept(pytester: Pytester) -> None:
    """With the user's own stepdoc output, the reporter adds no record of its own."""
    pytester.makepyfile(
        test_own="""
        from stepdoc import step

        def test_a():
            with step("One"):
                pass
        """
    )
    pytester.runpytest(
        "--report-dir=reports", "--stepdoc-procedure=out/procedure.md"
    ).assert_outcomes(passed=1)
    assert (pytester.path / "out" / "procedure.md").exists()
    assert not (_run_dir(pytester) / "stepdoc.json").exists()
    steps = _procedure(pytester, "test_own", "test_a")["steps"]
    assert [s["description"] for s in steps] == ["One"]


@requires_stepdoc
def test_report_stepdoc_false_turns_it_off(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_off="""
        from stepdoc import step

        def test_a():
            with step("One"):
                pass
        """
    )
    pytester.makeini("[pytest]\nreport_stepdoc = false\n")
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    assert not (_run_dir(pytester) / "stepdoc.json").exists()
    assert _procedure(pytester, "test_off", "test_a") == {"steps": []}


@requires_stepdoc
@requires_verifier
def test_verifier_checks_land_in_their_step(pytester: Pytester) -> None:
    """stepdoc's verifier adapter puts each verify check in the step that made it."""
    pytester.makepyfile(
        test_vs="""
        from stepdoc import step

        def test_a(verify):
            with step("Measure"):
                verify.equal(1, 1, name="Reply")
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    measure = _procedure(pytester, "test_vs", "test_a")["steps"][0]
    assert [(c["kind"], c["description"]) for c in measure["substeps"]] == [
        ("check", "Verify 'Reply' == 1")
    ]


@requires_stepdoc
@requires_verifier
def test_verifier_check_shows_names_and_values(pytester: Pytester) -> None:
    """An expected value given by name reads ``<name> (value)``: the procedure's
    symbolic form with this run's value."""
    pytester.makepyfile(
        test_sym="""
        import pytest
        from stepdoc import step

        @pytest.fixture
        def wdata():
            return 243

        def test_a(verify, wdata):
            with step("Read back"):
                verify.equal(wdata, wdata, name="Read from `DA_SCRATCH_1_ADDR`")
                verify.between(5, 1, wdata, name="Range")
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    step = _procedure(pytester, "test_sym", "test_a")["steps"][0]
    # stepdoc with check notes starts a named check's text with the checked
    # expression: 'Name': wdata == <wdata>.
    name = "'Read from `DA_SCRATCH_1_ADDR`'"
    first = f"{name}: wdata" if _stepdoc_has_check_notes() else name
    assert [c["description"] for c in step["substeps"]] == [
        f"Verify {first} == <wdata> (243)",
        "Verify 'Range' ∈ [1, <wdata> (243)]",
    ]


def _stepdoc_has_check_notes() -> bool:
    """stepdoc 0.4's Check has ``note`` (and the checked expression in its text)."""
    try:
        from stepdoc.core.model import Check
    except ImportError:
        return False
    return "note" in getattr(Check, "__dataclass_fields__", {})


requires_stepdoc_check_notes = pytest.mark.skipif(
    not _stepdoc_has_check_notes(), reason="stepdoc without Check.note"
)


@requires_stepdoc_check_notes
@requires_verifier
def test_verifier_check_note_reaches_procedure_and_html(pytester: Pytester) -> None:
    """A check's note (pytest-verifier's ``note=``) is the check node's ``note``;
    the Procedure tab shows it after the text."""
    pytester.makepyfile(
        test_note="""
        from stepdoc import step

        def test_a(verify):
            with step("Verify CMD FIFO flags at startup"):
                verify.record({
                    "check_type": "equal", "name": "TXFE", "description": "Verify 'TXFE' == 1",
                    "actual": 1, "expected": 1, "note": "CMD FIFO empty",
                })
                verify.equal(0, 0, name="TX")
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    step = _procedure(pytester, "test_note", "test_a")["steps"][0]
    assert [(c["description"], c.get("note")) for c in step["substeps"]] == [
        ("Verify 'TXFE' == 1", "CMD FIFO empty"),
        ("Verify 'TX' == 0", None),
    ]
    run = _data(pytester)["tests"][0]["runs"][0]
    assert run["procedure"]["steps"][0]["substeps"][0]["note"] == "CMD FIFO empty"
    assert run["check_results"][0]["note"] == "CMD FIFO empty"


@requires_stepdoc_check_notes
@requires_verifier
def test_verifier_comment_note_reaches_procedure(pytester: Pytester) -> None:
    """A source comment above a check, or after it, is the check node's ``note``.

    stepdoc fills comment notes in when its recorder resolves; the reporter reads
    them at ``pytest_runtest_logfinish``. Until stepdoc resolves them before then,
    the test xfails instead of failing.
    """
    pytester.makepyfile(
        test_comment="""
        from stepdoc import step

        def test_a(verify):
            with step("Verify CMD FIFO flags at startup"):
                # CMD FIFO empty
                verify.equal(1, 1, name="TXFE")
                verify.equal(0, 0, name="TX")  # room for commands
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    stepdoc_json = json.loads((_run_dir(pytester) / "stepdoc.json").read_text())
    assert "CMD FIFO empty" in json.dumps(stepdoc_json)  # stepdoc found the comment
    step = _procedure(pytester, "test_comment", "test_a")["steps"][0]
    notes = [c.get("note") for c in step["substeps"]]
    if notes == [None, None]:
        pytest.xfail("stepdoc resolves comment notes after pytest_runtest_logfinish")
    assert notes == ["CMD FIFO empty", "room for commands"]


def test_check_node_note() -> None:
    """stepdoc's Check.note (note= or a source comment) is the node's ``note``;
    a blank or missing one is left out."""
    from types import SimpleNamespace as NS

    from pytest_reporter._stepdoc import _check

    def check(**kw: object) -> NS:
        base = {"text": "dat.txfe == 1", "passed": True, "actual": 1, "children": []}
        return NS(**{**base, **kw})

    node = _check(
        check(
            text="dev.block.esmi3_32dat.txfe == 1",
            symbolic_text="dev.block.esmi<channel>_32dat.txfe == 1",
            note="  CMD FIFO empty ",
        ),
        "1.1",
    )
    assert node["description"] == "Verify dev.block.esmi3_32dat.txfe == 1"
    assert node["note"] == "CMD FIFO empty"
    assert node["result"] == "got 1"
    assert "note" not in _check(check(note="  "), "1.2")
    assert "note" not in _check(check(), "1.3")  # an older stepdoc: no note attribute
    named = _check(
        check(
            text="'FIFO not full': dev.block.esmi3_ctl.tx == 0",
            symbolic_text="'FIFO not full': dev.block.esmi<channel>_ctl.tx == 0",
            note="room for commands",
        ),
        "1.3",
    )
    assert named["description"] == "Verify 'FIFO not full': dev.block.esmi3_ctl.tx == 0"
    assert named["note"] == "room for commands"


@pytest.mark.parametrize(
    ("symbolic", "concrete", "expected"),
    [
        ("'R' == <wdata>", "'R' == 243", "'R' == <wdata> (243)"),
        ("'R' == <wdata> * 2", "'R' == 486", "'R' == <wdata> * 2 (486)"),
        ("'Reply' == <reply>", "'Reply' == 'OK'", "'Reply' == <reply> ('OK')"),
        ("'I' ∈ [<lo> A, <hi> A]", "'I' ∈ [0.1A, 0.5A]", "'I' ∈ [<lo> A (0.1A), <hi> A (0.5A)]"),
        ("'V' == <vref> V ± 0.05V", "'V' == 3.3V ± 0.05V", "'V' == <vref> V (3.3V) ± 0.05V"),
        ("'L' == <exp>", "'L' == [1, 2]", "'L' == <exp> ([1, 2])"),
        # The checked expression (stepdoc 0.4) reads as this run has it.
        (
            "dev.block.esmi<channel>_32dat.txfe == 1",
            "dev.block.esmi3_32dat.txfe == 1",
            "dev.block.esmi3_32dat.txfe == 1",
        ),
        (
            "'FIFO not full': dev.block.esmi<channel>_ctl.tx == 0",
            "'FIFO not full': dev.block.esmi3_ctl.tx == 0",
            "'FIFO not full': dev.block.esmi3_ctl.tx == 0",
        ),
        ("'R': wdata == <wdata>", "'R': wdata == 243", "'R': wdata == <wdata> (243)"),
        ("reg[<i>].value == <exp>", "reg[2].value == 5", "reg[2].value == <exp> (5)"),
        (
            "dev.esmi<ch>.level ∈ [<lo>, 5]",
            "dev.esmi1.level ∈ [1, 5]",
            "dev.esmi1.level ∈ [<lo> (1), 5]",
        ),
        ("dev.esmi<ch>.ready is True", "dev.esmi2.ready is True", "dev.esmi2.ready is True"),
        ("write_count >= <n>", "write_count >= 8", "write_count >= <n> (8)"),
        ("'a == b' == <x>", "'a == b' == 3", "'a == b' == <x> (3)"),
        # A name with an apostrophe and an operator (stepdoc writes it raw).
        (
            "'Don't > max': x<ch> == <lim>",
            "'Don't > max': x3 == 5",
            "'Don't > max': x3 == <lim> (5)",
        ),
        ("'a > b': x<ch> == <lim>", "'a > b': x3 == 5", "'a > b': x3 == <lim> (5)"),
        ("'it's': x<ch> == 1", "'it's': x3 == 1", "'it's': x3 == 1"),
        ("'Don't > max' == <lim>", "'Don't > max' == 5", "'Don't > max' == <lim> (5)"),
    ],
)
def test_with_values(symbolic: str, concrete: str, expected: str) -> None:
    from pytest_reporter._stepdoc import with_values

    assert with_values(symbolic, concrete) == expected


@requires_stepdoc
def test_html_renders_xss_safely(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_xss="""
        from stepdoc import step

        def test_a():
            with step("</script><script>alert(1)</script>"):
                pass
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    html = (_run_dir(pytester) / "report.html").read_text(encoding="utf-8")
    data_block = html[html.index(_DATA_BLOCK) :]
    data_block = data_block[: data_block.index("</script>")]
    assert "alert(1)" in data_block  # the title is in the data, escaped


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("plain title", None),
        ("a lone ` stays", None),
        (
            "Write into `dut.reg1 = 1` now",
            [
                {"text": "Write into ", "style": None},
                {"text": "dut.reg1 = 1", "style": "mono"},
                {"text": " now", "style": None},
            ],
        ),
        (
            "``a`b`` and `c`",
            [
                {"text": "a`b", "style": "mono"},
                {"text": " and ", "style": None},
                {"text": "c", "style": "mono"},
            ],
        ),
        ("`` `edge ``", [{"text": "`edge", "style": "mono"}]),
        ("empty `` span", None),
    ],
)
def test_title_code_spans_become_segments(
    title: str, expected: list[dict[str, Any]] | None
) -> None:
    from pytest_reporter._stepdoc import title_segments

    assert title_segments(title) == expected


@requires_stepdoc
def test_step_title_code_spans_reach_procedure_json(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_mono="""
        from stepdoc import step

        def test_a():
            with step("Write into `dut.reg1 = 1`"):
                pass
            with step("Plain"):
                pass
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    first, second = _procedure(pytester, "test_mono", "test_a")["steps"]
    assert first["description"] == "Write into `dut.reg1 = 1`"
    assert first["description_segments"] == [
        {"text": "Write into ", "style": None},
        {"text": "dut.reg1 = 1", "style": "mono"},
    ]
    assert "description_segments" not in second


requires_stepdoc_repeat = pytest.mark.skipif(
    importlib.util.find_spec("stepdoc") is None or not hasattr(__import__("stepdoc"), "repeat"),
    reason="stepdoc without loop collapsing (repeat)",
)


def test_repeat_and_repeated_write_nodes() -> None:
    """stepdoc's Repeat (a collapsed loop) and an Action with count > 1 for a write."""
    from types import SimpleNamespace as NS

    from pytest_reporter._stepdoc import StepCollector

    def action(target: str, op: str, value: object, direction: str, count: int = 1) -> NS:
        return NS(target=target, op=op, value=value, direction=direction, meta={}, count=count)

    write = action("dev.fifo.fifo_data", "write", 90, "in", count=16)
    loop = NS(
        until="FIFO is empty",
        count=16,
        entries=[
            action("dev.fifo.status.empty", "read", True, "out"),
            action("dev.fifo.fifo_data", "write", 90, "in"),
        ],
    )
    plain = NS(until=None, count=None, entries=[])
    titled = NS(title="Drain the FIFO", until="FIFO is empty", count=2, entries=[])
    only_title = NS(title="Pulse enable", until=None, count=3, entries=[])
    collector = StepCollector()
    assert collector._entry(write, "1.1") == {
        "kind": "action",
        "number": "1.1",
        "description": "Repeat dev.fifo.fifo_data = 90",
        "outcome": "info",
        "exc": None,
        "result": "(16 times)",
    }
    node = collector._entry(loop, "1.2")
    assert _shape([node]) == [
        (
            "1.2",
            "repeat",
            "Repeat until FIFO is empty",
            "info",
            [
                ("1.2.1", "action", "Read dev.fifo.status.empty", "info"),
                ("1.2.2", "action", "dev.fifo.fifo_data = 90", "info"),
            ],
        )
    ]
    assert node["result"] == "16 times"
    assert collector._entry(titled, "3.1")["description"] == (
        "Drain the FIFO (repeat until FIFO is empty)"
    )
    assert collector._entry(only_title, "3.2")["description"] == "Pulse enable (repeat)"
    assert collector._entry(plain, "2.1") == {
        "kind": "repeat",
        "number": "2.1",
        "description": "Repeat",
        "outcome": "info",
        "exc": None,
    }


@requires_stepdoc_repeat
def test_loops_from_stepdoc(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_loop="""
        import stepdoc
        from stepdoc import repeat, step

        def read_fifo():
            stepdoc.record_action("dev.fifo.fifo_data", "write", 90)

        def empty(state):
            stepdoc.record_action("dev.fifo.status.empty", "read", state["n"] == 0)
            return state["n"] == 0

        def test_a():
            state = {"n": 4}
            with step("Empty FIFO"):
                for _ in range(16):
                    read_fifo()
                with repeat(until="FIFO is empty"):
                    while not empty(state):
                        read_fifo()
                        state["n"] -= 1
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)

    step = _procedure(pytester, "test_loop", "test_a")["steps"][0]
    assert _shape(step["substeps"]) == [
        ("1.1", "action", "Repeat dev.fifo.fifo_data = 90", "info"),
        (
            "1.2",
            "repeat",
            "Repeat until FIFO is empty",
            "info",
            [
                ("1.2.1", "action", "Read dev.fifo.status.empty", "info"),
                ("1.2.2", "action", "dev.fifo.fifo_data = 90", "info"),
            ],
        ),
    ]
    assert [n.get("result") for n in step["substeps"]] == ["(16 times)", "4 times"]


def _has_loop_values() -> bool:
    """stepdoc that keeps each pass's value when a loop writes a different one."""
    if importlib.util.find_spec("stepdoc") is None:
        return False
    model = importlib.import_module("stepdoc.core.model")
    return "values_count" in getattr(getattr(model, "Action", None), "__dataclass_fields__", {})


requires_stepdoc_loop_values = pytest.mark.skipif(
    not _has_loop_values(), reason="stepdoc without Action.values (loop values)"
)


def test_action_values_sequence() -> None:
    """A write that sent another value each pass shows them as a compact sequence."""
    from types import SimpleNamespace as NS

    from pytest_reporter._stepdoc import MAX_VALUES, _action, sequence

    def write(values: object, total: int, count: int = 1, **kw: object) -> NS:
        last = values[-1] if isinstance(values, list) else None
        fields = {"target": "dev.fifo.data", "op": "write", "value": last, "direction": "in"}
        fields.update(meta={}, count=count, values=values, values_count=total)
        fields.update(kw)
        return NS(**fields)

    assert _action(write(list(range(16)), 16), "3.1.1") == {
        "kind": "action",
        "number": "3.1.1",
        "description": "dev.fifo.data = 0, 1, … 15",
        "outcome": "info",
        "exc": None,
        "values": list(range(16)),
        "values_count": 16,
    }
    # Four or fewer: all of them; a unit once, after the sequence.
    node = _action(write([1, 2, 3, 4], 4, meta={"unit": "mV"}), "1")
    assert node["description"] == "dev.fifo.data = 1, 2, 3, 4 mV"
    # The same write again on one line (ACT-4): Repeat, with how often.
    node = _action(write([0, 1, 2, 3, 4], 5, count=5), "1")
    assert node["description"] == "Repeat dev.fifo.data = 0, 1, … 4"
    assert node["result"] == "(5 times)"
    # A request with other bodies is repeated, not polled; its status stays.
    request = write(
        [{"n": 1}, {"n": 2}],
        2,
        count=2,
        op="request",
        target="POST /users",
        direction="exchange",
        meta={"status": 201},
    )
    node = _action(request, "1")
    assert node["description"] == "Repeat POST /users  {'n': 1}, {'n': 2}"
    assert node["result"] == "201 (2 times)"
    # A list stepdoc cut: the total says so.
    assert sequence([0, 1], 70) == "0, 1, …"
    assert sequence([0, 1, 2, 3], 70) == "0, 1, … 3"
    long = _action(write(list(range(100)), 100), "1")
    assert long["values"] == list(range(32)) + list(range(68, 100))
    assert len(long["values"]) == MAX_VALUES
    assert long["values_count"] == 100
    # One value (or stepdoc before Action.values): as before, no values key.
    node = _action(write(None, 1), "1")
    assert node["description"] == "dev.fifo.data"
    assert "values" not in node
    old = NS(target="dev.a", op="write", value=5, direction="in", meta={}, count=1)
    assert _action(old, "1")["description"] == "dev.a = 5"
    # Reads never show values.
    read = write([1, 2], 2, direction="out", op="read", value=2)
    assert _action(read, "1")["description"] == "Read dev.fifo.data"
    # A write repeated in each pass of a loop: the values span every pass.
    node = _action(write([0, 1, 2, 3, 10, 11, 12, 13], 8, count=4), "1", passes=2)
    assert node["description"] == "Repeat dev.fifo.data = 0, 1, … 13"
    assert node["result"] == "(4 times per pass, 8 values)"
    # One value per pass: nothing to add; more values than passes: say how many.
    assert "result" not in _action(write(list(range(4)), 4), "1", passes=4)
    assert _action(write(list(range(5)), 5), "1", passes=4)["result"] == "(5 values)"


def test_action_values_json_safe() -> None:
    """Loop values in a node are JSON-safe and bounded, whatever the loop wrote."""
    import json
    from types import SimpleNamespace as NS

    from pytest_reporter._stepdoc import _action

    circular: list[object] = []
    circular.append(circular)
    raw = [
        0.0,
        float("nan"),
        float("inf"),
        b"x" * 100_000,
        {(1, 2): 3},
        circular,
        "s" * 1000,
        2**200,
        True,
        None,
        7,
        1.5,
    ]
    action = NS(
        target="dev.buf",
        op="write",
        value=raw[-1],
        direction="in",
        meta={},
        count=1,
        values=raw,
        values_count=len(raw),
    )
    node = _action(action, "1")
    text = json.dumps(node, allow_nan=False)
    assert len(text) < 5000
    values = node["values"]
    assert values[0] == 0.0
    assert values[1] == "nan"
    assert values[2] == "inf"
    assert isinstance(values[3], str) and values[3].startswith("b'xxx")
    assert len(values[3]) == 200 and values[3].endswith("…")
    assert values[4] == "{(1, 2): 3}"
    assert values[5] == "[[...]]"
    assert len(values[6]) == 200 and values[6].endswith("…")
    assert isinstance(values[7], str) and len(values[7]) <= 200
    assert values[8:] == [True, None, 7, 1.5]


@requires_stepdoc_loop_values
def test_loop_values_from_stepdoc(pytester: Pytester) -> None:
    """A loop whose pass writes a new value each time collapses to one pass."""
    pytester.makepyfile(
        test_loop="""
        import stepdoc
        from stepdoc import repeat, step

        def test_a():
            with step("Outer"):
                with repeat("Mixed"):
                    for i in range(16):
                        stepdoc.record_action("dev.fifo.data", "write", i)
                        stepdoc.record_action("dev.da", "read", 7)
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)

    step = _procedure(pytester, "test_loop", "test_a")["steps"][0]
    assert _shape(step["substeps"]) == [
        (
            "1.1",
            "step",
            "Mixed (repeat)",
            "passed",
            [
                ("1.1.1", "action", "dev.fifo.data = 0, 1, … 15", "info"),
                ("1.1.2", "action", "Read dev.da", "info"),
            ],
        )
    ]
    mixed = step["substeps"][0]
    assert mixed["result"] == "16 times"
    assert mixed["substeps"][0]["values"] == list(range(16))
    assert mixed["substeps"][0]["values_count"] == 16
    assert "result" not in mixed["substeps"][0]


@requires_stepdoc_loop_values
def test_loop_values_helper_lines_stay_apart(pytester: Pytester) -> None:
    """A helper called from two lines writes twice; in a loop it is one entry."""
    pytester.makepyfile(
        test_helper="""
        import stepdoc
        from stepdoc import step

        def set_mode(m):
            stepdoc.record_action("dev.mode", "write", m)

        def test_a():
            with step("Configure"):
                set_mode(1)
                set_mode(2)
            with step("Sweep"):
                for i in range(3):
                    for j in range(4):
                        stepdoc.record_action("dev.data", "write", j + 10 * i)
                    stepdoc.record_action("dev.da", "read", 7)
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)

    configure, sweep = _procedure(pytester, "test_helper", "test_a")["steps"]
    assert [s["description"] for s in configure["substeps"]] == ["dev.mode = 1", "dev.mode = 2"]
    (loop,) = sweep["substeps"]
    assert loop["kind"] == "repeat" and loop["result"] == "3 times"
    write = loop["substeps"][0]
    assert write["description"] == "Repeat dev.data = 0, 1, … 23"
    assert write["result"] == "(4 times per pass, 12 values)"


def test_notes_loop_steps_and_counters() -> None:
    """stepdoc's note=, a titled repeat() (a step with a loop) and counter=/inc=."""
    from types import SimpleNamespace as NS

    from pytest_reporter._stepdoc import StepCollector

    collector = StepCollector()
    loop_step = NS(
        title="Fill the CMD FIFO",
        status="passed",
        section="procedure",
        started=0.0,
        ended=0.0,
        error=None,
        note="512 words, 12 reserved",
        loop=NS(until="tx = 1", count=500, counter="write_count", inc=None),
        entries=[],
    )
    node = collector._entry(loop_step, "2")
    assert node["kind"] == "step"
    assert node["description"] == ("Fill the CMD FIFO (repeat until tx = 1, counting write_count)")
    assert node["result"] == "500 times"
    assert node["note"] == "512 words, 12 reserved"
    stepped = NS(until=None, count=2, counter="bytes", inc=4, note=None, entries=[])
    assert collector._entry(stepped, "1.1")["description"] == "Repeat, bytes +4 each pass"
    assert "note" not in collector._entry(stepped, "1.1")


requires_stepdoc_notes = pytest.mark.skipif(
    importlib.util.find_spec("stepdoc") is None
    or not hasattr(__import__("stepdoc"), "repeat")
    or "counter" not in inspect.signature(__import__("stepdoc").repeat).parameters,
    reason="stepdoc without note=, loop steps and counter=",
)


@requires_stepdoc_notes
def test_notes_and_loop_steps_from_stepdoc(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_loop="""
        import stepdoc
        from stepdoc import repeat, step

        def test_a():
            with step("Turn off", note="Power is cut first."):
                pass
            with repeat("Fill", until="full", counter="n", note="One read per pass."):
                n = 0
                while n < 3:
                    stepdoc.record_action("dev.fifo.fifo_data", "read", 1)
                    n += 1
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)

    steps = _procedure(pytester, "test_loop", "test_a")["steps"]
    assert [(s["number"], s["description"], s.get("note")) for s in steps] == [
        ("1", "Turn off", "Power is cut first."),
        ("2", "Fill (repeat until full, counting n)", "One read per pass."),
    ]
    assert steps[1]["result"] == "3 times"
    assert _shape(steps[1]["substeps"]) == [("2.1", "action", "Read dev.fifo.fifo_data", "info")]


def _folds_verifier_loops() -> bool:
    """stepdoc whose verifier adapter folds checks made in every pass of a loop
    (and places a retry's checks in its own steps: ``Recorder.attempt``)."""
    if importlib.util.find_spec("stepdoc") is None:
        return False
    recorder = importlib.import_module("stepdoc.core.recorder")
    return hasattr(recorder.Recorder("probe"), "attempt")


requires_stepdoc_verifier_loops = pytest.mark.skipif(
    not _folds_verifier_loops(), reason="stepdoc that does not fold verifier checks in loops"
)


@requires_verifier
@requires_stepdoc_verifier_loops
def test_verifier_checks_in_a_loop_fold_into_its_pass(pytester: Pytester) -> None:
    """stepdoc places pytest-verifier's checks after the phase and folds the ones
    made in every pass of a collapsed loop into the one pass shown; the reporter
    reads its steps afterwards, so procedure.json shows one check, for the first
    attempt and for a retry alike."""
    pytester.makepyfile(
        test_vloop="""
        import stepdoc
        from stepdoc import repeat, step

        ATTEMPTS = []

        def write(target, value):  # a bridge: the write's line is its caller's
            stepdoc.record_action(target, "write", value, value_from=("value",))

        def test_a(verify):
            ATTEMPTS.append(1)
            with step("Write words"):
                with repeat("Each word"):
                    for i in range(6):
                        write("dev.fifo.data", i)
                        got = 7
                        verify.equal(got, 7, name="Readback")
            assert len(ATTEMPTS) > 1
        """
    )
    pytester.runpytest("--report-dir=reports", "--report-retries=1").assert_outcomes(passed=1)

    for rest in ((), ("retries", "01")):
        (step,) = _procedure(pytester, "test_vloop", "test_a", *rest)["steps"]
        (loop,) = step["substeps"]
        assert loop["result"] == "6 times"
        assert [(n["kind"], n["description"]) for n in loop["substeps"]] == [
            ("action", "dev.fifo.data = 0, 1, … 5"),
            ("check", "Verify 'Readback': got == 7"),
        ]
