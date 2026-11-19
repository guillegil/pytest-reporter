"""Operand names of pytest-verifier checks (``actual_name=``, ``expected_name=``).

A record carries each name as this run spells it (``actual_name``:
``tb.dev.map.block.reg3.F``) and, when pytest-verifier knows it, with every
interpolation as ``<expression>`` (``actual_name_symbolic``:
``tb.dev.map.block.reg<channel>.F``). Verification cards and the failure strip
show this run's text; the Procedure tab shows the symbolic one, with this run's
name in the result.

The card renderers run under Node with a minimal DOM (text only), as in
``test_html_check_notes.py``.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS
from typing import TYPE_CHECKING, Any

import pytest

from pytest_reporter._html_builder._js import JS
from pytest_reporter._stepdoc import _check

if TYPE_CHECKING:
    from pytest import Pytester

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
requires_stepdoc = pytest.mark.skipif(
    importlib.util.find_spec("stepdoc") is None, reason="stepdoc is not installed"
)


def _verifier_has_operand_names() -> bool:
    if importlib.util.find_spec("pytest_verifier") is None:
        return False
    from pytest_verifier import Verify

    return "actual_name" in inspect.signature(Verify.equal).parameters


requires_operand_names = pytest.mark.skipif(
    not _verifier_has_operand_names(),
    reason="pytest-verifier with actual_name= / expected_name= is not installed",
)

ACTUAL = "tb.dev.map.block.reg3.F"
ACTUAL_SYMBOLIC = "tb.dev.map.block.reg<channel>.F"


def _record(**fields: object) -> dict[str, Any]:
    """A pytest-verifier record of ``verify.equal(v, wdata, actual_name=f"...")``."""
    base: dict[str, Any] = {
        "check_type": "equal",
        "name": ACTUAL,
        "auto_name": True,
        "description": f"Verify '{ACTUAL}' == wdata (243)",
        "actual_name": ACTUAL,
        "actual_name_symbolic": ACTUAL_SYMBOLIC,
        "expected_name": "wdata",
        "actual": 240,
        "expected": 243,
        "passed": False,
        "detail": "expected wdata (243), got 240",
        "phase": "call",
    }
    base.update(fields)
    return {k: v for k, v in base.items() if v is not None}


def _stepdoc_check(record: dict[str, Any], **fields: object) -> NS:
    """What stepdoc's pytest-verifier adapter makes of ``record``: the text is
    the description without ``Verify``, and ``source`` is the record."""
    base = {
        "text": record["description"][len("Verify ") :],
        "passed": record.get("passed"),
        "actual": record.get("actual"),
        "detail": None if record.get("passed") else record.get("detail"),
        "children": [],
        "source": record,
    }
    return NS(**{**base, **fields})


# ---------------------------------------------------------------------------
# Procedure nodes
# ---------------------------------------------------------------------------


def test_procedure_check_reads_symbolic_names() -> None:
    """The text has the names as the test writes them; the result names the
    value as this run has it."""
    record = _record()
    # stepdoc words the check after the argument's source (a local variable)
    check = _stepdoc_check(
        record, text="block_reg_f == wdata (243)", symbolic_text="block_reg_f == <wdata>"
    )
    node = _check(check, "1.1")
    assert node["description"] == f"Verify {ACTUAL_SYMBOLIC} == wdata (243)"
    assert node["result"] == f"got {ACTUAL} = 240"
    assert node["actual_name"] == ACTUAL
    assert node["expected_name"] == "wdata"
    assert node["outcome"] == "failed"
    assert node["detail"] == "expected wdata (243), got 240"


def test_procedure_check_with_a_name_keeps_it() -> None:
    record = _record(
        name="Stored word", auto_name=None, description="Verify 'Stored word' == wdata (243)"
    )
    check = _stepdoc_check(record, text="'Stored word': block_reg_f == wdata (243)")
    node = _check(check, "1.1")
    assert node["description"] == f"Verify 'Stored word': {ACTUAL_SYMBOLIC} == wdata (243)"
    # stepdoc without the checked expression in the text: 'Stored word' == ...
    plain = _check(_stepdoc_check(record), "1.2")
    assert plain["description"] == node["description"]


def test_procedure_check_without_a_symbolic_form() -> None:
    """A plain string: the text has the name, and the result needs no name."""
    record = _record(actual_name_symbolic=None)
    node = _check(_stepdoc_check(record), "1.1")
    assert node["description"] == f"Verify {ACTUAL} == wdata (243)"
    assert node["result"] == "got 240"


def test_procedure_check_symbolic_expected_name() -> None:
    record = _record(
        check_type="less_equal",
        description=f"Verify '{ACTUAL}' <= limits[3] (255)",
        expected_name="limits[3]",
        expected_name_symbolic="limits[<channel>]",
        threshold=255,
        expected=None,
    )
    node = _check(_stepdoc_check(record), "1.1")
    assert node["description"] == f"Verify {ACTUAL_SYMBOLIC} <= limits[<channel>] (255)"
    assert node["expected_name"] == "limits[3]"


def test_procedure_check_actual_name_only() -> None:
    """Without ``expected_name`` the expected side is stepdoc's: the name it
    found in the source, with this run's value."""
    record = _record(expected_name=None, description=f"Verify '{ACTUAL}' == 243")
    check = _stepdoc_check(
        record, text="block_reg_f == 243", symbolic_text="block_reg_f == <wdata>"
    )
    assert _check(check, "1.1")["description"] == f"Verify {ACTUAL_SYMBOLIC} == <wdata> (243)"
    # No symbolic text from stepdoc (a literal expected value)
    literal = _stepdoc_check(record, text="block_reg_f == 243")
    assert _check(literal, "1.2")["description"] == f"Verify {ACTUAL_SYMBOLIC} == 243"
    # A name beside the checked expression, with an operator in it
    named = _record(
        name="a == b", auto_name=None, expected_name=None, description="Verify 'a == b' == 243"
    )
    check = _stepdoc_check(
        named, text="'a == b': block_reg_f == 243", symbolic_text="'a == b': block_reg_f == <wdata>"
    )
    assert (
        _check(check, "1.3")["description"]
        == f"Verify 'a == b': {ACTUAL_SYMBOLIC} == <wdata> (243)"
    )


def test_procedure_check_operator_in_the_name_or_the_expression() -> None:
    """The operator that starts the expected side is found past the ones the
    name or the checked expression hold."""
    # stepdoc found no expression (a literal first argument): 'name' == <wdata>
    named = _record(
        name="x == y", auto_name=None, expected_name=None, description="Verify 'x == y' == 243"
    )
    check = _stepdoc_check(named, symbolic_text="'x == y' == <wdata>")
    assert (
        _check(check, "1.1")["description"]
        == f"Verify 'x == y': {ACTUAL_SYMBOLIC} == <wdata> (243)"
    )
    # The checked expression is a comparison itself
    record = _record(expected_name=None, description=f"Verify '{ACTUAL}' == False")
    check = _stepdoc_check(record, text="a == b == False", symbolic_text="a == b == <flag>")
    assert _check(check, "1.2")["description"] == f"Verify {ACTUAL_SYMBOLIC} == <flag> (False)"
    # Fewer operators in the symbolic text than in this run's: left as it is
    check = _stepdoc_check(record, text="a == b == False", symbolic_text="<cmp> == <flag>")
    assert _check(check, "1.3")["description"] == f"Verify {ACTUAL_SYMBOLIC} == False"


def test_procedure_check_expected_name_that_occurs_in_the_operator() -> None:
    """Only the name before the value is replaced by its symbolic form."""
    record = _record(
        check_type="length",
        expected_name="n",
        expected_name_symbolic="<k>",
        description=f"Verify '{ACTUAL}' has length n (2)",
    )
    check = _stepdoc_check(record)
    assert _check(check, "1.1")["description"] == f"Verify {ACTUAL_SYMBOLIC} has length <k> (2)"
    record = _record(
        expected_name="=",
        expected_name_symbolic="<eq>",
        description=f"Verify '{ACTUAL}' == = (243)",
    )
    check = _stepdoc_check(record)
    assert _check(check, "1.2")["description"] == f"Verify {ACTUAL_SYMBOLIC} == <eq> (243)"


def test_procedure_check_generic_text() -> None:
    """``generic`` is the check without this run's values; the segments put
    the words in plain text and the code in monospace."""
    record = _record(expected_name=None, description=f"Verify '{ACTUAL}' == 243")
    check = _stepdoc_check(
        record, text="block_reg_f == 243", symbolic_text="block_reg_f == <wdata>"
    )
    node = _check(check, "1.1")
    assert node["generic"] == f"Verify {ACTUAL_SYMBOLIC} == <wdata>"
    assert node["generic_segments"] == [
        {"text": "Verify ", "style": None},
        {"text": f"{ACTUAL_SYMBOLIC} == <wdata>", "style": "mono"},
    ]
    assert node["description_segments"] == [
        {"text": "Verify ", "style": None},
        {"text": f"{ACTUAL_SYMBOLIC} == <wdata> (243)", "style": "mono"},
    ]
    # A name= is words, not code
    named = _record(
        name="Stored word",
        auto_name=None,
        expected_name=None,
        description="Verify 'Stored word' == 243",
    )
    check = _stepdoc_check(
        named,
        text="'Stored word': block_reg_f == 243",
        symbolic_text="'Stored word': block_reg_f == <wdata>",
    )
    assert _check(check, "1.2")["generic_segments"] == [
        {"text": "Verify 'Stored word': ", "style": None},
        {"text": f"{ACTUAL_SYMBOLIC} == <wdata>", "style": "mono"},
    ]
    # An expected_name without a symbolic text from stepdoc: stepdoc's wording
    check = _stepdoc_check(_record(), text="block_reg_f == wdata (243)")
    assert _check(check, "1.3")["generic"] == "Verify block_reg_f == wdata (243)"


def test_procedure_check_worded_by_stepdoc() -> None:
    """A stepdoc that words checks with the operand names (``Check.operands``)
    gives both texts: they are shown as they are."""
    record = _record(name="Stored word", auto_name=None)
    check = _stepdoc_check(
        record,
        text=f"'Stored word': {ACTUAL} == wdata (243)",
        symbolic_text=f"'Stored word': {ACTUAL_SYMBOLIC} == <wdata>",
        label="Stored word",
        operands={"actual": {"concrete": ACTUAL, "symbolic": ACTUAL_SYMBOLIC}},
    )
    node = _check(check, "1.1")
    assert node["description"] == f"Verify 'Stored word': {ACTUAL} == wdata (243)"
    assert node["result"] == "got 240"
    assert node["generic"] == f"Verify 'Stored word': {ACTUAL_SYMBOLIC} == <wdata>"
    assert node["generic_segments"] == [
        {"text": "Verify 'Stored word': ", "style": None},
        {"text": f"{ACTUAL_SYMBOLIC} == <wdata>", "style": "mono"},
    ]
    assert node["actual_name"] == ACTUAL


def test_action_generic_text() -> None:
    from pytest_reporter._stepdoc import _action

    write = NS(
        op="write",
        target="dev.reg3",
        direction="in",
        value=243,
        meta={},
        count=1,
        symbolic_target="dev.reg<channel>",
        symbolic_value="<wdata>",
    )
    node = _action(write, "1.1")
    assert node["description"] == "dev.reg3 = 243"
    assert node["generic"] == "dev.reg<channel> = <wdata>"
    read = NS(
        op="read",
        target="dev.reg3",
        direction="out",
        value=240,
        meta={},
        count=1,
        symbolic_target="dev.reg<channel>",
        bound_to="rdata",
    )
    node = _action(read, "1.2")
    assert node["result"] == "240"
    assert node["generic_result"] == "<rdata>"
    # Nothing symbolic: the same text, so no separate generic one
    assert "generic" not in _action(NS(op="write", target="a", direction="in", value=1), "1.3")


def test_procedure_check_expected_name_only() -> None:
    """Without ``actual_name`` the checked value keeps stepdoc's wording, and
    the expected side is not annotated twice."""
    record = _record(
        name="block_reg_f",
        actual_name=None,
        actual_name_symbolic=None,
        description="Verify 'block_reg_f' == wdata (243)",
    )
    check = _stepdoc_check(
        record, text="dev.blk.reg3.F == wdata (243)", symbolic_text="dev.blk.reg<ch>.F == <wdata>"
    )
    node = _check(check, "1.1")
    assert node["description"] == "Verify dev.blk.reg3.F == wdata (243)"
    assert node["result"] == "got 240"
    assert "actual_name" not in node


def test_procedure_check_other_shapes_are_left_alone() -> None:
    """A description of another shape, a missing record, or one without operand
    names: the check reads as stepdoc worded it."""
    odd = _record(description="something else")
    check = _stepdoc_check(odd, text="x == 1", symbolic_text="x == <n>")
    assert _check(check, "1.1")["description"] == "Verify x == <n> (1)"
    no_source = NS(text="x == 1", symbolic_text="x == <n>", passed=True, actual=1, children=[])
    assert _check(no_source, "1.2")["description"] == "Verify x == <n> (1)"
    unnamed = _record(actual_name=None, actual_name_symbolic=None, expected_name=None)
    plain = _check(_stepdoc_check(unnamed), "1.3")
    assert plain["description"] == unnamed["description"]
    assert "actual_name" not in plain
    blank = _record(actual_name="  ", expected_name=5)  # not names: ignored
    assert _check(_stepdoc_check(blank), "1.4")["description"] == blank["description"]


def test_procedure_children_use_their_own_names() -> None:
    child = _record(passed=True, actual=243, detail="243 == wdata (243)")
    parent = NS(
        text="'All channels' all satisfy",
        passed=True,
        actual=None,
        children=[_stepdoc_check(child)],
        source={"check_type": "all_satisfy", "name": "All channels"},
    )
    node = _check(parent, "2")
    assert node["description"] == "Verify 'All channels' all satisfy"
    assert node["substeps"][0]["description"] == f"Verify {ACTUAL_SYMBOLIC} == wdata (243)"
    assert node["substeps"][0]["result"] == f"got {ACTUAL} = 243"


# ---------------------------------------------------------------------------
# Verification cards and the failure strip (Node)
# ---------------------------------------------------------------------------

_DOM = """
const window = {};
function Node(tag) { this.tag = tag; this.children = []; this.className = ''; this.attrs = {}; }
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.setAttribute = function (k, v) { this.attrs[k] = v; };
Node.prototype.addEventListener = function () {};
Object.defineProperty(Node.prototype, 'textContent', {
  get() { return this.text !== undefined ? this.text
                 : this.children.map(c => c.textContent).join(''); },
  set(v) { this.text = String(v); this.children = []; },
});
const document = {
  createElement: tag => new Node(tag),
  createElementNS: (ns, tag) => new Node(tag),
  createTextNode: text => { const n = new Node('#text'); n.text = String(text); return n; },
  createDocumentFragment: () => new Node('#fragment'),
  querySelector: () => null,
};
function findAll(node, cls, out) {
  out = out || [];
  if ((' ' + node.className + ' ').includes(' ' + cls + ' ')) out.push(node);
  node.children.forEach(c => findAll(c, cls, out));
  return out;
}
const texts = (node, cls) => findAll(node, cls).map(n => n.textContent);
"""

_FUNCTIONS = (
    "el",
    "svgEl",
    "chevronSvg",
    "isBad",
    "failedPhase",
    "failedChecks",
    "failureReason",
    "renderFailureStrip",
    "renderCheckResults",
    "checkNote",
    "checkOperand",
    "operandNameEl",
    "checkLabel",
    "renderCheckDetail",
    "renderCheckBody",
    "renderGuardCheck",
)


def _function(name: str) -> str:
    start = JS.index(f"function {name}(")
    end = JS.index("\nfunction ", start + 1)
    return JS[start:end]


def _node(script: str) -> Any:  # noqa: ANN401
    source = "\n".join([_DOM, *(_function(n) for n in _FUNCTIONS), script])
    out = subprocess.run(
        ["node", "-"],
        input=source,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


_NAMED = {
    "check_type": "less_equal",
    "name": "In range",
    "description": "Verify 'In range' <= limits[3] (255)",
    "actual_name": ACTUAL,
    "actual_name_symbolic": ACTUAL_SYMBOLIC,
    "expected_name": "limits[3]",
    "expected_name_symbolic": "limits[<channel>]",
    "actual": 300,
    "threshold": 255,
    "passed": False,
    "detail": "expected <= limits[3] (255), got 300",
    "location": "tests/test_rw.py:26",
}


@requires_node
def test_check_operand() -> None:
    checks = [
        _record(),  # the name is the operand already
        _NAMED,
        {"name": "Vout"},
        {"name": "x", "actual_name": "  "},
        {"name": "x", "actual_name": 5},
    ]
    got = _node(
        "const checks = " + json.dumps(checks) + ";\n"
        "console.log(JSON.stringify(checks.map(checkOperand)));"
    )
    assert got == ["", ACTUAL, "", "", ""]


@requires_node
def test_card_shows_the_names() -> None:
    """The header has this run's name beside the label; the body lists both
    names, each with its symbolic form when it differs."""
    checks = [_NAMED, _record(), {"check_type": "equal", "name": "Vout", "passed": True}]
    got = _node(
        "const checks = " + json.dumps(checks) + ";\n"
        "const cards = findAll(renderCheckResults(checks), 'check-card');\n"
        "console.log(JSON.stringify(cards.map(card => ({\n"
        "  header: texts(findAll(card, 'check-card-header')[0], 'check-operand'),\n"
        "  labels: texts(card, 'label'),\n"
        "  names: texts(card, 'operand-name'),\n"
        "}))));"
    )
    named, auto, plain = got
    assert named["header"] == [ACTUAL]
    assert named["labels"][:5] == ["Result", "Actual name", "Actual", "Expected name", "Threshold"]
    assert named["names"] == [
        f"{ACTUAL}written as {ACTUAL_SYMBOLIC}",
        "limits[3]written as limits[<channel>]",
    ]
    # Without name= the label is the operand: it is not repeated in the header
    assert auto["header"] == []
    assert auto["names"] == [f"{ACTUAL}written as {ACTUAL_SYMBOLIC}", "wdata"]
    assert plain["header"] == []
    assert plain["names"] == []
    assert "Actual name" not in plain["labels"]


@requires_node
def test_failure_strip_and_reason_name_the_value() -> None:
    run = {
        "outcome": "failed",
        "phases": {"call": {"outcome": "failed", "longrepr": ""}},
        "check_results": [_NAMED, _record()],
    }
    got = _node(
        "const run = " + json.dumps(run) + ";\n"
        "const strip = renderFailureStrip(run, () => {});\n"
        "console.log(JSON.stringify([texts(strip, 'check-operand'), failureReason(run)]));"
    )
    assert got == [
        [ACTUAL],  # only the check with a label of its own: the other's text has it
        f"In range ({ACTUAL}) — expected <= limits[3] (255), got 300",
    ]


@requires_node
def test_nested_check_shows_its_operand() -> None:
    got = _node(
        "const box = renderGuardCheck(" + json.dumps(_NAMED) + ", true);\n"
        "console.log(JSON.stringify([texts(box, 'check-operand'), texts(box, 'operand-name')]));"
    )
    assert got == [
        [ACTUAL],
        [f"{ACTUAL}written as {ACTUAL_SYMBOLIC}", "limits[3]written as limits[<channel>]"],
    ]


# ---------------------------------------------------------------------------
# Through pytest
# ---------------------------------------------------------------------------

_DATA_BLOCK = '<script type="application/json" id="report-data">'


def _run_dir(pytester: Pytester) -> Path:
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    assert len(runs) == 1
    return runs[0]


def _data(pytester: Pytester) -> dict[str, Any]:
    html = (_run_dir(pytester) / "report.html").read_text(encoding="utf-8")
    start = html.index(_DATA_BLOCK) + len(_DATA_BLOCK)
    return json.loads(html[start : html.index("</script>", start)])  # type: ignore[no-any-return]


def test_names_reach_the_report_data(pytester: Pytester) -> None:
    """The names on ``report.verify_checks`` are in ``checks.json`` and in the
    HTML data, whatever pytest-verifier is installed."""
    record = _record(actual_name_symbolic="tb.dev.map.block.reg<channel></script>.F")
    pytester.makeconftest(f"""
        import pytest

        RECORD = {record!r}

        @pytest.hookimpl(wrapper=True)
        def pytest_runtest_makereport(item, call):
            report = yield
            if report.when == "call":
                report.verify_checks = [dict(RECORD)]
            return report
    """)
    pytester.makepyfile(test_x="def test_a():\n    pass\n")
    pytester.runpytest("--report-dir=reports", "-p", "no:pytest_verifier").assert_outcomes(passed=1)
    path = _run_dir(pytester) / "tests" / "test_x.py" / "test_a" / "default" / "checks.json"
    assert json.loads(path.read_text(encoding="utf-8"))["checks"] == [record]
    assert _data(pytester)["tests"][0]["runs"][0]["check_results"] == [record]


@requires_stepdoc
@requires_operand_names
def test_operand_names_from_pytest_verifier(pytester: Pytester) -> None:
    """End to end: the cards get this run's names, the procedure the symbolic ones."""
    pytester.makepyfile(
        test_rw="""
        import types

        import pytest
        from stepdoc import step

        @pytest.fixture
        def channel():
            return 3

        def test_a(verify, channel):
            wdata = 243
            block = types.SimpleNamespace(reg3=types.SimpleNamespace(F=240))
            with step("Read back the register"):
                block_reg_f = getattr(block, f"reg{channel}").F
                verify.equal(block_reg_f, wdata,
                             actual_name=f"tb.dev.map.block.reg{channel}.F",
                             expected_name="wdata")
                verify.less_equal(block_reg_f, 255, name="In range",
                                  actual_name=f"tb.dev.map.block.reg{channel}.F")
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(failed=1)

    checks = _data(pytester)["tests"][0]["runs"][0]["check_results"]
    assert [(c["name"], c["actual_name"], c["actual_name_symbolic"]) for c in checks] == [
        (ACTUAL, ACTUAL, ACTUAL_SYMBOLIC),
        ("In range", ACTUAL, ACTUAL_SYMBOLIC),
    ]
    assert checks[0]["expected_name"] == "wdata"

    path = _run_dir(pytester) / "tests" / "test_rw.py" / "test_a" / "default" / "procedure.json"
    substeps = json.loads(path.read_text(encoding="utf-8"))["steps"][0]["substeps"]
    # The generic line reads the same whichever stepdoc worded the check
    assert [s["generic"] for s in substeps] == [
        f"Verify {ACTUAL_SYMBOLIC} == <wdata>",
        f"Verify 'In range': {ACTUAL_SYMBOLIC} <= 255",
    ]
    assert [(s["description"], s["result"]) for s in substeps] in (
        # stepdoc words checks with the operand names itself (Check.operands)
        [
            (f"Verify {ACTUAL} == wdata (243)", "got 240"),
            (f"Verify 'In range': {ACTUAL} <= 255", "got 240"),
        ],
        # an earlier stepdoc: the reporter does
        [
            (f"Verify {ACTUAL_SYMBOLIC} == wdata (243)", f"got {ACTUAL} = 240"),
            (f"Verify 'In range': {ACTUAL_SYMBOLIC} <= 255", f"got {ACTUAL} = 240"),
        ],
    )
    assert substeps[0]["outcome"] == "failed"
    assert substeps[0]["actual_name"] == ACTUAL
