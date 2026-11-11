"""Test procedures come from stepdoc's steps (``from stepdoc import step``).

pytest-reporter has no step API of its own. With stepdoc installed it follows
stepdoc's ``pytest_stepdoc_step_*`` hooks and writes each attempt's steps to
``procedure.json``. stepdoc stays optional: without it procedures are empty.
"""

from __future__ import annotations

import importlib.util
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
